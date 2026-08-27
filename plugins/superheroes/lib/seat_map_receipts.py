#!/usr/bin/env python3
"""Seat-map receipt projections (#681) — invariant: no shared accumulated seat-map blob in the
driver. The only stored submitted-map state is ``state["seatMapReceipts"]`` (append-only,
round-scoped). Every read of submitted-map content goes through exactly one function below;
``receipts`` is the sole reader of raw state."""
import json

import liveness_cache
import seat_map
import version_skew

# Evidence / breach / provenance keys — union or most-conservative merge, never last-wins (#681).
_EVIDENCE_MAP_KEYS = frozenset({
    "violations",
    "liveCellsSource",
    "liveCells",
    "liveVendors",
    "livenessPinScoped",
    "authorFamily",
})
_LIST_EVIDENCE_MAP_KEYS = frozenset({
    "violations",
    "liveCells",
    "liveVendors",
})
# liveCellsSource trust — lower rank is less trusted; unrecognized sources rank below unprobed.
_LIVE_CELLS_SOURCE_TRUST = {
    liveness_cache.LIVE_CELLS_SOURCE_PROBED: 3,
    liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED: 2,
    liveness_cache.LIVE_CELLS_SOURCE_UNPROBED: 1,
}
_UNRECOGNIZED_LIVE_CELLS_SOURCE_TRUST = 0


def receipts(state):
    """Ordered receipt list — legacy ``state["seatMap"]`` dict prepended when present, then receipts."""
    receipts_list: list[dict] = []
    sm = state.get("seatMap")
    if isinstance(sm, dict) and sm:
        receipts_list.append({"round": "legacy", "map": sm})
    raw = state.get("seatMapReceipts")
    if isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, dict) and isinstance(entry.get("map"), dict):
                receipts_list.append(entry)
    return receipts_list


def latest_with_seats(state):
    """Seats-identity projection — last receipt whose ``map["seats"]`` is a non-empty dict."""
    for entry in reversed(receipts(state)):
        seats = entry["map"].get("seats")
        if isinstance(seats, dict) and seats:
            return entry["map"]
    return {}


def any_seats(state):
    """Seats-existence projection — True iff any receipt carries a non-empty ``seats`` dict."""
    for entry in receipts(state):
        seats = entry["map"].get("seats")
        if isinstance(seats, dict) and seats:
            return True
    return False


def same_family_seats(state):
    """Degradations projection — union of same-family seats across all receipts."""
    seats: list[str] = []
    for entry in receipts(state):
        degradations = entry["map"].get("degradations")
        if not isinstance(degradations, list):
            continue
        for deg in degradations:
            if isinstance(deg, dict) and deg.get("constraint") == "same-family":
                seat = deg.get("seat")
                seats.append(seat if isinstance(seat, str) and seat else "unnamed-seat")
    return sorted(set(seats))


def unexcused_violations(state):
    """Violations projection — per-receipt ``unexcused_violations``, deduped by (constraint, seat)."""
    seen: set[tuple] = set()
    merged: list[dict] = []
    for entry in receipts(state):
        for v in seat_map.unexcused_violations(entry["map"]):
            key = (str(v.get("constraint", "")), str(v.get("seat") or ""))
            if key in seen:
                continue
            seen.add(key)
            merged.append(v)
    merged.sort(key=lambda item: (str(item.get("constraint", "")), str(item.get("seat") or "")))
    return merged


def pin_excused_records(state):
    """Pin-excusal projection — per-receipt ``classify_violations`` excusedByPin lists."""
    records: list[dict] = []
    for entry in receipts(state):
        classified = seat_map.classify_violations(entry["map"])
        for rec in classified.get("excusedByPin") or []:
            if isinstance(rec, dict):
                records.append(rec)
    return records


def skew_records(state):
    """Skew projection — per-receipt skew degradations, deduped by ``_skew_record_identity``."""
    seen: set[tuple] = set()
    merged: list[dict] = []
    for entry in receipts(state):
        for row in _skew_records_from_seat_map(entry["map"]):
            key = _skew_record_identity(row)
            if key is None or key in seen:
                continue
            seen.add(key)
            merged.append(row)
    merged.sort(
        key=lambda item: (
            str(item.get("constraint", "")),
            str(item.get("status", "")),
            str(item.get("detail", "")),
            str(item.get("inspectedRoot", "")),
        ),
    )
    return merged


def plugin_version_skew_status(state):
    """Skew-status projection — tri-state ``pluginVersionSkew`` across receipts."""
    last_recognized = None
    for entry in receipts(state):
        pvs = entry["map"].get("pluginVersionSkew")
        if not isinstance(pvs, dict):
            continue
        status = pvs.get("status")
        try:
            if status in version_skew.STATUSES:
                last_recognized = status
            else:
                return "unknown"
        except TypeError:
            return "unknown"
    if last_recognized is None:
        return "absent"
    return last_recognized


def canary_map(state, round_map):
    """Canary projection — round map when it carries seats, else latest-with-seats."""
    if isinstance(round_map, dict):
        seats = round_map.get("seats")
        if isinstance(seats, dict) and seats:
            return round_map
    return latest_with_seats(state)


def emit_receipt_seat_map(state):
    """Derived read-time union for ``build_receipt`` — latest seats, merged evidence, last-wins scalars."""
    receipt_list = receipts(state)
    base = dict(latest_with_seats(state))
    seen: set[str] = set()
    merged_degs: list = []
    for entry in receipt_list:
        degs = entry["map"].get("degradations")
        if not isinstance(degs, list):
            continue
        for row in degs:
            if isinstance(row, dict):
                key = json.dumps(row, sort_keys=True)
                if key in seen:
                    continue
                seen.add(key)
            merged_degs.append(row)
    if merged_degs:
        base["degradations"] = merged_degs
    for key in _LIST_EVIDENCE_MAP_KEYS:
        seen_rows: set[str] = set()
        merged_rows: list = []
        for entry in receipt_list:
            rows = entry["map"].get(key)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if isinstance(row, dict):
                    row_key = json.dumps(row, sort_keys=True)
                    if row_key in seen_rows:
                        continue
                    seen_rows.add(row_key)
                merged_rows.append(row)
        if merged_rows:
            base[key] = merged_rows
        else:
            base.pop(key, None)
    live_cells_sources: list = []
    for entry in receipt_list:
        if "liveCellsSource" in entry["map"]:
            live_cells_sources.append(entry["map"]["liveCellsSource"])
    if live_cells_sources:
        base["liveCellsSource"] = _merge_live_cells_source(live_cells_sources)
    else:
        base.pop("liveCellsSource", None)
    pin_values: list = []
    for entry in receipt_list:
        if "livenessPinScoped" in entry["map"]:
            pin_values.append(entry["map"]["livenessPinScoped"])
    if pin_values:
        # Any receipt not explicitly False leaves liveness evidence unproven — True wins over False.
        base["livenessPinScoped"] = any(val is not False for val in pin_values)
    else:
        base.pop("livenessPinScoped", None)
    author_families: list = []
    for entry in receipt_list:
        if "authorFamily" in entry["map"]:
            author_families.append(entry["map"]["authorFamily"])
    if (
        author_families
        and all(isinstance(fam, str) and fam for fam in author_families)
        and len(set(author_families)) == 1
    ):
        base["authorFamily"] = author_families[0]
    else:
        base.pop("authorFamily", None)
    for entry in receipt_list:
        map_ = entry["map"]
        for k, v in map_.items():
            if k in ("seats", "degradations") or k in _EVIDENCE_MAP_KEYS:
                continue
            base[k] = v
    return base


def _merge_live_cells_source(sources: list) -> object:
    """Least-trusted liveCellsSource across receipts — disagreement is unproven provenance."""
    best_rank = -1
    worst_value = None
    for source in sources:
        rank = _LIVE_CELLS_SOURCE_TRUST.get(source, _UNRECOGNIZED_LIVE_CELLS_SOURCE_TRUST)
        if rank < best_rank or best_rank < 0:
            best_rank = rank
            worst_value = source
    return worst_value


def _skew_record_identity(rec):
    """Union key for plugin-version-skew disclosures — (constraint, status, detail, inspectedRoot).
    All skew records share one constraint and carry no seat, so the breach channel's (constraint,
    seat) key would collapse distinct disclosures (#1107)."""
    if not isinstance(rec, dict):
        return None
    if rec.get("constraint") != version_skew.CONSTRAINT:
        return None
    return (
        str(rec.get("constraint", "")),
        str(rec.get("status", "")),
        str(rec.get("detail", "")),
        str(rec.get("inspectedRoot", "")),
    )


def _enrich_skew_degradation(deg, seat_map_blob):
    """One seat-map skew degradation row, with tri-state fields filled from ``pluginVersionSkew``."""
    if not isinstance(deg, dict) or deg.get("constraint") != version_skew.CONSTRAINT:
        return None
    rec = dict(deg)
    pvs = seat_map_blob.get("pluginVersionSkew") if isinstance(seat_map_blob, dict) else None
    if not isinstance(pvs, dict):
        pvs = {}
    for field, pvs_key in (("status", "status"), ("detail", "detail"),
                           ("inspectedRoot", "inspectedRoot")):
        if rec.get(field) in (None, ""):
            val = pvs.get(pvs_key)
            if val not in (None, ""):
                rec[field] = val
    status = rec.get("status")
    if status in (None, ""):
        rec["status"] = version_skew.default_missing_status()
        status = rec["status"]
    if not version_skew.appends_degradation(status):
        return None
    return rec


def _skew_records_from_seat_map(seat_map_blob):
    """Plugin-version-skew degradations from one seat map's degradations list."""
    degradations = seat_map_blob.get("degradations") if isinstance(seat_map_blob, dict) else None
    if not isinstance(degradations, list):
        degradations = []
    records = []
    for deg in degradations:
        rec = _enrich_skew_degradation(deg, seat_map_blob)
        if rec is None:
            continue
        records.append(rec)
    pvs = seat_map_blob.get("pluginVersionSkew") if isinstance(seat_map_blob, dict) else None
    if isinstance(pvs, dict) and not records:
        status = pvs.get("status")
        try:
            unknown_status = status not in version_skew.STATUSES
        except TypeError:
            unknown_status = True
        if unknown_status:
            offending = status
            synthetic_status = (
                offending
                if offending not in (None, "") and version_skew.appends_degradation(offending)
                else version_skew.default_missing_status()
            )
            records.append({
                "constraint": version_skew.CONSTRAINT,
                "status": synthetic_status,
                "detail": pvs.get("detail") or version_skew.DETAIL_SEMANTICS_DIVERGENT,
                "reason": "unrecognized pluginVersionSkew.status: %r" % offending,
                "inspectedRoot": pvs.get("inspectedRoot") or "",
            })
    return records
