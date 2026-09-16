"""Single entry for reading and validating a dispatch seat bundle (#1269).

A caller supplies a four-key JSON seat ``{vendor, model, effort, role}`` at dispatch
entry. Downstream code receives the validated bundle intact; no function re-assembles
scalars or resolves role outside ``resolve_entry``.
"""
from __future__ import annotations

import inspect
import json

import dispatch_guard
import model_registry

_BUILD_ARGV_RUN_KINDS = frozenset({"review", "build", "fix"})
_DROPPED_FLAGS = ("--engine", "--model", "--effort", "--engine-model", "--vendor", "--role")
_LEGACY_KEYWORDS = frozenset({"engine", "model", "effort", "engine_model", "role"})
_MODE_BRIEF_CHECK = "brief-check"


def _signature_accepted_params(func) -> str:
    params = []
    for name, param in inspect.signature(func).parameters.items():
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        if name in ("args", "kwargs"):
            continue
        params.append(name)
    return ", ".join(params)


def _dispatch_review_accepted() -> str:
    import engine_dispatch  # noqa: WPS433 — lazy: avoid import cycle at module load

    return _signature_accepted_params(engine_dispatch.dispatch_review)


def _dispatch_write_accepted() -> str:
    import engine_dispatch  # noqa: WPS433 — lazy: avoid import cycle at module load

    return _signature_accepted_params(engine_dispatch.dispatch_write)

_SEAT_JSON_SHAPE = (
    'JSON object {"vendor": "<vendor>", "model": "<id>|null", "effort": <str|null>, '
    '"role": "<role>"} (the effort key is required; its value may be null; role is '
    "required and must not be null)"
)
_ACCEPTED_SEAT = _SEAT_JSON_SHAPE
_ENTRY_VERBS = frozenset({
    "dispatch-review", "dispatch-write", "build-argv", "guard-check",
})


def _format_valid(values: tuple[str, ...]) -> str:
    return ", ".join(values)


def accepted_seat_detail() -> str:
    return f"pass --seat as {_ACCEPTED_SEAT}"


def accepted_role_detail() -> str:
    roles = _format_valid(model_registry.roles())
    return f'role must be a member of the seat JSON "role" key; valid roles: {roles}'


def legacy_refusal(*, dropped_flags: tuple[str, ...] | None = None) -> dict:
    """Structured refusal for dropped CLI flags or legacy library call shapes."""
    parts = [
        "dispatch seat must be supplied as a whole via --seat;",
        accepted_seat_detail() + ".",
    ]
    if dropped_flags:
        flags = ", ".join(sorted(set(dropped_flags)))
        role_note = ""
        if "--role" in dropped_flags:
            role_note = " (role now travels inside --seat)"
        parts.insert(
            0,
            f"removed flag(s) {flags} are no longer accepted "
            f"(vendor and role now live inside the --seat bundle, not separate flags)"
            f"{role_note};",
        )
    return {
        "ok": False,
        "reason": "legacy-seat-args",
        "detail": " ".join(parts),
    }


def scan_dropped_flags(argv: list[str]) -> list[str]:
    """Return dropped legacy flags present in argv (both spellings)."""
    found: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        matched = None
        for flag in _DROPPED_FLAGS:
            if arg == flag:
                matched = flag
                break
            prefix = flag + "="
            if arg.startswith(prefix):
                matched = flag
                break
        if matched is not None:
            if matched not in found:
                found.append(matched)
            if arg == matched and i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 2
                continue
        i += 1
    return found


def legacy_call_detected(args: tuple, kwargs: dict) -> bool:
    if args:
        return True
    return bool(_LEGACY_KEYWORDS & kwargs.keys())


def unknown_kwargs_detected(kwargs: dict) -> tuple[str, ...]:
    if not kwargs:
        return ()
    return tuple(sorted(kwargs.keys()))


def unknown_kwargs_refusal(unknown_keys: tuple[str, ...], *, accepted_params: str) -> dict:
    keys = ", ".join(unknown_keys)
    return {
        "ok": False,
        "reason": "unknown-dispatch-kwargs",
        "detail": (
            f"unknown keyword argument(s) {keys}; "
            f"accepted parameters: {accepted_params}; "
            f"{accepted_seat_detail()}; {accepted_role_detail()}."
        ),
    }


def dispatch_review_accepted_params() -> str:
    return _dispatch_review_accepted()


def dispatch_write_accepted_params() -> str:
    return _dispatch_write_accepted()


def _normalize_effort(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return stripped.casefold().replace("_", "-")


def _match_effort(value: str | None, allowed: tuple[str, ...]) -> str | None:
    if not allowed:
        return None
    norm = _normalize_effort(value)
    if norm is None:
        return None
    for candidate in allowed:
        if _normalize_effort(candidate) == norm:
            return candidate
    return None


def _cross_vendor_effort_hint(effort: str) -> str | None:
    norm = _normalize_effort(effort)
    if norm is None:
        return None
    hits: list[str] = []
    for vendor in model_registry.vendors():
        for allowed in model_registry.effort_enum(vendor):
            if _normalize_effort(allowed) == norm:
                hits.append(vendor)
                break
    if len(hits) == 1:
        return f"effort {effort!r} is valid for vendor {hits[0]!r}, not for this model"
    if len(hits) > 1:
        return (
            f"effort {effort!r} is valid for vendors "
            f"{_format_valid(tuple(hits))}, not for this model"
        )
    return None


def _model_allowed_efforts(vendor: str, model_id: str) -> tuple[str, ...] | None:
    if not model_registry.is_registered(vendor, model_id):
        return None
    return model_registry.allowed_efforts(vendor, model_id)


def _parse_json(raw: str) -> dict:
    try:
        obj = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {
            "ok": False,
            "reason": "seat-unparseable",
            "detail": (
                f"seat value is neither valid JSON nor a composed token; "
                f"accepted: {_ACCEPTED_SEAT}"
            ),
        }
    if not isinstance(obj, dict):
        return {
            "ok": False,
            "reason": "seat-not-object",
            "detail": f"seat JSON must be an object; accepted: {_ACCEPTED_SEAT}",
        }
    if "effort" not in obj:
        return {
            "ok": False,
            "reason": "effort-key-absent",
            "detail": (
                'JSON seat must include the "effort" key (value may be null); '
                f"accepted: {_ACCEPTED_SEAT}"
            ),
        }
    vendor = obj.get("vendor")
    if not isinstance(vendor, str) or not vendor.strip():
        valid = _format_valid(model_registry.vendors())
        return {
            "ok": False,
            "reason": "vendor-invalid",
            "detail": (
                f"seat vendor must be a non-empty string registered in model_registry; "
                f"valid vendors: {valid}; accepted: {_ACCEPTED_SEAT}"
            ),
        }
    vendor = vendor.strip()
    if vendor not in model_registry.vendors():
        valid = _format_valid(model_registry.vendors())
        return {
            "ok": False,
            "reason": "unknown-vendor",
            "detail": (
                f"unknown vendor {vendor!r}; valid vendors: {valid}; "
                f"accepted: {_ACCEPTED_SEAT}"
            ),
        }
    model = obj.get("model")
    if model is not None and not isinstance(model, str):
        return {
            "ok": False,
            "reason": "model-invalid",
            "detail": (
                f"seat model must be a string or null; accepted: {_ACCEPTED_SEAT}"
            ),
        }
    effort = obj.get("effort")
    if effort is not None and not isinstance(effort, str):
        return {
            "ok": False,
            "reason": "effort-invalid",
            "detail": (
                f"seat effort must be a string or null; accepted: {_ACCEPTED_SEAT}"
            ),
        }
    if isinstance(effort, str) and not effort.strip():
        effort = None
    return {
        "ok": True,
        "vendor": vendor,
        "model": model,
        "effort": effort,
        "source": "json",
    }


def _parse_token(raw: str, *, vendor_hint: str | None) -> dict:
    text = raw.strip()
    if ":" not in text:
        return {
            "ok": False,
            "reason": "seat-unparseable",
            "detail": (
                f"seat value is neither valid JSON nor a composed token; "
                f"accepted: {_ACCEPTED_SEAT}"
            ),
        }
    vendor, token = text.split(":", 1)
    vendor = vendor.strip()
    token = token.strip()
    if vendor_hint is not None and vendor != vendor_hint:
        return {
            "ok": False,
            "reason": "vendor-hint-mismatch",
            "detail": (
                f"composed token vendor {vendor!r} does not match hint {vendor_hint!r}; "
                f"accepted: {_ACCEPTED_SEAT}"
            ),
        }
    if vendor not in model_registry.vendors():
        valid = _format_valid(model_registry.vendors())
        return {
            "ok": False,
            "reason": "unknown-vendor",
            "detail": (
                f"unknown vendor {vendor!r}; valid vendors: {valid}; "
                f"accepted: {_ACCEPTED_SEAT}"
            ),
        }
    parsed = model_registry.parse_dispatch_token(vendor, token)
    if parsed is None:
        return {
            "ok": False,
            "reason": "token-unresolvable",
            "detail": (
                f"composed token {token!r} is not self-contained for vendor {vendor!r}; "
                f"use JSON seat form {_SEAT_JSON_SHAPE} for this vendor"
            ),
        }
    model_id, effort = parsed
    return {
        "ok": True,
        "vendor": vendor,
        "model": model_id,
        "effort": effort,
        "source": "token",
    }


def parse(raw, *, vendor_hint=None) -> dict:
    if not isinstance(raw, str) or not raw.strip():
        return {
            "ok": False,
            "reason": "seat-empty",
            "detail": f"seat value must be non-empty; accepted: {_ACCEPTED_SEAT}",
        }
    text = raw.strip()
    if text.startswith("{"):
        return _parse_json(text)
    return _parse_token(text, vendor_hint=vendor_hint)


def _validate_model_effort(bundle: dict) -> dict:
    vendor = bundle["vendor"]
    model_id = bundle.get("model")
    effort = bundle.get("effort")
    source = bundle.get("source")

    if not isinstance(model_id, str) or not model_id:
        return {
            "ok": False,
            "reason": "model-required",
            "detail": (
                "seat model must be a registry model id; "
                f"accepted: {_ACCEPTED_SEAT}"
            ),
        }

    if not model_registry.is_registered(vendor, model_id):
        parsed = model_registry.parse_dispatch_token(vendor, model_id)
        if parsed is None:
            out = dict(bundle)
            out.update({
                "ok": True,
                "vendor": vendor,
                "model": model_id,
                "effort": effort,
                "effortSource": "caller",
            })
            return out
        model_id, tok_effort = parsed
        if tok_effort is not None and effort is not None and tok_effort != effort:
            return {
                "ok": False,
                "reason": "effort-token-conflict",
                "detail": (
                    f"effort {effort!r} conflicts with effort {tok_effort!r} "
                    f"encoded in model token {bundle.get('model')!r}; "
                    f"accepted: {_ACCEPTED_SEAT}"
                ),
            }
        if effort is None and tok_effort is not None:
            effort = tok_effort

    allowed = _model_allowed_efforts(vendor, model_id)
    if allowed is None:
        return {
            "ok": False,
            "reason": "unknown-model",
            "detail": (
                f"model {model_id!r} is not registered for vendor {vendor!r}; "
                f"accepted: {_ACCEPTED_SEAT}"
            ),
        }

    effort_source = "caller"
    if not allowed:
        if effort is not None:
            return {
                "ok": False,
                "reason": "invalid-model-effort",
                "detail": (
                    f"model {model_id!r} declares an empty effort set — only null effort "
                    f"is accepted; got {effort!r}; accepted efforts for this model: (none)"
                ),
            }
        effort_source = "declared-none"
    else:
        matched = _match_effort(effort, allowed)
        if matched is None:
            allowed_text = _format_valid(allowed) if allowed else "(none)"
            detail = (
                f"effort {effort!r} is not valid for model {model_id!r}; "
                f"accepted efforts for this model: {allowed_text}"
            )
            hint = _cross_vendor_effort_hint(effort) if isinstance(effort, str) else None
            if hint:
                detail = f"{detail}; {hint}"
            return {
                "ok": False,
                "reason": "invalid-model-effort",
                "detail": detail,
            }
        if effort is None:
            if len(allowed) == 1:
                matched = allowed[0]
                effort_source = "resolved"
            else:
                return {
                    "ok": False,
                    "reason": "invalid-model-effort",
                    "detail": (
                        f"effort is required for model {model_id!r}; "
                        f"accepted efforts for this model: {_format_valid(allowed)}"
                    ),
                }
        elif source == "token" and bundle.get("effort") is None:
            effort_source = "resolved"
        else:
            effort_source = "caller"
        effort = matched

    out = dict(bundle)
    out.update({
        "ok": True,
        "vendor": vendor,
        "model": model_id,
        "effort": effort,
        "effortSource": effort_source,
    })
    return out


def validate(bundle: dict, role: str) -> dict:
    if not bundle.get("ok"):
        return bundle
    if not isinstance(role, str) or role not in model_registry.roles():
        valid = _format_valid(model_registry.roles())
        return {
            "ok": False,
            "reason": "unknown-role",
            "detail": (
                f"unknown role {role!r}; valid roles: {valid}; {accepted_role_detail()}"
            ),
        }
    checked = _validate_model_effort(bundle)
    if not checked.get("ok"):
        return checked
    return checked


def validate_effort_only(bundle: dict) -> dict:
    """Model-level effort validation without registry role allowlist (build-argv entry)."""
    if not bundle.get("ok"):
        return bundle
    return _validate_model_effort(bundle)


def _entry_refusal(reason: str, detail: str) -> dict:
    return {"ok": False, "reason": reason, "detail": detail}


def _parse_entry_dict(obj: dict) -> dict:
    if not isinstance(obj, dict):
        return _entry_refusal(
            "seat-not-object",
            f"seat JSON must be an object; accepted: {_ACCEPTED_SEAT}",
        )
    if "effort" not in obj:
        return _entry_refusal(
            "effort-key-absent",
            (
                'JSON seat must include the "effort" key (value may be null); '
                f"accepted: {_ACCEPTED_SEAT}"
            ),
        )
    if "role" not in obj:
        return _entry_refusal(
            "role-key-absent",
            (
                'JSON seat must include the "role" key; '
                f"accepted: {_ACCEPTED_SEAT}; {accepted_role_detail()}"
            ),
        )
    role = obj.get("role")
    if role is None:
        return _entry_refusal(
            "role-null",
            (
                'JSON seat "role" must not be null; '
                f"accepted: {_ACCEPTED_SEAT}; {accepted_role_detail()}"
            ),
        )
    if not isinstance(role, str) or role not in model_registry.roles():
        valid = _format_valid(model_registry.roles())
        return _entry_refusal(
            "unknown-role",
            (
                f"unknown role {role!r}; valid roles: {valid}; "
                f"accepted: {_ACCEPTED_SEAT}; {accepted_role_detail()}"
            ),
        )
    vendor = obj.get("vendor")
    if not isinstance(vendor, str) or not vendor.strip():
        valid = _format_valid(model_registry.vendors())
        return _entry_refusal(
            "vendor-invalid",
            (
                f"seat vendor must be a non-empty string registered in model_registry; "
                f"valid vendors: {valid}; accepted: {_ACCEPTED_SEAT}"
            ),
        )
    vendor = vendor.strip()
    if vendor not in model_registry.vendors():
        valid = _format_valid(model_registry.vendors())
        return _entry_refusal(
            "unknown-vendor",
            (
                f"unknown vendor {vendor!r}; valid vendors: {valid}; "
                f"accepted: {_ACCEPTED_SEAT}"
            ),
        )
    model = obj.get("model")
    if model is not None and not isinstance(model, str):
        return _entry_refusal(
            "model-invalid",
            f"seat model must be a string or null; accepted: {_ACCEPTED_SEAT}",
        )
    effort = obj.get("effort")
    if effort is not None and not isinstance(effort, str):
        return _entry_refusal(
            "effort-invalid",
            f"seat effort must be a string or null; accepted: {_ACCEPTED_SEAT}",
        )
    if isinstance(effort, str) and not effort.strip():
        effort = None
    return {
        "ok": True,
        "vendor": vendor,
        "model": model,
        "effort": effort,
        "role": role,
        "source": "json",
    }


def _parse_entry_raw(seat_raw) -> dict:
    if isinstance(seat_raw, dict):
        return _parse_entry_dict(seat_raw)
    if not isinstance(seat_raw, str) or not seat_raw.strip():
        return _entry_refusal(
            "seat-empty",
            f"seat value must be non-empty; accepted: {_ACCEPTED_SEAT}",
        )
    text = seat_raw.strip()
    if text.startswith("{"):
        try:
            obj = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            return _entry_refusal(
                "seat-unparseable",
                (
                    f"seat value is not valid JSON; accepted: {_ACCEPTED_SEAT}"
                ),
            )
        return _parse_entry_dict(obj)
    return _entry_refusal(
        "seat-token-dropped",
        (
            "bare composed-token --seat form is no longer accepted because it cannot "
            f"carry a role; pass --seat as {_ACCEPTED_SEAT}"
        ),
    )


def _mode_role_coherence_refusal(role: str) -> dict:
    return _entry_refusal(
        "mode-role-mismatch",
        (
            f"--mode {_MODE_BRIEF_CHECK} requires seat role 'brief-check'; "
            f"got role {role!r}; accepted: {_ACCEPTED_SEAT}; "
            f'{accepted_role_detail()}'
        ),
    )


def run_kind_for_role(role: str) -> str | None:
    """Derive build-argv sandbox run kind from a registry role's read_write classification."""
    rw = model_registry.role_read_write(role)
    if rw == "read":
        return "review"
    if rw == "write":
        kind = model_registry.engine_pref_role_kind(role)
        if kind in _BUILD_ARGV_RUN_KINDS:
            return kind
        return "build"
    return None


def _run_kind_unclassified_refusal(role: str) -> dict:
    return _entry_refusal(
        "run-kind-unclassified",
        (
            f"role {role!r} has no read_write classification; "
            f"build-argv requires a read or write role; accepted: {_ACCEPTED_SEAT}; "
            f"{accepted_role_detail()}"
        ),
    )


def build_argv_run_kind_mismatch_refusal(
    role: str, *, supplied: str, accepted: str,
) -> dict:
    return _entry_refusal(
        "run-kind-role-mismatch",
        (
            f"--run-kind {supplied!r} disagrees with seat role {role!r} "
            f"(read_write={model_registry.role_read_write(role)!r}); "
            f"accepted run kind for this role: {accepted!r}; "
            f"accepted: {_ACCEPTED_SEAT}; {accepted_role_detail()}"
        ),
    )


def _verb_role_coherence_refusal(role: str, *, verb: str) -> dict:
    rw = model_registry.role_read_write(role)
    if verb == "dispatch-write" and rw == "read":
        detail = (
            f"role {role!r} is read-only (read_write=read); "
            f"dispatch-write requires a write role; accepted: {_ACCEPTED_SEAT}; "
            f"{accepted_role_detail()}"
        )
    elif verb == "dispatch-review" and rw == "write":
        detail = (
            f"role {role!r} is write-only (read_write=write); "
            f"dispatch-review requires a read role; accepted: {_ACCEPTED_SEAT}; "
            f"{accepted_role_detail()}"
        )
    else:
        return None
    return _entry_refusal("verb-role-mismatch", detail)


def _malformed_allowlist_verdict_detail(role: str, vendor: str) -> str:
    return (
        "allowlist guard returned malformed verdict — expected dispatch_guard.validate("
        f"{role!r}, {vendor!r}, model, effort) to return ok, reason, allowlist, and "
        "allowlist_pairs naming the sanctioned model allowlist for this role and vendor, "
        "with echoed role, vendor, model_id (or resolved_model), effort, and a non-empty "
        "allowlist_pairs containing the resolved (model, effort) pair; "
        "fix the seat or re-run dispatch_guard check"
    )


def _normalize_allowlist_verdict(verdict, *, role: str, vendor: str, model: str, effort):
    malformed = _malformed_allowlist_verdict_detail(role, vendor)
    if not isinstance(verdict, dict):
        return _entry_refusal("allowlist-malformed", malformed)
    if verdict.get("ok") is not True:
        reason = verdict.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            return _entry_refusal("allowlist-malformed", malformed)
        return {
            "ok": False,
            "reason": "allowlist-refused",
            "detail": reason,
            "allowlistVerdict": verdict,
        }
    if verdict.get("role") != role or verdict.get("vendor") != vendor:
        return _entry_refusal("allowlist-malformed", malformed)
    resolved_model = verdict.get("model_id")
    if resolved_model is None:
        resolved_model = verdict.get("resolved_model")
    if resolved_model is None or verdict.get("effort") != effort:
        return _entry_refusal("allowlist-malformed", malformed)
    pairs = verdict.get("allowlist_pairs")
    if not isinstance(pairs, (list, tuple)) or not pairs:
        return _entry_refusal("allowlist-malformed", malformed)
    normalized_pairs = []
    for pair in pairs:
        if (
            isinstance(pair, (list, tuple))
            and len(pair) == 2
        ):
            normalized_pairs.append((pair[0], pair[1]))
    if (model, effort) not in normalized_pairs:
        return _entry_refusal("allowlist-malformed", malformed)
    return {"ok": True, "allowlistVerdict": verdict}


def resolve_entry(seat_raw, *, verb, mode=None) -> dict:
    """Single chokepoint for dispatch entry seat resolution (#1269 WO-1)."""
    if verb not in _ENTRY_VERBS:
        return _entry_refusal(
            "unknown-verb",
            f"unknown resolve_entry verb {verb!r}; accepted verbs: "
            f"{_format_valid(tuple(sorted(_ENTRY_VERBS)))}",
        )
    parsed = _parse_entry_raw(seat_raw)
    if not parsed.get("ok"):
        return parsed
    role = parsed["role"]
    if mode == _MODE_BRIEF_CHECK and role != "brief-check":
        return _mode_role_coherence_refusal(role)
    if verb in ("dispatch-review", "dispatch-write"):
        verb_refusal = _verb_role_coherence_refusal(role, verb=verb)
        if verb_refusal is not None:
            return verb_refusal
    if verb == "build-argv" and run_kind_for_role(role) is None:
        return _run_kind_unclassified_refusal(role)
    checked = _validate_model_effort(parsed)
    if not checked.get("ok"):
        return checked
    role = checked["role"]
    vendor = checked["vendor"]
    model = checked["model"]
    effort = checked.get("effort")
    try:
        verdict = dispatch_guard.validate(role, vendor, model, effort)
    except Exception:
        return _entry_refusal(
            "allowlist-raised",
            "allowlist guard raised unexpectedly",
        )
    normalized = _normalize_allowlist_verdict(
        verdict, role=role, vendor=vendor, model=model, effort=effort,
    )
    if not normalized.get("ok"):
        return normalized
    return {
        "ok": True,
        "vendor": vendor,
        "model": model,
        "effort": effort,
        "role": role,
        "effortSource": checked.get("effortSource", "caller"),
        "roleSource": "seat",
        "allowlistVerdict": normalized["allowlistVerdict"],
    }
