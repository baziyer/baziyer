#!/usr/bin/env python3
"""Render the last year of GitHub contributions as an isometric city."""
import json, math, os, sys, urllib.request
from datetime import date, timedelta

LOGIN = sys.argv[1] if len(sys.argv) > 1 else "baziyer"
CALENDAR_QUERY = """query($login:String!){ user(login:$login){ contributionsCollection{
  contributionCalendar{ weeks{ contributionDays{ date contributionCount } } } } } }"""

THEMES = {
    "light": dict(ink="#1f2328", muted="#59636e", ground="#f6f8fa", grid="#d0d7de",
                  pub_top="#79c0ff", pub_left="#218bff", pub_right="#0969da",
                  private_top="#f2cc60", private_left="#d29922", private_right="#9e6a03"),
    "dark": dict(ink="#e6edf3", muted="#8b949e", ground="#161b22", grid="#30363d",
                 pub_top="#79c0ff", pub_left="#58a6ff", pub_right="#1f6feb",
                 private_top="#f2cc60", private_left="#d29922", private_right="#9e6a03"),
}


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


def segment(cx, bottom, height, kind, roof=True):
    half_width, half_depth = 8, 2.7
    top = bottom - height
    left = polygon(f"{kind}-left", ((cx - half_width, top), (cx, top + half_depth),
                                     (cx, bottom + half_depth), (cx - half_width, bottom)))
    right = polygon(f"{kind}-right", ((cx, top + half_depth), (cx + half_width, top),
                                       (cx + half_width, bottom), (cx, bottom + half_depth)))
    cap = polygon(f"{kind}-top", ((cx, top - half_depth), (cx + half_width, top),
                                   (cx, top + half_depth), (cx - half_width, top))) if roof else ""
    return left + right + cap


def render(days, theme):
    total = sum(n for _, n, _ in days)
    if total == 0:
        return "<svg xmlns='http://www.w3.org/2000/svg' width='800' height='60'><text x='0' y='30'>No contributions yet</text></svg>"

    W, H = 800, 410
    origin_x, origin_y, step_x, step_y = 100, 190, 12, 3
    first = date.fromisoformat(days[0][0])
    grid_start = first - timedelta(days=(first.weekday() + 1) % 7)
    maximum = max(n for _, n, _ in days)
    public_total = sum(n - private for _, n, private in days)
    private_total = sum(private for _, _, private in days)
    cells = []
    month_labels = []

    for day, count, private in days:
        current = date.fromisoformat(day)
        weekday = (current.weekday() + 1) % 7
        week = (current - grid_start).days // 7
        cx = origin_x + (week - weekday) * step_x
        cy = origin_y + (week + weekday) * step_y
        cells.append((week + weekday, week, weekday, cx, cy, count, private))
        if current.day == 1:
            month_labels.append(f'<text class="month" x="{origin_x + week * step_x:.1f}" y="{H - 13}">{current.strftime("%b")}</text>')

    city = []
    for _, week, weekday, cx, cy, count, private in sorted(cells):
        ground = ((cx, cy - step_y), (cx + step_x, cy), (cx, cy + step_y), (cx - step_x, cy))
        city.append(polygon("ground", ground))
        if not count:
            continue
        height = 5 + 120 * math.sqrt(count / maximum)
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
<text class="total" x="24" y="32">{total:,}</text><text class="muted" x="108" y="32">contributions</text>
<rect x="500" y="18" width="12" height="12" rx="2" fill="{t['pub_left']}"/><text x="519" y="29">{public_total:,} public</text>
<rect x="646" y="18" width="12" height="12" rx="2" fill="{t['private_left']}"/><text x="665" y="29">{private_total:,} private</text>
<text class="muted" x="24" y="57">One building per day · height uses a square-root scale</text>
{"".join(city)}
{"".join(month_labels)}
</svg>"""


if __name__ == "__main__":
    if "--check" in sys.argv:
        sample = [(f"2026-01-{day:02}", day, day // 2) for day in range(1, 15)]
        svg = render(sample, THEMES["dark"])
        assert "public-left" in svg and "private-left" in svg and "56 public" in svg
        sys.exit()
    contributions = fetch()
    for name, colors in THEMES.items():
        with open(f"chart-{name}.svg", "w") as output:
            output.write(render(contributions, colors))
