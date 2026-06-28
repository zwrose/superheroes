# plugins/superheroes/lib/task_list_cli.py
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import definition_doc, docload, task_list

# Rough count of lines that LOOK like task headings (any separator) — used by build_phase.js to
# distinguish "doc has zero task headings" from "format mismatch / silent parse failure".
_RAW_HEADING_RE = re.compile(r"^###\s+Task\s+\d+", re.MULTILINE)

ap = argparse.ArgumentParser()
ap.add_argument("--work-item", required=True)
a = ap.parse_args()
root = os.getcwd()
try:
    _fm, body = docload.load_doc(definition_doc.doc_path(a.work_item, "tasks", root))
except (OSError, ValueError):          # missing/malformed tasks doc -> fail closed (empty)
    print(json.dumps({"tasks": [], "raw_task_heading_count": 0}))
    sys.exit(0)
raw_count = len(_RAW_HEADING_RE.findall(body))
print(json.dumps({"tasks": task_list.parse(body), "raw_task_heading_count": raw_count}))
