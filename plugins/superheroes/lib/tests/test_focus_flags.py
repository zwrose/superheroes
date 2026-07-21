"""Real-seam tests (§12.2) for lib/focus_flags.py — the mechanical focus flags (#511).

Exercises the production call shape: a REAL unified-diff payload through
compute_focus_flags, and the REAL argv path through a subprocess run of the script.
No internal seam is monkeypatched. Also carries the §13 named-consumer drift guard.
"""
import importlib.util
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "..", "focus_flags.py")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FF = _load(_SCRIPT, "focus_flags")


# A REAL unified diff (actual `git diff` text shape) touching BOTH a migration file and a
# dependency lockfile — the real payload, no stubbed seam.
_DIFF_MIGRATION_AND_LOCK = """\
diff --git a/db/migrations/013_add_orders.sql b/db/migrations/013_add_orders.sql
new file mode 100644
index 0000000..a1b2c3d
--- /dev/null
+++ b/db/migrations/013_add_orders.sql
@@ -0,0 +1,3 @@
+CREATE TABLE orders (id SERIAL PRIMARY KEY, total NUMERIC NOT NULL);
+CREATE INDEX idx_orders_total ON orders(total);
+-- no down migration provided
diff --git a/package-lock.json b/package-lock.json
index 1111111..2222222 100644
--- a/package-lock.json
+++ b/package-lock.json
@@ -10,6 +10,6 @@
-    "left-pad": "1.2.0",
+    "left-pad": "1.3.0",
"""

# An ordinary diff: a docs edit and a plain source edit — no migration, no lockfile.
_DIFF_PLAIN = """\
diff --git a/README.md b/README.md
index 3333333..4444444 100644
--- a/README.md
+++ b/README.md
@@ -1,3 +1,3 @@
-# Old title
+# New title
diff --git a/src/util.py b/src/util.py
index 5555555..6666666 100644
--- a/src/util.py
+++ b/src/util.py
@@ -1,2 +1,2 @@
-def f(): return 1
+def f(): return 2
"""


def test_real_payload_emits_both_flags_naming_the_files():
    # Real seam: the actual function over a real diff string. Both rules fire, each naming
    # the file that triggered it.
    flags = FF.compute_focus_flags(_DIFF_MIGRATION_AND_LOCK)
    assert len(flags) == 2
    migration_flag = next(f for f in flags if "rollback" in f.lower())
    lock_flag = next(f for f in flags if "supply-chain" in f.lower())
    assert "db/migrations/013_add_orders.sql" in migration_flag
    assert "package-lock.json" in lock_flag


def test_real_argv_subprocess_prints_flags_to_stdout(tmp_path):
    # Real argv: run the script as production does — sys.executable, the real script path,
    # a real temp diff file on disk. Not just the in-process function.
    diff_path = tmp_path / "diff.txt"
    diff_path.write_text(_DIFF_MIGRATION_AND_LOCK, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, _SCRIPT, str(diff_path)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    assert len(lines) == 2
    assert any("rollback" in ln.lower() and "013_add_orders.sql" in ln for ln in lines)
    assert any("supply-chain" in ln.lower() and "package-lock.json" in ln for ln in lines)


def test_additive_only_no_false_injection_function(tmp_path):
    # The additive-only guard: a plain diff (no migration, no lockfile) yields NOTHING.
    # The mechanism can only add grep-grounded emphasis — never inject a spurious flag,
    # never remove or down-scope a lens.
    assert FF.compute_focus_flags(_DIFF_PLAIN) == []
    assert FF.compute_focus_flags("") == []


def test_additive_only_no_false_injection_cli(tmp_path):
    diff_path = tmp_path / "plain.txt"
    diff_path.write_text(_DIFF_PLAIN, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, _SCRIPT, str(diff_path)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == ""


# A hunk BODY line that renders as `+++ package-lock.json` — an added source line, NOT a
# `+++ b/` file header. The parser must not misread it as a lockfile header (false
# injection). Regression detector for the Fix-2 in-hunk tracking bug.
_DIFF_HUNK_BODY_LOOKS_LIKE_HEADER = """\
diff --git a/notes.md b/notes.md
index 111..222 100644
--- a/notes.md
+++ b/notes.md
@@ -1,1 +1,2 @@
 line one
+++ package-lock.json
"""

# A pure rename: the b-side (`package-lock.json`) is named ONLY by the `diff --git` header,
# with no `+++ b/` line for it. Exercises the b-side capture path independently.
_DIFF_RENAME_ONLY_LOCKFILE = """\
diff --git a/old_lock b/package-lock.json
similarity index 100%
rename from old_lock
rename to package-lock.json
"""

# A migration detected ONLY by its `migrations/` path segment: the basename
# (`007_thing.sql`) does match a name-regex, so give it one that does NOT — a bare
# `thing.sql` under `db/migrations/` — to exercise the directory-segment branch alone.
_DIFF_MIGRATIONS_PATH_SEGMENT = """\
diff --git a/db/migrations/thing.sql b/db/migrations/thing.sql
index 3333333..4444444 100644
--- a/db/migrations/thing.sql
+++ b/db/migrations/thing.sql
@@ -1,1 +1,1 @@
-SELECT 1;
+SELECT 2;
"""


def test_hunk_body_plus_plus_line_is_not_a_false_header():
    # Regression for Fix 2: an added source line rendering as `+++ package-lock.json` inside
    # a hunk must NOT be misread as a lockfile header — the diff touches only notes.md, so
    # NO flag fires. This is the detector that would have caught the false injection.
    assert FF.compute_focus_flags(_DIFF_HUNK_BODY_LOOKS_LIKE_HEADER) == []


def test_rename_only_b_side_captures_lockfile():
    # The lockfile is named ONLY by the `diff --git` b-side (no `+++ b/` line for it); the
    # lockfile flag must still fire from the b-side capture path.
    flags = FF.compute_focus_flags(_DIFF_RENAME_ONLY_LOCKFILE)
    assert len(flags) == 1
    assert "supply-chain" in flags[0].lower()
    assert "package-lock.json" in flags[0]


def test_migration_detected_by_path_segment_branch():
    # The basename (`thing.sql`) matches no migration name-regex; detection rides the
    # `migrations/` path segment alone. The migration flag must still fire.
    flags = FF.compute_focus_flags(_DIFF_MIGRATIONS_PATH_SEGMENT)
    assert len(flags) == 1
    assert "rollback" in flags[0].lower()
    assert "db/migrations/thing.sql" in flags[0]


def test_named_consumer_drift_guard():
    # §13 named-consumer guard: the review-code specialist dispatch (auto-fix-loop.md) is
    # the wired consumer. Read it fail-closed — if the wiring prose drops the literal
    # `focus_flags.py` reference, this test fails so the consumer can't silently drift out.
    ref = os.path.join(
        _HERE, "..", "..", "skills", "review-code", "reference", "auto-fix-loop.md"
    )
    with open(ref, "r", encoding="utf-8") as fh:
        text = fh.read()
    assert "focus_flags.py" in text
