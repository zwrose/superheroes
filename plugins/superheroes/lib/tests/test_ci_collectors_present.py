"""CI collector presence — ensures coupling lens real-seam tests cannot silently skip."""
import os
import shutil
import sys

import pytest

_LIB = os.path.join(os.path.dirname(__file__), "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import guardian_coupling_adapters as adapters
import guardian_tools as gt

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def _resolve_collector_bin(name):
    """Locate a collector binary — mirrors test_guardian_lens_coupling._resolve_collector_bin."""
    found = shutil.which(name)
    if found:
        return found
    if name != adapters.IMPORT_LINTER_BIN:
        return None
    try:
        from importlib.metadata import distribution
        dist = distribution("import-linter")
        for f in dist.files or ():
            rel = str(f).replace("\\", "/")
            if rel.endswith("/lint-imports") or f.name == "lint-imports":
                path = os.path.realpath(str(dist.locate_file(f)))
                if os.path.isfile(path) and os.access(path, os.X_OK):
                    return path
    except Exception:
        return None
    return None


def test_ci_installs_coupling_collectors():
    # Axis: CI environment provides both coupling collectors and co-located TypeScript.
    if os.environ.get("CI") != "true":
        pytest.skip("CI-only guard — local dev without collectors must not fail")

    missing = []
    depcruise = _resolve_collector_bin(adapters.DEPCRUISE_BIN)
    if depcruise is None:
        missing.append(
            f"{adapters.DEPCRUISE_BIN} not found — install via "
            "ci.yml step 'Install coupling collectors (ungate coupling lens real-seam tests)'"
        )
    lint_imports = _resolve_collector_bin(adapters.IMPORT_LINTER_BIN)
    if lint_imports is None:
        missing.append(
            f"{adapters.IMPORT_LINTER_BIN} not found — install via "
            "ci.yml step 'Install Python dependencies (validators + tests + import-linter)'"
        )
    ts_path = gt.typescript_toolchain_node_path(_REPO_ROOT, adapters.TYPESCRIPT_SUPPORTED_MAJORS)
    if ts_path is None:
        missing.append(
            "TypeScript toolchain not resolvable next to depcruise — install via "
            "ci.yml step 'Install coupling collectors (ungate coupling lens real-seam tests)' "
            "(dependency-cruiser@18 with co-installed typescript@5)"
        )

    assert not missing, ";\n".join(missing)
