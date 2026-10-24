"""Credentials: transcript metadata failure must not bypass pass scrubbing."""
import base64
import importlib.util
import io
import json
import sys
from pathlib import Path


def test_surrogate_transcript_path_does_not_bypass_pass_scrubbing(tmp_path, monkeypatch, capsys):
    # axis: a filesystem path that strict UTF-8 cannot encode must not abort credential cleanup.
    home = tmp_path / "home"
    home.mkdir()
    reviewer_home = tmp_path / "reviewer"
    env_file = tmp_path / "session-env.sh"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("CODEX_HOME", str(reviewer_home))
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))
    monkeypatch.delenv("SUPERHEROES_REVIEWER_PASS_SHA256", raising=False)

    claims = base64.urlsafe_b64encode(b'{"exp":4000000000}').rstrip(b"=").decode("ascii")
    access = "fixture." + claims + ".signature"
    raw_pass = json.dumps({
        "auth_mode": "chatgpt",
        "OPENAI_API_KEY": None,
        "tokens": {"access_token": access, "id_token": "fixture-id", "refresh_token": ""},
    }).encode("utf-8")
    encoded_pass = base64.b64encode(raw_pass).decode("ascii")
    monkeypatch.setenv("SUPERHEROES_REVIEWER_PASS", encoded_pass)

    transcript = str(tmp_path / "session-") + chr(0xDCFF) + ".jsonl"
    Path(transcript).write_bytes(b"")
    payload = {"source": "startup", "cwd": str(tmp_path), "transcript_path": transcript}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(sys, "argv", ["session_start.py"])
    hook_path = Path(__file__).resolve().parents[2] / "hooks" / "session_start.py"
    spec = importlib.util.spec_from_file_location("session_start_2110_break_it", hook_path)
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)

    assert hook.main() == 0
    exports = env_file.read_text(encoding="utf-8", errors="surrogateescape")
    assert "unset SUPERHEROES_REVIEWER_PASS" in exports.splitlines()
    assert (reviewer_home / "auth.json").read_bytes() == raw_pass
    captured = capsys.readouterr()
    for secret in (encoded_pass, access, "fixture-id"):
        assert secret not in captured.out + captured.err + exports
