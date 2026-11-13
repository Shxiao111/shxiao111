"""Long-lived regressions owned by the card generator: calendar streak semantics, and a smoke test that every card
renders to well-formed svg from canned API responses, so a rendering bug fails CI instead of the daily run."""
import contextlib
import datetime as dt
import io
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

import gen_cards
from common import SEASON, SEASONS, season_of
from gen_cards import streaks
from paper import punch

TODAY = dt.date(2026, 9, 23)


def fake_gql(repos, commits, pinned=()):
    """A stand-in for gen_cards.gql answering the three queries collect() makes; repos come back 2 per page."""
    days = [TODAY - dt.timedelta(days=370 - i) for i in range(371)]
    calendar = {"weeks": [{"contributionDays": [{"date": d.isoformat(), "contributionCount": i % 3}
                                                for i, d in enumerate(days[w:w + 7], w)]}
                          for w in range(0, len(days), 7)]}

    def gql(query, variables):
        if query is gen_cards.REPOS_QUERY:
            start = int(variables["after"] or 0)
            return {"user": {"repositories": {"totalCount": len(repos), "nodes": repos[start:start + 2],
                                              "pageInfo": {"hasNextPage": start + 2 < len(repos), "endCursor": str(start + 2)}}}}
        if query is gen_cards.QUERY:
            return {"prs": {"issueCount": 3}, "issues": {"issueCount": 1}, "user": {"contributionsCollection": {
                "commitContributionsByRepository": commits, "contributionCalendar": calendar},
                "pinnedItems": {"nodes": list(pinned)}}}
        if query is gen_cards.YEARS_QUERY:
            return {"user": {"contributionsCollection": {"contributionYears": []}}}
        raise AssertionError(query)
    return gql


def repo(name, desc, pushed, langs, stars=0, owner="shxiao111", private=False):
    return {"name": name, "description": desc, "pushedAt": f"{pushed}T00:00:00Z", "stargazerCount": stars,
            "forkCount": 1, "owner": {"login": owner}, "isPrivate": private,
            "languages": {"edges": [{"size": s, "node": {"name": n, "color": c}} for n, s, c in langs]}}


class CardTests(unittest.TestCase):
    """Every card renders, punched or not, for a full profile and for an empty one."""

    def render_all(self, d):
        for theme in ("dark", "light"):
            for fn in (gen_cards.stats_panel, gen_cards.shelf_card, gen_cards.toc_card, gen_cards.works_card):
                with self.subTest(card=fn.__name__, theme=theme):
                    svg = fn(theme, d)
                    ET.fromstring(svg)
                    self.assertIn("prefers-reduced-motion", svg)
                    # where the others have shafts of sun, summer wears the light off the sea (summer.water_light)
                    # on the panel and the shelf, and the hero's halos on the works card
                    self.assertEqual('<filter id="sea' in svg, SEASON == "summer" and fn in (gen_cards.stats_panel, gen_cards.shelf_card))
                    self.assertEqual('<radialGradient id="sunWGlow"' in svg, SEASON == "summer" and fn is gen_cards.works_card)
                    self.assertFalse(SEASON == "summer" and 'Soft"' in svg)
                    ET.fromstring(punch(svg, theme == "dark"))

    def test_full_profile(self):
        repos = [repo("shxiao111", "profile", "2026-09-20", [("Python", 900, "#3572A5")], 3),
                 repo("tool", "a <small> & sharp tool", "2026-09-01", [("Rust", 5000, "#dea584"), ("Shell", 50, None)], 5),
                 repo("notes", None, "2025-03-02", [("Jupyter Notebook", 3000, None)]),
                 repo("x" * 80, "  spaced \n out  ", "2026-01-01", [("TypeScript", 800, "#3178c6"), ("Vue", 200, "#41b883")]),
                 repo("empty", None, "2024-05-05", [])]
        commits = [{"repository": repo("tool", None, "2026-09-01", [("Shell", 9000, None), ("Rust", 5000, "#dea584")]),
                    "contributions": {"totalCount": 7}},
                   {"repository": repo("secret", None, "2026-09-01", [], private=True), "contributions": {"totalCount": 100}}]
        with mock.patch.object(gen_cards, "gql", fake_gql(repos, commits)):
            d = gen_cards.collect()
        self.assertEqual(d["repos"], 5)
        self.assertEqual(d["stars"], 8)
        self.assertEqual(d["commits"], 7)
        # the shelf holds what was committed to, private work left out, each set in its main language's cloth
        self.assertEqual(d["shelf"], [{"name": "tool", "commits": 7, "lang": "Rust", "color": "#dea584"}])
        self.assertEqual((d["prs"], d["issues"]), (3, 1))
        self.assertEqual([r["name"] for r in d["own"]][:2], ["tool", "x" * 80])
        self.assertEqual(d["works"], [])   # nothing pinned: an empty bookcase
        self.assertIn(">stars<", gen_cards.stats_panel("dark", d))
        self.assertNotIn(">stars<", gen_cards.stats_panel("dark", dict(d, stars=0)))   # a zero is left out
        self.render_all(d)

    def test_pinned(self):
        """Pinned repositories fill the bookcase in pinned order, someone else's included, private ones left out."""
        pinned = [repo("byrdocs-web", "the <BYR> Docs site " * 6, "2026-09-10", [("Vue", 9, "#41b883")], 40, owner="byrdocs"),
                  repo("secret", "hidden", "2026-09-10", [], private=True),
                  repo("MyVeryLongCamelCaseRepositoryNameThatKeepsGoing", None, "2024-01-01", [("Shell", 5, None)]),
                  None]
        with mock.patch.object(gen_cards, "gql", fake_gql([], [], pinned)):
            d = gen_cards.collect()
        self.assertEqual([(v["name"], v["owner"]) for v in d["works"]],
                         [("byrdocs-web", "byrdocs"), ("MyVeryLongCamelCaseRepositoryNameThatKeepsGoing", "shxiao111")])
        self.assertEqual(d["works"][1]["lang"], "")   # Shell alone doesn't colour a cover
        self.render_all(d)

    def test_bookcase_shelves(self):
        """The bookcase always has two shelves, the top one taking the odd volume; the card keeps the other cards'
        width and its height, however many are pinned."""
        with mock.patch.object(gen_cards, "gql", fake_gql([], [], [])):
            d = gen_cards.collect()
        vol = gen_cards.volume(repo("v", "a volume", "2026-09-20", [("Rust", 5, "#dea584")], 12))
        heights = {}
        for n in range(7):
            d["works"] = [dict(vol, name=f"v{k}") for k in range(n)]
            svg = gen_cards.works_card("dark", d)
            ET.fromstring(svg)
            heights[n] = svg.split('height="', 1)[1].split('"', 1)[0]
            self.assertEqual(svg.count('class="cv"'), n)
            self.assertIn('viewBox="0 0 1200 ', svg)
        self.assertEqual(len(set(heights.values())), 1)

    def test_wrap_blurb(self):
        """Blurbs break between words, or anywhere in CJK text, and every line fits."""
        self.assertEqual(gen_cards.wrap_blurb("  a  quiet   story ", 10.5, 162), ["a quiet story"])
        text = "北京邮电大学生存指南，从沙河到西土城，从入学到毕业的全方位攻略 with some English words"
        lines = gen_cards.wrap_blurb(text, 10.5, 162)
        self.assertGreater(len(lines), 2)
        self.assertEqual("".join(lines).replace(" ", ""), text.replace(" ", ""))
        self.assertTrue(all(gen_cards.text_width("jbmono", ln, 10.5) <= 162 for ln in lines))
        long = gen_cards.wrap_blurb("Modern protocol-side framework implementation", 16, 108)
        self.assertEqual("".join(long).replace(" ", ""), "Modernprotocol-sideframeworkimplementation")
        self.assertTrue(all(gen_cards.text_width("jbmono", ln, 16) <= 108 for ln in long))

    def test_title_lines(self):
        """Titles break after separators or between camelCase words, and always fit."""
        self.assertEqual(gen_cards.title_lines("notes", 132, 67), (26, ["notes"]))
        size, lines = gen_cards.title_lines("byrdocs-web-frontend", 132, 67)
        self.assertEqual("".join(lines), "byrdocs-web-frontend")
        self.assertTrue(all(ln.endswith("-") for ln in lines[:-1]))
        for name in ("MyVeryLongCamelCaseRepositoryNameThatKeepsGoing", "x" * 80):
            size, lines = gen_cards.title_lines(name, 132, 67)
            self.assertLessEqual(len(lines), 3)
            self.assertTrue(all(gen_cards.text_width("outfit", ln, size) <= 132 for ln in lines))
            self.assertLessEqual((len(lines) - 1) * size * gen_cards.LEAD + size * gen_cards.CAP, 67)

    def test_empty_profile(self):
        with mock.patch.object(gen_cards, "gql", fake_gql([], [])):
            d = gen_cards.collect()
        self.assertEqual((d["repos"], d["commits"], d["shelf"], d["own"]), (0, 0, [], []))
        self.render_all(d)

    def test_snake(self):
        """snk's svgs are framed as the contributions card once, a second run leaves them alone, and a missing
        one (a local run without snk) is skipped."""
        raw = ('<svg viewBox="-16 -32 880 192" width="880" height="192" xmlns="http://www.w3.org/2000/svg">'
               '<style>:root{--c1:#5c2a16}.c{fill:red}</style><rect class="c" x="0" y="0" width="12" height="12"/></svg>')
        with tempfile.TemporaryDirectory() as out, mock.patch.object(gen_cards, "OUT", out), \
                contextlib.redirect_stdout(io.StringIO()):
            path = os.path.join(out, "snake-dark.svg")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(raw)
            gen_cards.wrap_snake({"active_days": 42})
            with open(path, encoding="utf-8") as fh:
                framed = fh.read()
            gen_cards.wrap_snake({"active_days": 42})
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), framed)
            self.assertFalse(os.path.exists(os.path.join(out, "snake-light.svg")))
        ET.fromstring(framed)
        self.assertIn(">the bookworm<", framed)
        # snk is asked for autumn's colours (cards.yml); the card wears the season's
        self.assertIn(f"--c1:{gen_cards.PAL['dark']['snake'][2]}", framed)
        self.assertIn("42 active days · last 12 months", framed)

    def test_season_follows_the_calendar(self):
        self.assertEqual([season_of(m) for m in (1, 4, 7, 10, 12)], ["winter", "spring", "summer", "autumn", "winter"])
        self.assertLessEqual({season_of(m) for m in range(1, 13)}, set(SEASONS))   # every month has a drawn theme

    @unittest.skipIf(os.environ.get("SEASON_RERUN"), "already inside a season's own run")
    def test_other_seasons(self):
        """The season is fixed at import (common.SEASON), so each season not in wear gets a run of its own: these
        tests again, and gen_hero's pages, which CI otherwise only builds for the season in wear."""
        here = os.path.dirname(os.path.abspath(__file__))
        pages = ("import xml.etree.ElementTree as ET, gen_hero as g\n"
                 "for t in ('dark', 'light'):\n"
                 "    for svg in (g.hero(t), g.footer(t), g.chapter(t, g.CHAPTERS[0])): ET.fromstring(svg)")
        for season in SEASONS:
            if season == SEASON:
                continue
            env = dict(os.environ, SEASON=season, SEASON_RERUN="1")
            for cmd in (["-m", "unittest", "test_gen_cards"], ["-c", pages]):
                with self.subTest(season=season, run=cmd[0]):
                    run = subprocess.run([sys.executable, *cmd], cwd=here, env=env, capture_output=True, text=True)
                    self.assertEqual(run.returncode, 0, run.stderr)

    def test_shelf_many_repositories(self):
        """shelf_card handles more than 34 repositories without crashing on empty candidates; the note counts them all."""
        d = {"shelf": [{"name": f"repo-{i}", "commits": 1, "lang": f"L{i}", "color": None} for i in range(40)]}
        for theme in ("dark", "light"):
            svg = gen_cards.shelf_card(theme, d)
            ET.fromstring(svg)
            self.assertIn("40 repositories · 40 commits", svg)

    def test_shelf_sets(self):
        """A set per repository: one that took most of the year's commits doesn't crowd the others off, every set is
        titled, a long name cut short, and a repository with no language of its own is shelved as "other"."""
        shelf = [{"name": "the-big-one", "commits": 400, "lang": "Python", "color": "#3572A5"},
                 {"name": "a-repository-name-far-too-long-for-any-spine", "commits": 9, "lang": "Python", "color": "#3572A5"},
                 {"name": "notes", "commits": 1, "lang": "", "color": None}]
        svg = gen_cards.shelf_card("light", {"shelf": shelf})
        root = ET.fromstring(svg)
        spines = [t.text for t in root.iter("{http://www.w3.org/2000/svg}text") if "rotate(90)" in (t.get("transform") or "")]
        titles = [t for t in spines if not set(t) <= set("IVXL")]   # the rest are volume numbers
        self.assertEqual(titles[0], "the-big-one")
        self.assertTrue(titles[1].startswith("a-repository") and titles[1].endswith("..."))
        self.assertEqual(titles[2], "notes")
        self.assertLess(len(spines) - 3, 30)   # by commits alone the big one would take 33 of the 34 volumes
        self.assertIn(">other<", svg)
        self.assertIn("3 repositories · 410 commits", svg)
        self.assertIn("1 repository ·", gen_cards.shelf_card("dark", {"shelf": shelf[:1]}))

    def test_colophon(self):
        """The colophon gives the edition when the workflow numbers the run, and the day either way."""
        d = {"today": TODAY}
        with mock.patch.object(gen_cards, "EDITION", "57"):
            svg = gen_cards.colophon_card("dark", d)
        ET.fromstring(svg)
        self.assertIn(">Edition no. 57, printed sep 23, 2026<", svg)
        with mock.patch.object(gen_cards, "EDITION", None):
            self.assertIn(">Printed sep 23, 2026<", gen_cards.colophon_card("light", d))

    def test_book_counts(self):
        """Every language gets a volume and the shelf holds exactly 34, even when slivers rounded up to one book
        would overfill it (one language at 97% and five at 0.6%: 32 + 5 floors to 37)."""
        for shares in ([.97] + [.006] * 5, [1 / 6] * 6, [.5, .3, .2], [1.0], [1 / 40] * 34):
            with self.subTest(shares=shares):
                counts = gen_cards.book_counts(shares, 34)
                self.assertEqual(sum(counts), 34)
                self.assertTrue(all(c >= 1 for c in counts))
        self.assertEqual(gen_cards.book_counts([.97] + [.006] * 5, 34), [29, 1, 1, 1, 1, 1])
        self.assertEqual(gen_cards.book_counts([], 34), [])

    def test_shelf_legend_fits(self):
        """Six long language names are cut short rather than run the legend off the card."""
        shelf = [{"name": f"repo-{i}", "commits": 1, "lang": n, "color": None}
                 for i, n in enumerate(("Common Workflow Language", "Jupyter Notebook", "Visual Basic .NET",
                                        "Classic ASP Extended", "TypeScript Definitions", "Rich Text Format"))]
        svg = gen_cards.shelf_card("dark", {"shelf": shelf})
        root = ET.fromstring(svg)
        ns = "{http://www.w3.org/2000/svg}"
        rows = [t for t in root.iter(f"{ns}text") if t.get("y") == str(gen_cards.SHELF_Y + 56)]
        self.assertEqual(len(rows), 6)
        last = rows[-1]
        name, pct = (ts.text for ts in last.iter(f"{ns}tspan"))
        right = (float(last.get("x")) + gen_cards.text_width("jbmono", name, 12)
                 + 7 + gen_cards.text_width("jbmono", pct, 12))
        self.assertLessEqual(right, 1200 - 48)
        self.assertTrue(any(ts.text.endswith("...") for t in rows for ts in t.iter(f"{ns}tspan")))

    def test_main(self):
        """main() writes the ten cards, all well-formed, into OUT."""
        repos = [repo("tool", "a tool", "2026-09-01", [("Rust", 5000, "#dea584"), ("Python", 900, "#3572A5")], 5)]
        with tempfile.TemporaryDirectory() as out, mock.patch.object(gen_cards, "OUT", out),                 mock.patch.object(gen_cards, "gql", fake_gql(repos, [])), contextlib.redirect_stdout(io.StringIO()):
            gen_cards.main()
            names = sorted(os.listdir(out))
            self.assertEqual(names, sorted(f"{n}-{t}.svg" for n in ("stats", "shelf", "toc", "works", "colophon")
                                           for t in ("dark", "light")))
            for n in names:
                with open(os.path.join(out, n), encoding="utf-8") as fh:
                    ET.fromstring(fh.read())

    def test_all_days_chunking(self):
        """all_days chunks multi-year queries into batches of at most chunk_size."""
        queried = []
        def mock_gql(query, variables):
            if query is gen_cards.YEARS_QUERY:
                return {"user": {"contributionsCollection": {"contributionYears": [2024, 2025, 2026]}}}
            queried.append(query)
            user = {}
            for y in [2024, 2025, 2026]:
                if f"y{y}:" in query:
                    user[f"y{y}"] = {"contributionCalendar": {"weeks": [{"contributionDays": [{"date": f"{y}-01-01", "contributionCount": 1}]}]}}
            return {"user": user}
        with mock.patch.object(gen_cards, "gql", mock_gql):
            days = gen_cards.all_days(chunk_size=2)
        self.assertEqual(len(queried), 2)
        self.assertEqual(len(days), 3)


class StreakTests(unittest.TestCase):
    """Keep totals and streak dates correct across gaps and the open current day."""

    def test_streaks(self):
        cases = [
            # name, days, today, current, longest, total
            ("empty", [], "2026-01-02", (0, None, None), (0, None, None), 0),
            ("year boundary", [("2025-12-31", 2), ("2026-01-01", 1)], "2026-01-01",
             (2, "2025-12-31", "2026-01-01"), (2, "2025-12-31", "2026-01-01"), 3),
            ("missing year", [("2024-12-31", 1), ("2026-01-01", 1)], "2026-01-01",
             (1, "2026-01-01", "2026-01-01"), (1, "2024-12-31", "2024-12-31"), 2),
            ("missing day", [("2026-01-01", 1), ("2026-01-03", 1)], "2026-01-03",
             (1, "2026-01-03", "2026-01-03"), (1, "2026-01-01", "2026-01-01"), 2),
            ("open today", [("2026-01-01", 1), ("2026-01-02", 0)], "2026-01-02",
             (1, "2026-01-01", "2026-01-01"), (1, "2026-01-01", "2026-01-01"), 1),
            ("today absent", [("2026-01-01", 1)], "2026-01-02",
             (1, "2026-01-01", "2026-01-01"), (1, "2026-01-01", "2026-01-01"), 1),
            ("stale history", [("2026-01-01", 1)], "2026-01-03",
             (0, None, None), (1, "2026-01-01", "2026-01-01"), 1),
            ("zero yesterday", [("2026-01-01", 1), ("2026-01-02", 0)], "2026-01-03",
             (0, None, None), (1, "2026-01-01", "2026-01-01"), 1),
            ("future ignored", [("2026-01-01", 1), ("2026-01-02", 5)], "2026-01-01",
             (1, "2026-01-01", "2026-01-01"), (1, "2026-01-01", "2026-01-01"), 1),
        ]
        for name, days, today, current, longest, total in cases:
            with self.subTest(name=name):
                result = streaks(days, dt.date.fromisoformat(today))
                for key, expected in (("current", current), ("longest", longest)):
                    actual = tuple(v.isoformat() if isinstance(v, dt.date) else v for v in result[key])
                    self.assertEqual(actual, expected)
                self.assertEqual(result["total"], total)
                first = next((day for day, count in days if count > 0 and day <= today), None)
                self.assertEqual(result["first"], dt.date.fromisoformat(first) if first else None)
