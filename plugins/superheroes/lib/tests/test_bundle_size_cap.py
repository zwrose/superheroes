import os

# Mechanical size tripwire for the generated showrunner bundle (#295).
#
# The Claude Code Workflow tool hard-caps both `script` and `scriptPath` payloads at 524,288 bytes;
# a bundle over that ceiling cannot launch at all (the call is rejected before any agent dispatches).
# Bundle growth has run ~20-38KB per feature PR, so a single unnoticed merge can breach the cap.
#
# Guard threshold = cap - 2 x worst-observed-single-merge-jump:
#     524,288  (Workflow script-size cap, bytes)
#   - 2 x 38,000  (worst observed single-merge growth ~38KB, 0.10.0 -> PR #285, with a 2x safety margin)
#   = 448,288  ->  rounded DOWN to 448,000 for a clean number.
#
# So CI reddens with two worst-case merges of headroom to spare, long before the Workflow tool would
# refuse to launch. Assert against the COMMITTED artifact's byte size (what actually gets launched),
# not a fresh emit — this is the size gate; bundle freshness vs. the emitter is test_bundle_drift.py's
# job, and parseability is showrunner_bundle_smoke.js's.
GUARD_BYTES = 448_000

BUNDLE = os.path.join(os.path.dirname(__file__), "..", "showrunner.bundle.js")


def test_committed_bundle_under_workflow_size_cap():
    size = os.path.getsize(BUNDLE)
    assert size <= GUARD_BYTES, (
        f"showrunner.bundle.js is {size} bytes, over the {GUARD_BYTES}-byte guard "
        f"(Workflow cap 524288 - 2x ~38KB worst-merge margin). Comment stripping in "
        f"bundle_showrunner.js should keep it well under; regenerate with "
        f"`node plugins/superheroes/lib/bundle_showrunner.js --write` and investigate the growth."
    )
