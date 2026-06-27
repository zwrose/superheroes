import os, subprocess
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

def test_committed_bundle_matches_fresh_emit():
    r = subprocess.run(
        ["node", "plugins/superheroes/lib/bundle_showrunner.js", "--check"],
        cwd=ROOT, text=True, capture_output=True, timeout=30)
    assert r.returncode == 0, r.stdout + r.stderr
