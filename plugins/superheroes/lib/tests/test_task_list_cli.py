# plugins/superheroes/lib/tests/test_task_list_cli.py
import json, os, subprocess, sys
HERE = os.path.dirname(__file__)
CLI = os.path.join(HERE, "..", "task_list_cli.py")


def test_cli_emits_tasks_json_for_missing_doc(tmp_path):
    # No tasks doc under tmp_path -> fail-closed empty list, exit 0.
    out = subprocess.run([sys.executable, CLI, "--work-item", "does-not-exist"],
                         cwd=str(tmp_path), capture_output=True, text=True)
    assert out.returncode == 0
    data = json.loads(out.stdout)
    assert data["tasks"] == []
    assert data["raw_task_heading_count"] == 0


# ---------------------------------------------------------------------------
# Fence-aware raw-heading count (C-I2): a `### Task N` inside a code fence must
# NOT inflate raw_task_heading_count (which would trip a false "format mismatch"
# park on a doc that legitimately has zero tasks). An UNFENCED `### Task N` with a
# bad separator must still be counted so the silent-zero guard fires.
# ---------------------------------------------------------------------------
import re
sys.path.insert(0, os.path.join(HERE, ".."))
import task_list_cli  # noqa: E402


def _raw_count(body):
    """Drive the CLI's raw-heading counter directly over a body string."""
    return task_list_cli.raw_task_heading_count(body)


def test_raw_count_zero_when_only_fenced_task_heading():
    # The only `### Task N` lines are inside a code fence -> raw count 0 (no false mismatch).
    body = (
        "## Goal\n"
        "Demonstrate the tasks format with an example:\n"
        "\n"
        "```\n"
        "### Task 1: An example heading inside a fence\n"
        "### Task 2: Another example\n"
        "```\n"
        "\n"
        "No real tasks here.\n"
    )
    assert _raw_count(body) == 0


def test_raw_count_counts_unfenced_bad_separator_heading():
    # An UNFENCED `### Task N` whose separator the parser rejects (here '=', not in the
    # tolerated set) must still be counted so the silent-zero guard fires on a genuine
    # format mismatch.
    body = "### Task 1 = bad separator the parser rejects\n"
    import task_list
    assert task_list.parse(body) == []          # parser rejects it (format mismatch)
    assert _raw_count(body) > 0                  # raw count still catches it
