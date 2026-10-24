"""The host model a session is running on, from the best record available (#2110).

The session-start hook exports the start event's model as `SUPERHEROES_HOST_MODEL`, and empty when
the event names none. A session whose start event omits the model used to read as
`host-model-unknown`, which left `hostFamily` None and made a native Claude reviewer ineligible, so
the panel dropped every Claude seat. This module adds the second record: the model of the latest
main-chain assistant turn of this session's own transcript written since this start.

The hook never reads the transcript for a model (on `resume` the file already holds a previous
run's turns). It exports the transcript path and the file's size at start (the byte offset the
reader begins from), and seat composition reads the model at the time of use. A model recorded
before this start, a subagent's turn or a parent session's record never stands in for the live one.

Stdlib only. No public function raises.
"""
import json
import os
import re

HOST_MODEL_ENV = "SUPERHEROES_HOST_MODEL"
TRANSCRIPT_ENV = "SUPERHEROES_SESSION_TRANSCRIPT"
TRANSCRIPT_FROM_ENV = "SUPERHEROES_SESSION_TRANSCRIPT_FROM"
SESSION_ENV_VARS = (HOST_MODEL_ENV, TRANSCRIPT_ENV, TRANSCRIPT_FROM_ENV)

_HOST_MODEL_RE = re.compile(r"^[A-Za-z0-9._:/\[\]-]{1,128}$")
_MAX_PATH = 4096
_BLOCK = 64 * 1024


def shape_ok(value):
    """The stripped value when it has the shape of a model id, else empty."""
    if not isinstance(value, str):
        return ""
    value = value.strip()
    return value if _HOST_MODEL_RE.match(value) else ""


def from_payload(payload):
    """Shape-checked host model from the SessionStart payload, or empty."""
    try:
        model = payload.get("model")
        if isinstance(model, str):
            return shape_ok(model)
        if isinstance(model, dict):
            return shape_ok(model.get("id"))
    except Exception:
        pass
    return ""


def transcript_from_payload(payload):
    """`(path, start)` for the payload's transcript: the path when it is an absolute, bounded,
    single-line string that encodes as strict UTF-8 (the env file is written in UTF-8), and the
    file's size now as the byte offset this session starts from ('0' when the file does not exist
    yet, '' when its size cannot be read). Else ('', '')."""
    try:
        path = payload.get("transcript_path")
        if (not isinstance(path, str) or not os.path.isabs(path) or len(path) > _MAX_PATH
                or "\n" in path or "\r" in path or "\x00" in path):
            return "", ""
        path.encode("utf-8")
        try:
            return path, str(os.path.getsize(path))
        except FileNotFoundError:
            return path, "0"
        except Exception:
            return path, ""
    except Exception:
        return "", ""


def _line_model(line):
    """The shape-checked model of one transcript line when it is a main-chain assistant turn."""
    try:
        obj = json.loads(line.decode("utf-8"))
    except Exception:
        return ""
    if not isinstance(obj, dict) or obj.get("type") != "assistant" or obj.get("isSidechain") is True:
        return ""
    message = obj.get("message")
    return shape_ok(message.get("model")) if isinstance(message, dict) else ""


def from_transcript(path, start):
    """The model of the last main-chain assistant turn at or after byte offset `start` of the
    transcript at `path`, or empty. `start` is the env/flag string and must be all ASCII digits."""
    try:
        if (not isinstance(path, str) or not path or not isinstance(start, str) or not start
                or not start.isascii() or not start.isdigit()):
            return ""
        begin = int(start)
        with open(path, "rb") as fh:
            size = os.fstat(fh.fileno()).st_size
            if begin > size:
                return ""
            at_line_start = begin == 0
            if not at_line_start:
                fh.seek(begin - 1)
                at_line_start = fh.read(1) == b"\n"
            pos, carry = size, b""
            while pos > begin:
                lo = max(begin, pos - _BLOCK)
                fh.seek(lo)
                data = fh.read(pos - lo) + carry
                pos = lo
                parts = data.split(b"\n")
                carry = parts[0]
                for line in reversed(parts[1:]):
                    model = _line_model(line)
                    if model:
                        return model
            # `carry` is now the first line of the region; a partial line at the boundary is ignored.
            return _line_model(carry) if at_line_start else ""
    except Exception:
        return ""


def resolve(host_model, transcript_path, transcript_start):
    """`(model, source)`: the start event's model wins, else this session's transcript, else none."""
    try:
        model = shape_ok(host_model)
        if model:
            return model, "start-event"
        model = from_transcript(transcript_path, transcript_start)
        if model:
            return model, "transcript"
    except Exception:
        pass
    return "", "none"
