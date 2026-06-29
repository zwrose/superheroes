import os, re
LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULES = ["showrunner.js", "review_panel_shell.js", "build_phase.js", "test_pilot_phase.js", "io_seam.js"]
IO_RE = re.compile(r"\bio\(\)\.(writeFile|readText|readJson|mkdirp)\b")
def test_every_io_io_call_is_awaited():
    offenders = []
    for m in MODULES:
        p = os.path.join(LIB, m)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                for mt in IO_RE.finditer(line):
                    if not line[:mt.start()].rstrip().endswith("await"):
                        offenders.append("%s:%d: %s" % (m, i, line.strip()))
    assert not offenders, "un-awaited io() IO call(s) — the seam is async in the bundle:\n" + "\n".join(offenders)
