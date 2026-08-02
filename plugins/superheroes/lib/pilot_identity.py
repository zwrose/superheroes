"""Identity-probe exercise harness and mid-wave lapse episode (D3 / §5).

Drives the two-state identity-probe exercise by invoking probe callables — an evaluator
fed fabricated answers cannot mint a passing exercise without anything having been probed.

Non-goals: no HTTP or browser driving of its own — browser context creation and credential
injection are C7's; the durable slot-record mutation that a park performs is A2a's state
machine driven by B5's wave runtime; capture artifact production is B4's.
"""
import pilot_contract
import pilot_probe
import pilot_slot

REFUSAL_IDENTITY_ANSWER_INVALID = "identity-answer-invalid"
REFUSAL_IDENTITY_ANSWER_REASON_UNKNOWN = "identity-answer-reason-unknown"
REFUSAL_IDENTITY_EXPECTED_MISSING = "identity-expected-missing"
REFUSAL_IDENTITY_PROBE_ANSWERS_IDENTICAL = "identity-probe-answers-identical"
REFUSAL_IDENTITY_PROBE_SEEDED_REFUSED = "identity-probe-seeded-refused"
REFUSAL_IDENTITY_PROBE_SEEDED_IDENTITY_MISMATCH = "identity-probe-seeded-identity-mismatch"
REFUSAL_IDENTITY_PROBE_UNSEEDED_NOT_NO_SESSION = "identity-probe-unseeded-not-no-session"
REFUSAL_IDENTITY_PROBE_NOT_CALLABLE = "identity-probe-not-callable"
REFUSAL_IDENTITY_PROBE_LEGS_NOT_DISTINCT = "identity-probe-legs-not-distinct"
REFUSAL_IDENTITY_PROBE_LEG_FAILED = "identity-probe-leg-failed"
REFUSAL_IDENTITY_ACCOUNT_SET_EMPTY = "identity-account-set-empty"
REFUSAL_IDENTITY_ACCOUNT_SET_MISMATCH = "identity-account-set-mismatch"
REFUSAL_IDENTITY_WRONG_ACCOUNT_VACUOUS = "identity-wrong-account-vacuous"
REFUSAL_IDENTITY_WRONG_ACCOUNT_NOT_DISCRIMINATED = "identity-wrong-account-not-discriminated"
REFUSAL_IDENTITY_WRONG_ACCOUNT_UNEXPECTED_IDENTITY = "identity-wrong-account-unexpected-identity"
REFUSAL_IDENTITY_WRONG_ACCOUNT_INCONCLUSIVE = "identity-wrong-account-inconclusive"
REFUSAL_LAPSE_SIGN_IN_PATH_INVALID = "lapse-sign-in-path-invalid"
REFUSAL_LAPSE_REPROBE_BUDGET_INVALID = "lapse-reprobe-budget-invalid"
REFUSAL_LAPSE_PROBE_NOT_CALLABLE = "lapse-probe-not-callable"
REFUSAL_LAPSE_REMINT_UNAVAILABLE = "lapse-remint-unavailable"
REFUSAL_LAPSE_REMINT_FAILED = "lapse-remint-failed"
REFUSAL_IDENTITY_DECLARATION_SLOT_INVALID = "identity-declaration-slot-invalid"
REFUSAL_IDENTITY_DECLARATION_INVALID = "identity-declaration-invalid"
REFUSAL_IDENTITY_RECEIPT_ARGUMENT_INVALID = "identity-receipt-argument-invalid"

ACTION_CONTINUE = "continue"
ACTION_REPROBE = "reprobe"
ACTION_PARK = "park"
ACTION_REMINT = "remint"
ACTION_DEFER = "defer"
ACTION_REFUSE = "refuse"


class PilotIdentityError(Exception):
    """Identity-probe or lapse-episode refusal."""

    def __init__(self, reason, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def probe_answer(*, identity=None, reason=None):
    """Normalize and validate one probe answer."""
  # bite-axis: answer shape — exactly one of identity or reason; identity non-empty str;
  # reason must be a known probe token.
    has_identity = identity is not None
    has_reason = reason is not None
    if has_identity and has_reason or not has_identity and not has_reason:
        raise PilotIdentityError(REFUSAL_IDENTITY_ANSWER_INVALID)
    if has_identity:
        if not isinstance(identity, str) or not identity:
            raise PilotIdentityError(REFUSAL_IDENTITY_ANSWER_INVALID)
        return {"identity": identity, "reason": None}
    if reason not in pilot_probe.ALL_PROBE_REASONS:
        raise PilotIdentityError(REFUSAL_IDENTITY_ANSWER_REASON_UNKNOWN)
    return {"identity": None, "reason": reason}


def _normalize_answer_dict(answer):
    if not isinstance(answer, dict):
        raise PilotIdentityError(REFUSAL_IDENTITY_ANSWER_INVALID)
    identity = answer.get("identity")
    reason = answer.get("reason")
    has_identity = identity is not None
    has_reason = reason is not None
    if has_identity and has_reason or not has_identity and not has_reason:
        raise PilotIdentityError(REFUSAL_IDENTITY_ANSWER_INVALID)
    try:
        return probe_answer(identity=identity, reason=reason)
    except PilotIdentityError:
        raise


def evaluate_pair(seeded, unseeded, *, expected_identity):
    """Grade two probe answers for one account.

    Helper only — does not establish that answers came from two contexts.
    The authoritative exercise is ``run_pair_exercise``.
    """
  # bite-axis: pair grading — check order is load-bearing; identical answers refuse before
  # seeded/unseeded discrimination checks.
    try:
        seeded_norm = _normalize_answer_dict(seeded)
    except PilotIdentityError as exc:
        return {"ok": False, "reason": exc.reason, "detail": exc.detail}
    try:
        unseeded_norm = _normalize_answer_dict(unseeded)
    except PilotIdentityError as exc:
        return {"ok": False, "reason": exc.reason, "detail": exc.detail}

    if not isinstance(expected_identity, str) or not expected_identity:
        return {
            "ok": False,
            "reason": REFUSAL_IDENTITY_EXPECTED_MISSING,
            "detail": None,
        }

    if seeded_norm == unseeded_norm:
        return {
            "ok": False,
            "reason": REFUSAL_IDENTITY_PROBE_ANSWERS_IDENTICAL,
            "detail": None,
        }

    if seeded_norm["reason"] is not None:
        return {
            "ok": False,
            "reason": REFUSAL_IDENTITY_PROBE_SEEDED_REFUSED,
            "detail": seeded_norm["reason"],
        }

    if seeded_norm["identity"] != expected_identity:
        return {
            "ok": False,
            "reason": REFUSAL_IDENTITY_PROBE_SEEDED_IDENTITY_MISMATCH,
            "detail": None,
        }

    if unseeded_norm["reason"] != pilot_probe.REASON_NO_SESSION:
        actual = unseeded_norm["reason"] if unseeded_norm["reason"] is not None else unseeded_norm["identity"]
        return {
            "ok": False,
            "reason": REFUSAL_IDENTITY_PROBE_UNSEEDED_NOT_NO_SESSION,
            "detail": actual,
        }

    return {"ok": True, "reason": None, "detail": None}


def run_pair_exercise(*, expected_identity, seeded_probe, unseeded_probe):
    """Authoritative single-account identity-probe exercise."""
  # bite-axis: exercise authority — invokes each probe callable exactly once and grades via
  # evaluate_pair; distinct callables required but different browser contexts are C7's.
    if not callable(seeded_probe) or not callable(unseeded_probe):
        raise PilotIdentityError(REFUSAL_IDENTITY_PROBE_NOT_CALLABLE)
    # bite-disclosure: distinct callables are verified here; whether they ran in different
    # browser contexts cannot be checked — context creation is C7's responsibility.
    if seeded_probe is unseeded_probe:
        raise PilotIdentityError(REFUSAL_IDENTITY_PROBE_LEGS_NOT_DISTINCT)

    for leg_name, probe in (("seeded", seeded_probe), ("unseeded", unseeded_probe)):
        try:
            raw = probe()
        except Exception:
            return {
                "ok": False,
                "reason": REFUSAL_IDENTITY_PROBE_LEG_FAILED,
                "detail": leg_name,
            }
        try:
            normalized = _normalize_answer_dict(raw)
        except PilotIdentityError as exc:
            return {
                "ok": False,
                "reason": exc.reason,
                "detail": leg_name,
            }
        if leg_name == "seeded":
            seeded_norm = normalized
        else:
            unseeded_norm = normalized

    seeded_arg = (
        {"identity": seeded_norm["identity"]}
        if seeded_norm["identity"] is not None
        else {"reason": seeded_norm["reason"]}
    )
    unseeded_arg = (
        {"identity": unseeded_norm["identity"]}
        if unseeded_norm["identity"] is not None
        else {"reason": unseeded_norm["reason"]}
    )
    return evaluate_pair(
        seeded_arg,
        unseeded_arg,
        expected_identity=expected_identity,
    )


def evaluate_slot(slot_accounts, expected_identities, answers):
    """Per-account-context-pair harness across a slot's whole account set."""
  # bite-axis: account-set alignment — authoritative account list from slot_accounts; all three
  # input key sets must match exactly.
    if not isinstance(slot_accounts, dict):
        raise PilotIdentityError(REFUSAL_IDENTITY_ACCOUNT_SET_MISMATCH)
    accounts_field = slot_accounts.get("accounts")
    if not isinstance(accounts_field, list):
        raise PilotIdentityError(REFUSAL_IDENTITY_ACCOUNT_SET_MISMATCH)
    account_list = pilot_slot.account_keys(slot_accounts)
    if not account_list:
        raise PilotIdentityError(REFUSAL_IDENTITY_ACCOUNT_SET_EMPTY)

    if not isinstance(expected_identities, dict):
        raise PilotIdentityError(REFUSAL_IDENTITY_ACCOUNT_SET_MISMATCH)
    if not isinstance(answers, dict):
        raise PilotIdentityError(REFUSAL_IDENTITY_ACCOUNT_SET_MISMATCH)

    expected_keys = set(expected_identities.keys())
    answer_keys = set(answers.keys())
    slot_keys = set(account_list)

    if expected_keys != slot_keys or answer_keys != slot_keys:
        missing_from_answers = sorted(slot_keys - answer_keys)
        extra_in_answers = sorted(answer_keys - slot_keys)
        missing_from_expected = sorted(slot_keys - expected_keys)
        extra_in_expected = sorted(expected_keys - slot_keys)
        detail_parts = []
        if missing_from_answers:
            detail_parts.append("missing from answers: " + ",".join(missing_from_answers))
        if extra_in_answers:
            detail_parts.append("extra in answers: " + ",".join(extra_in_answers))
        if missing_from_expected:
            detail_parts.append("missing from expected: " + ",".join(missing_from_expected))
        if extra_in_expected:
            detail_parts.append("extra in expected: " + ",".join(extra_in_expected))
        raise PilotIdentityError(
            REFUSAL_IDENTITY_ACCOUNT_SET_MISMATCH,
            "; ".join(detail_parts),
        )

    results = {}
    first_failure = None
    for account in account_list:
        entry = answers.get(account)
        if not isinstance(entry, dict):
            pair_result = {
                "ok": False,
                "reason": REFUSAL_IDENTITY_ANSWER_INVALID,
                "detail": None,
            }
        else:
            seeded = entry.get("seeded")
            unseeded = entry.get("unseeded")
            if seeded is None or unseeded is None:
                pair_result = {
                    "ok": False,
                    "reason": REFUSAL_IDENTITY_ANSWER_INVALID,
                    "detail": None,
                }
            else:
                pair_result = evaluate_pair(
                    seeded,
                    unseeded,
                    expected_identity=expected_identities[account],
                )
        results[account] = pair_result
        if not pair_result["ok"] and first_failure is None:
            first_failure = pair_result

    if first_failure is not None:
        return {
            "ok": False,
            "reason": first_failure["reason"],
            "accounts": results,
        }
    return {"ok": True, "reason": None, "accounts": results}


def evaluate_wrong_account_leg(answer, *, expected_identity, other_identity):
    """Grade the valid-but-wrong-account leg (D3 free leg under minting)."""
  # bite-axis: wrong-account discrimination — vacuous when identities coincide; inconclusive
  # on infrastructure and lapse tokens; pass only on wrong-identity token or other_identity.
    if other_identity == expected_identity:
        raise PilotIdentityError(REFUSAL_IDENTITY_WRONG_ACCOUNT_VACUOUS)

    try:
        normalized = _normalize_answer_dict(answer)
    except PilotIdentityError:
        raise PilotIdentityError(REFUSAL_IDENTITY_WRONG_ACCOUNT_INCONCLUSIVE)

    if normalized["reason"] == pilot_probe.REASON_WRONG_IDENTITY:
        return {"ok": True, "reason": None, "detail": None}

    if normalized["identity"] == other_identity:
        return {"ok": True, "reason": None, "detail": None}

    if normalized["identity"] == expected_identity:
        raise PilotIdentityError(REFUSAL_IDENTITY_WRONG_ACCOUNT_NOT_DISCRIMINATED)

    if normalized["identity"] is not None:
        raise PilotIdentityError(REFUSAL_IDENTITY_WRONG_ACCOUNT_UNEXPECTED_IDENTITY)

    raise PilotIdentityError(REFUSAL_IDENTITY_WRONG_ACCOUNT_INCONCLUSIVE)


def lapse_step(answer, *, sign_in_path, reprobe_count):
    """Pure lapse decision from one probe answer (design §5/§10)."""
  # bite-axis: lapse routing — only no-session routes to lapse; infrastructure defers;
  # identity-class tokens refuse; reprobe budget is exactly one.
    if (
        not isinstance(sign_in_path, str)
        or sign_in_path not in pilot_contract.SIGN_IN_PATHS
    ):
        raise PilotIdentityError(REFUSAL_LAPSE_SIGN_IN_PATH_INVALID)
    if (
        not isinstance(reprobe_count, int)
        or isinstance(reprobe_count, bool)
        or reprobe_count not in (0, 1)
    ):
        raise PilotIdentityError(REFUSAL_LAPSE_REPROBE_BUDGET_INVALID)

    try:
        normalized = _normalize_answer_dict(answer)
    except PilotIdentityError as exc:
        return {"action": ACTION_REFUSE, "class": None, "reason": exc.reason}

    if normalized["identity"] is not None:
        return {"action": ACTION_CONTINUE, "class": None, "reason": None}

    reason = normalized["reason"]
    classification = pilot_probe.classify(reason)

    if classification == "lapse":
        if reprobe_count == 0:
            return {
                "action": ACTION_REPROBE,
                "class": "lapse",
                "reason": reason,
            }
        if sign_in_path == "captured":
            return {
                "action": ACTION_PARK,
                "class": "lapse",
                "reason": reason,
            }
        return {
            "action": ACTION_REMINT,
            "class": "lapse",
            "reason": reason,
        }

    if classification == "infrastructure":
        return {
            "action": ACTION_DEFER,
            "class": "infrastructure",
            "reason": reason,
        }

    return {
        "action": ACTION_REFUSE,
        "class": "identity",
        "reason": reason,
    }


def lapse_episode(probe, *, sign_in_path, remint=None):
    """Authoritative lapse path — owns the re-probe budget."""
  # bite-axis: lapse episode — at most two probe calls; remint success required for continuation;
  # probe failures defer rather than lapse.
    if not callable(probe):
        raise PilotIdentityError(REFUSAL_LAPSE_PROBE_NOT_CALLABLE)

    probe_calls = 0
    first_reason = None
    second_reason = None

    try:
        first_raw = probe()
        probe_calls = 1
    except Exception:
        return {
            "action": ACTION_DEFER,
            "class": None,
            "reason": REFUSAL_IDENTITY_PROBE_LEG_FAILED,
            "probeCalls": probe_calls,
        }

    first_step = lapse_step(first_raw, sign_in_path=sign_in_path, reprobe_count=0)
    if first_step["action"] != ACTION_REPROBE:
        first_step["probeCalls"] = probe_calls
        return first_step

    first_reason = first_step["reason"]

    try:
        second_raw = probe()
        probe_calls = 2
    except Exception:
        return {
            "action": ACTION_DEFER,
            "class": None,
            "reason": REFUSAL_IDENTITY_PROBE_LEG_FAILED,
            "probeCalls": probe_calls,
        }

    second_step = lapse_step(second_raw, sign_in_path=sign_in_path, reprobe_count=1)
    second_reason = second_step["reason"]

    if second_step["action"] == ACTION_REMINT:
        if remint is None or not callable(remint):
            raise PilotIdentityError(REFUSAL_LAPSE_REMINT_UNAVAILABLE)
        try:
            remint_ok = remint()
        except Exception:
            remint_ok = False
        if not remint_ok:
            return {
                "action": ACTION_PARK,
                "class": "lapse",
                "reason": REFUSAL_LAPSE_REMINT_FAILED,
                "reminted": False,
                "firstReason": first_reason,
                "secondReason": second_reason,
                "probeCalls": probe_calls,
            }
        return {
            "action": ACTION_CONTINUE,
            "class": None,
            "reason": None,
            "reminted": True,
            "firstReason": first_reason,
            "secondReason": second_reason,
            "probeCalls": probe_calls,
        }

    if second_step["action"] == ACTION_PARK:
        # bite-disclosure: durable park — slot-record transition and work preservation are
        # pilot_lifecycle's lock-serialized state machine driven by B5's wave runtime; this
        # module returns the required action and evidence only.
        return {
            "action": ACTION_PARK,
            "class": "lapse",
            "reason": second_reason,
            "firstReason": first_reason,
            "secondReason": second_reason,
            "probeCalls": probe_calls,
        }

    second_step["probeCalls"] = probe_calls
    if first_reason is not None:
        second_step["firstReason"] = first_reason
    return second_step


def identity_probe_declaration(*, slot_ref, policy_digest, expected_identities):
    """Canonical declaration an identity-probe receipt is bound to."""
  # bite-axis: declaration binding — slot ref, policy digest, sorted account keys, and digest-only
  # expected identities; policy material never travels in the declaration.
    try:
        slot, generation = pilot_slot.parse_slot_ref(slot_ref)
    except pilot_slot.PilotSlotError:
        raise PilotIdentityError(REFUSAL_IDENTITY_DECLARATION_SLOT_INVALID)

    if not isinstance(policy_digest, str) or not policy_digest:
        raise PilotIdentityError(REFUSAL_IDENTITY_DECLARATION_INVALID)

    if not isinstance(expected_identities, dict):
        raise PilotIdentityError(REFUSAL_IDENTITY_DECLARATION_INVALID)

    account_keys = sorted(expected_identities.keys())
    expected_identity_digest = pilot_contract.declaration_digest(expected_identities)

    return {
        "slot": slot,
        "generation": generation,
        "policyDigest": policy_digest,
        "accountKeys": account_keys,
        "expectedIdentityDigest": expected_identity_digest,
    }


def identity_probe_receipt(declaration, result, *, exercised_at):
    """Build the registry record for kind identity-probe."""
  # bite-axis: receipt assembly — pass/fail from evaluate_slot; evidence never carries expected
  # identity values; kind must remain in DECLARATION_KINDS.
    assert "identity-probe" in pilot_contract.DECLARATION_KINDS

    if not isinstance(exercised_at, str) or not exercised_at:
        raise PilotIdentityError(REFUSAL_IDENTITY_RECEIPT_ARGUMENT_INVALID)

    if not isinstance(result, dict):
        raise PilotIdentityError(REFUSAL_IDENTITY_RECEIPT_ARGUMENT_INVALID)

    ok = result.get("ok")
    if ok is True:
        passed = sum(1 for account_result in result.get("accounts", {}).values() if account_result.get("ok"))
        evidence = "%d account(s) passed" % passed
        receipt_result = "pass"
    elif ok is False:
        evidence = result.get("reason") or "fail"
        receipt_result = "fail"
    else:
        raise PilotIdentityError(REFUSAL_IDENTITY_RECEIPT_ARGUMENT_INVALID)

    return {
        "kind": "identity-probe",
        "declarationDigest": pilot_contract.declaration_digest(declaration),
        "exercisedAt": exercised_at,
        "receipt": {
            "result": receipt_result,
            "evidence": evidence,
        },
    }


def require_identity_probe_exercised(registry, declaration):
    """Require a matching exercised identity-probe record in the registry.

    A registry record is the durable receipt of an exercise that happened; it is never a
    substitute for running the live probe in the current preflight. ``is_exercised`` carries
    no freshness or launched-instance binding — the declaration binds slot, generation, and
    policy digest.
    """
    return pilot_contract.require_exercised(registry, "identity-probe", declaration)
