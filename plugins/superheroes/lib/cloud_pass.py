"""The reviewer pass: a copy of the reviewer tool's sign-in file with its renewal key blanked,
base64-encoded, so a cloud session can run the reviewer without being able to renew the sign-in.

The pass exists in exactly three places: the clipboard, the cloud environment's variables, and
the reviewer's sign-in file on the cloud machine. No function here prints it, logs it, returns it
in a result, or writes it to any other path. `make` hands it to the clipboard command and nowhere
else; `place` opens exactly one path for writing.

  cloud_pass.py make      owner's machine: put the pass block on the clipboard
  cloud_pass.py place     cloud machine, session start: write the pass to the reviewer's sign-in
  cloud_pass.py confirm   cloud session: does the reviewer answer with the pass in this environment
  cloud_pass.py record-confirmation --confirmation JSON [--cwd D] [--account A] [--environment E]
                          [--root D]   owner's machine: move the setup record's lapse date

Stdlib only. Every public function takes `env=None` (a mapping; default the process environment)
and returns a plain dict; an expected failure is a refusal with a `reason` token, never a raise.
"""
import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

PASS_ENV = "SUPERHEROES_REVIEWER_PASS"
CLOUD_ENV = "CLAUDE_CODE_REMOTE"
PLUGIN_DIRS_ENV = "CLAUDE_CODE_PLUGIN_DIRS"
CLOUD_PLUGIN_DIR = "/opt/superheroes/plugin"
RENEWAL_ENDPOINT_ENVS = ("CODEX_REFRESH_TOKEN_URL_OVERRIDE", "CODEX_REVOKE_TOKEN_URL_OVERRIDE")
DEAD_ENDPOINT = "http://127.0.0.1:9/"
SEPARATE_HOME_ENV = "SUPERHEROES_REVIEWER_PASS_HOME"
SEPARATE_HOME_DEFAULT = "~/.codex-cloud"
CONFIRMATION_SCHEMA = "cloud-pass-confirmation/1"

_CODEX_HOME_ENV = "CODEX_HOME"
_AUTH_FILE = "auth.json"
_CLIPBOARD_COMMANDS = (("pbcopy",), ("wl-copy",), ("xclip", "-selection", "clipboard"))
_CLIPBOARD_TIMEOUT = 30


def _env(env):
    return os.environ if env is None else env


def _is_cloud(env):
    return env.get(CLOUD_ENV) == "true"


def _expand_home(path, env):
    """expanduser against the SUPPLIED env's HOME, not the process's own."""
    if not path.startswith("~"):
        return path
    home = env.get("HOME")
    if not isinstance(home, str) or not home:
        return os.path.expanduser(path)
    if path == "~" or path.startswith("~" + os.sep):
        return home + path[1:]
    return os.path.expanduser(path)


def _default_signin_path(env):
    """The reviewer's default sign-in file: CODEX_HOME when set and non-empty, else ~/.codex."""
    configured = env.get(_CODEX_HOME_ENV)
    if isinstance(configured, str) and configured.strip():
        return os.path.join(_expand_home(configured.strip(), env), _AUTH_FILE)
    return os.path.join(_expand_home("~", env), ".codex", _AUTH_FILE)


def _separate_signin_path(env):
    configured = env.get(SEPARATE_HOME_ENV)
    if not (isinstance(configured, str) and configured.strip()):
        configured = SEPARATE_HOME_DEFAULT
    return os.path.join(_expand_home(configured.strip(), env), _AUTH_FILE)


def _refusal(reason, message, **extra):
    out = {"action": "refused", "reason": reason, "message": message}
    out.update(extra)
    return out


def _skipped(reason):
    return {"action": "skipped", "reason": reason}


def _expiry(access_token):
    """Seconds since the epoch from the access token's payload part, or None when unreadable."""
    try:
        parts = access_token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        exp = claims["exp"]
        if isinstance(exp, bool) or not isinstance(exp, (int, float)):
            return None
        datetime.fromtimestamp(exp, timezone.utc)
        return exp
    except Exception:
        return None


def _date(exp):
    return datetime.fromtimestamp(exp, timezone.utc).strftime("%Y-%m-%d")


def _lapse_date(signin):
    tokens = signin.get("tokens") if isinstance(signin, dict) else None
    token = tokens.get("access_token") if isinstance(tokens, dict) else None
    exp = _expiry(token) if isinstance(token, str) else None
    return None if exp is None else _date(exp)


def _present(tokens, key):
    return isinstance(tokens, dict) and isinstance(tokens.get(key), str) and bool(tokens[key])


def _read_object(path):
    """The JSON object in `path`, or None when it cannot be read, is not JSON, or is not an object."""
    try:
        with open(path, "rb") as fh:
            value = json.loads(fh.read())
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _decode_pass(env):
    """(decoded bytes, parsed object) from PASS_ENV; (None, None) when it is not a JSON object."""
    try:
        raw = base64.b64decode(env[PASS_ENV].strip(), validate=True)
        value = json.loads(raw)
    except Exception:
        return None, None
    return (raw, value) if isinstance(value, dict) else (None, None)


def _find_clipboard(env):
    for argv in _CLIPBOARD_COMMANDS:
        found = shutil.which(argv[0], path=env.get("PATH") or "")
        if found:
            return (found,) + argv[1:]
    return None


def _run_clipboard(argv, text):
    # DEVNULL, not pipes: xclip forks a selection owner that keeps inherited pipes open.
    proc = subprocess.run(list(argv), input=text, text=True, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, timeout=_CLIPBOARD_TIMEOUT)
    if proc.returncode != 0:
        raise RuntimeError("clipboard command exited non-zero")


def copy_to_clipboard(text, env=None):
    """Feed `text` to the first clipboard command on the path. Raises LookupError when none is
    there; any other failure raises as it happened."""
    env = _env(env)
    argv = _find_clipboard(env)
    if argv is None:
        raise LookupError("no clipboard command (pbcopy, wl-copy or xclip) is on the path")
    _run_clipboard(argv, text)


def make(env=None, clipboard=None, now=None):
    """Owner's machine: build the pass from the separate sign-in and put the four-line block on
    the clipboard. Reads no setup record and writes no file."""
    env = _env(env)
    now = time.time() if now is None else now
    path = _separate_signin_path(env)
    if not os.path.isfile(path):
        return _refusal(
            "no-separate-sign-in",
            "There is no separate reviewer sign-in yet: sign in once by running the reviewer "
            "tool's login with %s set to %s, then run this command again."
            % (_CODEX_HOME_ENV, os.path.dirname(path)))
    if os.path.realpath(path) == os.path.realpath(_default_signin_path(env)):
        return _refusal(
            "separate-sign-in-is-main",
            "The separate sign-in is the same file as the reviewer's main sign-in; a pass must "
            "come from its own sign-in so the main one is never given away.")
    signin = _read_object(path)
    if signin is None:
        return _refusal("sign-in-unreadable",
                        "The separate sign-in file cannot be read as a JSON object.")
    tokens = signin.get("tokens")
    if not (_present(tokens, "access_token") and _present(tokens, "id_token")):
        return _refusal("sign-in-incomplete",
                        "The separate sign-in is missing its access token or id token; sign in "
                        "again to the separate sign-in.")
    exp = _expiry(tokens["access_token"])
    if exp is None:
        return _refusal("pass-expiry-unreadable",
                        "The separate sign-in's expiry cannot be read; sign in again to the "
                        "separate sign-in.")
    if not exp > now:
        return _refusal("sign-in-expired",
                        "The separate sign-in has expired; sign in again to the separate "
                        "sign-in, then run this command again.")
    copied = {"id_token": tokens["id_token"], "access_token": tokens["access_token"],
              "refresh_token": ""}
    if "account_id" in tokens:
        copied["account_id"] = tokens["account_id"]
    pass_obj = {
        "auth_mode": signin.get("auth_mode", "chatgpt"),
        "OPENAI_API_KEY": None,
        "tokens": copied,
        "last_refresh": datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    encoded = base64.b64encode(json.dumps(pass_obj).encode("utf-8")).decode("ascii")
    lines = ["%s=%s" % (PASS_ENV, encoded),
             "%s=%s" % (PLUGIN_DIRS_ENV, CLOUD_PLUGIN_DIR)]
    lines += ["%s=%s" % (name, DEAD_ENDPOINT) for name in RENEWAL_ENDPOINT_ENVS]
    block = "\n".join(lines) + "\n"
    use_default = clipboard is None
    try:
        if use_default:
            copy_to_clipboard(block, env)
        else:
            clipboard(block)
    except LookupError:
        if not use_default:
            return _refusal("clipboard-failed",
                            "The clipboard command failed, so nothing was copied.")
        return _refusal("no-clipboard",
                        "No clipboard command (pbcopy, wl-copy or xclip) is on the path, so "
                        "the pass was not made.")
    except Exception:
        return _refusal("clipboard-failed",
                        "The clipboard command failed, so nothing was copied.")
    return {
        "action": "copied", "reason": None, "passLapses": _date(exp),
        "daysLeft": round((exp - now) / 86400.0, 1), "characters": len(block),
        "message": "The pass block is on the clipboard: paste it into the cloud environment's "
                   "variables, replacing these four lines if they are already there.",
    }


def _write_signin(path, data):
    """Open the destination itself and write; no temporary file and no rename, so the pass never
    exists at a second path, even if the process is killed mid-write."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, mode=0o700, exist_ok=True)
    existed = os.path.lexists(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        if existed:
            os.fchmod(fd, 0o600)
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
    finally:
        os.close(fd)


def place(env=None):
    """Cloud machine, session start: write the pass from PASS_ENV to the reviewer's default
    sign-in file. Opens exactly one path for writing."""
    env = _env(env)
    if not _is_cloud(env):
        return _skipped("not-a-cloud-session")
    if not (isinstance(env.get(PASS_ENV), str) and env[PASS_ENV].strip()):
        return _skipped("no-pass-in-environment")
    raw, value = _decode_pass(env)
    if value is None:
        return _refusal("pass-unreadable", "The reviewer pass in the environment cannot be read.")
    tokens = value.get("tokens")
    if not (isinstance(tokens, dict) and tokens.get("refresh_token") == ""):
        return _refusal("pass-can-renew",
                        "The reviewer pass still carries a renewal key, so it was not placed; "
                        "make a fresh pass.")
    if not (_present(tokens, "access_token") and _present(tokens, "id_token")):
        return _refusal("pass-incomplete",
                        "The reviewer pass is missing its access token or id token; make a "
                        "fresh pass.")
    path = _default_signin_path(env)
    try:
        try:
            with open(path, "rb") as fh:
                same = fh.read() == raw
        except OSError:
            same = False
        if same:
            if os.stat(path).st_mode & 0o777 != 0o600:
                os.chmod(path, 0o600)
        else:
            _write_signin(path, raw)
    except Exception as exc:
        return _refusal("write-failed", "The reviewer pass could not be written.",
                        error=type(exc).__name__)
    return {"action": "placed", "reason": None, "passLapses": _lapse_date(value)}


def confirm(env=None, run=None, now=None):
    """Cloud session: does the reviewer answer with the pass in this environment. Never calls
    `place`; the invocation goes through `preflight_probe.cross_vendor_cli_probe`."""
    env = _env(env)
    now = time.time() if now is None else now
    out = {"schema": CONFIRMATION_SCHEMA, "reviewerAnswered": False, "passLapses": None,
           "reason": None}

    def no(reason):
        out["reason"] = reason
        return out

    if not _is_cloud(env):
        return no("not-a-cloud-session")
    if not (isinstance(env.get(PASS_ENV), str) and env[PASS_ENV].strip()):
        return no("no-pass-in-environment")
    _, expected = _decode_pass(env)
    if expected is None:
        return no("pass-unreadable")
    signin = _read_object(_default_signin_path(env))
    if signin is None or signin != expected:
        return no("pass-not-placed")
    if any(env.get(k) for k in ("CODEX_API_KEY", "OPENAI_API_KEY")):
        return no("api-key-in-environment")
    if signin.get("OPENAI_API_KEY") is not None:
        return no("api-key-in-sign-in")
    tokens = signin.get("tokens")
    token = tokens.get("access_token") if isinstance(tokens, dict) else None
    exp = _expiry(token) if isinstance(token, str) else None
    if exp is None:
        return no("pass-expiry-unreadable")
    out["passLapses"] = _date(exp)
    if not exp > now:
        return no("pass-lapsed")

    lib_dir = os.path.dirname(os.path.abspath(__file__))
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    import preflight_probe
    # The expected reply is the word the probe prompt actually asks for, read from that prompt.
    asked = re.findall(r"single word (\w+) and nothing else", preflight_probe.probe_prompt())
    if len(asked) != 1:
        return no("reviewer-did-not-answer")
    real = run if run is not None else subprocess.run
    kept = []

    def keeping_run(argv, **kwargs):
        # Always explicit, and never carrying an API key: the probe must exercise the placed pass.
        probe_env = dict(env)
        probe_env.pop("CODEX_API_KEY", None)
        probe_env.pop(PASS_ENV, None)  # codex reads the placed sign-in; a snapshot would copy it
        kwargs["env"] = probe_env
        try:
            proc = real(argv, **kwargs)
        except Exception:
            kept.append((list(argv), None))
            raise
        kept.append((list(argv), proc))
        return proc

    preflight_probe.cross_vendor_cli_probe("codex", run=keeping_run)
    invoked = list(preflight_probe.cross_vendor_no_op_argv("codex"))
    proc = next((p for argv, p in reversed(kept) if argv == invoked), None)
    if proc is None:
        return no("reviewer-did-not-run")
    if getattr(proc, "returncode", None) != 0:
        return no("reviewer-refused")
    stdout = getattr(proc, "stdout", "")
    if not (isinstance(stdout, str) and stdout.strip() == asked[0]):
        return no("reviewer-answer-unexpected")
    out["reviewerAnswered"] = True
    return out


def record_confirmation(cwd, confirmation, *, account=None, environment=None, now=None,
                        root=None, env=None):
    """Owner's machine: hand a confirmation the reviewer answered to the setup record, which then
    moves only its lapse date. Every other case writes nothing."""
    unreadable = {"action": "refused", "reason": "confirmation-unreadable"}
    if not (isinstance(confirmation, dict) and confirmation.get("schema") == CONFIRMATION_SCHEMA
            and isinstance(confirmation.get("reviewerAnswered"), bool)):
        return unreadable
    if not confirmation["reviewerAnswered"]:
        return {"action": "noop", "reason": "reviewer-did-not-answer"}
    lapses = confirmation.get("passLapses")
    try:
        day = datetime.strptime(lapses, "%Y-%m-%d").date()
        if day.isoformat() != lapses:
            return unreadable
    except (TypeError, ValueError):
        return unreadable
    if day < datetime.fromtimestamp(time.time() if now is None else now, timezone.utc).date():
        return {"action": "noop", "reason": "pass-lapsed"}
    lib_dir = os.path.dirname(os.path.abspath(__file__))
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    import cloud_setup
    account = cloud_setup.launching_account(env, cwd) if account is None else account
    if account is None:
        return {"action": "refused", "reason": "account-unknown"}
    return cloud_setup.confirm_pass(cwd, account, lapses, environment=environment, root=root)


def _record_main(argv):
    parser = argparse.ArgumentParser(prog="cloud_pass.py record-confirmation")
    for option in ("--cwd", "--account", "--environment", "--root"):
        parser.add_argument(option, default=None)
    parser.add_argument("--confirmation", required=True)
    args = parser.parse_args(argv)
    try:
        confirmation = json.loads(args.confirmation)
    except ValueError:
        confirmation = None
    return record_confirmation(args.cwd or os.getcwd(), confirmation, account=args.account,
                               environment=args.environment, root=args.root)


_VERBS = {"make": make, "place": place, "confirm": confirm}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] == ["record-confirmation"]:
        result = _record_main(argv[1:])
    elif len(argv) != 1 or argv[0] not in _VERBS:
        result = _refusal("unknown-verb",
                          "Usage: cloud_pass.py make|place|confirm|record-confirmation")
    else:
        result = _VERBS[argv[0]]()
    sys.stdout.write(json.dumps(result) + "\n")
    return 1 if result.get("action") == "refused" else 0


if __name__ == "__main__":
    sys.exit(main())
