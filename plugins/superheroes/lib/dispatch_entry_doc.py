#!/usr/bin/env python3
"""Generate dispatch-entry.md from the dispatch shell's argparse declarations.

Reads parser trees only — never dispatches, spawns, or touches the network.
"""
from __future__ import annotations

import argparse
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import cli_contract as cc  # noqa: E402
import dispatch_guard  # noqa: E402
import engine_adapter  # noqa: E402
import engine_dispatch  # noqa: E402
import liveness_cache  # noqa: E402
import seat_bundle  # noqa: E402

_PLUGIN_ROOT = os.path.normpath(os.path.join(_LIB_DIR, ".."))
_DEFAULT_OUT = os.path.join(
    _PLUGIN_ROOT, "skills", "workhorse", "reference", "dispatch-entry.md"
)
_REGEN_CMD = "/usr/bin/python3 -B plugins/superheroes/lib/dispatch_entry_doc.py"
_CONTRACT_REQUIRED = (
    ("engine_dispatch", engine_dispatch),
    ("dispatch_guard", dispatch_guard),
)


class DispatchEntryDocError(Exception):
    """Raised when the generator cannot derive the entry doc."""


def _format_default(action: argparse.Action) -> str:
    if action.default is None:
        return "none"
    if action.default is argparse.SUPPRESS:
        return "none"
    if isinstance(action.default, str):
        return action.default
    return repr(action.default)


def _format_options(action: argparse.Action) -> str:
    opts = action.option_strings
    if opts:
        return ", ".join(opts)
    return action.dest


def _subcommand_label(cli_name: str, path: tuple[str, ...]) -> str:
    if not path:
        return cli_name
    return "%s %s" % (cli_name, " ".join(path))


def _iter_subcommands(parser: argparse.ArgumentParser, cli_name: str):
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
        yield _subcommand_label(cli_name, path), current


def _collect_undeclared_contracts() -> list[tuple[str, tuple[str, ...], str, str]]:
    defects = []
    for cli_name, mod in _CONTRACT_REQUIRED:
        parser = mod.build_parser()
        for path, opts, dest in cc.census_undeclared(parser):
            defects.append((cli_name, path, opts, dest))
    return defects


def _argument_rows(parser: argparse.ArgumentParser) -> list[tuple[str, str, str, str, str]]:
    rows = []
    for _path, action in cc.iter_caller_supplied_actions(parser):
        contract = cc.contract_for_action(action)
        if contract is None:
            contract = "undeclared"
        required = "yes" if action.required else "no"
        rows.append((
            _format_options(action),
            required,
            contract,
            _format_default(action),
            (action.help or "").strip(),
        ))
    return rows


def _render_argument_table(rows: list[tuple[str, str, str, str, str]]) -> list[str]:
    if not rows:
        return ["No caller-supplied flags.", ""]
    out = [
        "| Flag | Required | Contract | Default | Help |",
        "| --- | --- | --- | --- | --- |",
    ]
    for flag, required, contract, default, help_text in rows:
        help_text = help_text.replace("|", "\\|")
        out.append("| `%s` | %s | `%s` | %s | %s |" % (
            flag, required, contract, default, help_text,
        ))
    out.append("")
    return out


def _envelope_values() -> dict[str, int]:
    return {
        "max_wait_min": engine_dispatch.MIN_SYNC_WAIT,
        "max_wait_max": engine_dispatch.MAX_SYNC_WAIT,
        "run_lock_ttl": engine_dispatch.RUN_LOCK_TTL,
        "dispatch_timeout": engine_dispatch.RETRY_MIN_TIMEOUT,
        "expected_items_cap": engine_dispatch.MAX_EXPECTED_ITEMS,
        "stdout_capture_cap": engine_dispatch.MAX_STDOUT_CAPTURE,
        "stderr_capture_cap": engine_dispatch.MAX_STDERR_CAPTURE,
        "abandon_confirm_seconds": engine_dispatch.ABANDON_CONFIRM_SECONDS,
        "liveness_cache_ttl": liveness_cache.DEFAULT_TTL_SECONDS,
    }


def _render_envelope() -> list[str]:
    values = _envelope_values()
    return [
        "## Variance envelope",
        "",
        "The dispatch shell declares what may vary and what may not. Dropped entry-surface rows "
        "appear in neither half.",
        "",
        "### Never varies (hard shell)",
        "",
        "- The supervisor journal (`journal.jsonl` under the journal root).",
        "- The run lock (`run.lock` in each run directory).",
        "- `--max-wait` bounds enforcement (callers may choose a slice inside the declared range; "
        "the runner refuses outside it).",
        "- The run-directory layout (prompt, progress, stdout, stderr, terminal marker).",
        "- The parse, scrub, and forfeit-grading boundary (engine stdout is evidence; the runner "
        "grades and folds).",
        "- The allowlist gate (`dispatch_guard.py check`) on every dispatch path.",
        "- Every terminal result carries `ok`, `terminal`, `runDir`, and `argv`.",
        "",
        "### Declared soft (each bound read from code at generation time)",
        "",
        "| Surface | Bound |",
        "| --- | --- |",
        "| `--max-wait` range | [%d, %d] seconds |" % (
            values["max_wait_min"], values["max_wait_max"],
        ),
        "| Run-lock TTL | %d seconds (`2 × MAX_SYNC_WAIT`) |" % values["run_lock_ttl"],
        "| Dispatch timeouts (`--timeout`, `--retry-timeout` default) | %d seconds |" % (
            values["dispatch_timeout"],
        ),
        "| Expected-items cap (`--expect-item` / `--expect-items-file`) | %d paths |" % (
            values["expected_items_cap"],
        ),
        "| Stdout capture cap | %d bytes |" % values["stdout_capture_cap"],
        "| Stderr capture cap | %d bytes |" % values["stderr_capture_cap"],
        "| Abandon confirm window | %d seconds |" % values["abandon_confirm_seconds"],
        "| Liveness cache TTL | %d seconds |" % values["liveness_cache_ttl"],
        "",
    ]


def _parser_sections() -> list[str]:
    parsers = (
        ("engine_dispatch.py", engine_dispatch.build_parser()),
        ("engine_adapter.py", engine_adapter.build_parser()),
        ("dispatch_guard.py", dispatch_guard.build_parser()),
    )
    out: list[str] = [
        "## Dispatch CLIs",
        "",
        "Each table is derived from the parser tree at generation time. Regenerate this file after "
        "any argument change.",
        "",
    ]
    for cli_name, parser in parsers:
        out.append("### `%s`" % cli_name)
        out.append("")
        for sub_name, subparser in _iter_subcommands(parser, cli_name):
            out.append("#### `%s`" % sub_name)
            out.append("")
            out.extend(_render_argument_table(_argument_rows(subparser)))
    return out


def generate(*, check_contracts: bool = True) -> str:
    if check_contracts:
        defects = _collect_undeclared_contracts()
        if defects:
            lines = ["undeclared caller-contract arguments:"]
            for cli_name, path, opts, dest in defects:
                label = _subcommand_label(cli_name, path)
                lines.append("  %s: %s (%s)" % (label, opts, dest))
            raise DispatchEntryDocError("\n".join(lines))

    lines = [
        "<!-- generated by %s — do not edit by hand -->" % _REGEN_CMD,
        "# Contents",
        "",
        "1. [Dispatch entry reference](#dispatch-entry-reference)",
        "2. [Accepted seat shapes](#accepted-seat-shapes)",
        "3. [Dispatch CLIs](#dispatch-clis)",
        "4. [Variance envelope](#variance-envelope)",
        "",
        "---",
        "",
        "# Dispatch entry reference",
        "",
        "Generated from the dispatch shell's argparse declarations. To refresh after an argument "
        "change, run:",
        "",
        "    %s" % _REGEN_CMD,
        "",
        "## Accepted seat shapes",
        "",
        seat_bundle.accepted_seat_detail() + ". " + seat_bundle.accepted_role_detail(),
        "",
    ]
    lines.extend(_parser_sections())
    lines.extend(_render_envelope())
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    out_path = _DEFAULT_OUT
    if argv:
        if len(argv) != 1 or argv[0] != "--check":
            sys.stderr.write("usage: dispatch_entry_doc.py [--check]\n")
            return 2
        out_path = _DEFAULT_OUT
    try:
        text = generate()
    except DispatchEntryDocError as exc:
        sys.stderr.write("dispatch_entry_doc error: %s\n" % exc)
        return 1
    if argv and argv[0] == "--check":
        if not os.path.isfile(out_path):
            sys.stderr.write(
                "dispatch_entry_doc error: %s is missing — run the generator\n" % out_path
            )
            return 1
        with open(out_path, encoding="utf-8") as fh:
            committed = fh.read()
        if committed != text:
            sys.stderr.write(
                "dispatch_entry_doc error: %s is stale — run the generator\n" % out_path
            )
            return 1
        sys.stdout.write("%s: ok\n" % out_path)
        return 0
    try:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError as exc:
        sys.stderr.write("dispatch_entry_doc error: cannot write %s: %s\n" % (out_path, exc))
        return 1
    sys.stdout.write(out_path + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
