"""Guards for the artifact title a review sheet is published under (lib/sheet_title.py)."""
import hashlib
import json
import re
from pathlib import Path

import pytest

import sheet_title

THEME = Path(__file__).resolve().parents[2] / "theme"
TEMPLATE_TEXT = (THEME / "review-template.html").read_text(encoding="utf-8")


def _sample(name):
    return json.loads((THEME / name).read_text(encoding="utf-8"))


def _stage(tmp_path, capsys, sheet, *extra):
    sheet_path, out = tmp_path / "sheet.json", tmp_path / "review-template.html"
    sheet_path.write_text(json.dumps(sheet, indent=2) + "\n", encoding="utf-8")
    code = sheet_title.main(["stage", "--sheet", str(sheet_path), "--project", "superheroes", *extra, "--out", str(out)])
    return code, json.loads(capsys.readouterr().out), out, sheet_path


def _page_title(out):
    titles = re.findall(r"<title>([^<]*)</title>", out.read_text(encoding="utf-8"))
    assert len(titles) == 1
    return titles[0]


def _pr_sheet():
    sheet = _sample("sample-pr-sheet.json")
    sheet["prSheet"]["number"] = 1900
    return sheet


def _index_sheet():
    return {"schema": "superheroes-sheet/1", "kind": "index", "title": "What waits on you", "cards": [],
            "index": {"rows": []}}


# Bites on: a PR sheet published under anything but the owner's ruled shape.
def test_pr_sheet_title(tmp_path, capsys):
    code, result, out, _ = _stage(tmp_path, capsys, _pr_sheet())
    assert code == 0 and result["ok"]
    assert _page_title(out) == "superheroes PR #1900 review sheet"
    assert result["title"] == "superheroes PR #1900 review sheet"


# Bites on: a stack sheet naming anything but its bottom and top PRs.
def test_stack_sheet_title(tmp_path, capsys):
    code, _, out, _ = _stage(tmp_path, capsys, _sample("sample-stack-sheet.json"))
    assert code == 0
    assert _page_title(out) == "superheroes stack PR #5–#7 review sheet"


def test_index_sheet_title(tmp_path, capsys):
    code, _, out, _ = _stage(tmp_path, capsys, _index_sheet())
    assert code == 0
    assert _page_title(out) == "superheroes open decisions review sheet"


@pytest.mark.parametrize("kind", ["plain", "remainder", "final"])
def test_discovery_sheet_title(tmp_path, capsys, kind):
    sheet = _sample("sample-final-sheet.json" if kind == "final" else "sample-sheet.json")
    if kind == "plain":
        sheet["kind"] = "plain"
        sheet.pop("remainder", None)
    assert sheet["kind"] == kind
    code, _, out, _ = _stage(tmp_path, capsys, sheet, "--slug", "weekly-plan")
    assert code == 0
    assert _page_title(out) == "superheroes weekly-plan review sheet"


# Bites on: staging that moves anything but the <title>, or that touches the data file (its digest keys the verdict).
def test_only_the_title_moves(tmp_path, capsys):
    sheet = _pr_sheet()
    sheet_path = tmp_path / "sheet.json"
    sheet_path.write_text(json.dumps(sheet, indent=2) + "\n", encoding="utf-8")
    before = hashlib.sha256(sheet_path.read_bytes()).hexdigest()
    code, _, out, _ = _stage(tmp_path, capsys, sheet)
    assert code == 0
    assert hashlib.sha256(sheet_path.read_bytes()).hexdigest() == before
    staged = out.read_text(encoding="utf-8")
    assert staged.replace("<title>superheroes PR #1900 review sheet</title>", "<title>Review sheet</title>") == TEMPLATE_TEXT


@pytest.mark.parametrize("sheet, extra, problem", [
    ("remainder", [], "needs --slug"),
    ("pr", ["--slug", "x"], "--slug is only for"),
    ("odd", [], "not a sheet kind"),
])
def test_refusals_write_nothing(tmp_path, capsys, sheet, extra, problem):
    data = {"pr": _pr_sheet(), "remainder": _sample("sample-sheet.json"), "odd": {"kind": "odd"}}[sheet]
    code, result, out, _ = _stage(tmp_path, capsys, data, *extra)
    assert code == 1 and not result["ok"]
    assert any(problem in p for p in result["problems"])
    assert not out.exists()


def test_project_name_carries_no_owner():
    with pytest.raises(sheet_title.Refusal):
        sheet_title.title_for(_pr_sheet(), "zwrose/superheroes")


def test_title_is_escaped_for_the_page():
    page = sheet_title.stage_page(TEMPLATE_TEXT, "a <b> & c")
    assert "<title>a &lt;b&gt; &amp; c</title>" in page


def test_template_with_no_single_title_is_refused():
    with pytest.raises(sheet_title.Refusal):
        sheet_title.stage_page(TEMPLATE_TEXT + "<title>x</title>", "t")
