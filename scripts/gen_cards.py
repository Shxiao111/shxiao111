#!/usr/bin/env python3
"""Render the profile's stats panel, bookshelf, preface & contents book page and works-in-progress ledge as themed
SVGs, and frame the contribution snake.

Runs in GitHub Actions (see .github/workflows/cards.yml) and writes
dist/{stats,shelf,toc,works,colophon}-{dark,light}.svg.
If Platane/snk has already left dist/snake-{dark,light}.svg there, they are framed as the contributions card
(a local run without them just skips it).
Only the standard library is used. Fonts are embedded from scripts/fonts.json (which also carries their advance
widths, for measuring text), the illustrations from scripts/art/<season>/ (see prep_images.py; common.SEASON picks
the season, and with it the palettes and what stands in the bookshelf's vase).
Repositories, stars, languages, commits, pull requests and issues count public work only, so a local run with a
personal token matches the Actions run.  The calendar and streaks are github's own contribution calendar, which
includes private contributions only as far as the token's viewer may see them (or the profile shares them).
"""
import colorsys
import datetime as dt
import json
import os
import random
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request

from common import CALM, EASE, FONTS, SEASON, art, esc, fontface, smooth_fade, star_path, write_svg
from paper import punch
from sunlight import halo, light_rays
from spring import BLOSSOM_PETAL
if SEASON == "winter":       # the sprig in the bookshelf's vase: maple, plum blossom, cherry blossom, or hibiscus
    from winter import MIST_CSS, PLUM_COLORS as LEAF_COLORS, PLUM_STALK as STALK_END, flake_def, ice, mist, plum_def as leaf_def
elif SEASON == "spring":
    from spring import BLOSSOM_STALK as STALK_END, PETAL_COLORS as LEAF_COLORS, blossom_def as leaf_def, leaf_light
elif SEASON == "summer":
    from summer import BLOSSOM_STALK as STALK_END, PETAL_COLORS as LEAF_COLORS, hibiscus_def as leaf_def, water_light
else:
    from maple import LEAF_COLORS, STALK_END, leaf_def

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "dist")
LOGIN = os.environ.get("GH_LOGIN", "shxiao111")
EDITION = os.environ.get("GITHUB_RUN_NUMBER")   # the workflow's run counter, the colophon's edition; a local run has none
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

# ---- the preface: the left page of the book card, beside the contents -----------------------------
PREFACE = [                      # (icon, text): icons are "cap", "books" or "blossom"; \n breaks the line
    ("cap", "A sophomore in\nComputer Science and Technology"),
    ("books", "A member of BYR Docs"),
    ("blossom", "She is Amano Tooko.\nAs you can see, a literary girl."),
]
PREFACE_NAMES = ["BYR Docs", "Amano Tooko"]   # inked in the accent colour
# --------------------------------------------------------------------------------------------------

STATS_IMG, WORKS_IMG = art("stats"), art("works")

# pull requests and issues through search, which can be limited to public repositories; user.pullRequests can't
QUERY = """
query($login: String!, $prs: String!, $issues: String!) {
  prs: search(query: $prs, type: ISSUE, first: 1) { issueCount }
  issues: search(query: $issues, type: ISSUE, first: 1) { issueCount }
  user(login: $login) {
    contributionsCollection {
      commitContributionsByRepository(maxRepositories: 100) {
        repository { name isPrivate languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } } }
        contributions { totalCount }
      }
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
    pinnedItems(first: 6, types: REPOSITORY) {
      nodes {
        ... on Repository {
          name description isPrivate pushedAt stargazerCount forkCount owner { login }
          languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } }
        }
      }
    }
  }
}
"""
REPOS_QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        name description pushedAt stargazerCount forkCount owner { login }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def gql(query, variables, retries=2):
    if not TOKEN:
        sys.exit("GITHUB_TOKEN is not set")
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": "profile-cards"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                res = json.load(resp)
            if res.get("errors"):
                if attempt < retries:   # github reports its own timeouts this way, under a 200
                    time.sleep(1.5 * (attempt + 1))
                    continue
                sys.exit(json.dumps(res["errors"], indent=2))
            return res["data"]
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            if attempt < retries and e.code in (429, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                continue
            sys.exit(f"GitHub GraphQL HTTP {e.code}: {e.reason}\n{err_body}")
        except OSError as e:   # URLError, and what it does not wrap: a timeout or a reset while reading the answer
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            sys.exit(f"Network error connecting to GitHub: {getattr(e, 'reason', e)}")


YEARS_QUERY = "query($login: String!) { user(login: $login) { contributionsCollection { contributionYears } } }"


def all_days(chunk_size=5):
    """Every calendar day of every contribution year, as sorted (date, count) pairs."""
    years = gql(YEARS_QUERY, {"login": LOGIN})["user"]["contributionsCollection"]["contributionYears"]
    if not years:
        return []
    days = {}
    for i in range(0, len(years), chunk_size):
        chunk = years[i:i + chunk_size]
        fields = " ".join(
            f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z") '
            "{ contributionCalendar { weeks { contributionDays { date contributionCount } } } }" for y in chunk)
        u = gql("query($login: String!) { user(login: $login) { %s } }" % fields, {"login": LOGIN})["user"]
        for y in chunk:
            for w in u[f"y{y}"]["contributionCalendar"]["weeks"]:
                for day in w["contributionDays"]:
                    days[day["date"]] = day["contributionCount"]
    return sorted(days.items())


def all_repos():
    """(total count, every public non-fork repository I own), a page of 100 at a time."""
    repos, after = [], None
    while True:
        page = gql(REPOS_QUERY, {"login": LOGIN, "after": after})["user"]["repositories"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return page["totalCount"], repos
        after = page["pageInfo"]["endCursor"]


def streaks(days, today):
    """All-time total plus current and longest streak as (length, first day, last day).
    Input is sorted by date. Missing dates break a streak.
    Today still counts as open: a streak that ran through yesterday is kept."""
    days = [(dt.date.fromisoformat(k), c) for k, c in days if dt.date.fromisoformat(k) <= today]
    longest, run, start = (0, None, None), 0, None
    previous = None
    for day, c in days:
        if previous is not None and day != previous + dt.timedelta(days=1):
            run = 0
        if c > 0:
            start = day if run == 0 else start
            run += 1
            if run > longest[0]:
                longest = (run, start, day)
        else:
            run = 0
        previous = day
    i = len(days) - 1
    if i >= 0 and days[i] == (today, 0):
        i -= 1
    end, n = (days[i][0] if i >= 0 else None), 0
    expected = end if end in (today, today - dt.timedelta(days=1)) else None
    while i >= 0 and days[i][0] == expected and days[i][1] > 0:
        n += 1
        expected -= dt.timedelta(days=1)
        i -= 1
    current = (n, days[i + 1][0], end) if n else (0, None, None)
    first = next((day for day, c in days if c > 0), None)
    return {"total": sum(c for _, c in days), "current": current, "longest": longest, "first": first}


SKIP_LANGS = {"XSLT", "Makefile", "DTrace", "HTML", "Shell", "Batchfile", "CMake"}


def collect():
    res = gql(QUERY, {"login": LOGIN, "prs": f"author:{LOGIN} is:pr is:public",
                      "issues": f"author:{LOGIN} is:issue is:public"})
    u = res["user"]
    repo_count, repos = all_repos()
    # my own repositories, latest first; the profile repository itself is where the reader already is
    own = sorted((r for r in repos if r["name"].lower() != LOGIN.lower()), key=lambda r: r["pushedAt"], reverse=True)
    # chapter ii: the pinned repositories
    works = [volume(r) for r in u["pinnedItems"]["nodes"] if r and not r["isPrivate"]][:WORKS_MAX]
    cc = u["contributionsCollection"]
    # the bookshelf: every public repository committed to over the calendar's 12 months, mine or not, the most
    # written-in first
    shelf = sorted(({"name": r["repository"]["name"], "commits": r["contributions"]["totalCount"], **main_lang(r["repository"])}
                    for r in cc["commitContributionsByRepository"] if not r["repository"]["isPrivate"]),
                   key=lambda v: -v["commits"])
    days = [(d["date"], d["contributionCount"]) for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    today = dt.date.fromisoformat(days[-1][0])   # the calendar ends on github's "today"
    return {
        "today": today,
        "streak": streaks(all_days(), today),
        "stars": sum(r["stargazerCount"] for r in repos),
        "repos": repo_count,
        # public commits over the calendar's 12 months; restrictedContributionsCount would add private PRs and
        # reviews too, not just commits
        "commits": sum(v["commits"] for v in shelf),
        "prs": res["prs"]["issueCount"],
        "issues": res["issues"]["issueCount"],
        "active_days": sum(1 for _, c in days if c > 0),
        "days_count": len(days),
        "shelf": shelf,
        "own": [{"name": r["name"], "pushed": dt.date.fromisoformat(r["pushedAt"][:10]),
                 "desc": " ".join((r["description"] or "").split()),
                 "langs": [e["node"]["name"] for e in r["languages"]["edges"] if e["node"]["name"] not in SKIP_LANGS]}
                for r in own],
        "works": works,
    }


def main_lang(r):
    """The language a repository is mostly written in, and github's colour for it."""
    lang = next((e["node"] for e in r["languages"]["edges"] if e["node"]["name"] not in SKIP_LANGS), None)
    return {"lang": lang["name"] if lang else "", "color": lang["color"] if lang else None}


def volume(r):
    """A repository as one volume in the works-in-progress bookcase: its main language colours the cover's wash."""
    return {"name": r["name"], "owner": r["owner"]["login"], "desc": " ".join((r["description"] or "").split()),
            "stars": r["stargazerCount"], "forks": r["forkCount"],
            "pushed": dt.date.fromisoformat(r["pushedAt"][:10]), **main_lang(r)}


AUTUMN = {
    "dark": dict(
        bg0="#1b180e", bg1="#121210", border="#3a3418",
        title="#fbf6e0", label="#c2b788", value="#fbf6e0", muted="#9a9068",
        accent="#e4cf5a", accent2="#a0a741", track="#2c2814",
        langs=["#f2e173", "#d9b84a", "#a0a741", "#6fb8a8", "#f5d49f", "#b38f2e"],
        grad0="#ffffff", grad1="#e4cf5a",
        pbg0="#1b180e", pbg1="#121210", pbg2="#0d1413", frame="#e8d98a", frameO=".20", grainO=".045",
        blobA="#c9a227", blobAo=".26", blobB="#2f6b62", blobBo=".34", blobC="#8b6fb0", blobCo=".22",
        spark="#fff2b0", toneR="0 .5 .9", toneG="0 .46 .82", toneB="0 .4 .7",
        # bookshelf and contents page
        wood="#6b4a2a", wood0="#553820", wood1="#3a2613", woodLine="#1e1208", wallShade="#000", wallShadeO=".55",
        bookShade="#000", bookShadeO=".55", clothDim="0", foil="#ecd27a", foilDark="#2a1d0a",
        vase0="#7aa593", vase1="#3c5c50", metal0="#8a826c", metal1="#4a453a", stem="#8a5a32",
        ribbon0="#e0552a", ribbon1="#9c3a18", ribbonShadeO=".35", gutter="#000", gutterO=".42",
        nextPage="#221e13", flap0="#0e0d08", flap1="#5c5238", flap2="#39321f", flap3="#282316", curlShadeO=".5", blossom="#f2a2b5",
        # works-in-progress bookcase: the bunkobon jackets and the case's back panel
        glintO=".16",
        # the bookcase card's picture is most of the card, where the stats panel's is under half of it: at dusk it
        # takes a deeper curve, and the card a night page (see works_card)
        worksTone=dict(toneR="0 .36 .86", toneG="0 .26 .64", toneB="0 .16 .42"),
        paper="#efe6cf", ink="#2b2418", inkMuted="#6d604a", coverDim=".1", back0="#2b1e13", back1="#1a120b",
        # the bookworm and its five shades of page: the colours cards.yml asks snk for, which snake_card swaps for
        # another season's
        snake=["#b99cff", "#2a221a", "#5c2a16", "#9c3a18", "#e0552a", "#ff9660"]),
    "light": dict(
        bg0="#fffdf3", bg1="#f8f2d8", border="#e6dcae",
        title="#3b340c", label="#6f6434", value="#3b340c", muted="#8f8454",
        accent="#a8841a", accent2="#6f7a1a", track="#eee5bf",
        langs=["#a8841a", "#d4b64a", "#6f7a1a", "#3f8f7f", "#d49a5a", "#5e4c0c"],
        grad0="#3b340c", grad1="#a8841a",
        pbg0="#faf4d9", pbg1="#fffdf3", pbg2="#f0f2df", frame="#8a7a1a", frameO=".18", grainO=".03",
        blobA="#f2e173", blobAo=".50", blobB="#d8e3a4", blobBo=".55", blobC="#e6dcf5", blobCo=".70",
        spark="#b8921c", toneR="0 1", toneG="0 1", toneB="0 1",
        wood="#dcb682", wood0="#c0915a", wood1="#9a6a38", woodLine="#6b4520", wallShade="#7a5a2a", wallShadeO=".22",
        bookShade="#5a4520", bookShadeO=".22", clothDim="0", foil="#f3d98a", foilDark="#3a2a10",
        vase0="#b3d0c1", vase1="#6f9483", metal0="#c2b9a2", metal1="#7d7462", stem="#7a5230",
        ribbon0="#d9481c", ribbon1="#a82a10", ribbonShadeO=".16", gutter="#6b5a2a", gutterO=".16",
        nextPage="#efe4c3", flap0="#cdbb86", flap1="#fffbef", flap2="#f3e8cb", flap3="#e4d5aa", curlShadeO=".16", blossom="#dc7690",
        glintO=".22",
        paper="#fffbf2", ink="#2b2418", inkMuted="#6d604a", coverDim="0", back0="#e6d0a8", back1="#d2b88a",
        snake=["#7c5cbf", "#f1e7d3", "#f8c89a", "#f08a4b", "#d9481c", "#a82a10"]),
}

# Winter: the snow's blue and the festival night's violet, pewter and silver foil for brass and gilt, and plum red
# where autumn has vermilion.
WINTER = {
    "dark": dict(
        bg0="#17152b", bg1="#0f1020", border="#2f2e58",
        title="#eef0ff", label="#aab0d8", value="#eef0ff", muted="#7f85ae",
        accent="#b9a8ff", accent2="#7fb6e8", track="#25254a",
        langs=["#b9a8ff", "#7fb6e8", "#f29bb5", "#8fd6c8", "#dcd6ff", "#5f7fc8"],
        grad0="#ffffff", grad1="#b9a8ff",
        pbg0="#18152d", pbg1="#0f1020", pbg2="#0b1526", frame="#b9b4f0", frameO=".22", grainO=".045",
        blobA="#6a5cc9", blobAo=".26", blobB="#2a5a8f", blobBo=".34", blobC="#4f8fd0", blobCo=".22",
        spark="#eaf2ff", toneR="0 1", toneG="0 1", toneB="0 1",
        wood="#5e4d48", wood0="#4b3c38", wood1="#2e2422", woodLine="#160f0e", wallShade="#000", wallShadeO=".55",
        bookShade="#000", bookShadeO=".55", clothDim="0", foil="#dfe5f5", foilDark="#1c2238",
        vase0="#7aa593", vase1="#3c5c50", metal0="#8d93a6", metal1="#484c5c", stem="#8a6a5c",
        ribbon0="#e0506c", ribbon1="#9c2a44", ribbonShadeO=".35", gutter="#000", gutterO=".42",
        nextPage="#1c1b36", flap0="#0b0b18", flap1="#55567e", flap2="#333452", flap3="#24253e", curlShadeO=".5", blossom="#f2a2b5",
        glintO=".16",
        paper="#e9e8f2", ink="#22243a", inkMuted="#62668a", coverDim=".1", back0="#1e1f33", back1="#12131f",
        snake=["#f29bb5", "#1e1f3a", "#2c3a78", "#4763b8", "#7fa2ea", "#d3e2ff"], drift="#b9cbf9"),
    "light": dict(
        bg0="#fbfaff", bg1="#f0eefa", border="#d6d3ee",
        title="#2a2350", label="#5c5a8a", value="#2a2350", muted="#8583ad",
        accent="#6a55c0", accent2="#3d7fc4", track="#e4e2f5",
        langs=["#6a55c0", "#3d7fc4", "#d9627f", "#3f9f8f", "#a99ad9", "#2a3f7a"],
        grad0="#2a2350", grad1="#6a55c0",
        pbg0="#f1eefb", pbg1="#fbfaff", pbg2="#eaf2fb", frame="#6a5cb0", frameO=".18", grainO=".03",
        blobA="#d9cdf7", blobAo=".50", blobB="#cfe3f7", blobBo=".55", blobC="#fbd9e4", blobCo=".60",
        spark="#8b73d6", toneR="0 1", toneG="0 1", toneB="0 1",
        wood="#d9cbb8", wood0="#c2b19b", wood1="#978673", woodLine="#5f5242", wallShade="#4a4a6a", wallShadeO=".20",
        bookShade="#3a3a5a", bookShadeO=".22", clothDim="0", foil="#f2f5fc", foilDark="#2a3050",
        vase0="#b3d0c1", vase1="#6f9483", metal0="#c5cad8", metal1="#7c8296", stem="#5a4034",
        ribbon0="#d94a64", ribbon1="#a82a48", ribbonShadeO=".16", gutter="#4a4a7a", gutterO=".14",
        nextPage="#e7e6f6", flap0="#b9b9d6", flap1="#ffffff", flap2="#efeffa", flap3="#dadaee", curlShadeO=".16", blossom="#dc7690",
        glintO=".22",
        paper="#fdfdff", ink="#22243a", inkMuted="#62668a", coverDim="0", back0="#dfe5ee", back1="#c5cfdd",
        snake=["#d9627f", "#ebebf7", "#c9d6f3", "#93b2ea", "#5d80d2", "#3b4fa2"], drift="#8c9fe6"),
}

# Spring: new-leaf green and cherry pink, on autumn's wood and gilt; the ribbon and the bookworm are cherry too.
SPRING = {
    "dark": dict(
        bg0="#171e0e", bg1="#0f1610", border="#2f3d1a",
        title="#f1f9dc", label="#b4c48c", value="#f1f9dc", muted="#8a9a68",
        accent="#b4dc5a", accent2="#f29bb5", track="#232e14",
        langs=["#b4dc5a", "#f29bb5", "#6fc8b8", "#e8d870", "#a9c8f2", "#7fa83a"],
        grad0="#ffffff", grad1="#b4dc5a",
        pbg0="#171e0e", pbg1="#0f1610", pbg2="#0b1716", frame="#cfe69a", frameO=".20", grainO=".045",
        blobA="#6fa82a", blobAo=".26", blobB="#2a6f6a", blobBo=".34", blobC="#c9668a", blobCo=".22",
        spark="#ffe3ec", toneR="0 1", toneG="0 1", toneB="0 1",
        wood="#6b4a2a", wood0="#553820", wood1="#3a2613", woodLine="#1e1208", wallShade="#000", wallShadeO=".55",
        bookShade="#000", bookShadeO=".55", clothDim="0", foil="#ecd27a", foilDark="#2a1d0a",
        vase0="#7aa593", vase1="#3c5c50", metal0="#8a826c", metal1="#4a453a", stem="#8a5a3c",
        ribbon0="#e8718a", ribbon1="#a83a58", ribbonShadeO=".35", gutter="#000", gutterO=".42",
        nextPage="#1b2312", flap0="#0b0f08", flap1="#56633c", flap2="#343f22", flap3="#242c18", curlShadeO=".5", blossom="#f2a2b5",
        glintO=".16",
        paper="#eef0dc", ink="#232b18", inkMuted="#66704e", coverDim=".1", back0="#1e2716", back1="#12180c",
        snake=["#f29bb5", "#1c2414", "#2f4a1a", "#4c7a22", "#7fb52e", "#c6ec6a"]),
    "light": dict(
        bg0="#fcfff5", bg1="#f1f8da", border="#d9e6b0",
        title="#1f3210", label="#5c6e34", value="#1f3210", muted="#84945c",
        accent="#5f8f14", accent2="#d9627f", track="#e6f0c4",
        langs=["#5f8f14", "#d9627f", "#2f8f7f", "#b89a1c", "#5a84c8", "#35520c"],
        grad0="#1f3210", grad1="#5f8f14",
        pbg0="#f3f9dc", pbg1="#fcfff5", pbg2="#eaf5ea", frame="#5f8a1a", frameO=".18", grainO=".03",
        blobA="#d6ec8c", blobAo=".50", blobB="#c8e6d0", blobBo=".55", blobC="#fbd9e4", blobCo=".60",
        spark="#e0809a", toneR="0 1", toneG="0 1", toneB="0 1",
        wood="#dcb682", wood0="#c0915a", wood1="#9a6a38", woodLine="#6b4520", wallShade="#5a6a2a", wallShadeO=".22",
        bookShade="#3a4a20", bookShadeO=".22", clothDim="0", foil="#f3d98a", foilDark="#3a2a10",
        vase0="#b3d0c1", vase1="#6f9483", metal0="#c2b9a2", metal1="#7d7462", stem="#6a4a30",
        ribbon0="#e0607c", ribbon1="#b03a58", ribbonShadeO=".16", gutter="#4a5a2a", gutterO=".16",
        nextPage="#e8f0cc", flap0="#b9c88e", flap1="#fdfff4", flap2="#eef5d6", flap3="#dbe6b6", curlShadeO=".16", blossom="#dc7690",
        glintO=".22",
        paper="#fdfff6", ink="#232b18", inkMuted="#66704e", coverDim="0", back0="#e4eec2", back1="#cfdea0",
        snake=["#d9627f", "#edf3dc", "#cfe69a", "#9fcf4a", "#6a9a1c", "#3f6a14"]),
}

# Summer: the sky's blue and hibiscus pink, on autumn's wood and gilt; the ribbon and the bookworm are hibiscus too.
SUMMER = {
    "dark": dict(
        bg0="#0f1d2e", bg1="#0c1622", border="#1f3a55",
        title="#eaf6ff", label="#9fbdd6", value="#eaf6ff", muted="#7391ab",
        accent="#7cc8f5", accent2="#f2859b", track="#172a40",
        langs=["#7cc8f5", "#f2859b", "#5fd0c0", "#f0d67a", "#b9a8ff", "#3f8fd0"],
        grad0="#ffffff", grad1="#7cc8f5",
        pbg0="#0f1d2e", pbg1="#0c1622", pbg2="#0a1a1f", frame="#a9d6f5", frameO=".20", grainO=".045",
        blobA="#2a8fd6", blobAo=".26", blobB="#1f7a7a", blobBo=".34", blobC="#d9607c", blobCo=".20",
        spark="#fff3c4", toneR="0 1", toneG="0 1", toneB="0 1",
        wood="#6b4a2a", wood0="#553820", wood1="#3a2613", woodLine="#1e1208", wallShade="#000", wallShadeO=".55",
        bookShade="#000", bookShadeO=".55", clothDim="0", foil="#ecd27a", foilDark="#2a1d0a",
        vase0="#7aa593", vase1="#3c5c50", metal0="#8a826c", metal1="#4a453a", stem="#7a8a4c",
        ribbon0="#ef5a78", ribbon1="#a82a4a", ribbonShadeO=".35", gutter="#000", gutterO=".42",
        nextPage="#14253a", flap0="#080f18", flap1="#3f5a78", flap2="#263a52", flap3="#1a2a3e", curlShadeO=".5", blossom="#f2a2b5",
        glintO=".16",
        paper="#e8f0f6", ink="#1a2a3a", inkMuted="#5a6e84", coverDim=".1", back0="#16263a", back1="#0d1826",
        snake=["#f2859b", "#142234", "#1a4a78", "#2a78b8", "#4aa8e8", "#a8dcff"]),
    "light": dict(
        bg0="#fafdff", bg1="#eaf5fc", border="#cfe3f2",
        title="#0f2c47", label="#4a6a88", value="#0f2c47", muted="#7c97b0",
        accent="#1f7fc8", accent2="#d9506c", track="#dcecf7",
        langs=["#1f7fc8", "#d9506c", "#1f9f8f", "#c89a1c", "#7a6ad0", "#0f3f6f"],
        grad0="#0f2c47", grad1="#1f7fc8",
        pbg0="#e8f5fd", pbg1="#fafdff", pbg2="#e6f7f3", frame="#2f7fbf", frameO=".18", grainO=".03",
        blobA="#bfe3fa", blobAo=".50", blobB="#c4ece4", blobBo=".55", blobC="#fbd9e0", blobCo=".60",
        spark="#e3a41c", toneR="0 1", toneG="0 1", toneB="0 1",
        wood="#dcb682", wood0="#c0915a", wood1="#9a6a38", woodLine="#6b4520", wallShade="#2a4a6a", wallShadeO=".20",
        bookShade="#203a5a", bookShadeO=".22", clothDim="0", foil="#f3d98a", foilDark="#3a2a10",
        vase0="#b3d0c1", vase1="#6f9483", metal0="#c2b9a2", metal1="#7d7462", stem="#55703a",
        ribbon0="#e0405f", ribbon1="#b02a48", ribbonShadeO=".16", gutter="#2a4a6a", gutterO=".14",
        nextPage="#e2eff8", flap0="#a9c4d8", flap1="#ffffff", flap2="#eef6fb", flap3="#d6e6f2", curlShadeO=".16", blossom="#dc7690",
        glintO=".22",
        paper="#fcfeff", ink="#1a2a3a", inkMuted="#5a6e84", coverDim="0", back0="#dcebf5", back1="#c2d9ea",
        snake=["#d9506c", "#e8f1f8", "#bfe0f7", "#7fc0ee", "#2f8fd6", "#145a9c"]),
}
# only autumn's pictures are toned down for the dark theme (toneR/G/B, worksTone): the other seasons' keep their
# daylight on the night page
PAL = {"autumn": AUTUMN, "winter": WINTER, "spring": SPRING, "summer": SUMMER}[SEASON]
# px over which the stats picture fades in from its left edge: winter's girl stands close to that edge
STATS_FADE = {"autumn": 230, "winter": 120, "spring": 150, "summer": 150}[SEASON]


# github shows these 1200px cards about 850px wide: print smaller than this lands under 11px on screen.  A spine is
# too narrow for it, so a title there is set as large as the spine takes (SPINE)
SMALL = 15
SPINE = (12, 14)           # a spine title's smallest and largest size
SPINE_TRACK = .055         # its letter-spacing, in ems

CSS = (fontface("outfit") + fontface("jbmono") +
       ".t{font-family:'Outfit',sans-serif;font-weight:800}"
       ".m{font-family:'JetBrains Mono',monospace;font-weight:500}"
       "@keyframes bar{from{transform:scaleX(0)}to{transform:scaleX(1)}}"
       ".b{transform-origin:left;animation:bar 1.2s cubic-bezier(.2,.8,.2,1) .2s both}" + CALM)
if SEASON == "winter":
    CSS += MIST_CSS

ICON = {
    "star": '<path d="M0,-6.5 L1.9,-2 L6.5,-1.7 L2.9,1.4 L4,6 L0,3.5 L-4,6 L-2.9,1.4 L-6.5,-1.7 L-1.9,-2 Z"/>',
    "commit": '<circle r="3.2" fill="none" stroke-width="1.8"/><path d="M-7.5,0 H-3.2 M3.2,0 H7.5" stroke-width="1.8"/>',
    "pr": ('<circle cx="-4" cy="-4.2" r="2.1" fill="none" stroke-width="1.6"/>'
           '<circle cx="-4" cy="4.6" r="2.1" fill="none" stroke-width="1.6"/>'
           '<circle cx="4.6" cy="4.6" r="2.1" fill="none" stroke-width="1.6"/>'
           '<path d="M-4,-2.1 V2.5 M4.6,2.5 V-0.8 Q4.6,-4.2 1.2,-4.2 H-0.6" fill="none" stroke-width="1.6"/>'),
    "issue": '<circle r="6" fill="none" stroke-width="1.8"/><circle r="1.7"/>',
    "repo": '<path d="M-5,-6.5 H5 V6.5 H-3.4 Q-5,6.5 -5,4.9 Z M-5,3.3 H5" fill="none" stroke-width="1.6"/>',
}


def fmt(n):
    return f"{n/1000:.1f}k" if n >= 10000 else f"{n:,}"


def text_width(key, text, size, spacing=0.0):
    """Advance width in px from the tables in fonts.json (printable ASCII); anything else falls back to a system
    font, so guess: 1em for wide CJK characters, .6em otherwise."""
    adv = FONTS[key]["adv"]
    w = 0.0
    for ch in text:
        o = ord(ch)
        if 32 <= o < 127:
            w += adv[o - 32] / 1000 * size
        else:
            w += size if unicodedata.east_asian_width(ch) in "WF" else size * .6
        w += spacing
    return w


def clip_text(key, text, size, max_w, spacing=0.0):
    """`text`, cut short with an ellipsis if it is wider than max_w."""
    if text_width(key, text, size, spacing) <= max_w:
        return text
    while text and text_width(key, text + "...", size, spacing) > max_w:
        text = text[:-1]
    return text.rstrip(" ,.;:-，。、") + "..."


def rgb(c):
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return [int(c[i:i + 2], 16) for i in (0, 2, 4)]


def mix(a, b, t):
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(rgb(a), rgb(b)))


def luma(c):
    r, g, b = (v / 255 for v in rgb(c))
    return .2126 * r + .7152 * g + .0722 * b


def hex_to_hls(hex_str):
    r, g, b = (v / 255.0 for v in rgb(hex_str))
    return colorsys.rgb_to_hls(r, g, b)


def hls_to_hex(h, l, s):
    rgb_t = colorsys.hls_to_rgb(h, max(0.05, min(0.95, l)), max(0.1, min(1.0, s)))
    return "#" + "".join(f"{round(x * 255):02x}" for x in rgb_t)


def hue_dist(h1, h2):
    diff = abs(h1 - h2)
    return min(diff, 1.0 - diff)


def resolve_cloth_colors(langs, fallback):
    """Cloth colours from GitHub's language colours, with no language named here.  Languages whose hues fall
    within 30° of each other are told apart by lightness (dominant -> deep L~0.24, second -> L~0.54, third -> light
    tint L~0.72, and so on) and their saturation clamped, keeping each one's GitHub hue; a language with no
    neighbour keeps its GitHub colour untouched."""
    raw_colors = [c or fallback[i % len(fallback)] for i, (_, _, c) in enumerate(langs)]
    n = len(langs)
    hls_list = [hex_to_hls(c) for c in raw_colors]
    out = list(raw_colors)

    visited = set()
    clusters = []
    for i in range(n):
        if i in visited:
            continue
        cluster = [i]
        visited.add(i)
        for j in range(i + 1, n):
            if j not in visited and hue_dist(hls_list[i][0], hls_list[j][0]) < 0.083:
                cluster.append(j)
                visited.add(j)
        clusters.append(cluster)

    for cluster in clusters:
        if len(cluster) == 1:
            continue
        levels = [0.24, 0.54, 0.72, 0.38, 0.62]
        for rank, idx in enumerate(cluster):
            h, l, s = hls_list[idx]
            target_l = levels[rank % len(levels)]
            target_s = min(0.85, max(0.45, s * 1.15))
            out[idx] = hls_to_hex(h, target_l, target_s)

    return {langs[i][0]: out[i] for i in range(n)}


def card_frame(p, w, h, gid):
    return (f'<defs><style><![CDATA[{CSS}]]></style>'
            f'<linearGradient id="bg{gid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{p["bg0"]}"/><stop offset="1" stop-color="{p["bg1"]}"/></linearGradient>'
            f'<linearGradient id="tg{gid}" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{p["grad0"]}"/><stop offset="1" stop-color="{p["grad1"]}"/></linearGradient>'
            f'<linearGradient id="rg{gid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{p["accent"]}"/><stop offset="1" stop-color="{p["accent2"]}"/></linearGradient>'
            f'</defs>'
            f'<rect x="0.75" y="0.75" width="{w-1.5}" height="{h-1.5}" rx="16" fill="url(#bg{gid})" stroke="{p["border"]}" stroke-width="1.5"/>')


def date_span(a, b):
    f = lambda d: f"{d.strftime('%b').lower()} {d.day}"
    return f(a) if a == b else f"{f(a)} - {f(b)}"


# the stats panel and the bookshelf stand one above the other in the profile and are lit by one window: its shafts
# are drawn across the pair, so a single band runs on down over the seam between them rather than stopping at it
STATS_H, SHELF_H = 480, 336
PAIR_H = STATS_H + SHELF_H


def stats_panel(theme, d):
    """Stats on the left, the window illustration (scripts/stats.jpg) fading in on the right."""
    p = PAL[theme]
    W, H = 1200, STATS_H
    IW = 524                      # stats.jpg is 1048x960 -> 524x480
    ix = W - IW
    s = d["streak"]
    cur_n, cur_a, cur_b = s["current"]
    long_n, long_a, long_b = s["longest"]
    since = f"since {s['first'].strftime('%b').lower()} {s['first'].year}" if s["first"] else "no contributions yet"
    big = [
        (fmt(s["total"]), "total contributions", since, False),
        (fmt(cur_n), "current streak", date_span(cur_a, cur_b) if cur_n else "start one today", True),
        (fmt(long_n), "longest streak", date_span(long_a, long_b) if long_n else "-", False),
    ]
    body = []
    for i, (val, label, sub, hot) in enumerate(big):
        x = 56 + i * 210
        fill = "url(#pgrad)" if hot else p["value"]
        if hot:   # a glow behind the number: lighter than the page on either theme, or it reads as a shadow
            glow = p["accent"] if theme == "dark" else p["blobA"]
            body.append(f'<text x="{x}" y="172" class="t" font-size="56" letter-spacing="-1" fill="{glow}" opacity=".5" filter="url(#pglow)">{val}</text>')
        body.append(f'<text x="{x}" y="172" class="t" font-size="56" letter-spacing="-1" fill="{fill}">{val}</text>')
        body.append(f'<text x="{x}" y="204" class="m" font-size="{SMALL + 1}" fill="{p["label"]}">{label}</text>')
        body.append(f'<text x="{x}" y="226" class="m" font-size="{SMALL}" fill="{p["muted"]}">{sub}</text>')
    # pline is laid out in user space: a gradient sized to a horizontal line's zero-height box isn't painted
    body.append('<line x1="56" y1="262" x2="636" y2="262" stroke="url(#pline)" stroke-width="1.2"/>')
    rows = [("star", "stars", d["stars"]), ("commit", "commits · 1y", d["commits"]),
            ("pr", "pull requests", d["prs"]), ("issue", "issues", d["issues"]), ("repo", "repos", d["repos"])]
    rows = [r for r in rows if r[2]]   # a bare 0 says nothing: the others close up over it
    for i, (ic, label, val) in enumerate(rows):
        x = 56 + i * 136
        body.append(f'<g transform="translate({x+7} 300)" fill="{p["accent"]}" stroke="{p["accent"]}" stroke-linecap="round" stroke-linejoin="round">{ICON[ic]}</g>')
        body.append(f'<text x="{x}" y="346" class="t" font-size="28" fill="{p["value"]}">{fmt(val)}</text>')
        body.append(f'<text x="{x}" y="370" class="m" font-size="{SMALL}" fill="{p["label"]}">{label}</text>')
    frac = d["active_days"] / max(d["days_count"], 1)
    body.append(f'<text x="56" y="408" class="m" font-size="{SMALL + 1}" fill="{p["label"]}">{d["active_days"]} active days</text>'
                f'<text x="636" y="408" class="m" font-size="{SMALL}" text-anchor="end" fill="{p["muted"]}">last 12 months</text>'
                f'<rect x="56" y="420" width="580" height="8" rx="4" fill="{p["track"]}"/>'
                f'<rect class="b" style="transform-box:fill-box" x="56" y="420" width="{580*frac:.1f}" height="8" rx="4" fill="url(#pbar)"/>')
    sparks = "".join(
        f'<g transform="translate({x} {y})"><path d="{star_path(r)}" fill="{p["spark"]}">'
        f'<animate attributeName="opacity" values="0.15;1;0.15" dur="{dur}s" begin="{beg}s" repeatCount="indefinite"/></path></g>'
        for x, y, r, dur, beg in [(640, 58, 7, 3.2, 0), (604, 236, 5, 2.7, 1.1), (1150, 430, 8, 3.6, .5), (700, 448, 5, 2.9, 1.8)])
    # the window light, falling from the upper right: the bookshelf below shares these shafts, so each band is the
    # top slice of one long shaft that carries on over the seam (see PAIR_H)
    sun_defs, sun = light_rays("sunS", 30, W - 60, H, theme == "dark", from_left=False, seed=9, count=4,
                               span=PAIR_H, y0=0)
    frost, fog, wrap = "", "", ("", "")
    if SEASON == "summer":
        # no shafts at noon: the panel is by the sea, and the light off the water plays over it - under the picture,
        # where the frost goes in winter, so no ripple crosses her face
        sun_defs, frost = water_light("seaS", W, H, theme == "dark", seed=9)
        sun = ""
    if SEASON == "spring":       # nor under the trees: the sun through their new leaves, under the picture likewise
        sun_defs, frost = leaf_light("leafS", W, H, theme == "dark", seed=9)
        sun = ""
    if SEASON == "winter":
        # no low sun in winter: the panel is a cold pane.  Frost builds up round its edges, thinning out where the
        # picture comes in with ice of its own; and now and then the whole pane mists over, and clears
        ice_defs, wash, frost = ice("iceS", W, H, theme == "dark", seed=11, fade=(ix, ix + STATS_FADE))
        frost = wash + frost
        fog_defs, fog = mist("mistS", "pall", W, H, theme == "dark", seed=2)
        sun_defs, sun, wrap = ice_defs + fog_defs, "", ('<g id="pall">', "</g>")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="github stats of {esc(LOGIN)}">
<defs><style><![CDATA[{CSS}]]></style>
<clipPath id="pcard"><rect width="{W}" height="{H}" rx="28" ry="28"/></clipPath>
<linearGradient id="pbg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{p['pbg0']}"/><stop offset=".55" stop-color="{p['pbg1']}"/><stop offset="1" stop-color="{p['pbg2']}"/></linearGradient>
<linearGradient id="pgrad" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{p['grad0']}"/><stop offset="1" stop-color="{p['grad1']}"/></linearGradient>
<linearGradient id="pbar" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{p['accent2']}"/><stop offset="1" stop-color="{p['accent']}"/></linearGradient>
<linearGradient id="pline" gradientUnits="userSpaceOnUse" x1="56" y1="0" x2="636" y2="0"><stop offset="0" stop-color="{p['accent']}" stop-opacity=".7"/><stop offset="1" stop-color="{p['accent']}" stop-opacity="0"/></linearGradient>
<linearGradient id="pfade" gradientUnits="userSpaceOnUse" x1="{ix}" y1="0" x2="{ix+STATS_FADE}" y2="0">{smooth_fade(fade_in=True)}</linearGradient>
<mask id="pmask"><rect x="{ix}" y="0" width="{IW}" height="{H}" fill="url(#pfade)"/></mask>
<filter id="pblur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="45"/></filter>
<filter id="pglow" filterUnits="userSpaceOnUse" x="0" y="60" width="{ix}" height="200"><feGaussianBlur stdDeviation="14"/></filter>
<filter id="ptint" color-interpolation-filters="sRGB"><feComponentTransfer><feFuncR type="table" tableValues="{p['toneR']}"/><feFuncG type="table" tableValues="{p['toneG']}"/><feFuncB type="table" tableValues="{p['toneB']}"/></feComponentTransfer></filter>
<filter id="pgrain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/></filter>
{sun_defs}
</defs>
<g clip-path="url(#pcard)">{wrap[0]}
<rect width="{W}" height="{H}" fill="url(#pbg)"/>
<g filter="url(#pblur)">
<ellipse cx="300" cy="60" rx="380" ry="170" fill="{p['blobA']}" opacity="{p['blobAo']}"><animate attributeName="cx" values="300;400;300" dur="18s" repeatCount="indefinite"/></ellipse>
<ellipse cx="160" cy="470" rx="320" ry="140" fill="{p['blobB']}" opacity="{p['blobBo']}"/>
<ellipse cx="820" cy="300" rx="240" ry="220" fill="{p['blobC']}" opacity="{p['blobCo']}"><animate attributeName="rx" values="240;290;240" dur="15s" repeatCount="indefinite"/></ellipse>
</g>{frost}
<image href="data:image/jpeg;base64,{STATS_IMG}" x="{ix}" y="0" width="{IW}" height="{H}" preserveAspectRatio="xMidYMid slice" mask="url(#pmask)" filter="url(#ptint)"/>
{sun}
<g class="mo">{sparks}</g>
<rect width="{W}" height="{H}" filter="url(#pgrain)" opacity="{p['grainO']}"/>
<text x="56" y="84" class="m" font-size="{SMALL + 1}" letter-spacing="2.5" fill="{p['accent']}">github stats</text>
{"".join(body)}{wrap[1]}{fog}
<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="27" fill="none" stroke="{p['frame']}" stroke-opacity="{p['frameO']}" stroke-width="1.5"/>
</g>
</svg>'''


SHELF_Y = 258          # top of the shelf board, where the books stand
ROMAN_NUMS = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
              "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
              "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII", "XXVIII", "XXIX", "XXX",
              "XXXI", "XXXII", "XXXIII", "XXXIV", "XXXV"]


def roman(n):
    return ROMAN_NUMS[n] if 0 < n < len(ROMAN_NUMS) else str(n)


def spine_trim(style, x, y, w, foil, ornament, vol_idx=0):
    """Gilt work and raised bands on a spine, the foot a mirror image of the head; every volume of one language
    shares a style, like a set.  The front of the shelf board hides the bottom 4px of each book, so the foot is
    measured from what shows."""
    head, foot = y, SHELF_Y - 4

    def mirrored(d, hh, piece):   # `piece(top_y)` d px in from the head, and again d px in from the foot
        return piece(head + d) + piece(foot - d - hh)

    def rule(d, hh=1.4, o=.85):
        return mirrored(d, hh, lambda yy: f'<rect x="{x + 2.5:.1f}" y="{yy:.1f}" width="{w - 5:.1f}" height="{hh}" fill="{foil}" opacity="{o}"/>')

    # 4 raised bands (bamboo ribs / sewing cords) across the spine
    span = foot - head
    bands = []
    for frac in (0.22, 0.41, 0.61, 0.80):
        by = head + span * frac
        bands.append(
            f'<rect x="{x:.1f}" y="{by:.1f}" width="{w:.1f}" height="1" fill="#fff" opacity=".18"/>'
            f'<rect x="{x:.1f}" y="{by + 1:.1f}" width="{w:.1f}" height="2" fill="#000" opacity=".22"/>'
            f'<rect x="{x:.1f}" y="{by + 3:.1f}" width="{w:.1f}" height="1" fill="#000" opacity=".35"/>'
        )
    ribs = "".join(bands)

    mid_y = (head + foot) / 2
    if vol_idx > 0 and w >= 16:
        # Classical Roman volume numbering for multi-volume collection
        num_str = roman(vol_idx + 1)
        font_sz = min(9.5, max(7.0, w * 0.42))
        vol_label = (
            f'<rect x="-2" y="-2" width="4" height="4" transform="translate({x + w / 2:.1f} {mid_y - font_sz - 4:.1f}) rotate(45)" fill="{foil}" opacity=".6"/>'
            f'<text x="{x + w / 2:.1f}" y="{mid_y + font_sz * 0.35:.1f}" text-anchor="middle" class="m" font-size="{font_sz:.1f}" '
            f'font-weight="700" letter-spacing="0.5" fill="{foil}" opacity=".9">{num_str}</text>'
            f'<rect x="-2" y="-2" width="4" height="4" transform="translate({x + w / 2:.1f} {mid_y + font_sz + 4:.1f}) rotate(45)" fill="{foil}" opacity=".6"/>'
        )
    elif ornament:
        vol_label = (f'<rect x="-2.6" y="-2.6" width="5.2" height="5.2" transform="translate({x + w / 2:.1f} {mid_y:.1f}) rotate(45)" '
                     f'fill="{foil}" opacity=".7"/>')
    else:
        vol_label = ""

    if style == 0:        # double gilt rules
        trim = rule(11) + rule(15.5) + vol_label
    elif style == 1:      # dark leather bands edged in gilt
        band = mirrored(9, 13, lambda yy: f'<rect x="{x:.1f}" y="{yy:.1f}" width="{w:.1f}" height="13" fill="#000" opacity=".24"/>')
        trim = band + rule(7.4, 1.2, .8) + rule(22.4, 1.2, .8) + vol_label
    else:
        trim = rule(12, 2.4) + vol_label   # one broad gilt rule
    return ribs + trim

def vase(p, cx, base):
    """A celadon bud vase with a sprig that sways a little - maple, plum blossom in winter, cherry in spring, hibiscus in summer - and now and then
    drops a leaf or a flower on the shelf."""
    rnd = random.Random(3)
    mouth = base - 54
    stems = ["M0,4 C-3,-22 -14,-44 -30,-66", "M1,4 C4,-26 10,-52 20,-86", "M0,4 C2,-14 0,-28 8,-44"]
    # (x, y, scale, angle): where a leaf's stalk joins a stem (at the tips and part way along), relative to the
    # mouth, and which way the leaf points
    spots = [(-30, -66, 1.0, -36), (-11.7, -35.9, .8, -72), (20, -86, 1.05, 16), (10.9, -52.7, .8, 62), (8, -44, .9, 24)]
    sx, sy = STALK_END
    leaves = []
    for x, y, s, a in spots:
        c = rnd.choice(LEAF_COLORS)
        dur, beg = rnd.uniform(3.5, 5.5), -rnd.uniform(0, 5)
        leaves.append(   # hung by the end of its stalk, so it sways about the stem
            f'<g transform="translate({x} {y}) rotate({a})"><g>'
            f'<animateTransform attributeName="transform" type="rotate" values="-7;7;-7" keyTimes="0;.5;1" calcMode="spline" '
            f'keySplines="{EASE};{EASE}" dur="{dur:.1f}s" begin="{beg:.1f}s" repeatCount="indefinite"/>'
            f'<use href="#vleaf" transform="scale({s}) translate({-sx} {-sy})" fill="{c}"/></g></g>')
    stems = "".join(f'<path d="{s}"/>' for s in stems)
    sprig = (f'<g transform="translate({cx} {mouth})"><g>'
             f'<animateTransform attributeName="transform" type="rotate" values="-1.6;1.6;-1.6" keyTimes="0;.5;1" calcMode="spline" '
             f'keySplines="{EASE};{EASE}" dur="7s" repeatCount="indefinite"/>'
             f'<g fill="none" stroke="{p["stem"]}" stroke-width="1.6" stroke-linecap="round">{stems}</g>'
             f'{"".join(leaves)}</g></g>')
    body = (
        # Wooden footed stand ring
        f'<ellipse cx="{cx}" cy="{base + 1}" rx="14" ry="3.5" fill="{p["wood1"]}"/>'
        f'<ellipse cx="{cx}" cy="{base}" rx="13" ry="3" fill="url(#wood)"/>'
        # Drop shadow onto shelf
        f'<ellipse cx="{cx}" cy="{base + 2}" rx="15" ry="3.8" fill="#000" opacity="{p["wallShadeO"]}" filter="url(#bshade)"/>'
        # Vase porcelain body
        f'<path d="M{cx - 5},{mouth} Q{cx - 6},{mouth + 8} {cx - 15},{mouth + 28} '
        f'Q{cx - 20},{mouth + 44} {cx - 16},{base - 4} Q{cx - 15},{base} {cx},{base} '
        f'Q{cx + 15},{base} {cx + 16},{base - 4} Q{cx + 20},{mouth + 44} {cx + 15},{mouth + 28} '
        f'Q{cx + 6},{mouth + 8} {cx + 5},{mouth} Z" fill="url(#vaseG)"/>'
        # Delicate celadon crackle glaze veins (冰裂开片纹)
        f'<path d="M{cx - 6},{mouth + 20} Q{cx - 2},{mouth + 28} {cx + 2},{mouth + 26} T{cx + 8},{mouth + 38} '
        f'M{cx - 12},{mouth + 32} Q{cx - 6},{mouth + 42} {cx - 1},{mouth + 38} T{cx + 6},{mouth + 46}" '
        f'fill="none" stroke="{p["stem"]}" stroke-opacity=".18" stroke-width=".7" stroke-linecap="round"/>'
        # Specular glaze highlight on the window side (瓷器玉质双层高光弧)
        f'<path d="M{cx + 8},{mouth + 14} Q{cx + 15},{mouth + 28} {cx + 12},{base - 8}" '
        f'fill="none" stroke="#fff" stroke-opacity=".45" stroke-width="2.6" stroke-linecap="round"/>'
        f'<path d="M{cx + 8},{mouth + 14} Q{cx + 15},{mouth + 28} {cx + 12},{base - 8}" '
        f'fill="none" stroke="#fff" stroke-opacity=".80" stroke-width="1.0" stroke-linecap="round"/>'
        # Porcelain lip rim (卷沿)
        f'<ellipse cx="{cx}" cy="{mouth}" rx="5.8" ry="2.4" fill="url(#vaseG)"/>'
        f'<ellipse cx="{cx}" cy="{mouth}" rx="4.8" ry="1.8" fill="{p["vase1"]}"/>'
        f'<ellipse cx="{cx}" cy="{mouth - 0.4}" rx="5.2" ry="1.2" fill="none" stroke="#fff" stroke-opacity=".5" stroke-width=".8"/>'
    )
    # the falling leaf: lets go of the sprig, flutters down, lies on the board a moment and fades
    kt = "0;.1;.2;.3;.4;1"
    spl = f'keyTimes="{kt}" calcMode="spline" keySplines="{";".join([EASE] * 5)}" dur="18s" begin="6s" repeatCount="indefinite"'
    c = LEAF_COLORS[1]
    fall = (f'<g class="mo" transform="translate({cx} {mouth})"><g opacity="0">'
            f'<animate attributeName="opacity" values="0;1;1;1;0;0" keyTimes="0;.03;.4;.52;.6;1" dur="18s" begin="6s" repeatCount="indefinite"/>'
            f'<animateTransform attributeName="transform" type="translate" values="-26 -60;-10 -32;-30 -4;6 26;30 {base - 3 - mouth};30 {base - 3 - mouth}" {spl}/>'
            f'<g><animateTransform attributeName="transform" type="scale" values="1 1;1 1;1 1;1 1;1 .35;1 .35" {spl}/>'
            f'<g><animateTransform attributeName="transform" type="rotate" values="0;50;-25;60;95;95" {spl}/>'
            f'<use href="#vleaf" transform="scale(1.1)" fill="{c}"/></g></g></g></g>')
    return sprig + body, fall


def book_counts(shares, n):
    """Volumes per language: `shares` of n books by largest remainder, one at least each.  A few slivers rounded up
    to their one volume can push the total past n, so the most generously rounded runs give one back."""
    raw = [s * n for s in shares]
    counts = [max(1, int(r)) for r in raw]
    while shares and sum(counts) < n:
        i = max(range(len(raw)), key=lambda i: raw[i] - counts[i])
        counts[i] += 1
    while sum(counts) > n:
        candidates = [i for i in range(len(raw)) if counts[i] > 1]
        if not candidates:
            break
        i = max(candidates, key=lambda i: counts[i] - raw[i])
        counts[i] -= 1
    return counts


def shelf_card(theme, d):
    """The year's writing as a shelf of books: each repository committed to is a set of matching volumes, titled on
    its first spine and bound in its main language's cloth.  A set has as many volumes as the square root of its
    commits earns it (one at least), so a year spent in one repository still leaves the others their place.
    A bookend and a vase with the season's sprig close the row."""
    p = PAL[theme]
    W, H = 1200, SHELF_H
    dark = theme == "dark"
    rnd = random.Random(7)

    N, X0, X1 = 34, 60, 1046
    shelf = d["shelf"][:N]
    total = sum(r["commits"] for r in shelf) or 1
    share = {}                    # of the commits, by the main language of the repository they went to
    for r in shelf:
        share[r["lang"]] = share.get(r["lang"], 0) + r["commits"] / total
    langs = sorted(((n or "other", s, next(r["color"] for r in shelf if r["lang"] == n)) for n, s in share.items()),
                   key=lambda lang: -lang[1])
    cloth_map = resolve_cloth_colors(langs, p["langs"])
    if p["clothDim"] != "0":
        cloth_map = {n: mix(c, "#000", float(p["clothDim"])) for n, c in cloth_map.items()}
    langs = langs[:6]             # what the legend has room for
    roots = [r["commits"] ** .5 for r in shelf]
    counts = book_counts([x / sum(roots) for x in roots], N)
    vols, sets = [], {}
    for si, (r, n) in enumerate(zip(shelf, counts)):
        name = r["name"]
        # sets bound in one language's cloth are told apart by its shade, as well as by their trim
        j = sets[r["lang"]] = sets.get(r["lang"], -1) + 1
        cloth = mix(cloth_map[r["lang"] or "other"], "#fff" if j % 2 else "#000", (0, .2, .16, .34)[j % 4])
        bw, bh = rnd.uniform(24, 31), rnd.uniform(146, 172)
        room = text_width("outfit", name, SPINE[0], SPINE[0] * SPINE_TRACK) + 72   # the height a spine needs to carry this title whole
        for k in range(n):   # a set, but no two volumes quite alike: worn, faded, a little taller or thinner
            vols.append({"si": si, "name": name, "first": k == 0, "idx": k, "w": bw * rnd.uniform(.84, 1.16),
                         "h": min(184, max(bh + rnd.uniform(-10, 10), room * (k == 0))), "cloth": cloth,
                         "c": mix(cloth, rnd.choice(("#000", "#fff")), rnd.uniform(0, .11))})
    gap = 1.2
    k = (X1 - X0 - gap * (len(vols) - 1)) / max(sum(v["w"] for v in vols), 1)
    last_idx = len(vols) - 1
    candidates = [idx for idx in range(len(vols)) if idx != last_idx]
    num_pulled = min(3, len(candidates))
    pulled = set(rnd.sample(candidates, num_pulled)) if candidates else set()
    books, shadows, x = [], [], X0
    for i, v in enumerate(vols):
        w, h = v["w"] * k, v["h"]
        y = SHELF_Y - h
        foil = p["foil"] if luma(v["c"]) < .5 else p["foilDark"]
        title = ""
        # a long name is set smaller to fit between the head and foot trim, down to a size that still reads, and
        # past that it is cut short
        name = clip_text("outfit", v["name"], SPINE[0], h - 70, SPINE[0] * SPINE_TRACK)
        size = max(SPINE[0], min(SPINE[1], SPINE[1] * (h - 70) / text_width("outfit", name, SPINE[1], SPINE[1] * SPINE_TRACK)))
        if v["first"] and w >= 18:
            # spine titles read top to bottom; rotated, the glyphs sit to the right of the baseline
            title = (f'<text transform="translate({x + w / 2 - size * .36:.1f} {y + 32:.1f}) rotate(90)" class="t" font-size="{size:.1f}" '
                     f'letter-spacing="{size * SPINE_TRACK:.2f}" fill="{foil}">{esc(name)}</text>')
        body = (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="2" fill="{v["c"]}"/>'
                + spine_trim(v["si"] % 3, x, y, w, foil, not title, vol_idx=v["idx"]) + title
                + f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="2" fill="url(#spine)"/>')
        
        # Organic tilt on the last volume, naturally resting against the brass bookend
        is_leaning = (i == last_idx and len(vols) >= 4)
        tilt_transform = f' transform="rotate(5 {x + w:.1f} {SHELF_Y})"' if is_leaning else ""

        if i in pulled and not is_leaning:   # lifted book
            dur = rnd.uniform(14.0, 18.0)
            beg = -rnd.uniform(0, dur)
            body = (f'<g><animateTransform attributeName="transform" type="translate" values="0 0;0 -18;0 -18;0 0;0 0" '
                    f'keyTimes="0;.10;.32;.42;1" calcMode="spline" keySplines="{EASE};0 0 1 1;{EASE};0 0 1 1" '
                    f'dur="{dur:.1f}s" begin="{beg:.1f}s" repeatCount="indefinite"/>{body}</g>')
        elif is_leaning:
            body = f'<g{tilt_transform}>{body}</g>'

        books.append(f'<g><title>{esc(v["name"])}</title>{body}</g>')
        if i in pulled and not is_leaning:
            shadows.append(f'<g><animate attributeName="opacity" values="1;.3;1" dur="{dur:.1f}s" begin="{beg:.1f}s" repeatCount="indefinite"/>'
                           f'<rect x="{x - 3:.1f}" y="{y + 3:.1f}" width="{w:.1f}" height="{h - 3:.1f}" rx="2"/></g>')
        elif is_leaning:
            shadows.append(f'<rect x="{x - 3:.1f}" y="{y + 3:.1f}" width="{w:.1f}" height="{h - 3:.1f}" rx="2"{tilt_transform}/>')
        else:
            shadows.append(f'<rect x="{x - 3:.1f}" y="{y + 3:.1f}" width="{w:.1f}" height="{h - 3:.1f}" rx="2"/>')
        x += w + gap
    landed = 0.5
    grain = "".join(f'<path d="M44,{SHELF_Y + yy} C{280 + 90 * j},{SHELF_Y + yy - 1.8} {680 - 70 * j},{SHELF_Y + yy + 2.2} {W - 44},{SHELF_Y + yy}" '
                    f'fill="none" stroke="{p["woodLine"]}" stroke-opacity=".26" stroke-width=".9"/>' for j, yy in enumerate((4, 7.5, 11)))
    plank = (
        # Underside wall drop shadow
        f'<rect x="44" y="{SHELF_Y + 16}" width="{W - 88}" height="32" fill="url(#wall)"/>'
        # Shelf top board (where books stand)
        f'<rect x="44" y="{SHELF_Y - 4}" width="{W - 88}" height="5" fill="{p["wood"]}"/>'
        # Front shelf board with wood gradient
        f'<rect x="44" y="{SHELF_Y}" width="{W - 88}" height="16" rx="1.5" fill="url(#wood)"/>{grain}'
        # Top chamfer highlight line (倒角高光微条)
        f'<rect x="44" y="{SHELF_Y}" width="{W - 88}" height="1.4" fill="#fff" opacity=".35"/>'
        # Bottom chamfer shadow line (下边缘阴影条)
        f'<rect x="44" y="{SHELF_Y + 15}" width="{W - 88}" height="1.4" fill="#000" opacity=".35"/>'
        # Left and right beveled brass corner brackets (黄铜边角包角)
        f'<path d="M44,{SHELF_Y - 2} L52,{SHELF_Y - 2} L44,{SHELF_Y + 6} Z" fill="url(#metal)" opacity=".7"/>'
        f'<path d="M{W - 44},{SHELF_Y - 2} L{W - 52},{SHELF_Y - 2} L{W - 44},{SHELF_Y + 6} Z" fill="url(#metal)" opacity=".7"/>'
    )
    
    # Ornate antique brass scroll bookend
    bx = X1 + 10
    foil = p["foil"]
    bookend = (
        f'<path d="M{bx - 6},{SHELF_Y} L{bx + 22},{SHELF_Y} L{bx + 19},{SHELF_Y - 6} L{bx - 4},{SHELF_Y - 6} Z" fill="url(#metal)"/>'
        f'<rect x="{bx - 4}" y="{SHELF_Y - 6}" width="23" height="1.2" fill="#fff" opacity=".3"/>'
        f'<path d="M{bx - 2},{SHELF_Y - 6} '
        f'C{bx + 1},{SHELF_Y - 28} {bx + 9},{SHELF_Y - 46} {bx + 16},{SHELF_Y - 58} '
        f'C{bx + 12},{SHELF_Y - 66} {bx + 3},{SHELF_Y - 74} {bx - 3},{SHELF_Y - 78} '
        f'L{bx - 3},{SHELF_Y - 6} Z" fill="url(#metal)"/>'
        f'<path d="M{bx + 16},{SHELF_Y - 58} C{bx + 12},{SHELF_Y - 66} {bx + 3},{SHELF_Y - 74} {bx - 3},{SHELF_Y - 78}" '
        f'fill="none" stroke="#fff" stroke-width="1.2" opacity=".35"/>'
        f'<path d="M{bx + 1},{SHELF_Y - 14} C{bx + 5},{SHELF_Y - 32} {bx + 8},{SHELF_Y - 46} {bx + 5},{SHELF_Y - 58} '
        f'C{bx + 2},{SHELF_Y - 66} {bx - 1},{SHELF_Y - 68} {bx},{SHELF_Y - 72}" '
        f'fill="none" stroke="{foil}" stroke-width="1.2" opacity=".6" stroke-linecap="round"/>'
        f'<circle cx="{bx - 2}" cy="{SHELF_Y - 81}" r="3" fill="url(#metal)"/>'
        f'<circle cx="{bx - 2.8}" cy="{SHELF_Y - 81.8}" r="1" fill="#fff" opacity=".4"/>'
    )
    flowers, falling = vase(p, 1112, SHELF_Y - 2)
    # the legend runs from under the first book to the note's right edge: long names close up the gaps first,
    # then the longest are cut short to an even share of the line
    pcts = [f"{share * 100:.1f}%" for _, share, _ in langs]
    names = [name for name, _, _ in langs]
    fixed = sum(15 + 7 + text_width("jbmono", pct, SMALL) for pct in pcts)
    room = W - 48 - X0
    gap = 30
    if langs and fixed + sum(text_width("jbmono", n, SMALL) for n in names) + gap * (len(langs) - 1) > room:
        gap = 16
        budget = room - fixed - gap * (len(langs) - 1)
        widths = sorted(text_width("jbmono", n, SMALL) for n in names)
        cap = budget / len(names)
        for k, w in enumerate(widths):   # names narrower than an even share leave their slack to the rest
            if w > cap:
                break
            budget -= w
            cap = budget / max(len(names) - k - 1, 1)
        names = [clip_text("jbmono", n, SMALL, cap) for n in names]
    legend, lx = [], X0
    for si, (name, pct) in enumerate(zip(names, pcts)):
        legend.append(f'<rect x="{lx}" y="{SHELF_Y + 45}" width="8" height="13" rx="1.5" fill="{cloth_map[langs[si][0]]}"/>'
                      f'<rect x="{lx + 1}" y="{SHELF_Y + 48}" width="6" height="1.2" fill="{p["foil"]}" opacity=".8"/>'
                      f'<text x="{lx + 15}" y="{SHELF_Y + 56}" class="m" font-size="{SMALL}"><tspan fill="{p["label"]}">{esc(name)}</tspan>'
                      f'<tspan fill="{p["muted"]}" dx="7">{pct}</tspan></text>')
        lx += 15 + text_width("jbmono", name, SMALL) + 7 + text_width("jbmono", pct, SMALL) + gap
    if not vols:
        books = [f'<text x="{W / 2}" y="{SHELF_Y - 60}" text-anchor="middle" class="m" font-size="{SMALL}" fill="{p["muted"]}">no books on the shelf yet</text>']
    # the same window as the stats card above: the same shafts, drawn on down across this card, so the light reads
    # as one band running over the seam; `clip` keeps a shaft off the card's rounded corners
    sun_defs, sun = light_rays("sunShelf", 30, W - 60, H, dark, from_left=False, seed=9, count=4,
                               span=PAIR_H, y0=STATS_H, clip="sunS")
    if SEASON == "winter":       # no low sun in winter, and nothing in its place: the shelf is indoors
        sun_defs, sun = "", ""
    glow_color = p["accent"] if dark else p["blobA"]
    glow_op = ".10" if dark else ".22"
    ambient = f'<ellipse cx="860" cy="170" rx="340" ry="110" fill="{glow_color}" opacity="{glow_op}" filter="url(#shelfGlow)"/>'
    if SEASON == "summer":       # the same sea as the stats card above, on the wall behind the books: their print stays clear
        sun_defs, sea = water_light("seaShelf", W, H, dark, seed=4, clip="sunS")
        ambient, sun = ambient + sea, ""
    if SEASON == "spring":       # and the same leaves as over the stats card above
        sun_defs, sea = leaf_light("leafShelf", W, H, dark, seed=4, clip="sunS")
        ambient, sun = ambient + sea, ""

    # Contact shadow at the base of the books
    contact_shadow = (
        f'<rect x="52" y="{SHELF_Y - 14}" width="{X1 - 40}" height="14" fill="#000" opacity="{".38" if dark else ".12"}" filter="url(#bshade)"/>'
        f'<rect x="50" y="{SHELF_Y - 2}" width="{X1 - 38}" height="3" rx="1.5" fill="#000" opacity="{".60" if dark else ".25"}"/>'
    )
    css = "@keyframes late{from{opacity:0}to{opacity:1}}.late{animation:late .8s ease both}"
    n = len(d["shelf"])
    note = f"{n} repositor{'y' if n == 1 else 'ies'} · last 12 months"   # the commits are counted once, on the stats panel
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="the repositories {esc(LOGIN)} wrote in this year, as a bookshelf">'
            + card_frame(p, W, H, "S")
            + f'<defs><style><![CDATA[{css}]]></style>{leaf_def("vleaf")}'
            f'<linearGradient id="spine" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#000" stop-opacity=".36"/>'
            f'<stop offset=".14" stop-color="#000" stop-opacity=".12"/><stop offset=".4" stop-color="#fff" stop-opacity="0"/>'
            f'<stop offset=".64" stop-color="#fff" stop-opacity=".15"/><stop offset=".86" stop-color="#000" stop-opacity=".04"/>'
            f'<stop offset="1" stop-color="#000" stop-opacity=".32"/></linearGradient>'
            f'<linearGradient id="wood" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{p["wood0"]}"/><stop offset="1" stop-color="{p["wood1"]}"/></linearGradient>'
            f'<linearGradient id="wall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{p["wallShade"]}" stop-opacity="{p["wallShadeO"]}"/>'
            f'<stop offset="1" stop-color="{p["wallShade"]}" stop-opacity="0"/></linearGradient>'
            f'<linearGradient id="metal" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{p["metal0"]}"/><stop offset="1" stop-color="{p["metal1"]}"/></linearGradient>'
            f'<linearGradient id="vaseG" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{p["vase0"]}"/><stop offset=".4" stop-color="{p["vase0"]}"/>'
            f'<stop offset="1" stop-color="{p["vase1"]}"/></linearGradient>'
           f'<filter id="bshade" x="-50%" y="-10%" width="200%" height="120%"><feGaussianBlur stdDeviation="3"/></filter>'
           f'<clipPath id="sunS"><rect x="0.75" y="0.75" width="{W - 1.5}" height="{H - 1.5}" rx="16"/></clipPath>'
           f'<filter id="shelfGlow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="45"/></filter>{sun_defs}</defs>'
           + ambient
           + f'<g transform="translate(58 34)" fill="{p["accent"]}">{ICON["star"]}</g>'
           + f'<text x="76" y="40" class="t" font-size="19" fill="url(#tgS)">bookshelf</text>'
           + f'<text x="{W - 48}" y="40" class="m" font-size="{SMALL}" text-anchor="end" fill="{p["label"]}">{note}</text>'
           + f'<g class="late" style="animation-delay:{landed:.2f}s"><g fill="{p["bookShade"]}" opacity="{p["bookShadeO"]}" filter="url(#bshade)">{"".join(shadows)}</g></g>'
           + contact_shadow
           + "".join(books) + sun + flowers + bookend + plank + falling + "".join(legend) + "</svg>")


# the contents page's bottom-right corner curls up: (px along the bottom edge, px up the right edge) at rest,
# and when it lifts as if about to be turned
CURL_REST, CURL_LIFT = (86, 68), (112, 90)


def curl_geometry(W, H, a, b):
    """Path data and gradient axis for the corner folded back along the crease from (W-a, H) to (W, H-b).
    The flap is the corner mirrored over the crease, its edges bowed and its tip rounded like the card's corners;
    the crease itself bulges toward the corner, where the paper rolls over."""
    def lerp(A, B, t):
        return (A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t)

    def toward(A, B, dist):
        length = ((B[0] - A[0]) ** 2 + (B[1] - A[1]) ** 2) ** .5
        return lerp(A, B, dist / length)

    P1, P2, C = (W - a, H), (W, H - b), (W, H)
    dx, dy = P2[0] - P1[0], P2[1] - P1[1]
    t = ((C[0] - P1[0]) * dx + (C[1] - P1[1]) * dy) / (dx * dx + dy * dy)
    F = (P1[0] + t * dx, P1[1] + t * dy)             # foot of the corner on the crease
    T = (2 * F[0] - C[0], 2 * F[1] - C[1])           # where the corner's tip lands
    Q = lerp(F, C, .3)                               # crease control point
    A, B = toward(T, P1, 16), toward(T, P2, 16)
    c1, c2 = lerp(lerp(P1, A, .5), F, .18), lerp(lerp(B, P2, .5), F, .18)
    mid = lerp(lerp(P2, Q, .5), lerp(Q, P1, .5), .5)  # middle of the crease curve
    pt = lambda P: f"{P[0]:.1f},{P[1]:.1f}"
    return {
        "clip": f"M0,0 H{W} V{P2[1]:.1f} Q{pt(Q)} {pt(P1)} H0 Z",
        "flap": f"M{pt(P1)} Q{pt(c1)} {pt(A)} Q{pt(T)} {pt(B)} Q{pt(c2)} {pt(P2)} Q{pt(Q)} {pt(P1)} Z",
        "crease": f"M{pt(P2)} Q{pt(Q)} {pt(P1)}",
        "x1": f"{mid[0]:.1f}", "y1": f"{mid[1]:.1f}", "x2": f"{T[0]:.1f}", "y2": f"{T[1]:.1f}",
    }


def page_curl(W, H, p):
    """(defs, under, over) for a curled bottom-right corner: `under` is the next page showing through, drawn before
    the card; the card goes in <g clip-path="url(#curl)">; `over` is the flap and its shadow.  Every ten seconds
    the corner lifts a little, as if about to be turned, and settles back."""
    frames = [curl_geometry(W, H, *ab) for ab in (CURL_REST, CURL_REST, CURL_LIFT, CURL_REST, CURL_REST)]
    rest = frames[0]
    timing = (f'keyTimes="0;.5;.64;.82;1" calcMode="spline" keySplines="0 0 1 1;{EASE};{EASE};0 0 1 1" '
              f'dur="10s" begin="3s" repeatCount="indefinite"')

    def anim(attr, key=None):
        return f'<animate attributeName="{attr}" values="{";".join(f[key or attr] for f in frames)}" {timing}/>'

    stops = zip((0, .12, .45, 1), (p["flap0"], p["flap1"], p["flap2"], p["flap3"]))
    defs = (f'<clipPath id="curl"><path d="{rest["clip"]}">{anim("d", "clip")}</path></clipPath>'
            f'<linearGradient id="flapG" gradientUnits="userSpaceOnUse" x1="{rest["x1"]}" y1="{rest["y1"]}" x2="{rest["x2"]}" y2="{rest["y2"]}">'
            + "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in stops)
            + anim("x1") + anim("y1") + anim("x2") + anim("y2") + '</linearGradient>'
            f'<filter id="curlBlur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="5"/></filter>')
    under = (f'<rect x="0.75" y="0.75" width="{W - 1.5}" height="{H - 1.5}" rx="16" fill="{p["nextPage"]}" stroke="{p["border"]}" stroke-width="1.5"/>'
             # the roll shades the next page along the crease
             f'<path d="{rest["crease"]}" fill="none" stroke="#000" stroke-width="12" opacity="{p["curlShadeO"]}" filter="url(#curlBlur)">{anim("d", "crease")}</path>')
    over = (f'<path d="{rest["flap"]}" transform="translate(-4 -4)" fill="#000" opacity="{p["curlShadeO"]}" filter="url(#curlBlur)">{anim("d", "flap")}</path>'
            f'<path d="{rest["flap"]}" fill="url(#flapG)" stroke="{p["border"]}" stroke-opacity=".5" stroke-linejoin="round">{anim("d", "flap")}</path>')
    return defs, under, over


ROMAN = "i ii iii iv v vi vii viii ix x".split()


def toc_entry(p, x0, x1, y, num, name, value, sub, t):
    """One contents line: numeral, title, dot leaders running out to the value, and a note underneath.
    Fades in at t; the leaders' base length is the finished line, the set at 0s shortens it until they run out."""
    nx = x0 + 36
    vw = text_width("jbmono", value, SMALL)
    name = clip_text("outfit", name, 21, x1 - vw - 40 - nx)
    nw = text_width("outfit", name, 21)
    lx0, lx1 = nx + nw + 10, x1 - vw - 10
    sub = clip_text("jbmono", sub, SMALL, x1 - nx)
    leader = ""
    if lx1 > lx0 + 8:
        leader = (f'<line x1="{lx0:.1f}" y1="{y - 5}" x2="{lx1:.1f}" y2="{y - 5}" stroke="{p["muted"]}" stroke-width="1.8" '
                  f'stroke-linecap="round" stroke-dasharray="0 7"><set attributeName="x2" to="{lx0:.1f}" begin="0s" fill="freeze"/>'
                  f'<animate attributeName="x2" from="{lx0:.1f}" to="{lx1:.1f}" begin="{t + .25:.2f}s" dur=".7s" fill="freeze"/></line>')
    return (f'<g class="e" style="animation-delay:{t:.2f}s">'
            f'<text x="{x0 + 24}" y="{y}" text-anchor="end" class="h" font-size="28" fill="{p["accent"]}">{ROMAN[num]}.</text>'
            f'<text x="{nx}" y="{y}" class="t" font-size="21" fill="{p["value"]}">{esc(name)}</text>'
            f'<text x="{x1}" y="{y}" class="m" font-size="{SMALL}" text-anchor="end" fill="{p["label"]}">{esc(value)}</text>'
            f'<text x="{nx}" y="{y + 23}" class="m" font-size="{SMALL}" fill="{p["muted"]}">{esc(sub)}</text></g>' + leader, nx, nw)


# what drifts down the works card and across its covers: blossom petals, in winter snow crystals, in autumn the
# maple leaves of the footer and the vase - as (the element and what it draws, its drawing for <defs>, its size
# beside a petal's, and its colours when it brings its own: taken in turn, in place of the palette's one)
if SEASON == "winter":
    DRIFT, DRIFT_DEF, DRIFT_K, DRIFT_COLORS = ("use", 'href="#flake"'), flake_def("flake"), .6, None
elif SEASON == "autumn":
    DRIFT, DRIFT_DEF, DRIFT_K, DRIFT_COLORS = ("use", 'href="#drift"'), leaf_def("drift"), .6, LEAF_COLORS
else:
    DRIFT, DRIFT_DEF, DRIFT_K, DRIFT_COLORS = ("path", f'd="{BLOSSOM_PETAL}"'), "", 1, None


def drift_color(k, default):
    return DRIFT_COLORS[k % len(DRIFT_COLORS)] if DRIFT_COLORS else default


def preface_icon(kind, p):
    """Little drawn stand-ins for the prologue's emoji, about 20px across, centred on the origin."""
    line = f'fill="none" stroke="{p["accent"]}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"'
    if kind == "cap":         # mortarboard with its tassel
        return (f'<g {line}><path d="M0,-6.5 L10,-2.5 L0,1.5 L-10,-2.5 Z" fill="{p["accent"]}" fill-opacity=".25"/>'
                f'<path d="M-5.5,-.3 V4 Q0,7.5 5.5,4 V-.3"/><path d="M10,-2.5 V4.5"/></g>'
                f'<circle cx="10" cy="5.6" r="1.5" fill="{p["accent"]}"/>')
    if kind == "books":       # two standing, one leaning
        return (f'<g {line}><rect x="-8" y="-6.5" width="4.4" height="13" rx=".8"/><rect x="-2.6" y="-4.5" width="4.4" height="11" rx=".8"/>'
                f'<rect x="2.6" y="-6.5" width="4.4" height="13" rx=".8" transform="rotate(14 7 6.5)"/><path d="M-9.5,6.5 H10.5"/></g>')
    petals = "".join(f'<path d="{BLOSSOM_PETAL}" transform="rotate({a})"/>' for a in range(0, 360, 72))
    return f'<g fill="{p["blossom"]}">{petals}</g><circle r="1.7" fill="{p["accent"]}"/>'   # cherry blossom


def wrap(key, text, size, max_w):
    """Break `text` into lines no wider than max_w."""
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and text_width(key, trial, size) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur] if cur else lines


def preface_page(p, x0, x1, y0, t0):
    """The preface lines, hand-written one after another from t0: each line is uncovered left to right at
    writing speed (its clip's base width shows the whole line, the set at 0s hides it until the pen gets there).
    Returns (body, clip defs, last baseline)."""
    tx, size, lead, gap, speed = x0 + 36, 27, 31, 17, 280
    body, clips, y, t = [], [], y0, t0
    for i, (icon, text) in enumerate(PREFACE):
        body.append(f'<g class="e" style="animation-delay:{t:.2f}s"><g transform="translate({x0 + 14} {y - 8})">{preface_icon(icon, p)}</g></g>')
        lines = [ln for part in text.split("\n") for ln in wrap("caveat", part, size, x1 - tx)]
        for j, line in enumerate(lines):
            w = text_width("caveat", line, size) + 14
            dur = max(.3, w / speed)
            ink = esc(line)
            for name in PREFACE_NAMES:
                ink = ink.replace(esc(name), f'<tspan fill="{p["accent"]}">{esc(name)}</tspan>')
            clips.append(f'<clipPath id="pw{i}_{j}"><rect x="{tx - 6}" y="{y - size - 4}" width="{w:.1f}" height="{size + 16}">'
                         f'<set attributeName="width" to="0" begin="0s" fill="freeze"/>'
                         f'<animate attributeName="width" from="0" to="{w:.1f}" begin="{t:.2f}s" dur="{dur:.2f}s" fill="freeze"/></rect></clipPath>')
            body.append(f'<text x="{tx}" y="{y}" class="h" font-size="{size}" fill="{p["value"]}" clip-path="url(#pw{i}_{j})">{ink}</text>')
            t += dur + .08
            y += lead
        y += gap
    return "".join(body), "".join(clips), y - lead - gap


def toc_card(theme, d):
    """A book lying open: the preface on the left page (see PREFACE) and the contents - my own repositories,
    latest first - on the right.  A ribbon lies in the gutter; the bottom-right corner is curled."""
    p = PAL[theme]
    W = 1200
    today = d["today"]

    def when(day):
        m = day.strftime("%b").lower()
        return f"{m} {day.day}" if day.year == today.year else f"{m} {day.year}"

    chapters = []
    for r in d["own"][:4]:
        about = [r["langs"][0], r["desc"]] if r["desc"] and r["langs"] else [r["desc"] or ", ".join(r["langs"][:3])]
        chapters.append((r["name"], when(r["pushed"]), "  ·  ".join(a for a in about if a)))
    Y0, PITCH = 168, 62
    (lx0, lx1), (rx0, rx1) = (96, 552), (648, 1104)
    preface, preface_clips, preface_end = preface_page(p, lx0, lx1, Y0, .3)
    contents_end = Y0 + (max(len(chapters), 1) - 1) * PITCH + 23
    H = round(max(preface_end, contents_end) + 70)
    body = []
    for pi, (x0, x1, title, part, col) in enumerate([(lx0, lx1, "Preface", "about the author", ""),
                                                     (rx0, rx1, "Contents", "my repositories", "last pushed")]):
        body.append(f'<text x="{x0}" y="84" class="h" font-size="46" fill="url(#tgT)">{title}</text>'
                    f'<text x="{x0}" y="118" class="m" font-size="{SMALL}" letter-spacing="2" fill="{p["accent"]}">{part}</text>'
                    f'<text x="{x1}" y="118" class="m" font-size="{SMALL}" text-anchor="end" fill="{p["muted"]}">{col}</text>'
                    f'<rect x="{x0}" y="131" width="{x1 - x0}" height="1.2" fill="url(#rule)"/>'
                    f'<text x="{(x0 + x1) / 2}" y="{H - 26}" text-anchor="middle" class="h" font-size="20" fill="{p["muted"]}">~ {pi + 1} ~</text>')
    body.append(preface)
    if not chapters:
        body.append(f'<text x="{rx0 + 36}" y="{Y0}" class="h" font-size="24" fill="{p["muted"]}">blank pages, for now</text>')
    latest = None
    for j, (name, value, sub) in enumerate(chapters):
        y = Y0 + j * PITCH
        entry, nx, nw = toc_entry(p, rx0, rx1, y, j, name, value, sub, .5 + j * .18)
        body.append(entry)
        latest = latest or (nx, nw, y)
    underline = ""
    if latest:   # a red-pencil underline under the latest chapter, once the contents are written
        nx, nw, y = latest
        underline = (f'<path d="M{nx - 3:.1f},{y + 7} C{nx + nw * .3:.1f},{y + 3} {nx + nw * .65:.1f},{y + 10} {nx + nw + 5:.1f},{y + 4.5}" '
                     f'fill="none" stroke="{p["ribbon0"]}" stroke-width="2.4" stroke-linecap="round" opacity=".85" pathLength="1" stroke-dasharray="1 1">'
                     f'<set attributeName="stroke-dashoffset" to="1" begin="0s" fill="freeze"/>'
                     f'<animate attributeName="stroke-dashoffset" from="1" to="0" begin="{.5 + len(chapters) * .18 + .6:.2f}s" dur=".6s" fill="freeze"/></path>')
    gut = "".join(f'<stop offset="{i / 10:.1f}" stop-color="{p["gutter"]}" stop-opacity="{float(p["gutterO"]) * (3 * b * b - 2 * b ** 3):.3f}"/>'
                  for i in range(11) for b in [1 - abs(2 * i / 10 - 1)])
    L = 232
    ribbon = (f'<g transform="translate(600 0)"><g>'
              f'<animateTransform attributeName="transform" type="rotate" values="-1.4;1.4;-1.4" keyTimes="0;.5;1" calcMode="spline" '
              f'keySplines="{EASE};{EASE}" dur="7s" repeatCount="indefinite"/>'
              f'<path d="M-8,-2 H10 V{L + 2} L1,{L - 9} L-8,{L + 2} Z" transform="translate(3 3)" fill="#000" opacity="{p["ribbonShadeO"]}" filter="url(#rblur)"/>'
              f'<path d="M-9,-2 H9 V{L} L0,{L - 11} L-9,{L} Z" fill="url(#rib)"/>'
              f'<path d="M-4,0 V{L - 7}" stroke="#fff" stroke-opacity=".2" stroke-width="1.5"/></g></g>')
    css = (fontface("caveat") + ".h{font-family:'Caveat',cursive;font-weight:600}"
           "@keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}.e{animation:rise .6s ease both}")
    curl_defs, next_page, flap = page_curl(W, H, p)
    label = esc(f"preface: {' '.join(text.replace(chr(10), ' ') for _, text in PREFACE)} contents: repositories of {LOGIN}")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{label}">'
            + f'<defs>{curl_defs}</defs>' + next_page + '<g clip-path="url(#curl)">'
            + card_frame(p, W, H, "T")
            + f'<defs><style><![CDATA[{css}]]></style>{preface_clips}'
            f'<linearGradient id="gut" x1="0" y1="0" x2="1" y2="0">{gut}</linearGradient>'
            f'<linearGradient id="rule" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{p["accent"]}" stop-opacity=".7"/><stop offset="1" stop-color="{p["accent"]}" stop-opacity="0"/></linearGradient>'
            f'<linearGradient id="rib" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{p["ribbon1"]}"/><stop offset=".35" stop-color="{p["ribbon0"]}"/>'
            f'<stop offset="1" stop-color="{p["ribbon1"]}"/></linearGradient>'
            f'<filter id="rblur" x="-50%" y="-10%" width="200%" height="120%"><feGaussianBlur stdDeviation="2.5"/></filter></defs>'
            + f'<rect x="540" y="1.5" width="120" height="{H - 3}" fill="url(#gut)"/>'
            + f'<line x1="600" y1="1.5" x2="600" y2="{H - 1.5}" stroke="{p["gutter"]}" stroke-opacity="{p["gutterO"]}"/>'
            + "".join(body) + underline + ribbon + "</g>" + flap + "</svg>")


WORKS_MAX = 6              # github pins six at most: three to a shelf, on one shelf or two
COVER_W, COVER_H = 196, 278    # A6, a bunkobon
FRESH_DAYS = 30            # pushed this recently, a hand-written "new chapter" note is taped to the jacket
# the bookcase is seen square on from in front of its middle: its back panel is the opening shrunk this much toward
# that eye, so inside each shelf the walls, and the shelf's top or the underside of the one above, show in perspective
DEPTH = .93
# obi colours, taken in turn as on a bookshop's new-releases shelf: (band, print, the figure that shouts)
OBIS = [("#f4d31f", "#1d1a14", "#c8281e"), ("#1f1d1b", "#f7f1e3", "#f4d31f"),
        ("#c8281e", "#fff8ea", "#ffe14a"), ("#f8f5ec", "#1d1a14", "#c8281e")]
LEAD = 1.12                # title line spacing, in ems
CAP = .72                  # Outfit's cap height, in ems


def title_lines(name, max_w, max_h, max_lines=3):
    """A repository name set as a cover title, as large as fits in max_lines lines and max_h px from the first
    line's cap height to the last baseline: broken after - _ . or between camelCase words, never inside one.
    Returns (size, lines)."""
    parts = re.split(r"(?<=[-_.])(?=[^-_.])|(?<=[a-z0-9])(?=[A-Z])", name)
    for size in range(26, 13, -1):
        lines = [""]
        for part in parts:
            if lines[-1] and text_width("outfit", lines[-1] + part, size) > max_w:
                lines.append("")
            lines[-1] += part
        if (len(lines) <= max_lines and (len(lines) - 1) * size * LEAD + size * CAP <= max_h
                and all(text_width("outfit", ln, size) <= max_w for ln in lines)):
            return size, lines
    return size, [clip_text("outfit", ln, size, max_w) for ln in lines[:max_lines - 1]] + \
        [clip_text("outfit", "".join(lines[max_lines - 1:]), size, max_w)]


WIDE = "[\u2e80-\u9fff\uac00-\ud7af\uf900-\ufaff\ufe30-\ufe4f\uff00-\uffef]"   # CJK, hangul, full-width forms


def wrap_blurb(text, size, max_w):
    """Like wrap(), but CJK text (which has no spaces) may break between any two characters, and so may a word too
    long for a line of its own."""
    lines, cur = [], ""
    toks = []
    for tok in re.findall(WIDE + r"|[^\s" + WIDE[1:-1] + r"]+|\s+", text):
        while not tok.isspace() and len(tok) > 1 and text_width("jbmono", tok, size) > max_w:
            k = max(1, next(k for k in range(len(tok), 0, -1) if text_width("jbmono", tok[:k], size) <= max_w))
            toks.append(tok[:k])
            tok = tok[k:]
        toks.append(tok)
    for tok in toks:
        if cur and not tok.isspace() and text_width("jbmono", cur + tok, size) > max_w:
            lines.append(cur.rstrip())
            cur = ""
        if cur or not tok.isspace():
            cur += " " if tok.isspace() else tok
    return lines + [cur.rstrip()] if cur.strip() else lines


def wash(p, v, base, y0, y1):
    """The cover art between y0 and y1: a watercolour wash in the language's colour, laid on a diagonal from the
    lower left to the upper right with a few splatters, and cherry petals (in autumn maple leaves, in winter snow) drifting down across it.  Seeded by the
    repository's name, so each volume keeps its picture from day to day."""
    cw = COVER_W
    rnd = random.Random(v["name"])
    blobs = []
    for k in range(6):
        t = k / 5
        c = mix(base, rnd.choice(("#fff", "#000", p["paper"])), rnd.uniform(0, .45))
        if k == 3:
            c = mix(base, p["blossom"], .55)   # one wash of a second colour, as a painter would
        blobs.append(f'<ellipse cx="{20 + t * (cw - 40) + rnd.uniform(-18, 18):.0f}" cy="{y1 - 16 - t * (y1 - y0 - 30) + rnd.uniform(-12, 12):.0f}" '
                     f'rx="{rnd.uniform(38, 70):.0f}" ry="{rnd.uniform(26, 44):.0f}" fill="{c}" opacity="{rnd.uniform(.45, .8):.2f}"/>')
    dots = "".join(f'<circle cx="{rnd.uniform(8, cw - 8):.0f}" cy="{rnd.uniform(y0, y1 - 4):.0f}" r="{rnd.uniform(.6, 2.2):.1f}"/>'
                   for _ in range(12))
    petals = []
    for k in range(2):
        x0, dur, beg = rnd.uniform(30, cw - 60), rnd.uniform(11, 16), -rnd.uniform(0, 14)
        petals.append(f'<g class="mo"><animateTransform attributeName="transform" type="translate" values="{x0:.0f} {y0 - 30:.0f};{x0 + 40:.0f} {(y0 + y1) / 2:.0f};{x0 + 10:.0f} {y1 + 10}" '
                      f'dur="{dur:.1f}s" begin="{beg:.1f}s" repeatCount="indefinite"/>'
                      f'<{DRIFT[0]} {DRIFT[1]} transform="scale({1.5 * DRIFT_K:g})" fill="{drift_color(k, p.get("drift", p["blossom"]))}" opacity=".85">'
                      f'<animateTransform attributeName="transform" type="rotate" values="0;200;360" additive="sum" dur="{dur:.1f}s" begin="{beg:.1f}s" repeatCount="indefinite"/></{DRIFT[0]}></g>')
    return (f'<g filter="url(#wash)">{"".join(blobs)}</g><g fill="{base}" opacity=".45">{dots}</g>', "".join(petals))


def poly(*pts):
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"


def cover(p, i, v, today, shade=0, number=1, band=0):
    """One bunkobon standing face out, drawn at the origin.  It opens from the right, so the jacket folds round
    the spine at the right edge.  The paper jacket carries the catalogue
    number, title and author in a band across the top and a watercolour below; the obi (colour OBIS[band])
    carries the description as its copy and the stars in a round badge.  A glint crosses the jacket now and then.
    `shade` darkens the wash, so two volumes in one language aren't twins; `number` counts the author's volumes,
    for the catalogue number."""
    cw, ch = COVER_W, COVER_H
    cx = cw / 2
    ink, dim = p["ink"], float(p["coverDim"])
    base = mix(v["color"] or p["langs"][i % len(p["langs"])], "#000", shade)
    bg, oink, hot = OBIS[band % len(OBIS)]
    oy = round(ch * .66)         # top of the obi
    # the title band: catalogue number and volume, then the title and the author, centred
    size, lines = title_lines(v["name"], cw - 36, 62)
    lead = size * LEAD
    ty = 42 + size * CAP
    last = ty + (len(lines) - 1) * lead
    top = last + 34              # the author's line; below it the picture begins
    art, petals = wash(p, v, base, top - 14, oy)
    # plain paper over the top of the jacket, fading out below the author so the wash bleeds up into it
    fade = (f'<linearGradient id="bf{i}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{p["paper"]}" stop-opacity=".94"/>'
            f'<stop offset="{(top - 4) / (top + 26):.3f}" stop-color="{p["paper"]}" stop-opacity=".94"/>'
            f'<stop offset="1" stop-color="{p["paper"]}" stop-opacity="0"/></linearGradient>')
    title = "".join(f'<text x="{cx}" y="{ty + j * lead:.1f}" text-anchor="middle" class="t" font-size="{size}" fill="{ink}">{esc(ln)}</text>'
                    for j, ln in enumerate(lines))
    head_row = (f'<text x="15" y="26" class="m" font-size="14" fill="{p["inkMuted"]}">{esc(v["owner"][:1].lower())}-1-{number}</text>'
                f'<text x="{cw - 16}" y="27" text-anchor="end" class="h" font-size="19" fill="{p["inkMuted"]}">vol. {ROMAN[i]}</text>')
    author = (f'<rect x="{cx - 14}" y="{last + 10:.1f}" width="28" height=".8" fill="{ink}" opacity=".45"/>'
              f'<text x="{cx}" y="{last + 27:.1f}" text-anchor="middle" class="m" font-size="14" letter-spacing="1.2" fill="{p["inkMuted"]}">'
              f'{esc(clip_text("jbmono", v["owner"], 14, cw - 40, 1.2))}</text>')
    jacket = (f'<rect width="{cw}" height="{ch}" fill="{p["paper"]}"/>' + art
              + f'<rect width="{cw}" height="{top + 26:.1f}" fill="url(#bf{i})"/>'
              + petals
              + f'<rect width="{cw}" height="{ch}" filter="url(#paperG)" opacity=".07"/>'
              # the jacket's fold round the spine, on the right
              f'<path d="M{cw - 7},0 V{ch}" stroke="#000" stroke-opacity=".08"/><path d="M{cw - 8.2},0 V{ch}" stroke="#fff" stroke-opacity=".2"/>'
              + head_row + title + author)
    note = ""
    if (today - v["pushed"]).days <= FRESH_DAYS:   # a note in a shop assistant's hand, taped on: still being written
        note = (f'<g transform="translate({cw - 46} {oy - 22}) rotate(7)">'
                f'<rect x="-26" y="-15" width="54" height="34" fill="#000" opacity=".18"/>'
                f'<rect x="-28" y="-17" width="54" height="34" fill="#fff7cf"/>'
                f'<rect x="-12" y="-22" width="24" height="9" fill="{p["blossom"]}" opacity=".6" transform="rotate(-5)"/>'
                f'<text x="-1" y="0" text-anchor="middle" class="h" font-size="18" fill="#c8281e">new</text>'
                f'<text x="-1" y="13" text-anchor="middle" class="h" font-size="15" fill="{ink}">chapter!</text></g>')
    # the obi: the description as its copy in bold, the stars in a round badge on the right, the language at the foot
    badge = ""
    bw = cw - 28
    if v["stars"]:
        bw -= 62
        bx, by, on = cw - 39, oy + 43, "#fff" if luma(hot) < .5 else "#1d1a14"
        num = fmt(v["stars"])
        ns = min(24, 44 / text_width("outfit", num, 1))
        badge = (f'<circle cx="{bx}" cy="{by}" r="29" fill="{hot}"/>'
                 f'<circle cx="{bx}" cy="{by}" r="25.5" fill="none" stroke="{on}" stroke-opacity=".45" stroke-width=".8"/>'
                 f'<text x="{bx}" y="{by - 12}" text-anchor="middle" class="m" font-size="8.5" fill="{on}">loved by</text>'
                 f'<text x="{bx}" y="{by + ns * .36:.1f}" text-anchor="middle" class="t" font-size="{ns:.1f}" fill="{on}">{num}</text>'
                 f'<text x="{bx}" y="{by + 20}" text-anchor="middle" class="m" font-size="8.5" fill="{on}">'
                 f'reader{"s" if v["stars"] != 1 else ""}</text>')
    bs = 16
    copy = wrap_blurb(v["desc"], bs, bw) or ["(no blurb yet)"]
    if len(copy) > 3:
        copy = copy[:2] + [clip_text("jbmono", copy[2].rstrip(" ,.;:-，。、") + "...", bs, bw)]
    obi_fold = (f'<rect y="{oy}" width="{cw}" height="2.2" fill="#fff" opacity=".35"/>'
                f'<rect y="{oy + 2.2}" width="{cw}" height="1.8" fill="#000" opacity=".12"/>'
                f'<rect y="{ch - 2.5}" width="{cw}" height="2.5" fill="#000" opacity=".22"/>')
    obi = (f'<rect y="{oy}" width="{cw}" height="{ch - oy}" fill="{bg}"/>'
           f'<path d="M{cw - 7},{oy} V{ch}" stroke="#000" stroke-opacity=".1"/>'
           f'{obi_fold}'
           + "".join(f'<text x="14" y="{oy + 28 + j * 19}" class="m" font-size="{bs}" font-weight="700" fill="{oink}">{esc(ln)}</text>'
                     for j, ln in enumerate(copy))
           + badge +
           f'<text x="14" y="{ch - 9}" class="m" font-size="14" fill="{oink}" opacity=".75">{esc(clip_text("jbmono", v["lang"], 14, cw - 28))}</text>')
    glint = (f'<g class="mo" transform="translate(-120 0)">'
             f'<animateTransform attributeName="transform" type="translate" values="-120 0;-120 0;300 0;300 0" keyTimes="0;.84;.93;1" '
             f'calcMode="spline" keySplines="0 0 1 1;{EASE};0 0 1 1" dur="15s" begin="{3 + i * 1.6:.1f}s" repeatCount="indefinite"/>'
             f'<rect y="-20" width="70" height="{ch + 40}" transform="skewX(-18)" fill="url(#glint)"/></g>')
    about = f"{v['name']}: {v['desc']}" if v["desc"] else v["name"]
    return (f'<clipPath id="wc{i}"><rect width="{cw}" height="{ch}" rx="2"/></clipPath>{fade}',
            f'<title>{esc(about)}</title><g clip-path="url(#wc{i})">{jacket}{obi}<rect width="{cw}" height="{ch}" fill="url(#board)"/>'
            f'<rect width="{cw}" height="{ch}" fill="#000" opacity="{dim}"/>{glint}</g>{note}')


WORKS_W = 1200             # as wide as the other cards
WORKS_TUCK = 60            # how far the picture runs on under the bookcase, so its fade ends behind it
# the works card is painted with its picture's own light, so the picture fades into it: `bg` is the picture's colours
# down its right edge, top to bottom (sampled from works.jpg), then the bookcase's wood and back panel, the glow, and
# what drifts down across the card - autumn's golden tree (its leaves are maple.py's, in their own colours, and only
# cast petalShade), winter's snow sky and snow, spring's new leaves and cherry petals, summer's noon sky going down
# into cloud (nothing drifts there)
WORKS = {
    "autumn": dict(bg=["#fba02e", "#f79c3d", "#f7bb78"], wood0="#e2ae62", wood1="#b67a38", woodLine="#7a4a1c",
                   back0="#f9e2a8", back1="#eec07a", glow="#ffe9a6", petalShade="#6b4a1a"),
    "winter": dict(bg=["#f2f4f5", "#f8f8f8", "#d5dee0"], wood0="#b9c5d6", wood1="#8595ad", woodLine="#4a5670",
                   back0="#e6ebf3", back1="#cbd5e3", glow="#ffffff", petal="#a9bdf4", petalShade="#5a6a8a"),
    "spring": dict(bg=["#d4f1b8", "#f9fef3", "#ffffff"], wood0="#e6dcae", wood1="#b3a56a", woodLine="#6a6032",
                   back0="#f6fae2", back1="#dfecb8", glow="#fbffdc", petal="#fffaf0", petalShade="#4a6a2a"),
    "summer": dict(bg=["#1f92fd", "#2194fe", "#f0feff"], wood0="#fbf8ee", wood1="#d9d2bc", woodLine="#8a8266",
                   back0="#eef7fd", back1="#cfe4f3", glow="#ffffff"),
}[SEASON]


def tone(c, p):
    """A colour put through the theme's tone curves (toneR/G/B, as the picture's feComponentTransfer tables), so
    what's painted around the picture darkens with it on the dark theme."""
    def curve(v, table):
        t = [float(x) for x in table.split()]
        x = v / 255 * (len(t) - 1)
        i = min(int(x), len(t) - 2)
        return t[i] + (t[i + 1] - t[i]) * (x - i)
    return "#" + "".join(f"{round(255 * curve(v, p[k])):02x}" for v, k in zip(rgb(c), ("toneR", "toneG", "toneB")))
WORKS_M = 22               # the card's margin round the bookcase


def bookcase(p, d, rows, light=""):
    """The bookcase itself, drawn at the origin: rows of bunkobon standing face out, seen square on from in front of
    its middle (DEPTH), so each shelf shows its walls, and its floor or ceiling, in perspective.  `light` is laid
    over the inside of each shelf, behind the books.  Returns (defs, body, width, height)."""
    vols = d["works"]
    cw, ch = COVER_W, COVER_H
    cols = max(2, max(len(r) for r in rows))
    gap, pad, side, crown, plinth, board, head = 14, 16, 22, 22, 16, 22, 32
    W = cols * cw + (cols - 1) * gap + 2 * (pad + side)
    tier = head + ch + board
    H = crown + len(rows) * tier + plinth
    ex, ey = W / 2, H / 2

    def back(x, y, k=DEPTH):     # a point on the front plane, moved back into the case until it shrinks by k
        return ex + (x - ex) * k, ey + (y - ey) * k

    at = 1 - .3 * (1 - DEPTH)    # the books stand a third of the way back
    wood1, b0, b1 = p["wood1"], p["back0"], p["back1"]
    clips, body = [], []
    for t, row in enumerate(rows):
        x0, x1, y0, yf = side, W - side, crown + t * tier, crown + t * tier + head + ch
        (bx0, by0), (bx1, byf) = back(x0, y0), back(x1, yf)
        # inside the opening: the back panel, then the ceiling, floor and walls running back to it
        # warm under-shelf recessed spotlight wash in center of each shelf
        spot_w = (bx1 - bx0) * 0.72
        spotlight = (f'<ellipse cx="{(bx0 + bx1) / 2:.1f}" cy="{by0 + 2:.1f}" rx="{spot_w / 2:.1f}" ry="42" '
                     f'fill="url(#caseGlow)" opacity=".6"/>')
        # inside the opening: the back panel, then the ceiling, floor and walls running back to it
        inner = (f'<rect x="{bx0:.1f}" y="{by0:.1f}" width="{bx1 - bx0:.1f}" height="{byf - by0:.1f}" fill="url(#back)"/>'
                 f'{spotlight}'
                 f'<rect x="{bx0:.1f}" y="{by0:.1f}" width="{bx1 - bx0:.1f}" height="40" fill="url(#under)"/>'
                 f'<path d="{poly((x0, y0), (x1, y0), (bx1, by0), (bx0, by0))}" fill="{mix(b1, "#000", .35)}"/>'
                 f'<path d="{poly((x0, yf), (x1, yf), (bx1, byf), (bx0, byf))}" fill="url(#floor)"/>'
                 f'<path d="{poly((x0, y0), (bx0, by0), (bx0, byf), (x0, yf))}" fill="{mix(b1, "#000", .2)}"/>'
                 f'<path d="{poly((x1, y0), (bx1, by0), (bx1, byf), (x1, yf))}" fill="{mix(b0, "#fff", .06)}"/>'
                 # Brass shelf pins / brackets inside the left & right sidewalls
                 f'<rect x="{bx0 - 3:.1f}" y="{byf - 7:.1f}" width="5" height="3.5" rx="1" fill="url(#metal)" opacity=".75"/>'
                 f'<rect x="{bx1 - 2:.1f}" y="{byf - 7:.1f}" width="5" height="3.5" rx="1" fill="url(#metal)" opacity=".75"/>'
                 f'<path d="M{x0},{y0} L{bx0:.1f},{by0:.1f} L{bx1:.1f},{by0:.1f} L{x1},{y0} M{x0},{yf} L{bx0:.1f},{byf:.1f} L{bx1:.1f},{byf:.1f} L{x1},{yf} '
                 f'M{bx0:.1f},{by0:.1f} V{byf:.1f} M{bx1:.1f},{by0:.1f} V{byf:.1f}" fill="none" stroke="#000" stroke-opacity=".18"/>')
        n = len(row)
        x = W / 2 - (n * cw + (n - 1) * gap) / 2
        shadows, books = [], []
        for k, v in enumerate(row):
            i = sum(len(r) for r in rows[:t]) + k
            twins = sum(1 for u in vols[:i] if u["lang"] == v["lang"])
            number = 1 + sum(1 for u in vols[:i] if u["owner"] == v["owner"])
            clip, art = cover(p, i, v, d["today"], .14 * twins, number, i + t)   # each shelf starts one obi colour on
            clips.append(clip)
            bx, by = back(x, yf - ch, at)                      # the book, set back a little from the shelf's edge
            # its shadow on the back panel, down and to the right of the light, and where it meets the shelf
            sx, sy = back(x, yf - ch)
            shadows.append(f'<rect x="{sx + 4:.1f}" y="{sy + 4:.1f}" width="{cw * DEPTH:.1f}" height="{ch * DEPTH - 4:.1f}" rx="3"/>'
                           f'<ellipse cx="{bx + cw * at / 2:.1f}" cy="{by + ch * at + 1:.1f}" rx="{cw * at * .48:.1f}" ry="4.5" fill="#000" opacity=".35"/>')
            # Book display ledge (small wooden lip holding the book face-out)
            lip_w = cw * at + 12
            lip_x = bx - 6
            lip_y = by + ch * at - 4
            book_stand = (f'<path d="M{lip_x:.1f},{lip_y + 4:.1f} L{lip_x + 3:.1f},{lip_y:.1f} L{lip_x + lip_w - 3:.1f},{lip_y:.1f} L{lip_x + lip_w:.1f},{lip_y + 4:.1f} Z" '
                          f'fill="url(#wood)" opacity=".9"/>'
                          f'<line x1="{lip_x + 3:.1f}" y1="{lip_y:.1f}" x2="{lip_x + lip_w - 3:.1f}" y2="{lip_y:.1f}" stroke="#fff" stroke-width=".8" opacity=".35"/>')

            # Natural display pose: slight rotational ease depending on column position
            tilt = -1.2 if (k == 0 and n > 1) else (1.2 if (k == n - 1 and n > 1) else 0)
            tilt_tf = f' transform="rotate({tilt} {cw / 2} {ch})"' if tilt else ""

            books.append(f'<g transform="translate({bx:.1f} {by:.1f}) scale({at:.4f})">{book_stand}'
                         f'<g class="cv" style="animation-delay:{.2 + i * .15:.2f}s"{tilt_tf}>{art}</g></g>')
            x += cw + gap
        if not vols and t == 0:
            books.append(f'<text x="{W / 2}" y="{yf - ch / 2:.0f}" text-anchor="middle" class="h" font-size="28" '
                         f'fill="{p["muted"]}">nothing pinned yet</text>')
        landed = .2 + (sum(len(r) for r in rows[:t]) + n) * .15 + .6
        clips.append(f'<clipPath id="tier{t}"><rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{yf - y0}"/></clipPath>')
        body.append(f'<g clip-path="url(#tier{t})">{inner}'
                    f'<g class="late" style="animation-delay:{landed:.2f}s"><g fill="#000" opacity=".28" filter="url(#wshade)">{"".join(shadows)}</g></g></g>'
                    + "".join(books)
                    # the shelf's front edge with bevel and wood grain
                    + f'<rect x="{x0}" y="{yf}" width="{x1 - x0}" height="{board}" fill="url(#wood)"/>'
                    f'<rect x="{x0}" y="{yf}" width="{x1 - x0}" height="1.4" fill="#fff" opacity=".35"/>'
                    f'<rect x="{x0}" y="{yf + board - 1.2:.1f}" width="{x1 - x0}" height="1.2" fill="#000" opacity=".3"/>'
                    f'<path d="M{x0},{yf + board * .45:.1f} C{W * .35:.0f},{yf + board * .45 - 1.5:.1f} {W * .6:.0f},{yf + board * .45 + 2:.1f} {x1},{yf + board * .45:.1f}" '
                    f'fill="none" stroke="{p["woodLine"]}" stroke-opacity=".25" stroke-width=".8"/>'
                    # Brass brackets under the shelf ends
                    f'<path d="M{x0},{yf + board} L{x0 + 8},{yf + board} L{x0},{yf + board + 8} Z" fill="url(#metal)" opacity=".8"/>'
                    f'<path d="M{x1},{yf + board} L{x1 - 8},{yf + board} L{x1},{yf + board + 8} Z" fill="url(#metal)" opacity=".8"/>')
    # Classical architectural cabinetry: fluted pilasters on posts, stepped crown molding at top
    post_w = side
    flute_l = "".join(f'<line x1="{side * frac:.1f}" y1="{crown + 8}" x2="{side * frac:.1f}" y2="{H - plinth - 8}" stroke="{p["woodLine"]}" stroke-width="1.2" stroke-opacity=".32"/>'
                      for frac in (0.32, 0.5, 0.68))
    flute_r = "".join(f'<line x1="{W - side + side * frac:.1f}" y1="{crown + 8}" x2="{W - side + side * frac:.1f}" y2="{H - plinth - 8}" stroke="{p["woodLine"]}" stroke-width="1.2" stroke-opacity=".32"/>'
                      for frac in (0.32, 0.5, 0.68))
    crown_molding = (
        f'<rect x="-4" y="-3" width="{W + 8}" height="5" rx="1.5" fill="url(#wood)"/>'
        f'<rect x="-4" y="-3" width="{W + 8}" height="1.2" fill="#fff" opacity=".4"/>'
        f'<rect x="-2" y="2" width="{W + 4}" height="4" fill="url(#wood)"/>'
        f'<rect y="6" width="{W}" height="{crown - 6}" fill="url(#wood)"/>'
        f'<line x1="0" y1="{crown}" x2="{W}" y2="{crown}" stroke="{p["woodLine"]}" stroke-width="1" stroke-opacity=".4"/>'
    )
    plinth_base = (
        f'<rect x="-3" y="{H - plinth}" width="{W + 6}" height="{plinth}" rx="1" fill="{mix(wood1, "#000", .15)}"/>'
        f'<line x1="-3" y1="{H - plinth}" x2="{W + 3}" y2="{H - plinth}" stroke="#fff" stroke-width="1" stroke-opacity=".25"/>'
        f'<line x1="-3" y1="{H - plinth + 3}" x2="{W + 3}" y2="{H - plinth + 3}" stroke="#000" stroke-width="1" stroke-opacity=".35"/>'
    )
    frame = (f'<rect width="{post_w}" height="{H}" fill="url(#post)"/>{flute_l}'
             f'<rect x="{W - post_w}" width="{post_w}" height="{H}" fill="url(#post)"/>{flute_r}'
             f'{crown_molding}'
             f'{plinth_base}'
             f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="2" fill="none" stroke="{p["woodLine"]}" stroke-opacity=".5"/>')
    return "".join(clips), "".join(body) + frame, W, H


def works_card(theme, d):
    """Chapter ii: Tooko with a book in her arms (works.jpg: under the golden tree in autumn, crouched in the snow
    in winter, under new leaves in spring, against the sky in summer), fading into a two-shelf bookcase of the pinned repositories as bunkobon - the top shelf takes the odd
    one, and the case is two or three books wide - with leaves, petals or snow drifting down across both.  The books keep their full size, so their
    print stays legible."""
    p = dict(PAL[theme], **PAL[theme].get("worksTone", {}))
    vols = d["works"]
    half = (len(vols) + 1) // 2
    rows = [vols[:half], vols[half:]]
    dark = theme == "dark"
    # a palette with a dusk curve (worksTone: autumn's dark theme) gets a night page like the cards around it: the
    # picture fades into the page's own dark, and the bookcase is the bookshelf card's dark wood
    night = "worksTone" in PAL[theme]
    # otherwise the bookcase is made of the same light as the picture (honey-coloured wood and a pale gold back in
    # autumn, frosted blue in winter), toned with it
    pw = p if night else dict(p, **{k: tone(WORKS[k], p) for k in ("wood0", "wood1", "woodLine", "back0", "back1")})
    rnd = random.Random(21)
    # clean and serene interior without muddy dappled shade
    light = ""
    case_defs, case, cw, chh = bookcase(pw, d, rows, light)
    W, M = WORKS_W, WORKS_M
    H = chh + 2 * M
    cx, cy = W - M - cw, M
    IW = cx + WORKS_TUCK         # works.jpg (930x1092), pinned to the top left and cut to fill up to the bookcase
    petals = []
    # leaves drifting from the tree (or blossom, or snow), down and to the right, across the bookcase; none in summer
    for k in range(0 if SEASON == "summer" else 7):
        x0, dur = rnd.uniform(-40, W * .55), rnd.uniform(14, 22)
        beg, s, spin = -rnd.uniform(0, dur), rnd.uniform(1.6, 2.6), rnd.uniform(0, 360)
        petals.append(f'<g opacity="{rnd.uniform(.55, .85):.2f}"><animateTransform attributeName="transform" type="translate" '
                      f'values="{x0:.0f} -20;{x0 + W * .22:.0f} {H * .5:.0f};{x0 + W * .45:.0f} {H + 20}" dur="{dur:.1f}s" begin="{beg:.1f}s" repeatCount="indefinite"/>'
                      f'<{DRIFT[0]} {DRIFT[1]} transform="translate(1 2) scale({s * DRIFT_K:.2f})" fill="{WORKS["petalShade"]}" opacity=".25">'
                      f'<animateTransform attributeName="transform" type="rotate" values="{spin:.0f};{spin + 220:.0f};{spin + 360:.0f}" additive="sum" '
                      f'dur="{dur:.1f}s" begin="{beg:.1f}s" repeatCount="indefinite"/></{DRIFT[0]}>'
                      f'<{DRIFT[0]} {DRIFT[1]} transform="scale({s * DRIFT_K:.2f})" fill="{drift_color(k, WORKS.get("petal"))}">'
                      f'<animateTransform attributeName="transform" type="rotate" values="{spin:.0f};{spin + 220:.0f};{spin + 360:.0f}" additive="sum" '
                      f'dur="{dur:.1f}s" begin="{beg:.1f}s" repeatCount="indefinite"/></{DRIFT[0]}></g>')
    css = (fontface("caveat") + ".h{font-family:'Caveat',cursive;font-weight:600}"
           "@keyframes up{from{opacity:0;transform:translateY(28px)}to{opacity:1;transform:none}}"
           ".cv{animation:up .8s cubic-bezier(.3,.7,.4,1) both}"
           "@keyframes late{from{opacity:0}to{opacity:1}}.late{animation:late .8s ease both}")
    label = esc(f"works in progress: Tooko holding a book beside a bookcase of {len(vols)} pinned repositories: "
                f"{', '.join(v['name'] for v in vols) or 'none yet'}")
    wood0, wood1, b0, b1 = pw["wood0"], pw["wood1"], pw["back0"], pw["back1"]
    gold = [p["pbg0"], p["pbg1"], p["pbg2"]] if night else [tone(c, p) for c in WORKS["bg"]]
    glow = tone(WORKS["glow"], p)
    # the picture's light on the card around it and on the bookcase's near side: at night only a trace of it
    glow_o, haze = (' opacity=".25"', "") if night else ("", f'<rect x="-10" width="120" height="{chh}" fill="url(#haze)"/>')
    # the tree's light: shafts of sun from the upper left, across the picture and the card behind the bookcase
    sun_defs, sun = light_rays("sunW", 80, W - 80, H, dark, seed=5, count=5)
    fog, wrap = "", ("", "")
    if SEASON == "summer":
        # no tree to shade her: the sun itself, in the lens - the hero's big breathing halos, clear of her face, brighter to show
        # against the sky, and in the dark theme's glow on both pages (this card is painted in its picture's blue, whatever the page)
        sun_defs, sun = halo("sunW", [(150, 150, 190, True), (cx - 70, 330, 150, True), (110, 520, 110, False),
                                      (cx - 150, 640, 90, False), (470, 60, 70, False)], True, strength=1.6)
    if SEASON == "spring":
        # she stands under the leaves themselves: their light, in the dark theme's glow on both pages and brighter
        # (this card is painted in its picture's green, whatever the page)
        sun_defs, sun = leaf_light("leafW", W, H, True, seed=5, strength=2)
    if SEASON == "winter":       # no low sun in winter: now and then the whole card mists over like a cold pane
        sun_defs, fog = mist("mistW", "wall", W, H, dark, seed=6, delay=-15)
        sun, wrap = "", ('<g id="wall">', "</g>")

    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{label}">'
            + f'<defs><style><![CDATA[{CSS}{css}]]></style>{case_defs}{DRIFT_DEF}'
            f'<clipPath id="wcard"><rect width="{W}" height="{H}" rx="16"/></clipPath>'
            f'<linearGradient id="wbg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{gold[0]}"/>'
            f'<stop offset=".5" stop-color="{gold[1]}"/><stop offset="1" stop-color="{gold[2]}"/></linearGradient>'
            f'<filter id="wglow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="45"/></filter>'
            f'<filter id="dapple" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>'
            f'<linearGradient id="haze" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{glow}" stop-opacity=".55"/>'
            f'<stop offset="1" stop-color="{glow}" stop-opacity="0"/></linearGradient>{sun_defs}'
            f'<linearGradient id="wfade" gradientUnits="userSpaceOnUse" x1="{IW - 220}" y1="0" x2="{IW}" y2="0">{smooth_fade()}</linearGradient>'
            f'<mask id="wmask"><rect width="{IW}" height="{H}" fill="url(#wfade)"/></mask>'
            f'<filter id="wtint" color-interpolation-filters="sRGB"><feComponentTransfer><feFuncR type="table" tableValues="{p["toneR"]}"/>'
            f'<feFuncG type="table" tableValues="{p["toneG"]}"/><feFuncB type="table" tableValues="{p["toneB"]}"/></feComponentTransfer></filter>'

            f'<filter id="caseShade" x="-10%" y="-10%" width="120%" height="130%"><feGaussianBlur stdDeviation="9"/></filter>'
            f'<linearGradient id="board" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".12"/>'
            f'<stop offset=".45" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".14"/></linearGradient>'
            # watercolour: ragged, bleeding edges; and the jacket paper's grain
            f'<filter id="wash" x="-30%" y="-30%" width="160%" height="160%"><feTurbulence type="fractalNoise" baseFrequency=".035" numOctaves="3" seed="4"/>'
            f'<feDisplacementMap in="SourceGraphic" scale="30" xChannelSelector="R" yChannelSelector="G"/><feGaussianBlur stdDeviation="3"/></filter>'
            f'<filter id="paperG" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" stitchTiles="stitch"/>'
            f'<feColorMatrix type="saturate" values="0"/></filter>'
            f'<linearGradient id="glint" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            f'<stop offset=".5" stop-color="#fff" stop-opacity="{p["glintO"]}"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
            f'<linearGradient id="wood" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{wood0}"/><stop offset="1" stop-color="{wood1}"/></linearGradient>'
            f'<linearGradient id="post" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{wood1}"/><stop offset=".5" stop-color="{wood0}"/>'
            f'<stop offset="1" stop-color="{wood1}"/></linearGradient>'
            f'<linearGradient id="floor" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{mix(wood0, "#fff", .1)}"/><stop offset="1" stop-color="{mix(wood1, "#000", .1)}"/></linearGradient>'
            f'<linearGradient id="back" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{b0}"/><stop offset="1" stop-color="{b1}"/></linearGradient>'
            f'<linearGradient id="under" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000" stop-opacity=".45"/><stop offset="1" stop-color="#000" stop-opacity="0"/></linearGradient>'
            f'<radialGradient id="caseGlow" cx="50%" cy="0%" r="90%"><stop offset="0" stop-color="{glow}" stop-opacity=".36"/>'
            f'<stop offset=".5" stop-color="{glow}" stop-opacity=".12"/><stop offset="1" stop-color="{glow}" stop-opacity="0"/></radialGradient>'
            f'<linearGradient id="metal" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{p.get("metal0", "#8a826c")}"/><stop offset="1" stop-color="{p.get("metal1", "#4a453a")}"/></linearGradient>'
            f'<filter id="wshade" x="-20%" y="-10%" width="140%" height="120%"><feGaussianBlur stdDeviation="5"/></filter></defs>'
            + f'<g clip-path="url(#wcard)">{wrap[0]}'
            # the tree's light, all across the card: its colours, and soft patches of sun through the leaves
            f'<rect width="{W}" height="{H}" fill="url(#wbg)"/>'
            f'<g fill="{glow}" filter="url(#wglow)"{glow_o}><ellipse cx="{W * .62:.0f}" cy="{H * .18:.0f}" rx="260" ry="150" opacity=".55"/>'
            f'<ellipse cx="{W * .95:.0f}" cy="{H * .55:.0f}" rx="200" ry="260" opacity=".4"/>'
            f'<ellipse cx="{W * .7:.0f}" cy="{H * .95:.0f}" rx="320" ry="120" opacity=".45"/></g>'
            f'<image href="data:image/jpeg;base64,{WORKS_IMG}" width="{IW}" height="{H}" preserveAspectRatio="xMinYMin slice" mask="url(#wmask)" filter="url(#wtint)"/>'
            + sun +   # behind the bookcase, so the light never dims the books' print
            f'<rect x="{cx + 8}" y="{cy + 12}" width="{cw}" height="{chh}" fill="#000" opacity=".35" filter="url(#caseShade)"/>'
            f'<g transform="translate({cx} {cy})">{case}{haze}</g>'
            + '<g class="mo">' + "".join(petals) + f"</g>{wrap[1]}{fog}</g>"
            f'<rect x="0.75" y="0.75" width="{W - 1.5}" height="{H - 1.5}" rx="16" fill="none" stroke="{p["border"]}" stroke-width="1.5"/></svg>')


def snake_card(theme, raw):
    """The contributions card: snk's svg nested in a card like the others, scaled up to 16px cells on a 20px pitch.
    In a book the snake is a bookworm, eating its way through the year's pages, so that is what the card is called.
    No numbers in the header: the stats panel already gives the all-time total and the active days, and a 12-month
    total beside it never quite agrees.  Under the year, snk's bar of pages eaten starts each loop empty, so it gets
    a track in the colour of an uneaten page, or the band reads as left blank.
    Only fonts and .t/.m go in the style block; snk's own css uses .c/.s/.u."""
    p = PAL[theme]
    W, H = 1200, 300
    vb = re.search(r'viewBox="([^"]+)"', raw).group(1)
    vx, vy, vw, vh = map(float, vb.split())
    inner = raw[raw.index(">", raw.index("<svg")) + 1:raw.rindex("</svg>")]
    for autumn, mine in zip(AUTUMN[theme]["snake"], p["snake"]):   # snk was asked for autumn's colours
        inner = inner.replace(autumn, mine)
    wash = frost = ""
    if SEASON == "winter":       # frost builds up round the bookworm's year
        ice_defs, wash, frost = ice("iceN", W, H, theme == "dark", seed=3)
        wash = (f'<defs>{ice_defs}<clipPath id="iceNC"><rect x="0.75" y="0.75" width="{W-1.5}" height="{H-1.5}" rx="16"/></clipPath></defs>'
                f'<g clip-path="url(#iceNC)">{wash}</g>')
        frost = f'<g clip-path="url(#iceNC)">{frost}</g>'
    scale = 20 / 16               # snk: 12px cells on a 16px pitch
    gx, gy = 48, 78               # top-left of the grid
    css = (fontface("outfit") + fontface("jbmono") +
           ".t{font-family:'Outfit',sans-serif;font-weight:800}"
           ".m{font-family:'JetBrains Mono',monospace;font-weight:500}" + CALM)
    head = (f'<g transform="translate(58 34)" fill="{p["accent"]}">{ICON["star"]}</g>'
            f'<text x="76" y="40" class="t" font-size="19" fill="url(#tgN)">the bookworm</text>'
            f'<text x="{W-gx}" y="40" class="m" font-size="{SMALL}" text-anchor="end" fill="{p["label"]}">last 12 months</text>')
    bar = re.search(r'<rect class="u [^>]*?height="([\d.]+)"[^>]*?y="([\d.]+)"', inner)   # the first piece of snk's bar
    track = (f'<rect x="0" y="{bar.group(2)}" width="{vw + 2 * vx:g}" height="{bar.group(1)}" fill="{p["snake"][1]}"/>'
             if bar else "")
    grid = f'<svg x="{gx + vx*scale:.1f}" y="{gy + vy*scale:.1f}" width="{vw*scale:.1f}" height="{vh*scale:.1f}" viewBox="{vb}">{track}{inner}</svg>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="contribution snake of {esc(LOGIN)}">'
            f'<defs><style><![CDATA[{css}]]></style>'
            f'<linearGradient id="bgN" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{p["bg0"]}"/><stop offset="1" stop-color="{p["bg1"]}"/></linearGradient>'
            f'<linearGradient id="tgN" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{p["grad0"]}"/><stop offset="1" stop-color="{p["grad1"]}"/></linearGradient>'
            f'</defs>'
            f'<rect x="0.75" y="0.75" width="{W-1.5}" height="{H-1.5}" rx="16" fill="url(#bgN)" stroke="{p["border"]}" stroke-width="1.5"/>'
            # frost lies on the pane: over the year's cells (the glass's blue behind them), under the print
            + (wash + grid + frost + head if frost else head + grid) + '</svg>')


def colophon_card(theme, d):
    """The colophon, on the last page as in any book: which edition this is and when it was printed (the workflow's
    run number, and github's today), what it is set in and who bound it.  No frame: it is print on the page."""
    p = PAL[theme]
    W, H = 1200, 112
    t = d["today"]
    printed = f"printed {t.strftime('%b').lower()} {t.day}, {t.year}"
    line = f"Edition no. {EDITION}, {printed}" if EDITION else printed.capitalize()
    css = (fontface("caveat") + fontface("jbmono") + ".h{font-family:'Caveat',cursive;font-weight:600}"
           ".m{font-family:'JetBrains Mono',monospace;font-weight:500}")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="colophon: {esc(line)}">'
            f'<defs><style><![CDATA[{css}]]></style></defs>'
            f'<g transform="translate({W / 2:.0f} 16)"><path d="{star_path(6)}" fill="{p["accent"]}"/></g>'
            f'<text x="{W / 2:.0f}" y="62" text-anchor="middle" class="h" font-size="34" fill="{p["title"]}">{esc(line)}</text>'
            f'<text x="{W / 2:.0f}" y="94" text-anchor="middle" class="m" font-size="{SMALL + 1}" letter-spacing="1" fill="{p["muted"]}">'
            f'set in Outfit, Caveat &amp; JetBrains Mono · bound daily by GitHub Actions</text></svg>')


def wrap_snake():
    for theme in ("dark", "light"):
        path = os.path.join(OUT, f"snake-{theme}.svg")
        if not os.path.exists(path):
            print(f"no {path} (Platane/snk runs first in Actions); contributions card skipped")
            continue
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        if 'aria-label="contribution snake of' in raw:
            continue
        write_svg(path, punch(snake_card(theme, raw), theme == "dark"))
        print(f"framed {path} ({os.path.getsize(path)//1024} KB)")


def main():
    os.makedirs(OUT, exist_ok=True)
    d = collect()
    wrap_snake()
    for theme in ("dark", "light"):
        for name, fn in (("stats", stats_panel), ("shelf", shelf_card), ("toc", toc_card), ("works", works_card),
                         ("colophon", colophon_card)):
            path = os.path.join(OUT, f"{name}-{theme}.svg")
            svg = fn(theme, d)
            # a book page with a curled corner, a bookcase, and print on the last page: no binder holes
            if name not in ("toc", "works", "colophon"):
                # the shelf's holes go down the right edge, past the vase, so the row of books starts on a clean edge
                svg = punch(svg, theme == "dark", side="right" if name == "shelf" else "left")
            write_svg(path, svg)
            print(f"wrote {path} ({os.path.getsize(path)//1024} KB)")
    print(json.dumps(d, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
