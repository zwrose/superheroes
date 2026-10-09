#!/usr/bin/env python3
"""iPhone check driver — a simulated phone, one JSON object per verb.

Evidence that a check ran is produced only from an observation: no verb or function turns a
driver's exit code, a missing reading, a reading from the wrong context, or an unlabelled capture
into a completed step or a renderable piece of evidence, and a password field's value never leaves
the page or this tool. Every subprocess goes through ``_run`` (a timeout is ``returned: False``)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

IPHONE_ID_ENV = "SUPERHEROES_IPHONE_ID"
DEVICE_HUB_ENV = "SUPERHEROES_DEVICE_HUB"
READING_PARAM = "superheroes-reading"
UDID_RE = re.compile(r"[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}")
SIX = ("phone", "model", "iOS", "page", "where", "source")
GAPS = ("**What a simulator cannot show:** a real finger's touch (the timing and imprecision of a human "
        "tap, and multi-finger gestures) and real-device speed.")
_WHERE = {("browser",): "in the browser", ("installed",): "in the installed web app",
          ("browser", "installed"): "in the browser and in the installed web app"}


def _line(part, reason):
    return f"iPhone check did not run — {part}: {reason}"


UFR5 = _line("whole check", "no phone for this lane")


def _run(argv, timeout, env=None):
    """The one subprocess seam -> (returned, exit, stdout). A timeout never returned."""
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return False, None, ""
    except OSError:
        return True, 127, ""
    return True, p.returncode, p.stdout


def _inventory(timeout):
    returned, code, out = _run(["xcrun", "simctl", "list", "devices", "-j"], timeout)
    try:
        inv = json.loads(out) if returned and code == 0 else None
    except ValueError:
        inv = None
    return returned, inv if isinstance(inv, dict) else None


def device_labels(inv, udid):
    """Model, iOS and state of one phone from the parsed inventory, or None when it is not there."""
    devices = inv.get("devices") if isinstance(inv, dict) else None
    for runtime, devs in (devices.items() if isinstance(devices, dict) else ()):
        for d in devs if isinstance(devs, list) else ():
            if isinstance(d, dict) and str(d.get("udid", "")).upper() == udid.upper():
                version = re.search(r"SimRuntime\.iOS-(\d+(?:-\d+)*)$", runtime)
                dtype = str(d.get("deviceTypeIdentifier", ""))
                if not version or ".SimDeviceType." not in dtype:
                    return None
                return {"model": dtype.split(".SimDeviceType.", 1)[1].replace("-", " "),
                        "iOS": version.group(1).replace("-", "."), "state": d.get("state")}
    return None


def _labels(phone, page, where, timeout):
    """-> (returned, six labels | None, error). The phone is read from the live inventory."""
    returned, inv = _inventory(timeout)
    if not returned:
        return False, None, "the phone inventory never returned"
    info = device_labels(inv, phone)
    if info is None:
        return True, None, "the phone is not on this Mac"
    # Axis: a phone that is not Booted at capture time yields no labels, so no evidence
    if info["state"] != "Booted":
        return True, None, "the phone is not booted"
    return True, {"phone": phone, "model": info["model"], "iOS": info["iOS"], "page": page,
                  "where": where, "source": "Simulator"}, None


def classify_env(environ, issue_names_check=False):
    """The launch values alone -> ("off" | "did-not-run", line | None), or ("pending", None)."""
    phone, hub = environ.get(IPHONE_ID_ENV), environ.get(DEVICE_HUB_ENV)
    if phone is None and hub is None:
        # Axis: both unset — the lane asked for no phone; only an issue naming the check makes it a line
        return ("did-not-run", UFR5) if issue_names_check else ("off", None)
    # Axis: one value missing, a hub value outside available|unavailable, or an ID neither none nor a UDID
    if (phone is None or hub is None or hub not in ("available", "unavailable")
            or not (phone == "none" or UDID_RE.fullmatch(phone))):
        return "did-not-run", _line("whole check", "launch values unreadable")
    # Axis: `none` dominates — no other whole cause is reported next to it
    if phone == "none":
        return "did-not-run", UFR5
    if hub == "unavailable":
        return "did-not-run", _line("whole check", "Device Hub unavailable")
    return "pending", None


def _live_reason(udid):
    returned, code, _ = _run(["pgrep", "-x", "DeviceHub"], 10)
    # Axis: Device Hub not provably running (pgrep failed, errored or never returned)
    if not (returned and code == 0):
        return "Device Hub unavailable"
    # Axis: no axe binary on PATH
    if shutil.which("axe") is None:
        return "the driver tool (AXe) is missing"
    returned, inv = _inventory(30)
    # Axis: the UDID is not in the live inventory (an unreadable inventory counts as absent)
    if not (returned and device_labels(inv, udid)):
        return "the phone is not on this Mac"
    return None


def preflight(environ, issue_names_check=False):
    state, line = classify_env(environ, issue_names_check)
    udid = environ.get(IPHONE_ID_ENV)
    if state == "pending":
        reason = _live_reason(udid)
        state, line = ("ready", None) if reason is None else ("did-not-run", _line("whole check", reason))
    return {"ok": state == "ready", "state": state, "phone": udid if state == "ready" else None, "line": line}


def boot(phone, timeout):
    end = time.monotonic() + timeout
    code = None
    # An already-booted phone makes `boot` exit non-zero, so only `bootstatus` decides.
    for argv in (["xcrun", "simctl", "boot", phone], ["xcrun", "simctl", "bootstatus", phone, "-b"]):
        returned, code, _ = _run(argv, max(end - time.monotonic(), 0.1))
        if not returned:
            return {"ok": False, "returned": False, "line": _line("whole check", "the phone's boot never returned")}
    ok = code == 0
    return {"ok": ok, "returned": True, "line": None if ok else _line("whole check", "the phone did not boot")}


def open_url(phone, url, run_dir, timeout):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    token = secrets.token_hex(8)
    base, hash_, frag = url.partition("#")
    full = f"{base}{'&' if '?' in base else '?'}{READING_PARAM}=http://127.0.0.1:{port}/{token}{hash_}{frag}"
    returned, code, _ = _run(["xcrun", "simctl", "openurl", phone, full], timeout)
    ok = returned and code == 0
    if ok:
        os.makedirs(os.path.join(run_dir, "sessions"), exist_ok=True)
        with open(os.path.join(run_dir, "sessions", token + ".json"), "w") as fh:
            json.dump({"token": token, "port": port, "phone": phone, "url": full}, fh)
    return {"ok": ok, "returned": returned, "token": token, "port": port, "url": full}


def drive(phone, args, timeout):
    argv = ["axe", *args]
    if args[0] == "tap" and not any(a.startswith("--post-delay") for a in args):
        argv += ["--post-delay", "1"]  # AXe drops taps without it (cameroncooke/AXe#71)
    returned, code, out = _run(argv + ["--udid", phone], timeout, {**os.environ, "AXE_HID_STABILIZATION_MS": "2000"})
    return {"ok": returned and code == 0, "returned": returned, "exit": code, "stdout": out}


def shot(phone, out, page, where, timeout):
    res = {"ok": False, "returned": False, "path": out, "sha256": None, "labels": None}
    returned, code, _ = _run(["xcrun", "simctl", "io", phone, "screenshot", out], timeout)
    res["returned"] = returned
    if not (returned and code == 0 and os.path.isfile(out)):
        return res
    res["returned"], res["labels"], res["error"] = _labels(phone, page, where, timeout)
    if res["labels"]:
        with open(out, "rb") as fh:
            res["sha256"] = hashlib.sha256(fh.read()).hexdigest()
        res["ok"] = True
    return res


def accept_reading(reading, path, token, where, since_ms):
    """True only for a fresh, visible reading from the awaited context, posted to this session's token."""
    if not isinstance(reading, dict):
        return False
    # Axis: a POST to any path but this session's token
    if path != "/" + token:
        return False
    # Axis: a reading from the other context (Safari while waiting for the installed app, or the reverse)
    if reading.get("where") != where:
        return False
    # Axis: a hidden page
    if reading.get("visibility") != "visible":
        return False
    taken = reading.get("takenAt")
    # Axis: a reading taken before the call began (stale), or with no usable timestamp
    return isinstance(taken, (int, float)) and not isinstance(taken, bool) and taken >= since_ms


def strip_password_value(reading):
    out = dict(reading)
    focus = out.get("focused")
    # Axis: a password-focused reading keeps no value, whatever the page sent
    if isinstance(focus, dict) and str(focus.get("type")).lower() == "password":
        out.pop("value", None)
        out["valueWithheld"] = True
    return out


def _page_label(page):
    base, q, query = str(page or "").partition("?")
    query, h, frag = query.partition("#")
    keep = "&".join(p for p in query.split("&") if p and p.split("=", 1)[0] != READING_PARAM)
    return base + ("?" + keep if keep and q else "") + h + frag


def read(run_dir, token, where, timeout):
    since, end = time.time() * 1000, time.monotonic() + timeout
    accepted = []

    class Handler(BaseHTTPRequestHandler):
        timeout = 2

        def do_POST(self):
            try:
                reading = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 1 << 20)))
            except (ValueError, OSError):
                reading = None
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            if accept_reading(reading, self.path, token, where, since):
                accepted.append(strip_password_value(reading))

        def log_message(self, *a):
            pass

    try:
        if not re.fullmatch(r"[0-9a-f]+", token):
            raise ValueError("bad token")
        with open(os.path.join(run_dir, "sessions", token + ".json")) as fh:
            session = json.load(fh)
        server = HTTPServer(("127.0.0.1", int(session["port"])), Handler)
    except (OSError, ValueError, KeyError, TypeError) as e:
        return {"ok": False, "returned": True, "reading": None, "labels": None, "error": str(e)}
    with server:
        while not accepted and time.monotonic() < end:
            server.timeout = min(end - time.monotonic(), 0.25)
            server.handle_request()
    if not accepted:
        return {"ok": False, "returned": False, "reading": None, "labels": None}
    returned, labels, err = _labels(session["phone"], _page_label(accepted[0].get("page")), where, 30)
    if labels is None:
        return {"ok": False, "returned": returned, "reading": None, "labels": None, "error": err}
    return {"ok": True, "returned": True, "reading": accepted[0], "labels": labels}


def judge_step(step):
    """-> (completed, reason). Anything needed and null or missing is not completed."""
    kind, before, after = step.get("kind"), step.get("before"), step.get("after")
    after_focus = after.get("focused") if isinstance(after, dict) else None
    if kind == "tap-field":
        # Axis: a tap with no field focused afterwards
        if not after_focus:
            return False, "no field focused after the tap"
        # Axis: a tap with no keyboard seen
        if step.get("keyboardSeen") is not True:
            return False, "no keyboard seen after the tap"
        return True, "field focused and keyboard seen"
    if kind == "type":
        if step.get("password") is True or (isinstance(after_focus, dict) and after_focus.get("type") == "password"):
            # Axis: password typing leaves no value to compare, so only a changed screen counts
            if step.get("screenChanged") is not True:
                return False, "password typing: the screen did not change"
            return True, "password typing: the screen changed"
        old, new = (before or {}).get("value"), (after or {}).get("value")
        # Axis: typed text whose value is unchanged (or unreadable in either reading)
        if not (isinstance(old, str) and isinstance(new, str) and new != old):
            return False, "the field's value did not change"
        return True, "the field's value changed"
    if kind == "other":
        expected = step.get("expected")
        # Axis: a step that names no expected change cannot be observed to have worked
        if not (isinstance(expected, str) and expected.strip()):
            return False, "no expected change named"
        # Axis: the expected change was not seen
        if step.get("expectedSeen") is not True:
            return False, "the expected change was not seen"
        return True, "the expected change was seen"
    return False, "unknown step kind"


def _has_installed_reading(check):
    return any(isinstance(e, dict) and e.get("kind") == "reading" and (e.get("labels") or {}).get("where") == "installed"
               and (e.get("reading") or {}).get("where") == "installed" for e in check.get("evidence") or [])


def did_not_run_lines(check):
    # Axis: no phone for the lane — the UFR-5 line alone, whatever else is set
    if check.get("noPhone"):
        return [UFR5]
    # Axis: a whole-check cause is one whole line, never one per part
    if check.get("whole"):
        return [_line("whole check", check["whole"])]
    lines = []
    for part in ("browser", "installed"):
        p = (check.get("parts") or {}).get(part) or {}
        # Axis: only an included part can owe a line
        if not p.get("included", part in (check.get("where") or [])):
            continue
        done, reason = p.get("completed") is True, p.get("reason") or "not attempted"
        # Axis: FR-9 — an installed part is not completed without a reading taken in the installed app
        if part == "installed" and done and not _has_installed_reading(check):
            done, reason = False, "no page reading from the installed app"
        if not done:
            lines.append(_line({"browser": "browser check", "installed": "installed-app check"}[part], reason))
    return lines


def render(check):
    """-> (opening, section). Raises ValueError rather than emit evidence it cannot label."""
    evidence = check.get("evidence") or []
    for n, ev in enumerate(evidence, 1):
        labels = ev.get("labels") if isinstance(ev, dict) else None
        # Axis: evidence missing (absent, blank or non-string) any of the six labels is refused, never rendered bare
        if not isinstance(labels, dict) or any(not isinstance(labels.get(k), str) or not labels[k].strip() for k in SIX):
            raise ValueError(f"evidence {n} lacks one of the six labels")
        # Axis: evidence not taken from the Simulator
        if labels["source"] != "Simulator":
            raise ValueError(f"evidence {n} has source {labels['source']!r}, not Simulator")
        if ev.get("kind") == "reading":
            # Axis: a reading whose where label disagrees with the reading's own where
            if not isinstance(ev.get("reading"), dict) or labels["where"] != ev["reading"].get("where"):
                raise ValueError(f"evidence {n}: where label disagrees with the reading")
        elif ev.get("kind") != "screenshot" or not (ev.get("url") or ev.get("path")):
            raise ValueError(f"evidence {n} is neither a located screenshot nor a reading")
    opening = "\n\n".join(did_not_run_lines(check))
    if not evidence and (check.get("noPhone") or check.get("whole")):
        return opening, ""
    where = tuple(p for p in ("browser", "installed") if p in (check.get("where") or []))
    if where not in _WHERE or check.get("chosenBy") not in ("issue", "lane"):
        raise ValueError("where or chosenBy is not one of the contract's values")
    out = ["### iPhone check", f"**Where the check ran:** {_WHERE[where]} — chosen by the {check['chosenBy']}.", GAPS]
    for n, ev in enumerate(evidence, 1):
        lb = ev["labels"]
        out.append(f"#### iPhone evidence {n} — {ev['kind']} ({ev.get('part')}): {ev.get('caption', '')}")
        out.append(" · ".join(f"`{k}` {lb[k]}" for k in SIX))
        if ev["kind"] == "screenshot":
            out.append(f"![{ev.get('caption', '')}]({ev.get('url') or ev.get('path')})")
            continue
        rd = ev["reading"]
        f = rd.get("focused")
        focus = "none" if not isinstance(f, dict) else f"{f.get('tag')}{'#' + f['id'] if f.get('id') else ''} ({f.get('type')})"
        # Axis: a password-focused reading shows no value even if the evidence carries one
        if rd.get("valueWithheld") is True or (isinstance(f, dict) and f.get("type") == "password"):
            value = "withheld"
        else:
            value = f'"{rd["value"]}"' if isinstance(rd.get("value"), str) else "none"
        out.append(f"visible height {rd.get('visibleHeight')} · focused {focus} · value {value}")
    return opening, "\n\n".join(out)


def _parser():
    p = argparse.ArgumentParser(prog="iphone_check")
    sub = p.add_subparsers(dest="verb", required=True)
    for verb, flags, timeout in (
            ("preflight", (), None), ("boot", ("phone",), 120), ("open", ("phone", "url", "run-dir"), 30),
            ("drive", ("phone",), 30), ("shot", ("phone", "out", "page", "where"), 30),
            ("read", ("run-dir", "token", "where"), 15), ("judge", (), None), ("render", ("in",), None)):
        s = sub.add_parser(verb)
        for f in flags:
            s.add_argument("--" + f, required=True, choices=["browser", "installed"] if f == "where" else None)
        if timeout:
            s.add_argument("--timeout", type=float, default=timeout)
    sub.choices["preflight"].add_argument("--issue-names-check", action="store_true")
    return p


def _dispatch(a, rest):
    if a.verb == "preflight":
        return preflight(os.environ, a.issue_names_check)
    if a.verb == "boot":
        return boot(a.phone, a.timeout)
    if a.verb == "open":
        return open_url(a.phone, a.url, a.run_dir, a.timeout)
    if a.verb == "drive":
        return drive(a.phone, rest, a.timeout) if rest else {"ok": False, "error": "drive needs axe args after --"}
    if a.verb == "shot":
        return shot(a.phone, a.out, a.page, a.where, a.timeout)
    if a.verb == "read":
        return read(a.run_dir, a.token, a.where, a.timeout)
    try:
        if a.verb == "judge":
            step = json.load(sys.stdin)
            if not isinstance(step, dict):
                raise ValueError("a step is a JSON object")
            completed, reason = judge_step(step)
            return {"ok": True, "completed": completed, "reason": reason}
        with open(a.__dict__["in"]) as fh:
            opening, section = render(json.load(fh))
        return {"ok": True, "opening": opening, "section": section}
    except (ValueError, OSError, AttributeError, TypeError) as e:
        return {"ok": False, "error": str(e)}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    rest = []
    if "--" in argv:
        i = argv.index("--")
        argv, rest = argv[:i], argv[i + 1:]
    args = _parser().parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    out = _dispatch(args, rest)
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
