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
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer

import launch_ledger
from launcher import (DEVICE_HUB_AVAILABLE, DEVICE_HUB_ENV, DEVICE_HUB_PROCESS, DEVICE_HUB_UNAVAILABLE,
                      IPHONE_ID_ENV, IPHONE_NONE)

READING_PARAM = "superheroes-reading"
NOT_ESTABLISHED = "could not be established"
READING_WAIT = 3.0  # seconds: the cap on each of the two page-reading waits inside `shot`
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
    # Axis: one value missing, a hub value outside available|unavailable, or an ID neither none nor a canonical phone ID
    if (phone is None or hub is None or hub not in (DEVICE_HUB_AVAILABLE, DEVICE_HUB_UNAVAILABLE)
            or not (phone == IPHONE_NONE or launch_ledger.is_iphone_id(phone))):
        return "did-not-run", _line("whole check", "launch values unreadable")
    # Axis: `none` dominates — no other whole cause is reported next to it
    if phone == IPHONE_NONE:
        return "did-not-run", UFR5
    if hub == DEVICE_HUB_UNAVAILABLE:
        return "did-not-run", _line("whole check", "Device Hub unavailable")
    return "pending", None


def _live_reason(udid):
    returned, code, _ = _run(["pgrep", "-x", DEVICE_HUB_PROCESS], 10)
    # Axis: Device Hub not provably running (pgrep failed, errored or never returned)
    if not (returned and code == 0):
        return "Device Hub unavailable"
    # Axis: no axe binary on PATH
    if shutil.which("axe") is None:
        return "the driver tool (AXe) is missing"
    returned, inv = _inventory(30)
    # Axis: the inventory call timed out, exited non-zero or returned unparseable output
    if not returned or inv is None:
        return "the simulator inventory could not be read"
    # Axis: the inventory was read and the UDID is not in it
    if not device_labels(inv, udid):
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


class Listener(ThreadingHTTPServer):
    daemon_threads = False  # closing waits for a request in flight; its socket timeout bounds that wait


def _derive_labels(window):
    """-> (page, where, notes) from the page readings in the capture window; what cannot be established is NOT_ESTABLISHED."""
    pages, wheres, notes = set(), set(), []
    page_ok = where_ok = True
    for rd in window:
        page = rd.get("page")
        label = _page_label(page) if isinstance(page, str) and page.strip() else ""
        if label.strip():
            pages.add(label)
        else:
            page_ok = False
        if rd.get("where") in ("browser", "installed"):
            wheres.add(rd["where"])
        else:
            where_ok = False
    # Axis: a window reading with a missing, blank or non-string page (or a page that is blank once the reading parameter is stripped)
    if not page_ok:
        notes.append("a page reading carried no usable page")
    # Axis: the readings in the window name more than one page (the page changed during the capture)
    elif len(pages) != 1:
        notes.append("the page changed during the capture")
    # Axis: a window reading whose where is not browser or installed
    if not where_ok:
        notes.append("a page reading carried no usable where")
    # Axis: the readings in the window name more than one context
    elif len(wheres) != 1:
        notes.append("the context changed during the capture")
    page = next(iter(pages)) if page_ok and len(pages) == 1 else NOT_ESTABLISHED
    where = next(iter(wheres)) if where_ok and len(wheres) == 1 else NOT_ESTABLISHED
    return page, where, notes


def shot(phone, out, run_dir, token, timeout):
    """Screenshot a phone. `page` and `where` come only from the readings the phone's page posts during the call."""
    call_start_ms, end = time.time() * 1000, time.monotonic() + timeout
    res = {"ok": False, "returned": False, "path": out, "sha256": None, "labels": None, "labelNote": None}
    collected, cond, conns = [], threading.Condition(), set()
    requests = []  # one state per connection: request bytes delivered, and whether a POST body was fully parsed
    visible = lambda rd: rd.get("visibility") == "visible"

    def left():
        return max(end - time.monotonic(), 0.1)

    def wait_until(found):
        stop = time.monotonic() + max(min(READING_WAIT, end - time.monotonic()), 0)
        with cond:
            while not found():
                if (rest := stop - time.monotonic()) <= 0:
                    return False
                cond.wait(rest)
            return True

    class Counted:
        """Unbuffered request reader that counts the bytes a connection actually delivered, even when it stalls mid-line."""
        def __init__(self, raw, state):
            self.raw, self.state = raw, state

        def _byte(self):
            b = self.raw.read(1)
            self.state["bytes"] += len(b or b"")
            return b

        def readline(self, limit=-1):
            out = b""
            while limit < 0 or len(out) < limit:
                if not (b := self._byte()):
                    break
                out += b
                if b == b"\n":
                    break
            return out

        def read(self, n=-1):
            out = b""
            while n < 0 or len(out) < n:
                if not (b := self._byte()):
                    break
                out += b
            return out

        def __getattr__(self, name):
            return getattr(self.raw, name)

    class Handler(BaseHTTPRequestHandler):
        rbufsize = 0

        def handle(self):
            # Axis: a request still in flight when the call ends is tracked so it can be drained, then cut at the deadline
            with cond:
                conns.add(self.connection)
            try:
                super().handle()
            finally:
                with cond:
                    conns.discard(self.connection)
                    cond.notify_all()

        def setup(self):
            # Axis: a POST that stalls is dropped once the call's budget runs out, never outliving it
            self.timeout = max(min(2, end - time.monotonic()), 0.05)
            super().setup()
            self.state = {"bytes": 0, "parsed": False}
            self.rfile = Counted(self.rfile, self.state)
            with cond:
                requests.append(self.state)

        def do_POST(self):
            try:
                reading = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 1 << 20)))
                self.state["parsed"] = True
            except (ValueError, OSError):
                reading = None
            # Axis: hidden readings are kept too (a fresh, token-matched one is a visibility-loss observation); only visible ones label
            if isinstance(reading, dict) and accept_reading({**reading, "visibility": "visible"}, self.path, token,
                                                            reading.get("where"), call_start_ms):
                with cond:
                    collected.append((time.monotonic(), reading))
                    cond.notify_all()
            try:
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
            except OSError:
                pass  # the connection was cut at the call's deadline

        def log_message(self, *a):
            pass

    server, note, after_ms = None, None, None
    shot_start_ms = time.time() * 1000
    try:
        # Axis: a token or session the page's readings cannot be tied to (bad token, missing or malformed session file)
        try:
            if not re.fullmatch(r"[0-9a-f]+", token):
                raise ValueError("bad token")
            with open(os.path.join(run_dir, "sessions", token + ".json")) as fh:
                session = json.load(fh)
            session_phone, port = str(session["phone"]), int(session["port"])
        except (OSError, ValueError, KeyError, TypeError):
            note = "no usable session for this token, so no page reading could be matched to this capture"
        else:
            # Axis: a session opened on another phone — its readings are not this phone's
            if session_phone.upper() != phone.upper():
                note = "the session belongs to another phone"
            else:
                try:
                    server = Listener(("127.0.0.1", port), Handler)
                except OSError:
                    note = "the page-reading listener could not start"
        if server is not None:
            threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
            # Axis: no page reading arrived before the capture
            if not wait_until(lambda: any(visible(rd) for _, rd in collected)):
                note = "no page reading arrived before the capture"
        shot_start_ms = time.time() * 1000
        returned, code, _ = _run(["xcrun", "simctl", "io", phone, "screenshot", out], left())
        res["returned"] = returned
        shot_end_mono, shot_end_ms = time.monotonic(), time.time() * 1000
        if not (returned and code == 0 and os.path.isfile(out)):
            return res
        if server is not None and note is None:
            def first_after():
                # Axis: a reading is "after" only if it was received after the screenshot returned AND taken after it
                return next((i for i, (got, rd) in enumerate(collected)
                             if visible(rd) and got >= shot_end_mono and rd["takenAt"] >= shot_end_ms), None)
            if wait_until(lambda: first_after() is not None):
                with cond:
                    after_ms = collected[first_after()][1]["takenAt"]
            else:
                note = "no page reading arrived after the capture"
    finally:
        if server is not None:
            server.shutdown()
            # Axis: requests in flight are drained (a reading taken during the capture may land late), but never past the call's budget
            drain = max(end, time.monotonic() + 0.2)
            with cond:
                while conns and (rest := drain - time.monotonic()) > 0:
                    cond.wait(rest)
                for conn in list(conns):
                    try:
                        conn.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
            server.server_close()
    window, notes = [], []
    if after_ms is not None:
        # The window is every reading taken up to the first reading after the capture, whatever order the posts landed in
        window = [rd for _, rd in collected if visible(rd) and rd["takenAt"] <= after_ms]
    page, where, notes = _derive_labels(window) if window else (NOT_ESTABLISHED, NOT_ESTABLISHED, [])
    # Axis: the page left the foreground during the capture window — the screenshot may show something else
    # The capture context is the one the visible window agrees on; an observation concerns it when it is from that context
    # (or from none of the two awaited contexts), and an observation whose visibility is neither "visible" nor "hidden"
    # concerns it whatever its context; only an explicitly hidden reading from the other context is excluded. Every such observation from the latest one before the capture (ties
    # included, whatever order the posts landed in) through the first after it must be visible, or the labels are void.
    if window:
        wheres = {rd.get("where") for rd in window}
        candidate = next(iter(wheres)) if len(wheres) == 1 else None
        concerns = [rd for _, rd in collected
                    if candidate is None or rd.get("where") == candidate or rd.get("where") not in ("browser", "installed")
                    or rd.get("visibility") not in ("visible", "hidden")]
        start = max((rd["takenAt"] for rd in concerns if rd["takenAt"] <= shot_start_ms), default=shot_start_ms)
        if any(not visible(rd) and start <= rd["takenAt"] <= after_ms for rd in concerns):
            page, where = NOT_ESTABLISHED, NOT_ESTABLISHED
            notes.append("the page left the foreground during the capture")
    # Axis: a connection delivered request bytes but no fully parsed POST body (stall in the headers, timeout, cut at drain,
    # bad body), so an observation that could contradict the labels is missing. A bare connect delivers no bytes and is not one.
    with cond:
        cut_off = any(st["bytes"] > 0 and not st["parsed"] for st in requests)
    if cut_off:
        page, where = NOT_ESTABLISHED, NOT_ESTABLISHED
        notes.append("a page reading was cut off")
    res["returned"], res["labels"], err = _labels(phone, page, where, left())
    if err is not None:
        res["error"] = err
    if res["labels"]:
        with open(out, "rb") as fh:
            res["sha256"] = hashlib.sha256(fh.read()).hexdigest()
        res["ok"] = True
        res["labelNote"] = note or "; ".join(notes) or None
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


def _field_key(focused):
    f = focused if isinstance(focused, dict) else {}
    return next((f"{k}:{f[k]}" for k in ("id", "name") if isinstance(f.get(k), str) and f[k]), None)


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
        # Axis: a tap whose after-reading does not focus the intended field (a missed tap leaves another field focused); the target is the field's id, or name:<name> when it has no id
        target = step.get("target")
        if not (isinstance(target, str) and target and (key := _field_key(after_focus)) and target == (after_focus["id"] if key[:3] == "id:" else key)):
            return False, "the intended field did not receive focus"
        return True, "field focused and keyboard seen"
    if kind == "type":
        key, akey = _field_key((before or {}).get("focused")), _field_key(after_focus)
        # Axis: typed text (password or not) whose before and after readings do not name the same field (a value change or screen change elsewhere is not the typed field's)
        if key is None or key != akey:
            return False, "the field could not be identified" if None in (key, akey) else "the focus moved to another field"
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


def _screenshot_located(ev):
    """A screenshot is rendered only when readers can open it (url) or the file is named and hashed (path + sha256)."""
    return bool(ev.get("url")) or (bool(ev.get("path")) and isinstance(ev.get("sha256"), str) and bool(ev["sha256"]))


def _complete_reading(rd):
    """A reading carries a numeric visibleHeight, a where in browser|installed and a focused key (null allowed)."""
    return (isinstance(rd, dict) and isinstance(rd.get("visibleHeight"), (int, float))
            and not isinstance(rd.get("visibleHeight"), bool) and rd.get("where") in ("browser", "installed")
            and "focused" in rd)


def _has_installed_reading(check):
    return any(isinstance(e, dict) and e.get("kind") == "reading" and (e.get("labels") or {}).get("where") == "installed"
               and _complete_reading(e.get("reading")) and e["reading"]["where"] == "installed"
               for e in check.get("evidence") or [])


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
            # Axis: a reading missing a measurement the section prints (height, where, focused) is refused
            if not _complete_reading(ev["reading"]):
                raise ValueError(f"evidence {n}: the reading lacks visibleHeight, where or focused")
        elif ev.get("kind") != "screenshot" or not _screenshot_located(ev):
            raise ValueError(f"evidence {n} is neither a located screenshot nor a reading")
        # Axis: a screenshot whose where label is neither a context nor the fixed not-established value
        elif labels["where"] not in ("browser", "installed", NOT_ESTABLISHED):
            raise ValueError(f"evidence {n}: a screenshot's where label is not browser, installed or {NOT_ESTABLISHED}")
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
            # Axis: a PR comment shows an image only by a URL its readers can open; a local path is named, not embedded
            if ev.get("url"):
                out.append(f"![{ev.get('caption', '')}]({ev['url']})")
            else:
                out.append(f"screenshot file (on the capturing Mac, not posted): {ev['path']} · sha256 {ev['sha256']}")
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
            ("drive", ("phone",), 30), ("shot", ("phone", "out", "run-dir", "token"), 30),
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
        return shot(a.phone, a.out, a.run_dir, a.token, a.timeout)
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
