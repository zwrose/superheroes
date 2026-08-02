"""Pilot target boundary — exact-origin bindings, protected-target refusal, and verdicts (A3)."""
import os
import re
import stat
import subprocess
import time

import pilot_slot

BOUNDARY_SCHEMA_VERSION = 1

REFUSAL_ORIGIN_INVALID = "boundary-origin-invalid"
REFUSAL_SLOT_REF_INVALID = "boundary-slot-ref-invalid"
REFUSAL_REDIRECTS_INVALID = "boundary-redirects-invalid"
REFUSAL_PROTECTED_TARGETS_INVALID = "boundary-protected-targets-invalid"
REFUSAL_TARGET_OFF_ALLOWLIST = "boundary-target-off-allowlist"
REFUSAL_REDIRECT_OFF_ALLOWLIST = "boundary-redirect-off-allowlist"
REFUSAL_PROTECTED_TARGET = "boundary-protected-target-refused"
REFUSAL_DATASTORE_IDENTITY_MISMATCH = "boundary-datastore-identity-mismatch"
REFUSAL_DATASTORE_IDENTITY_UNAVAILABLE = "boundary-datastore-identity-unavailable"
REFUSAL_DATASTORE_OBSERVER_INVALID = "boundary-datastore-observer-invalid"
REFUSAL_DATASTORE_OBSERVER_FAILED = "boundary-datastore-observer-failed"
REFUSAL_UNVERIFIED = "boundary-unverified"

_CONNECTION_ENV_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class PilotBoundaryError(Exception):
  def __init__(self, reason, detail=None):
    super().__init__(reason)
    self.reason = reason
    self.detail = detail


def parse_origin(value):
  """Return canonical ``<scheme>://<host>:<port>`` or raise."""
  canonical = _parse_origin_or_none(value)
  if canonical is None:
    raise PilotBoundaryError(REFUSAL_ORIGIN_INVALID)
  return canonical


def target_binding(slot_ref, *, origin, permitted_redirects, protected_targets):
  """Build a validated target binding dict."""
  try:
    slot, generation = pilot_slot.parse_slot_ref(slot_ref)
    canonical_slot_ref = pilot_slot.format_slot_ref(slot, generation)
  except pilot_slot.PilotSlotError:
    raise PilotBoundaryError(REFUSAL_SLOT_REF_INVALID)

  canonical_origin = parse_origin(origin)

  if not isinstance(permitted_redirects, list):
    raise PilotBoundaryError(REFUSAL_REDIRECTS_INVALID)
  seen_redirects = set()
  canonical_redirects = []
  for redirect in permitted_redirects:
    try:
      parsed = parse_origin(redirect)
    except PilotBoundaryError:
      raise PilotBoundaryError(REFUSAL_REDIRECTS_INVALID)
    if parsed not in seen_redirects:
      seen_redirects.add(parsed)
      canonical_redirects.append(parsed)

  if not isinstance(protected_targets, list) or not protected_targets:
    raise PilotBoundaryError(REFUSAL_PROTECTED_TARGETS_INVALID)
  canonical_protected = []
  for target in protected_targets:
    if not isinstance(target, str) or not target:
      raise PilotBoundaryError(REFUSAL_PROTECTED_TARGETS_INVALID)
    parsed = _parse_origin_or_none(target)
    canonical_protected.append(parsed if parsed is not None else target)

  return {
    "slotRef": canonical_slot_ref,
    "origin": canonical_origin,
    "permittedRedirects": canonical_redirects,
    "protectedTargets": canonical_protected,
  }


def check_target(binding, url):
  """Check whether ``url`` is an allowed target; never raises on malformed input."""
  parsed = _parse_origin_or_none(url)
  if parsed is None:
    return {"ok": False, "reason": REFUSAL_ORIGIN_INVALID}
  if parsed in binding["protectedTargets"]:
    return {"ok": False, "reason": REFUSAL_PROTECTED_TARGET}
  if parsed != binding["origin"]:
    return {"ok": False, "reason": REFUSAL_TARGET_OFF_ALLOWLIST}
  return {"ok": True, "reason": None}


def check_redirect(binding, url):
  """Check whether ``url`` is an allowed redirect destination; never raises."""
  parsed = _parse_origin_or_none(url)
  if parsed is None:
    return {"ok": False, "reason": REFUSAL_ORIGIN_INVALID}
  if parsed in binding["protectedTargets"]:
    return {"ok": False, "reason": REFUSAL_PROTECTED_TARGET}
  if parsed == binding["origin"] or parsed in binding["permittedRedirects"]:
    return {"ok": True, "reason": None}
  return {"ok": False, "reason": REFUSAL_REDIRECT_OFF_ALLOWLIST}


def check_protected_identity(binding, identity):
  """Refuse when ``identity`` names a protected target or is unavailable."""
  if identity in binding["protectedTargets"]:
    return {"ok": False, "reason": REFUSAL_PROTECTED_TARGET}
  if not isinstance(identity, str) or not identity:
    return {"ok": False, "reason": REFUSAL_DATASTORE_IDENTITY_UNAVAILABLE}
  return {"ok": True, "reason": None}


def observe_datastore_identity(
  observer,
  *,
  connection_detail,
  reach_roots,
  run_cwd,
  timeout_seconds=20,
  max_output_bytes=4096,
):
  """Run the policy observer and return a strong observed identity."""
  _validate_observer(observer, connection_detail, reach_roots, run_cwd)
  env_var = observer["connectionEnvVar"]
  command = observer["command"]
  try:
    completed = subprocess.run(
      command,
      cwd=run_cwd,
      capture_output=True,
      timeout=timeout_seconds,
      shell=False,
      env={env_var: connection_detail},
    )
  except (OSError, subprocess.TimeoutExpired):
    raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_FAILED)

  if completed.returncode != 0:
    raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_FAILED)
  stdout = completed.stdout
  if len(stdout) > max_output_bytes:
    raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_FAILED)
  try:
    text = stdout.decode("utf-8")
  except UnicodeDecodeError:
    raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_FAILED)
  stripped = text.strip()
  if not stripped or "\n" in stripped or any(ord(ch) < 32 or ord(ch) == 127 for ch in stripped):
    raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_FAILED)

  return {
    "identity": stripped,
    "provenance": "observed",
    "strength": "strong",
    "weaker": False,
  }


def app_reported_identity(value):
  """Record a weaker app-reported identity when no observer is declared."""
  if not isinstance(value, str) or not value:
    raise PilotBoundaryError(REFUSAL_DATASTORE_IDENTITY_UNAVAILABLE)
  return {
    "identity": value,
    "provenance": "app-reported",
    "strength": "weaker",
    "weaker": True,
  }


def check_datastore_identity(binding, observation, expected_identity):
  """Compare observed identity against policy expectation."""
  protected = check_protected_identity(binding, observation["identity"])
  if not protected["ok"]:
    return {
      "ok": False,
      "reason": protected["reason"],
      "provenance": observation["provenance"],
      "strength": observation["strength"],
      "match": False,
    }
  if not isinstance(expected_identity, str) or not expected_identity:
    return {
      "ok": False,
      "reason": REFUSAL_DATASTORE_IDENTITY_UNAVAILABLE,
      "provenance": observation["provenance"],
      "strength": observation["strength"],
      "match": False,
    }
  if observation["identity"] != expected_identity:
    return {
      "ok": False,
      "reason": REFUSAL_DATASTORE_IDENTITY_MISMATCH,
      "provenance": observation["provenance"],
      "strength": observation["strength"],
      "match": False,
    }
  return {
    "ok": True,
    "reason": None,
    "provenance": observation["provenance"],
    "strength": observation["strength"],
    "match": True,
  }


def boundary_verdict(
  binding,
  *,
  checks,
  policy_digest,
  datastore_identity=None,
  verified_at=None,
):
  """Assemble a traveling verdict with outcomes only — no policy material."""
  check_entries = []
  first_failure_reason = None
  for name, result in checks:
    entry = {
      "check": name,
      "result": "pass" if result["ok"] else "refuse",
      "reason": result["reason"],
    }
    check_entries.append(entry)
    if not result["ok"] and first_failure_reason is None:
      first_failure_reason = result["reason"]

  verdict = {
    "schemaVersion": BOUNDARY_SCHEMA_VERSION,
    "slotRef": binding["slotRef"],
    "result": "pass" if first_failure_reason is None else "refuse",
    "reason": first_failure_reason,
    "checks": check_entries,
    "datastoreIdentity": None,
    "policyDigest": policy_digest,
    "verifiedAt": verified_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
  }
  if datastore_identity is not None:
    verdict["datastoreIdentity"] = {
      "provenance": datastore_identity["provenance"],
      "strength": datastore_identity["strength"],
      "match": datastore_identity["match"],
    }
  return verdict


def authorize_credentials(verdict, slot_ref, policy_digest):
  """Authorize credential minting only for a verified passing verdict."""
  if not isinstance(verdict, dict):
    raise PilotBoundaryError(REFUSAL_UNVERIFIED)
  schema_version = verdict.get("schemaVersion")
  if type(schema_version) is not int or schema_version != BOUNDARY_SCHEMA_VERSION:
    raise PilotBoundaryError(REFUSAL_UNVERIFIED)
  if verdict.get("result") != "pass":
    raise PilotBoundaryError(REFUSAL_UNVERIFIED)

  try:
    slot, generation = pilot_slot.parse_slot_ref(slot_ref)
    canonical_slot_ref = pilot_slot.format_slot_ref(slot, generation)
  except pilot_slot.PilotSlotError:
    raise PilotBoundaryError(REFUSAL_UNVERIFIED)

  if verdict.get("slotRef") != canonical_slot_ref:
    raise PilotBoundaryError(REFUSAL_UNVERIFIED)
  if (
    not isinstance(policy_digest, str)
    or not policy_digest
    or verdict.get("policyDigest") != policy_digest
  ):
    raise PilotBoundaryError(REFUSAL_UNVERIFIED)

  return {
    "slotRef": canonical_slot_ref,
    "policyDigest": policy_digest,
    "authorized": True,
  }


def _parse_origin_or_none(value):
  if not isinstance(value, str):
    return None
  sep_index = value.find("://")
  if sep_index < 1:
    return None
  scheme = value[:sep_index]
  if scheme.lower() not in ("http", "https"):
    return None
  rest = value[sep_index + 3:]
  if not rest or "/" in rest or "?" in rest or "#" in rest:
    return None
  if "@" in rest:
    return None

  if rest.startswith("["):
    close = rest.find("]")
    if close < 2 or close == len(rest) - 1:
      return None
    host = rest[:close + 1]
    if rest[close + 1:] != "" and not rest[close + 1:].startswith(":"):
      return None
    port_part = rest[close + 2:] if rest[close + 1:] else None
    if port_part is None:
      return None
  else:
    colon = rest.rfind(":")
    if colon < 1:
      return None
    host = rest[:colon]
    port_part = rest[colon + 1:]

  if not host or "*" in host or any(ch.isspace() for ch in host):
    return None
  if host.startswith("[") and not host.endswith("]"):
    return None
  if not host.startswith("[") and "/" in host:
    return None

  if not port_part or not port_part.isascii() or not port_part.isdigit():
    return None
  if len(port_part) > 1 and port_part[0] == "0":
    return None
  port = int(port_part)
  if port < 1 or port > 65535:
    return None

  return "%s://%s:%d" % (scheme.lower(), host.lower() if not host.startswith("[") else host, port)


def _path_components(path):
  return os.path.realpath(path).split(os.sep)


def _is_inside(path, root):
  path_parts = _path_components(path)
  root_parts = _path_components(root)
  if len(path_parts) < len(root_parts):
    return False
  return path_parts[:len(root_parts)] == root_parts


def _is_outside_all_reach_roots(path, reach_roots):
  real = os.path.realpath(path)
  for root in reach_roots:
    if _is_inside(real, root):
      return False
  return True


def _validate_observer(observer, connection_detail, reach_roots, run_cwd):
  if not isinstance(observer, dict) or set(observer.keys()) != {"command", "connectionEnvVar"}:
    raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)

  command = observer["command"]
  if not isinstance(command, list) or not command:
    raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)
  for part in command:
    if not isinstance(part, str) or not part:
      raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)

  env_var = observer["connectionEnvVar"]
  if not isinstance(env_var, str) or not _CONNECTION_ENV_VAR_RE.match(env_var):
    raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)

  if not isinstance(connection_detail, str) or not connection_detail:
    raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)

  if not isinstance(reach_roots, list):
    raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)
  for root in reach_roots:
    if not isinstance(root, str) or not os.path.isabs(root):
      raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)

  if not isinstance(run_cwd, str) or not os.path.isdir(run_cwd):
    raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)

  executable = command[0]
  if not os.path.isabs(executable):
    raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)
  try:
    st = os.stat(executable)
  except OSError:
    raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)
  if not stat.S_ISREG(st.st_mode):
    raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)
  if not _is_outside_all_reach_roots(executable, reach_roots):
    raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)

  if not _is_outside_all_reach_roots(run_cwd, reach_roots):
    raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)

  for part in command[1:]:
    candidate = part if os.path.isabs(part) else os.path.join(run_cwd, part)
    if os.path.exists(candidate) and not _is_outside_all_reach_roots(candidate, reach_roots):
      raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)
