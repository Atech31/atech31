#!/usr/bin/env python3
"""Generate GitHub stats, streak and language SVG cards (no third-party hosts)."""
import json, os, sys, urllib.request
from datetime import date, timedelta
from html import escape

TOKEN = os.environ.get("GH_TOKEN", "")
USER = os.environ.get("USERNAME", "Atech31")
OUT = os.environ.get("OUT_DIR", "assets")

BG, BORDER, TITLE, LABEL, VALUE, ACCENT, WARM = (
    "#1a1b27", "#2f3349", "#70a5fd", "#38bdae", "#a9b1d6", "#70a5fd", "#fe8d59")
FONT = "Segoe UI, Ubuntu, Helvetica, Arial, sans-serif"


def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


PROFILE_Q = """
query($login:String!){ user(login:$login){
  name createdAt
  pullRequests{totalCount} issues{totalCount}
  repositoriesContributedTo(first:1,contributionTypes:[COMMIT,PULL_REQUEST,ISSUE,REPOSITORY]){totalCount}
  repositories(ownerAffiliations:OWNER,isFork:false,first:100){
    nodes{ stargazerCount languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}} }
  }
}}"""

YEAR_Q = """
query($login:String!,$from:DateTime!,$to:DateTime!){ user(login:$login){
  contributionsCollection(from:$from,to:$to){
    totalCommitContributions restrictedContributionsCount
    contributionCalendar{ totalContributions weeks{contributionDays{date contributionCount}} }
  }
}}"""


def fetch():
    u = gql(PROFILE_Q, {"login": USER})["user"]
    start = int(u["createdAt"][:4])
    today = date.today()
    commits, days = 0, {}
    for y in range(start, today.year + 1):
        c = gql(YEAR_Q, {"login": USER, "from": f"{y}-01-01T00:00:00Z",
                         "to": f"{y}-12-31T23:59:59Z"})["user"]["contributionsCollection"]
        commits += c["totalCommitContributions"] + c["restrictedContributionsCount"]
        for w in c["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
    langs = {}
    stars = 0
    for r in u["repositories"]["nodes"]:
        stars += r["stargazerCount"]
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            langs.setdefault(n, [0, e["node"]["color"] or "#8b949e"])[0] += e["size"]
    return {
        "name": u["name"] or USER, "stars": stars, "commits": commits,
        "prs": u["pullRequests"]["totalCount"], "issues": u["issues"]["totalCount"],
        "contrib_to": u["repositoriesContributedTo"]["totalCount"],
        "days": days, "langs": langs,
    }


def streaks(days):
    ordered = sorted(days)
    longest = run = 0
    prev = None
    for d in ordered:
        dd = date.fromisoformat(d)
        if days[d] > 0:
            run = run + 1 if prev and dd - prev == timedelta(days=1) else 1
            longest = max(longest, run)
            prev = dd
        else:
            run, prev = 0, None
    cur, d = 0, date.today()
    if days.get(d.isoformat(), 0) == 0:
        d -= timedelta(days=1)
    while days.get(d.isoformat(), 0) > 0:
        cur += 1
        d -= timedelta(days=1)
    return cur, longest


def fmt(v):
    return "—" if v is None else f"{v:,}"


def card(w, h, body, title=None):
    t = (f'<text x="25" y="35" font-size="18" font-weight="600" fill="{TITLE}">{escape(title)}</text>'
         if title else "")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family="{FONT}"><rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="8" '
            f'fill="{BG}" stroke="{BORDER}"/>{t}{body}</svg>')


def stats_svg(d):
    rows = [("Total stars earned", d["stars"]), ("Total commits", d["commits"]),
            ("Total PRs", d["prs"]), ("Total issues", d["issues"]),
            ("Contributed to", d["contrib_to"])]
    body = ""
    for i, (k, v) in enumerate(rows):
        y = 70 + i * 26
        body += (f'<text x="25" y="{y}" font-size="14" fill="{LABEL}">{k}</text>'
                 f'<text x="375" y="{y}" font-size="14" fill="{VALUE}" text-anchor="end">{fmt(v)}</text>')
    return card(400, 200, body, f"{d['name']}'s GitHub stats")


def streak_svg(d):
    if d["days"] is None:
        total = cur = lng = None
    else:
        total = sum(d["days"].values())
        cur, lng = streaks(d["days"])
    def col(x, big, small, color):
        return (f'<text x="{x}" y="100" font-size="30" font-weight="600" fill="{color}" text-anchor="middle">{fmt(big)}</text>'
                f'<text x="{x}" y="128" font-size="13" fill="{LABEL}" text-anchor="middle">{small}</text>')
    body = (col(70, total, "Total contributions", ACCENT)
            + f'<circle cx="200" cy="95" r="45" fill="none" stroke="{ACCENT}" stroke-width="5"/>'
            + f'<text x="200" y="102" font-size="30" font-weight="600" fill="{ACCENT}" text-anchor="middle">{fmt(cur)}</text>'
            + f'<text x="200" y="165" font-size="13" fill="{WARM}" text-anchor="middle">Current streak</text>'
            + col(330, lng, "Longest streak", ACCENT))
    return card(400, 200, body)


def langs_svg(d):
    items = sorted(d["langs"].items(), key=lambda kv: -kv[1][0])[:6] if d["langs"] else []
    total = sum(v[0] for _, v in items) or 1
    body, x = "", 25
    bar_w = 350
    body += f'<clipPath id="c"><rect x="25" y="55" width="{bar_w}" height="10" rx="5"/></clipPath><g clip-path="url(#c)">'
    for n, (size, color) in items:
        w = bar_w * size / total
        body += f'<rect x="{x:.1f}" y="55" width="{w:.1f}" height="10" fill="{color}"/>'
        x += w
    body += "</g>"
    if not items:
        body += f'<text x="25" y="100" font-size="14" fill="{VALUE}">No data yet</text>'
    for i, (n, (size, color)) in enumerate(items):
        cx, cy = 25 + (i % 2) * 180, 95 + (i // 2) * 26
        pct = size * 100 / total
        body += (f'<circle cx="{cx+5}" cy="{cy-4}" r="5" fill="{color}"/>'
                 f'<text x="{cx+18}" y="{cy}" font-size="13" fill="{VALUE}">{escape(n)} {pct:.1f}%</text>')
    return card(400, 200, body, "Most used languages")


def main():
    os.makedirs(OUT, exist_ok=True)
    if "--placeholder" in sys.argv:
        d = {"name": USER, "stars": None, "commits": None, "prs": None, "issues": None,
             "contrib_to": None, "days": None, "langs": {}}
    else:
        if not TOKEN:
            sys.exit("GH_TOKEN is not set")
        d = fetch()
    for name, fn in (("stats", stats_svg), ("streak", streak_svg), ("langs", langs_svg)):
        with open(os.path.join(OUT, f"{name}.svg"), "w", encoding="utf-8") as f:
            f.write(fn(d))
    print("Generated", OUT)


if __name__ == "__main__":
    main()
