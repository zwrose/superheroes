"""A generic per-write idempotency primitive: apply a durable/remote write AT MOST ONCE
by reading reality, never by trusting a stored flag (the spine's reality-wins rule,
CONVENTIONS §4.7). Built generic (a key + a reader + an applier) so create / ready-flip /
draft-flip / push-reconcile all route through one seam; #118 generalizes it spine-wide
(its FR-4) rather than retrofitting a divergent scheme.

Fail-CLOSED: an unreadable current state never applies and never reports ok.
"""


def idempotent_apply(key, current_reader, apply_fn):
    """Apply `apply_fn` only if the live state does not already reflect `key`.

    key: an opaque string naming the intended end-state (informational; the actual
        match is decided by current_reader, which reads reality).
    current_reader: () -> (reflects, detail). reflects is True (already done — no-op),
        False (apply needed), or None (unreadable — fail closed, never apply).
    apply_fn: () -> (ok, detail). Performs the write; invoked only when reflects is False.

    Returns {key, already, applied, ok, reason, detail}.
    """
    try:
        reflects, read_detail = current_reader()
    except Exception as e:  # noqa: BLE001 — a throwing reader is an unreadable state, fail closed
        return {"key": key, "already": False, "applied": False, "ok": False,
                "reason": "current-state read raised: %s" % e, "detail": None}
    if reflects is None:
        return {"key": key, "already": False, "applied": False, "ok": False,
                "reason": "current state unreadable — fail closed", "detail": read_detail}
    if reflects is True:
        return {"key": key, "already": True, "applied": False, "ok": True,
                "reason": "already reflects intended write — no-op", "detail": read_detail}
    try:
        ok, apply_detail = apply_fn()
    except Exception as e:  # noqa: BLE001 — a throwing applier is a failed write, fail closed
        return {"key": key, "already": False, "applied": True, "ok": False,
                "reason": "apply raised: %s" % e, "detail": None}
    return {"key": key, "already": False, "applied": True, "ok": bool(ok),
            "reason": "applied" if ok else "apply failed", "detail": apply_detail}
