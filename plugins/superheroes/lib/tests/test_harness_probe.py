"""Unit tests for harness native project-context tripwire (lib/harness_probe.py)."""
import io
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.abspath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import harness_probe as hp  # noqa: E402


def test_native_layer_present_true_when_marker_in_text():
    assert hp.native_layer_present("preamble\n# claudeMd\nbody") is True


def test_native_layer_present_false_when_marker_absent():
    assert hp.native_layer_present("no harness marker here") is False


def test_native_layer_present_false_for_none_without_raise():
    assert hp.native_layer_present(None) is False


def test_native_layer_present_false_for_non_str_without_raise():
    assert hp.native_layer_present(42) is False
    assert hp.native_layer_present([]) is False


def test_native_layer_present_false_when_marker_embedded_mid_line():
    assert hp.native_layer_present("see the marker # claudeMd inline") is False


def test_native_layer_present_false_when_marker_is_prefix_token():
    assert hp.native_layer_present("x# claudeMd") is False


def test_native_layer_present_false_when_marker_is_suffix_token():
    assert hp.native_layer_present("# claudeMd-not-native") is False


def test_main_check_returns_0_when_file_contains_marker(tmp_path):
    path = tmp_path / "context.txt"
    path.write_text("foo\n# claudeMd\nbar\n", encoding="utf-8")
    assert hp.main(["--check", str(path)]) == 0


def test_main_check_returns_1_when_file_lacks_marker(tmp_path):
    path = tmp_path / "context.txt"
    path.write_text("no marker here\n", encoding="utf-8")
    assert hp.main(["--check", str(path)]) == 1


def test_main_check_returns_1_for_nonexistent_path():
    assert hp.main(["--check", "/nonexistent/harness_probe_evidence.txt"]) == 1


def test_main_check_stdin_returns_0_when_marker_present(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("# claudeMd\n"))
    assert hp.main(["--check", "-"]) == 0


def test_main_check_stdin_returns_1_when_marker_absent(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("no marker\n"))
    assert hp.main(["--check", "-"]) == 1


def test_main_procedure_print_returns_0_and_names_paths_version_fallback(capsys):
    assert hp.main([]) == 0
    out = capsys.readouterr().out
    for path in hp.SPAWN_PATHS:
        assert path in out
    assert "2.1.219" in out
    assert "revert" in out.lower() or "restore" in out.lower()


def test_precompact_evidence_passes_when_token_in_summary_region():
    evidence = (
        "hook payload: begin summary with ZZQX-TOKEN\n"
        "Compaction summary\n"
        "ZZQX-TOKEN the session preserved charter state.\n"
    )
    ok, reason = hp.precompact_evidence_passes(evidence, "ZZQX-TOKEN")
    assert ok is True
    assert reason == ""


def test_precompact_evidence_fails_when_validation_error_present():
    evidence = "Compaction summary\nZZQX-TOKEN\nHook JSON output validation failed\n"
    ok, reason = hp.precompact_evidence_passes(evidence, "ZZQX-TOKEN")
    assert ok is False
    assert "Hook JSON output validation failed" in reason


def test_precompact_evidence_fails_when_token_absent():
    evidence = "Compaction summary\nno token in the summary region\n"
    ok, reason = hp.precompact_evidence_passes(evidence, "ZZQX-TOKEN")
    assert ok is False
    assert "absent from generated summary region" in reason


def test_precompact_evidence_fails_when_token_only_outside_summary_region():
    evidence = (
        "additionalContext: begin your summary with ZZQX-TOKEN\n"
        "Compaction summary\n"
        "summary text without the expected token\n"
    )
    ok, reason = hp.precompact_evidence_passes(evidence, "ZZQX-TOKEN")
    assert ok is False
    assert "absent from generated summary region" in reason


def test_main_check_precompact_returns_0_when_token_in_summary_region(tmp_path):
    path = tmp_path / "evidence.txt"
    path.write_text(
        "Compaction summary\nZZQX-TOKEN preserved showrunner charter.\n",
        encoding="utf-8",
    )
    assert hp.main(["--check-precompact", str(path), "--precompact-token", "ZZQX-TOKEN"]) == 0


def test_main_check_precompact_returns_1_when_validation_error_present(tmp_path):
    path = tmp_path / "evidence.txt"
    path.write_text(
        "Compaction summary\nZZQX-TOKEN\nHook JSON output validation failed\n",
        encoding="utf-8",
    )
    assert hp.main(["--check-precompact", str(path), "--precompact-token", "ZZQX-TOKEN"]) == 1


def test_main_check_precompact_returns_1_when_token_absent(tmp_path):
    path = tmp_path / "evidence.txt"
    path.write_text("Compaction summary\nno token here\n", encoding="utf-8")
    assert hp.main(["--check-precompact", str(path), "--precompact-token", "ZZQX-TOKEN"]) == 1


def test_main_check_precompact_returns_1_when_token_only_outside_summary_region(tmp_path):
    path = tmp_path / "evidence.txt"
    path.write_text(
        "hook instruction mentions ZZQX-TOKEN only here\n"
        "Compaction summary\n"
        "generated summary without the token\n",
        encoding="utf-8",
    )
    assert hp.main(["--check-precompact", str(path), "--precompact-token", "ZZQX-TOKEN"]) == 1
