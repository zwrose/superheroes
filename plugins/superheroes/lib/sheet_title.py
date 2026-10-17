#!/usr/bin/env python3
"""Stages a review sheet's page with the artifact title the sheet is published under.

CLI:
  sheet_title.py stage --sheet FILE --project NAME [--slug SLUG] --out FILE

It reads the data file, writes theme/review-template.html to --out with its <title> set to the sheet's
artifact title, prints {"ok": true, "out": ..., "title": ...} and exits 0. On a refusal it writes
nothing, prints {"ok": false, "problems": [...]} (one line each) and exits 1.

The title, by the sheet's kind. <project> is the project's name as its repository names it (the name
part of owner/name):
  pr                       "<project> PR #<number> review sheet", number from prSheet.number
  stack                    "<project> stack PR #<bottom>–#<top> review sheet", from prSheet.prs, bottom PR first
  index                    "<project> open decisions review sheet"
  plain, remainder, final  "<project> <work-item slug> review sheet", the slug from --slug
--slug is required for those three kinds.

Only the page's <title> changes. The data file is read, never written, so the sheet's digest, its
answers and its verdict are the same as for the unchanged template, and the app bar still shows the
data file's own title.
"""
import argparse
import html
import json
import pathlib
import re
import sys

TEMPLATE_PATH = pathlib.Path(__file__).resolve().parents[1] / "theme" / "review-template.html"
_TITLE = re.compile(r"<title>[^<]*</title>")
_SLUG_KINDS = ("plain", "remainder", "final")


class Refusal(Exception):
    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems


def _number(value, where):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise Refusal(["%s is not a PR number" % where])
    return value


def title_for(sheet, project, slug=None):
    """The artifact title of a sheet, from its data file, the project's name and, for a discovery sheet, its slug."""
    if not isinstance(project, str) or not project.strip():
        raise Refusal(["the project name is empty"])
    kind = sheet.get("kind") if isinstance(sheet, dict) else None
    if kind not in ("pr", "stack", "index", *_SLUG_KINDS):
        raise Refusal(["the data file's kind is not a sheet kind: %r" % (kind,)])
    if kind in _SLUG_KINDS and (not isinstance(slug, str) or not slug.strip()):
        raise Refusal(["a %s sheet needs --slug, its work item's slug" % kind])
    pr_sheet = sheet.get("prSheet") if isinstance(sheet.get("prSheet"), dict) else {}
    if kind == "pr":
        return "%s PR #%d review sheet" % (project, _number(pr_sheet.get("number"), "prSheet.number"))
    if kind == "stack":
        prs = pr_sheet.get("prs")
        if not isinstance(prs, list) or len(prs) < 2 or not all(isinstance(pr, dict) for pr in prs):
            raise Refusal(["a stack sheet's prSheet.prs must list at least two PRs"])
        bottom = _number(prs[0].get("number"), "prSheet.prs[0].number")
        top = _number(prs[-1].get("number"), "prSheet.prs[-1].number")
        return "%s stack PR #%d–#%d review sheet" % (project, bottom, top)
    if kind == "index":
        return "%s open decisions review sheet" % project
    return "%s %s review sheet" % (project, slug)


def stage_page(template_text, title):
    """The template's text with its one <title> element set to the given title."""
    if len(_TITLE.findall(template_text)) != 1:
        raise Refusal(["the template does not have exactly one <title> element"])
    return _TITLE.sub(lambda _: "<title>%s</title>" % html.escape(title, quote=False), template_text)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Stage a review sheet's page with its artifact title.")
    parser.add_argument("command", choices=["stage"])
    parser.add_argument("--sheet", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--slug")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        try:
            sheet = json.loads(pathlib.Path(args.sheet).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as err:
            raise Refusal(["cannot read the data file %s: %s" % (args.sheet, err)])
        title = title_for(sheet, args.project, args.slug)
        page = stage_page(TEMPLATE_PATH.read_text(encoding="utf-8"), title)
        pathlib.Path(args.out).write_text(page, encoding="utf-8")
        result, code = {"ok": True, "out": args.out, "title": title}, 0
    except (Refusal, OSError) as err:
        result, code = {"ok": False, "problems": err.problems if isinstance(err, Refusal) else [str(err)]}, 1
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
