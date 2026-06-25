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
