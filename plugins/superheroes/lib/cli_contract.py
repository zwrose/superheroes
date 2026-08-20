"""Argparse-level caller-contract builders for dispatch CLIs.

Each builder is usable as argparse ``type=`` and carries ``__cli_contract__`` metadata so a census
can read declarations off the parsers themselves. Failures are ``argparse.ArgumentTypeError`` —
the process exits before any work, subprocess, or dispatch.
"""
from __future__ import annotations

import argparse
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import model_registry  # noqa: E402

CLI_CONTRACT_ATTR = "__cli_contract__"
ACTION_CONTRACT_ATTR = "cli_contract"
VALIDATED_CONTRACT_ATTR = "cli_contract_validated"
ACTION_ONLY_CONTRACTS = frozenset({"boolean-flag"})


def _format_valid(values: tuple[str, ...]) -> str:
    return ", ".join(values)


def _all_effort_values() -> tuple[str, ...]:
    seen: list[str] = []
    for vendor in model_registry.vendors():
        for effort in model_registry.effort_enum(vendor):
            if effort not in seen:
                seen.append(effort)
    return tuple(seen)


def role(value: str) -> str:
    if value not in model_registry.roles():
        valid = _format_valid(model_registry.roles())
        raise argparse.ArgumentTypeError(
            f"unknown role {value!r} — not a registered dispatch role; valid roles: {valid}"
        )
    return value


role.__cli_contract__ = "role"  # type: ignore[attr-defined]


def vendor(value: str) -> str:
    if value not in model_registry.vendors():
        valid = _format_valid(model_registry.vendors())
        raise argparse.ArgumentTypeError(
            f"unknown vendor {value!r}; valid vendors: {valid}"
        )
    return value


vendor.__cli_contract__ = "vendor"  # type: ignore[attr-defined]


def effort(value: str) -> str:
    valid_efforts = _all_effort_values()
    if value not in valid_efforts:
        valid = _format_valid(valid_efforts)
        raise argparse.ArgumentTypeError(
            f"unknown effort {value!r}; valid effort values: {valid}"
        )
    return value


effort.__cli_contract__ = "effort"  # type: ignore[attr-defined]


def model_not_a_role(value: str) -> str:
    if value in model_registry.roles():
        raise argparse.ArgumentTypeError(
            f"{value!r} is a dispatch role name, not a model — pass it via --role"
        )
    return value


model_not_a_role.__cli_contract__ = "model-not-a-role"  # type: ignore[attr-defined]


def existing_directory(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise argparse.ArgumentTypeError("path must be a non-empty string")
    path = value.strip()
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(f"{path!r} does not exist")
    if os.path.isfile(path) or not os.path.isdir(path):
        raise argparse.ArgumentTypeError(f"{path!r} exists but is not a directory")
    return path


existing_directory.__cli_contract__ = "existing-directory"  # type: ignore[attr-defined]


def creatable_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise argparse.ArgumentTypeError("path must be a non-empty string")
    path = value.strip()
    if os.path.exists(path):
        if os.path.isfile(path):
            raise argparse.ArgumentTypeError(f"{path!r} exists but is not a directory")
        if not os.path.isdir(path):
            raise argparse.ArgumentTypeError(f"{path!r} exists but is not a directory")
        return path
    probe = os.path.abspath(path)
    while not os.path.exists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            raise argparse.ArgumentTypeError(
                f"cannot create {path!r}: no parent directory"
            )
        probe = parent
    if os.path.isfile(probe):
        raise argparse.ArgumentTypeError(
            f"cannot create {path!r}: nearest existing ancestor {probe!r} is not a directory"
        )
    if not os.path.isdir(probe):
        raise argparse.ArgumentTypeError(
            f"cannot create {path!r}: nearest existing ancestor {probe!r} is not a directory"
        )
    return path


creatable_path.__cli_contract__ = "creatable-path"  # type: ignore[attr-defined]


def repo_root(value: str) -> str:
    path = existing_directory(value)
    if not os.path.exists(os.path.join(path, ".git")):
        raise argparse.ArgumentTypeError(
            f"{value.strip()!r} is not a git repository (missing .git)"
        )
    return path


repo_root.__cli_contract__ = "repo-root"  # type: ignore[attr-defined]


def free_text(value: str) -> str:
    return value


free_text.__cli_contract__ = "free-text"  # type: ignore[attr-defined]


def integer(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not a valid integer") from exc


integer.__cli_contract__ = "integer"  # type: ignore[attr-defined]


def optional_model_not_a_role(value: str | None) -> str | None:
    if value is None:
        return None
    return model_not_a_role(value)


optional_model_not_a_role.__cli_contract__ = "model-not-a-role"  # type: ignore[attr-defined]


def contract_for_action(action: argparse.Action) -> str | None:
    """Return the declared contract name for a parser action, if any."""
    declared = getattr(action, ACTION_CONTRACT_ATTR, None)
    if isinstance(declared, str) and declared:
        return declared
    type_fn = action.type
    if type_fn is not None:
        contract = getattr(type_fn, CLI_CONTRACT_ATTR, None)
        if isinstance(contract, str) and contract:
            return contract
    if action.choices:
        return "choices:" + ",".join(str(choice) for choice in action.choices)
    return None


def contract_is_validated(action: argparse.Action) -> bool:
    """Return whether the action's declared contract has an attached validator."""
    contract = contract_for_action(action)
    if contract is None:
        return False
    if contract in ACTION_ONLY_CONTRACTS:
        return action.nargs == 0 or action.const in (True, False, None)
    if contract and contract.startswith("choices:"):
        return action.choices is not None
    type_fn = action.type
    if type_fn is not None:
        if getattr(type_fn, CLI_CONTRACT_ATTR, None) == contract:
            return True
        if contract == "integer" and type_fn is int:
            return True
    return False


def add_argument(parser, *args, contract: str, **kwargs):
    """Add an argparse argument and attach its caller-contract declaration."""
    type_map = {
        "role": role,
        "vendor": vendor,
        "effort": effort,
        "model-not-a-role": model_not_a_role,
        "existing-directory": existing_directory,
        "creatable-path": creatable_path,
        "repo-root": repo_root,
        "free-text": free_text,
        "integer": integer,
    }
    if contract == "boolean-flag":
        kwargs.setdefault("action", "store_true")
    elif "type" not in kwargs and contract in type_map:
        kwargs["type"] = type_map[contract]
    action = parser.add_argument(*args, **kwargs)
    setattr(action, ACTION_CONTRACT_ATTR, contract)
    setattr(action, VALIDATED_CONTRACT_ATTR, contract_is_validated(action))
    return action


def iter_caller_supplied_actions(parser: argparse.ArgumentParser):
    """Yield (subcommand_path, action) for every caller-supplied flag on a parser tree."""
    stack: list[tuple[tuple[str, ...], argparse.ArgumentParser]] = [((), parser)]
    while stack:
        path, current = stack.pop()
        subparsers = None
        for action in current._actions:
            if isinstance(action, argparse._SubParsersAction):
                subparsers = action
                break
        if subparsers is not None:
            for name, subparser in subparsers.choices.items():
                stack.append((path + (name,), subparser))
            continue
        for action in current._actions:
            if not action.option_strings:
                continue
            if action.dest == "help":
                continue
            yield path, action


def census_undeclared(parser: argparse.ArgumentParser) -> list[tuple[tuple[str, ...], str, str]]:
    """Return undeclared caller-supplied arguments as (path, option_strings, dest)."""
    missing = []
    for path, action in iter_caller_supplied_actions(parser):
        if contract_for_action(action) is None:
            opts = ",".join(action.option_strings) or action.dest
            missing.append((path, opts, action.dest))
    return missing


def census_unvalidated(parser: argparse.ArgumentParser) -> list[tuple[tuple[str, ...], str, str, str]]:
    """Return declared-but-unvalidated arguments as (path, option_strings, dest, contract)."""
    unvalidated = []
    for path, action in iter_caller_supplied_actions(parser):
        contract = contract_for_action(action)
        if contract is None:
            continue
        if not getattr(action, VALIDATED_CONTRACT_ATTR, contract_is_validated(action)):
            opts = ",".join(action.option_strings) or action.dest
            unvalidated.append((path, opts, action.dest, contract))
    return unvalidated
