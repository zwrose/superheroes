"""The collector detector must reject reversed source priorities."""
import importlib.util
from pathlib import Path

import pytest


def test_collector_detector_rejects_reversed_priority_words(monkeypatch):
    # axis: the discuss collector detector rejects memory-first priority even when source-name positions stay unchanged.
    path = Path(__file__).with_name("test_advisor_inboxes_doctrine_2504.py")
    spec = importlib.util.spec_from_file_location("advisor_doctrine_priority_probe", path)
    doctrine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(doctrine)
    original_lines = doctrine._lines
    text = "\n".join(original_lines(doctrine.DISCUSS))
    before = (
        "from calibration first (`project_config.py advisor-issues`) "
        "and from the advisor's durable memory second"
    )
    after = (
        "from calibration second (`project_config.py advisor-issues`) "
        "and from the advisor's durable memory first"
    )
    assert text.count(before) == 1
    reversed_lines = text.replace(before, after).splitlines()

    def read_lines(rel):
        if rel == doctrine.DISCUSS:
            return reversed_lines
        return original_lines(rel)

    monkeypatch.setattr(doctrine, "_lines", read_lines)
    with pytest.raises(AssertionError):
        doctrine.test_discuss_step_two_resolves_the_collector_from_calibration_before_memory()
