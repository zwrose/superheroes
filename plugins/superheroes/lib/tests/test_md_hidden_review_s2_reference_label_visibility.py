"""Resolved reference-link labels are not visible body text."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import md_hidden as md  # noqa: E402


def test_single_line_reference_label_reads_unsure_on_its_line():
    # axis: reference-label visibility -- a resolved second label disappears from rendered text, so its mixed-content source line must read UNSURE without making later headings unsure.
    body = 'x [a][ZQ1] y\n\n## ZQ2\n\n[ZQ1]: /u\n'
    rendering = md.scan(body)
    assert rendering.state_at(0) == md.UNSURE, (
        rendering.lines, rendering.unsure
    )
    assert rendering.state_at(body.index('## ZQ2')) == md.VISIBLE
