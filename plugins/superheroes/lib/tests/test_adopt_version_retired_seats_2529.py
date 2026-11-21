"""adopt_version plan's retired-seat fields (issue #2529).

`retiredSeats` lists every review-panel seat an installed release inside the adoption span dropped,
read by each release's own `lib/seat_map.py` in a separate process; `retiredSeatPins` names the ones
the project still pins in core.md `enginePreferences.seatPins`. `null` means "could not be checked",
`[]` means "checked, none". The plan never writes anything.
"""
import json
import os
import subprocess
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import adopt_version as av  # noqa: E402
import core_md  # noqa: E402
import model_registry  # noqa: E402

_SEAT_MAP = "KNOWN_SEATS = {known!r}\nLEGACY_SEAT_ALIASES = {aliases!r}\n"


def _mkver(cache, ver, known=None, aliases=None, seat_map=None):
    """A version tree whose lib/seat_map.py is a stub (known/aliases) or the given source text;
    seat_map=False leaves the module out. TRANSITION.md and CHANGELOG.md let `plan` succeed."""
    root = cache / ver
    (root / "lib").mkdir(parents=True)
    if seat_map is None:
        seat_map = _SEAT_MAP.format(known=tuple(known or ()), aliases=dict.fromkeys(aliases or (), "x"))
    if seat_map is not False:
        (root / "lib" / "seat_map.py").write_text(seat_map)
    (root / "TRANSITION.md").write_text("## %s\n" % ver)
    (root / "CHANGELOG.md").write_text("## [%s](https://example.test) (2026-01-01)\n" % ver)


def _seed_project(tmp_path, seat_pins=None):
    """A git project with a core.md; seat_pins=None writes no enginePreferences at all."""
    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(["git", "-C", str(proj), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(proj), "remote", "add", "origin", "git@github.com:o/r.git"], check=True)
    facts = {"verifyCommand": "pytest", "stackTags": ["py"], "threatModel": "single-user", "patterns": ""}
    if seat_pins is not None:
        facts["enginePreferences"] = {"seatPins": seat_pins}
    cdir = proj / ".claude" / "superheroes"
    cdir.mkdir(parents=True)
    (cdir / "core.md").write_text(core_md.render_core(facts, "confirmed", "2026-07-19", "2026-07-19"))
    return proj


def _pins(*seats):
    model = model_registry.pin_only_models("codex")[0]
    return {s: {"vendor": "codex", "model": model, "effort": "high"} for s in seats}


@pytest.fixture(autouse=True)
def _store(tmp_path, monkeypatch):
    store = tmp_path / "store"
    store.mkdir()
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(store))
    return store


def _plan(capsys, cache, from_v, to_v, project=None, role="showrunner"):
    argv = ["plan", "--role", role, "--from", from_v, "--to", to_v, "--cache-dir", str(cache)]
    if project is not None:
        argv += ["--project", str(project)]
    code = av.main(argv)
    out = capsys.readouterr().out.strip()
    return code, json.loads(out) if out else None


def _snapshot(*roots):
    snap = {}
    for root in roots:
        for dp, dns, fns in os.walk(str(root)):
            dns[:] = sorted(d for d in dns if d != ".git")
            for d in dns:
                snap[os.path.join(dp, d)] = None
            for f in sorted(fns):
                with open(os.path.join(dp, f), "rb") as fh:
                    snap[os.path.join(dp, f)] = fh.read()
    return snap


def test_dropped_seat_is_named_and_the_pinned_one_is_listed(capsys, tmp_path):
    cache = tmp_path / "cache"
    _mkver(cache, "0.1.0", known=("code-reviewer", "grounding-seat"))
    _mkver(cache, "0.2.0", known=("code-reviewer",))
    proj = _seed_project(tmp_path, _pins("grounding-seat", "code-reviewer"))
    code, data = _plan(capsys, cache, "0.1.0", "0.2.0", proj)
    assert code == 0
    assert data["retiredSeats"] == [{"seat": "grounding-seat", "version": "0.2.0", "since": "0.1.0"}]
    assert data["retiredSeatPins"] == ["grounding-seat"]
    assert data["pinsProject"] == str(proj)


@pytest.mark.parametrize("span", [
    pytest.param((("0.1.0", ("code-reviewer", "old-seat"), ()),
                  ("0.2.0", ("code-reviewer",), ("old-seat",))), id="alias-in-to"),
    # the alias sits only in the middle release, so the `to` tree's own check cannot excuse the seat
    pytest.param((("0.1.0", ("code-reviewer", "old-seat"), ()),
                  ("0.2.0", ("code-reviewer",), ("old-seat",)),
                  ("0.3.0", ("code-reviewer", "new-seat"), ())), id="alias-in-middle-only"),
])
def test_seat_kept_as_a_legacy_alias_is_not_retired(capsys, tmp_path, span):
    cache = tmp_path / "cache"
    for ver, known, aliases in span:
        _mkver(cache, ver, known=known, aliases=aliases)
    proj = _seed_project(tmp_path, _pins("old-seat"))
    code, data = _plan(capsys, cache, span[0][0], span[-1][0], proj)
    assert code == 0
    assert data["retiredSeats"] == []
    assert data["retiredSeatPins"] == []


def test_seat_dropped_in_the_middle_and_back_in_to_is_not_retired(capsys, tmp_path):
    cache = tmp_path / "cache"
    _mkver(cache, "0.1.0", known=("code-reviewer", "wanderer"))
    _mkver(cache, "0.2.0", known=("code-reviewer",))
    _mkver(cache, "0.3.0", known=("code-reviewer", "wanderer"))
    proj = _seed_project(tmp_path, _pins("wanderer"))
    code, data = _plan(capsys, cache, "0.1.0", "0.3.0", proj)
    assert code == 0
    assert data["retiredSeats"] == []
    assert data["retiredSeatPins"] == []


@pytest.mark.parametrize("broken", [
    pytest.param(False, id="module-missing"),
    pytest.param("raise RuntimeError('no seats')\n", id="raises-on-import"),
    pytest.param("print('noise')\nKNOWN_SEATS = ('a',)\n", id="prints-non-json"),
    pytest.param("KNOWN_SEATS = (1, 2)\n", id="wrong-typed"),
    pytest.param("import time\ntime.sleep(60)\n", id="times-out"),
])
def test_unreadable_tree_makes_both_fields_null_and_the_plan_still_succeeds(
        capsys, tmp_path, monkeypatch, broken):
    monkeypatch.setattr(av, "STAMP_TIMEOUT_SECONDS", 2)
    cache = tmp_path / "cache"
    _mkver(cache, "0.1.0", known=("code-reviewer", "grounding-seat"))
    _mkver(cache, "0.2.0", seat_map=broken)
    _mkver(cache, "0.3.0", known=("code-reviewer",))
    proj = _seed_project(tmp_path, _pins("grounding-seat"))
    code, data = _plan(capsys, cache, "0.1.0", "0.3.0", proj)
    assert code == 0 and data["ok"] is True
    assert data["retiredSeats"] is None
    assert data["retiredSeatPins"] is None
    assert data["pinsProject"] == str(proj)


def test_no_seat_pins_in_core_gives_an_empty_list_while_the_seat_is_still_listed(capsys, tmp_path):
    cache = tmp_path / "cache"
    _mkver(cache, "0.1.0", known=("code-reviewer", "grounding-seat"))
    _mkver(cache, "0.2.0", known=("code-reviewer",))
    proj = _seed_project(tmp_path, seat_pins=None)
    code, data = _plan(capsys, cache, "0.1.0", "0.2.0", proj)
    assert code == 0
    assert data["retiredSeats"] == [{"seat": "grounding-seat", "version": "0.2.0", "since": "0.1.0"}]
    assert data["retiredSeatPins"] == []


def test_up_to_date_plan_reports_no_retired_seats_without_reading_a_tree(capsys, tmp_path):
    cache = tmp_path / "cache"
    _mkver(cache, "0.1.0", seat_map=False)
    proj = _seed_project(tmp_path, _pins("grounding-seat"))
    code, data = _plan(capsys, cache, "0.1.0", "0.1.0", proj)
    assert code == 0 and data["upToDate"] is True
    assert data["retiredSeats"] == []
    assert data["retiredSeatPins"] == []
    assert data["pinsProject"] == str(proj)


def test_plan_writes_nothing_to_the_project_the_store_or_any_version_tree(capsys, tmp_path, _store):
    cache = tmp_path / "cache"
    _mkver(cache, "0.1.0", known=("code-reviewer", "grounding-seat"))
    _mkver(cache, "0.2.0", known=("code-reviewer",))
    proj = _seed_project(tmp_path, _pins("grounding-seat"))
    core_before = (proj / ".claude" / "superheroes" / "core.md").read_bytes()
    before = _snapshot(cache, proj, _store)
    code, data = _plan(capsys, cache, "0.1.0", "0.2.0", proj)
    assert code == 0 and data["retiredSeatPins"] == ["grounding-seat"]
    assert (proj / ".claude" / "superheroes" / "core.md").read_bytes() == core_before
    assert _snapshot(cache, proj, _store) == before
    assert not [p for p in before if "__pycache__" in p]
    assert not [p for p in _snapshot(cache) if "__pycache__" in p]


def test_pin_read_edges(tmp_path):
    """Absent core.md reads [] ; a seatPins that is not an object, or a refused core.md, reads None."""
    bare = tmp_path / "bare"
    bare.mkdir()
    subprocess.run(["git", "-C", str(bare), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(bare), "remote", "add", "origin", "git@github.com:o/r.git"], check=True)
    assert av._project_pin_seats(str(bare)) == []
    listy = _seed_project(tmp_path, seat_pins=["code-reviewer"])
    assert av._project_pin_seats(str(listy)) is None
    core = listy / ".claude" / "superheroes" / "core.md"
    core.write_text("```json superheroes-core\n{not json\n```\n")
    assert av._project_pin_seats(str(listy)) is None
