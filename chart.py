#!/usr/bin/env python3
"""Render the last year of GitHub contributions as an isometric city."""
import json, os, sys, urllib.request
from datetime import date, timedelta

from PIL import Image, ImageColor, ImageDraw, ImageFont

LOGIN = sys.argv[1] if len(sys.argv) > 1 else "baziyer"
CALENDAR_QUERY = """query($login:String!){ user(login:$login){ contributionsCollection{
  contributionCalendar{ weeks{ contributionDays{ date contributionCount } } } } } }"""

THEMES = {
    "light": dict(bg="#ffffff", ink="#1f2328", muted="#59636e", ground="#f6f8fa", grid="#d0d7de",
                  pub_top="#79c0ff", pub_left="#218bff", pub_right="#0969da",
                  private_top="#f2cc60", private_left="#d29922", private_right="#9e6a03"),
    "dark": dict(bg="#010409", ink="#e6edf3", muted="#8b949e", ground="#161b22", grid="#30363d",
                 pub_top="#79c0ff", pub_left="#58a6ff", pub_right="#1f6feb",
                 private_top="#f2cc60", private_left="#d29922", private_right="#9e6a03"),
}

W, H = 800, 380
ORIGIN_X, ORIGIN_Y, STEP_X, STEP_Y = 100, 160, 12, 3


def graphql(query):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {os.environ['GH_TOKEN']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as response:
        body = json.load(response)
    if "errors" in body:
        sys.exit(body["errors"])
    return body["data"]["user"]


def fetch():
    weeks = graphql(CALENDAR_QUERY)["contributionsCollection"]["contributionCalendar"]["weeks"]
    totals = sorted((d["date"], d["contributionCount"]) for w in weeks for d in w["contributionDays"])[-365:]
    private = {}
    for start in range(0, len(totals), 50):  # Larger batches exceed GitHub's GraphQL resource limit.
        batch = totals[start:start + 50]
        fields = " ".join(
            f'd{i}: contributionsCollection(from:"{day}T00:00:00Z",to:"{day}T23:59:59Z")'
            "{restrictedContributionsCount}"
            for i, (day, _) in enumerate(batch)
        )
        result = graphql(f"query($login:String!){{user(login:$login){{{fields}}}}}")
        private.update((day, result[f"d{i}"]["restrictedContributionsCount"]) for i, (day, _) in enumerate(batch))
    return [(day, total, private[day]) for day, total in totals]


def polygon(css_class, points):
    return f'<polygon class="{css_class}" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in points)}"/>'


def segment_shapes(cx, bottom, height):
    half_width, half_depth = 8, 2.7
    top = bottom - height
    return (
        ((cx - half_width, top), (cx, top + half_depth), (cx, bottom + half_depth), (cx - half_width, bottom)),
        ((cx, top + half_depth), (cx + half_width, top), (cx + half_width, bottom), (cx, bottom + half_depth)),
        ((cx, top - half_depth), (cx + half_width, top), (cx, top + half_depth), (cx - half_width, top)),
    )


def segment(cx, bottom, height, kind, roof=True):
    left, right, cap = segment_shapes(cx, bottom, height)
    return polygon(f"{kind}-left", left) + polygon(f"{kind}-right", right) + (polygon(f"{kind}-top", cap) if roof else "")


def layout(days):
    first = date.fromisoformat(days[0][0])
    grid_start = first - timedelta(days=(first.weekday() + 1) % 7)
    cells, months = [], []
    for day, count, private in days:
        current = date.fromisoformat(day)
        weekday = (current.weekday() + 1) % 7
        week = (current - grid_start).days // 7
        cx = ORIGIN_X + (week - weekday) * STEP_X
        cy = ORIGIN_Y + (week + weekday) * STEP_Y
        cells.append((week + weekday, week, weekday, cx, cy, count, private))
        if current.day == 1:
            months.append((ORIGIN_X + week * STEP_X, current.strftime("%b")))
    return cells, months


def render(days, theme):
    total = sum(n for _, n, _ in days)
    if total == 0:
        return "<svg xmlns='http://www.w3.org/2000/svg' width='800' height='60'><text x='0' y='30'>No contributions yet</text></svg>"

    maximum = max(n for _, n, _ in days)
    public_total = sum(n - private for _, n, private in days)
    private_total = sum(private for _, _, private in days)
    cells, months = layout(days)

    city = []
    for _, week, weekday, cx, cy, count, private in sorted(cells):
        ground = ((cx, cy - STEP_Y), (cx + STEP_X, cy), (cx, cy + STEP_Y), (cx - STEP_X, cy))
        city.append(polygon("ground", ground))
        if not count:
            continue
        height = 100 * count / maximum
        private_height = height * private / count
        public_height = height - private_height
        if public_height:
            city.append(segment(cx, cy, public_height, "public", roof=not private_height))
        if private_height:
            city.append(segment(cx, cy - public_height, private_height, "private"))

    t = theme
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Isometric map of {total:,} GitHub contributions over the last year: {public_total:,} public and {private_total:,} private.">
<style>
text{{font:16px -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;fill:{t['ink']}}}
.total{{font-size:26px;font-weight:600}} .muted,.month{{fill:{t['muted']}}} .month{{font-size:12px;text-anchor:middle}}
.ground{{fill:{t['ground']};stroke:{t['grid']};stroke-width:.7}}
.public-top{{fill:{t['pub_top']}}}.public-left{{fill:{t['pub_left']}}}.public-right{{fill:{t['pub_right']}}}
.private-top{{fill:{t['private_top']}}}.private-left{{fill:{t['private_left']}}}.private-right{{fill:{t['private_right']}}}
</style>
<text class="total" x="24" y="32">{total:,}</text><text class="muted" x="120" y="32">contributions</text>
<rect x="500" y="18" width="12" height="12" rx="2" fill="{t['pub_left']}"/><text x="519" y="29">{public_total:,} public</text>
<rect x="646" y="18" width="12" height="12" rx="2" fill="{t['private_left']}"/><text x="665" y="29">{private_total:,} private</text>
{"".join(city)}
{"".join(f'<text class="month" x="{x:.1f}" y="{H - 13}">{label}</text>' for x, label in months)}
</svg>"""


def load_font(size, bold=False):
    names = ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
             "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def render_gif(days, theme, path, frame_count=180):
    scale = 2
    size = (W * scale, H * scale)
    cells, months = layout(days)
    cells = sorted(cells)
    maximum = max(n for _, n, _ in days)
    total = sum(n for _, n, _ in days)
    private_total = sum(private for _, _, private in days)
    public_total = total - private_total
    fonts = (load_font(26 * scale, True), load_font(16 * scale), load_font(12 * scale))

    def points(shape):
        return [(round(x * scale), round(y * scale)) for x, y in shape]

    def fill(draw, shape, color, alpha=255):
        draw.polygon(points(shape), fill=(*ImageColor.getrgb(color), alpha))

    frames = []
    build_end = max(2, round(frame_count * .62))
    hold_end = max(build_end + 1, round(frame_count * .72))
    for frame_number in range(frame_count):
        if frame_number < build_end:
            front = -2 + 58 * frame_number / (build_end - 1)
        elif frame_number < hold_end:
            front = 56
        else:
            front = -2 + 58 * (frame_number - hold_end + 1) / (frame_count - hold_end)
        image = Image.new("RGB", size, theme["bg"])
        draw = ImageDraw.Draw(image, "RGBA")
        draw.text((24 * scale, 8 * scale), f"{total:,}", font=fonts[0], fill=theme["ink"])
        draw.text((120 * scale, 14 * scale), "contributions", font=fonts[1], fill=theme["muted"])
        draw.rounded_rectangle((500 * scale, 18 * scale, 512 * scale, 30 * scale), 2 * scale, fill=theme["pub_left"])
        draw.text((519 * scale, 14 * scale), f"{public_total:,} public", font=fonts[1], fill=theme["ink"])
        draw.rounded_rectangle((646 * scale, 18 * scale, 658 * scale, 30 * scale), 2 * scale, fill=theme["private_left"])
        draw.text((665 * scale, 14 * scale), f"{private_total:,} private", font=fonts[1], fill=theme["ink"])

        for _, week, weekday, cx, cy, count, private in cells:
            ground = ((cx, cy - STEP_Y), (cx + STEP_X, cy), (cx, cy + STEP_Y), (cx - STEP_X, cy))
            fill(draw, ground, theme["ground"])
            draw.line(points(ground + (ground[0],)), fill=theme["grid"], width=max(1, scale))
            if not count:
                continue
            position = week + weekday / 7
            animated_position = position if frame_number < hold_end else 53 - position
            progress = max(0, min(1, (front - animated_position) / 2.5))
            progress = progress * progress * (3 - 2 * progress)
            growth = progress if frame_number < hold_end else 1 - progress
            if not growth:
                continue
            height = 100 * count / maximum * growth
            private_height = height * private / count
            public_height = height - private_height

            def draw_segment(bottom, segment_height, kind, roof=True):
                left, right, cap = segment_shapes(cx, bottom, segment_height)
                fill(draw, left, theme[f"{kind}_left"])
                fill(draw, right, theme[f"{kind}_right"])
                if roof:
                    fill(draw, cap, theme[f"{kind}_top"])

            if public_height:
                draw_segment(cy, public_height, "pub", not private_height)
            if private_height:
                draw_segment(cy - public_height, private_height, "private")

        for x, label in months:
            draw.text((x * scale, (H - 13) * scale), label, font=fonts[2], fill=theme["muted"], anchor="mm")
        frames.append(image.resize((W, H), Image.Resampling.LANCZOS))

    palette = frames[build_end].quantize(colors=128)
    frames = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=80, loop=0, optimize=True, disposal=1)


if __name__ == "__main__":
    if "--check" in sys.argv:
        sample = [(f"2026-01-{day:02}", day, day // 2) for day in range(1, 15)]
        svg = render(sample, THEMES["dark"])
        assert "public-left" in svg and "private-left" in svg and "56 public" in svg and "square-root" not in svg
        render_gif(sample, THEMES["dark"], "/tmp/chart-check.gif", 12)
        assert os.path.getsize("/tmp/chart-check.gif") > 1000
        sys.exit()
    contributions = fetch()
    for name, colors in THEMES.items():
        with open(f"chart-{name}.svg", "w") as output:
            output.write(render(contributions, colors))
        render_gif(contributions, colors, f"chart-{name}.gif")
