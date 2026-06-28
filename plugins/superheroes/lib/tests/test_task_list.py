# plugins/superheroes/lib/tests/test_task_list.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import task_list


def test_parses_tasks_in_order():
    body = "intro\n### Task 1: First\nblah\n### Task 2: Second thing\nmore\n"
    assert task_list.parse(body) == [
        {"id": "1", "title": "First"},
        {"id": "2", "title": "Second thing"},
    ]


def test_zero_tasks_returns_empty():
    assert task_list.parse("no tasks here\n## Heading\n") == []


def test_non_string_returns_empty():
    assert task_list.parse(None) == []
    assert task_list.parse(123) == []


def test_ignores_task_heading_inside_code_fence():
    body = "### Task 1: Real\n```\n### Task 2: Fake (in code)\n```\ntail\n"
    assert task_list.parse(body) == [{"id": "1", "title": "Real"}]


# ---------------------------------------------------------------------------
# Separator-tolerance tests (BUG-1): em-dash, en-dash, hyphen separators
# ---------------------------------------------------------------------------

def test_parses_colon_separator():
    # Canonical format — should already pass.
    body = "### Task 1: My title\n"
    assert task_list.parse(body) == [{"id": "1", "title": "My title"}]


def test_parses_em_dash_separator():
    # Em-dash (U+2014): the tasks author uses this — must also parse.
    body = "### Task 1 — My title\n"
    assert task_list.parse(body) == [{"id": "1", "title": "My title"}]


def test_parses_en_dash_separator():
    # En-dash (U+2013): similar variant.
    body = "### Task 1 – My title\n"
    assert task_list.parse(body) == [{"id": "1", "title": "My title"}]


def test_parses_hyphen_separator():
    # Plain hyphen: another common variant.
    body = "### Task 1 - My title\n"
    assert task_list.parse(body) == [{"id": "1", "title": "My title"}]


def test_non_task_heading_not_parsed():
    # A ### heading that is NOT a Task N heading must not be captured.
    body = "### Just a heading\n### Task Intro\n"
    assert task_list.parse(body) == []


def test_golden_realistic_tasks_doc():
    # Realistic multi-section tasks doc: only outer ### Task N: ... headings should parse;
    # the ### Task N: ... line inside a fenced block must be skipped.
    body = (
        "## Goal\n"
        "Some goal text\n"
        "\n"
        "## Architecture\n"
        "Some arch text\n"
        "\n"
        "## Tech Stack\n"
        "Some tech text\n"
        "\n"
        "### Task 1: Write the parser\n"
        "- [ ] step one\n"
        "- [ ] step two\n"
        "\n"
        "### Task 2: Write the tests\n"
        "- [ ] step one\n"
        "\n"
        "```python\n"
        "### Task 3: This is a code block heading (should NOT parse as task)\n"
        "```\n"
        "\n"
        "### Task 3: Add integration\n"
        "- [ ] step one\n"
    )
    result = task_list.parse(body)
    assert len(result) == 3, f"expected 3 tasks, got {len(result)}: {result}"
    assert result[0] == {"id": "1", "title": "Write the parser"}
    assert result[1] == {"id": "2", "title": "Write the tests"}
    assert result[2] == {"id": "3", "title": "Add integration"}
