#!/usr/bin/env python3
"""Fetch the last 12 months of GitHub contributions and render chart.svg.
Usage: GH_TOKEN=... python3 chart.py [login]   # writes chart-light.svg and chart-dark.svg
"""
import itertools, json, os, sys, urllib.request
from datetime import date

LOGIN = sys.argv[1] if len(sys.argv) > 1 else "baziyer"
QUERY = """query($login:String!){ user(login:$login){ contributionsCollection{
  contributionCalendar{ weeks{ contributionDays{ date contributionCount } } } } } }"""

def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {os.environ['GH_TOKEN']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if "errors" in body:
        sys.exit(body["errors"])
    weeks = body["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return sorted((d["date"], d["contributionCount"]) for w in weeks for d in w["contributionDays"])[-365:]

def nice_step(top):
    for s in (10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000):
        if top / s <= 5:
            return s
    return 100000

THEMES = {
    "light": dict(ink="#1f2328", muted="#59636e", grid="#d1d9e0", line="#2a78d6", bg="#ffffff"),
    "dark": dict(ink="#e6edf3", muted="#8b949e", grid="#30363d", line="#3987e5", bg="#0d1117"),
}

def render(days, t):
    counts = [c for _, c in days]
    cum = list(itertools.accumulate(counts))
    total, last90, prior90 = cum[-1], sum(counts[-90:]), sum(counts[-180:-90])
    mult = f"{last90 / prior90:.1f}×" if prior90 else "—"  # only used in the alt text
    if total == 0:
        return "<svg xmlns='http://www.w3.org/2000/svg' width='800' height='60'><text x='0' y='30'>No contributions yet</text></svg>"

    W, H = 640, 320
    x0, x1, y0, y1 = 72, 612, 24, 268  # plot box
    step = nice_step(total)
    ymax = max(step, -(-total // step) * step)
    n = len(days)
    px = lambda i: x0 + (x1 - x0) * i / (n - 1)
    py = lambda v: y1 - (y1 - y0) * v / ymax
    pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(cum))

    grid = "".join(
        f'<line class="grid" x1="{x0}" x2="{x1}" y1="{py(v):.1f}" y2="{py(v):.1f}"/>'
        f'<text class="muted" x="{x0 - 10}" y="{py(v) + 5:.1f}" text-anchor="end">{v:,}</text>'
        for v in range(0, ymax + 1, step)
    )
    months = "".join(
        f'<text class="muted" x="{px(i):.1f}" y="{y1 + 30}" text-anchor="middle">'
        f'{date.fromisoformat(d).strftime("%b")}</text>'
        for i, (d, _) in enumerate(days) if d.endswith("-01") and int(d[5:7]) % 2 and 6 < i < n - 6
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Cumulative GitHub contributions, last 12 months: {total:,}; last 90 days {last90:,}, {mult} the prior 90 days.">
<style>
text{{font:18px -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;fill:{t['ink']}}}
.muted{{fill:{t['muted']}}}
.grid{{stroke:{t['grid']};stroke-width:1}}
.area{{fill:{t['line']};opacity:.12}}
.line{{fill:none;stroke:{t['line']};stroke-width:2.5;stroke-linejoin:round}}
.dot{{fill:{t['line']};stroke:{t['bg']};stroke-width:2}}
.label{{font-weight:600}}
</style>
{grid}
<polygon class="area" points="{px(0):.1f},{y1} {pts} {x1},{y1}"/>
<polyline class="line" points="{pts}"/>
<circle class="dot" cx="{x1}" cy="{py(total):.1f}" r="6"/>
<text class="label" x="{x1 - 12}" y="{py(total) - 14:.1f}" text-anchor="end">{total:,}</text>
{months}
</svg>"""

if __name__ == "__main__":
    days = fetch()
    for name, t in THEMES.items():
        with open(f"chart-{name}.svg", "w") as f:
            f.write(render(days, t))
