"""Shared clause-guard chokepoint for drift detectors.

A declared clause is a complete normalized sentence or an explicitly bounded block,
not a bare fragment — a fragment can survive at its declared count while the obligation
around it is deleted, which is the rejected substring shape at finer granularity.
"""
import os
import re


def _heading_level(line):
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    match = re.match(r"^(#+)\s", stripped)
    return len(match.group(1)) if match else None


def section_span(lines, heading, label):
    """Return (start, end) line indices for a bounded markdown section."""
    indices = [i for i, line in enumerate(lines) if line.strip() == heading]
    if len(indices) == 0:
        raise RuntimeError(
            f"{label}: expected exactly one {heading!r} line, found 0"
        )
    if len(indices) > 1:
        raise RuntimeError(
            f"{label}: expected exactly one {heading!r} line, found {len(indices)}"
        )
    start = indices[0]
    start_level = _heading_level(lines[start])
    end = len(lines)
    for i in range(start + 1, len(lines)):
        level = _heading_level(lines[i])
        if level is not None and level <= start_level:
            end = i
            break
    return start, end


def normalize_clause(clause):
    """Compile a whitespace-tolerant but otherwise literal clause matcher."""
    return re.compile(r"\s+".join(re.escape(part) for part in clause.split()))


def count_clause_in_section(text, rel, section_heading, clause):
    """Count non-overlapping clause matches inside a bounded section."""
    lines = text.splitlines()
    start, end = section_span(lines, section_heading, rel)
    section_text = "\n".join(lines[start:end])
    pattern = normalize_clause(clause)
    return len(pattern.findall(section_text))


def check_clause(text, rel, section_heading, clause, expected_count):
    """Raise AssertionError when the section's clause count differs from expected."""
    actual = count_clause_in_section(text, rel, section_heading, clause)
    if actual != expected_count:
        raise AssertionError(
            f"{rel} (section {section_heading}): clause {clause!r} expected count "
            f"{expected_count}, found {actual} — re-sync the text or update the roster"
        )


def census_excluded(rel, excluded_dirs, excluded_files):
    """Whether a plugin-relative path is outside a pointer-census walk."""
    norm = os.path.normpath(rel)
    excluded_file_norms = {os.path.normpath(name) for name in excluded_files}
    if norm in excluded_file_norms:
        return True
    for d in excluded_dirs:
        normdir = os.path.normpath(d)
        if norm.startswith(normdir + os.sep):
            return True
    return False


def _mutate_section(text, rel, section_heading, new_section_text):
    lines = text.splitlines()
    start, end = section_span(lines, section_heading, rel)
    new_lines = lines[:start] + new_section_text.splitlines() + lines[end:]
    return "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")


def without_clause_in_section(text, rel, section_heading, clause):
    """Remove every clause occurrence inside the section; never writes to disk."""
    lines = text.splitlines()
    start, end = section_span(lines, section_heading, rel)
    section_text = "\n".join(lines[start:end])
    pattern = normalize_clause(clause)
    before = len(pattern.findall(section_text))
    if before < 1:
        raise AssertionError(
            f"mutation setup: clause {clause!r} not found in {rel} section "
            f"{section_heading!r} (count={before})"
        )
    new_section = pattern.sub("", section_text, count=before)
    after = len(pattern.findall(new_section))
    if after != 0:
        raise AssertionError(
            f"mutation setup: clause {clause!r} still in {rel} section "
            f"{section_heading!r} after removal (count={after})"
        )
    mutated = _mutate_section(text, rel, section_heading, new_section)
    if mutated == text:
        raise AssertionError(
            f"mutation setup: {rel} section {section_heading!r} unchanged after "
            f"removing clause {clause!r}"
        )
    return mutated


def drop_one_occurrence_in_section(text, rel, section_heading, clause):
    """Remove exactly one clause occurrence inside the section; never writes to disk."""
    lines = text.splitlines()
    start, end = section_span(lines, section_heading, rel)
    section_text = "\n".join(lines[start:end])
    pattern = normalize_clause(clause)
    before = len(pattern.findall(section_text))
    if before < 2:
        raise AssertionError(
            f"mutation setup: clause {clause!r} in {rel} section {section_heading!r} "
            f"has count {before} (need at least 2 for partial-drift mutant)"
        )
    new_section = pattern.sub("", section_text, count=1)
    after = len(pattern.findall(new_section))
    if after != before - 1:
        raise AssertionError(
            f"mutation setup: clause {clause!r} in {rel} section {section_heading!r} "
            f"expected count {before - 1} after drop, found {after}"
        )
    mutated = _mutate_section(text, rel, section_heading, new_section)
    if mutated == text:
        raise AssertionError(
            f"mutation setup: {rel} section {section_heading!r} unchanged after "
            f"dropping one occurrence of clause {clause!r}"
        )
    return mutated


def add_one_occurrence_in_section(text, rel, section_heading, clause):
    """Insert one additional clause occurrence inside the section; never writes to disk."""
    lines = text.splitlines()
    start, end = section_span(lines, section_heading, rel)
    section_text = "\n".join(lines[start:end])
    pattern = normalize_clause(clause)
    before = len(pattern.findall(section_text))
    planted_line = clause
    section_lines = section_text.splitlines()
    new_section_lines = section_lines[:1] + [planted_line] + section_lines[1:]
    new_section = "\n".join(new_section_lines)
    after = len(pattern.findall(new_section))
    if after != before + 1:
        raise AssertionError(
            f"mutation setup: clause {clause!r} in {rel} section {section_heading!r} "
            f"expected count {before + 1} after insert, found {after}"
        )
    mutated = _mutate_section(text, rel, section_heading, new_section)
    if mutated == text:
        raise AssertionError(
            f"mutation setup: {rel} section {section_heading!r} unchanged after "
            f"adding one occurrence of clause {clause!r}"
        )
    return mutated


def plant_clause_elsewhere(text, rel, source_section, target_section, clause):
    """Move every source occurrence to one target occurrence; never writes to disk."""
    lines = text.splitlines()
    source_start, source_end = section_span(lines, source_section, rel)
    source_text = "\n".join(lines[source_start:source_end])
    pattern = normalize_clause(clause)
    source_before = len(pattern.findall(source_text))
    if source_before < 1:
        raise AssertionError(
            f"mutation setup: clause {clause!r} not found in {rel} section "
            f"{source_section!r} (count={source_before})"
        )
    new_source = pattern.sub("", source_text, count=source_before)
    source_after = len(pattern.findall(new_source))
    if source_after != 0:
        raise AssertionError(
            f"mutation setup: clause {clause!r} still in {rel} section "
            f"{source_section!r} after removal (count={source_after})"
        )
    interim_lines = lines[:source_start] + new_source.splitlines() + lines[source_end:]
    interim = "\n".join(interim_lines) + ("\n" if text.endswith("\n") else "")

    target_lines = interim.splitlines()
    target_start, target_end = section_span(target_lines, target_section, rel)
    target_text = "\n".join(target_lines[target_start:target_end])
    target_before = len(pattern.findall(target_text))
    target_section_lines = target_text.splitlines()
    new_target_lines = target_section_lines[:1] + [clause] + target_section_lines[1:]
    new_target = "\n".join(new_target_lines)
    target_after = len(pattern.findall(new_target))
    if target_after != target_before + 1:
        raise AssertionError(
            f"mutation setup: clause {clause!r} in {rel} section {target_section!r} "
            f"expected count {target_before + 1} after plant, found {target_after}"
        )
    final_lines = (
        target_lines[:target_start]
        + new_target.splitlines()
        + target_lines[target_end:]
    )
    mutated = "\n".join(final_lines) + ("\n" if text.endswith("\n") else "")
    if mutated == text:
        raise AssertionError(
            f"mutation setup: {rel} unchanged after planting clause {clause!r} from "
            f"{source_section!r} into {target_section!r}"
        )
    return mutated
