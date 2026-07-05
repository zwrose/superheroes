import os, re

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_WF = os.path.join(_ROOT, ".github", "workflows", "release-evidence.yml")


def _text():
    with open(_WF) as fh:
        return fh.read()


def test_workflow_exists_and_parses():
    import yaml
    with open(_WF) as fh:
        data = yaml.safe_load(fh)
    assert "jobs" in data and "evidence" in data["jobs"]


def test_triggers_cover_pr_comment_and_dispatch():
    import yaml
    with open(_WF) as fh:
        data = yaml.safe_load(fh)
    on = data.get(True, data.get("on"))
    assert "pull_request" in on
    assert "issue_comment" in on
    assert "workflow_dispatch" in on


def test_never_uses_pull_request_target():
    import yaml
    with open(_WF) as fh:
        data = yaml.safe_load(fh)
    on = data.get(True, data.get("on"))
    assert "pull_request_target" not in on


def test_gated_to_release_please_branch():
    import yaml
    with open(_WF) as fh:
        data = yaml.safe_load(fh)
    text = _text()
    assert "release-please--*" in text  # is_release guard set in the ctx step
    # The side-effecting data steps (checkout, materialize, verify, upsert) must be gated on
    # is_release so a non-release PR touches nothing; the status step is deliberately `always()`
    # (it must report on every PR) and self-guards on IS_RELEASE instead. Assert both invariants.
    steps = data["jobs"]["evidence"]["steps"]
    def _named(substr):
        return [s for s in steps if substr.lower() in (s.get("name", "").lower())]
    for label in ("Checkout", "Materialize", "Verify release evidence", "Upsert"):
        matched = _named(label)
        assert matched, f"no step named ~{label!r}"
        assert all("is_release == 'true'" in str(s.get("if", "")) for s in matched), \
            f"side-effect step ~{label!r} not gated on is_release"
    status = _named("commit status")
    assert status and status[0].get("if") == "always()", "status step must be always()"
    assert 'is_release != "true"' in text  # ...and self-guard the non-release case internally


def test_checks_out_trusted_base_not_head():
    text = _text()
    # scripts run from the base ref; the head is read as data via git show
    assert "ref: ${{ steps.ctx.outputs.base }}" in text
    assert "git show" in text and "showrunner.bundle.js" in text
    # the head SHA is never used as a checkout ref
    assert "ref: ${{ steps.ctx.outputs.sha }}" not in text


def test_no_untrusted_payload_interpolated_into_run():
    # attacker-influenced payload fields must be passed via env, never inlined in a run: block.
    banned = [
        "${{ github.event.pull_request.head.ref }}",
        "${{ github.event.comment.body }}",
        "${{ github.event.pull_request.title }}",
        "${{ github.event.issue.title }}",
    ]
    # they may appear in the top-level env: map, but not on a line that also runs shell.
    for line in _text().splitlines():
        stripped = line.strip()
        is_env_assignment = re.match(r"^[A-Z0-9_]+:\s*\$\{\{", stripped)
        if is_env_assignment:
            continue
        for b in banned:
            assert b not in line, f"untrusted payload inlined outside env: {line}"


def test_runs_the_verifier_which_drives_the_classifier():
    # the workflow runs the verifier directly; the verifier imports the classifier (the single
    # home of the release-class globs), so classification runs transitively — assert both links.
    assert ".github/scripts/verify_release_evidence.py" in _text()
    verifier = os.path.join(_ROOT, ".github", "scripts", "verify_release_evidence.py")
    with open(verifier) as fh:
        assert "import classify_release" in fh.read()


def test_evidence_comments_are_author_filtered():
    # forged-evidence guard: only comments from a write-access author count as evidence.
    text = _text()
    assert "author_association" in text
    assert '"OWNER"' in text


def test_data_steps_tolerate_failure_so_status_always_reports():
    import yaml
    with open(_WF) as fh:
        steps = yaml.safe_load(fh)["jobs"]["evidence"]["steps"]
    # materialize + verify + upsert must be continue-on-error so an upstream hiccup can't skip
    # the always() status step and strand the required check.
    for label in ("Materialize", "Verify release evidence", "Upsert"):
        s = [x for x in steps if label.lower() in x.get("name", "").lower()][0]
        assert s.get("continue-on-error") is True, f"{label} must be continue-on-error"


def test_publishes_a_commit_status_named_release_evidence():
    text = _text()
    assert 'context="release-evidence"' in text
    assert "repos/$REPO/statuses/$SHA" in text


def test_all_third_party_actions_pinned_to_sha():
    for line in _text().splitlines():
        # anchor to a real YAML `uses:` key (optionally list-dashed) so prose like
        # "statuses: write" is not mistaken for an action reference.
        m = re.match(r"\s*(?:-\s*)?uses:\s*(\S+)", line)
        if not m:
            continue
        ref = m.group(1).split("@", 1)[1] if "@" in m.group(1) else ""
        assert re.fullmatch(r"[0-9a-f]{40}", ref), f"not SHA-pinned: {m.group(1)}"


def test_owed_comment_upsert_skips_issue_comment_event():
    text = _text()
    # the upsert step must not run on issue_comment (loop guard)
    assert "github.event_name != 'issue_comment'" in text
