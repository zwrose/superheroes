# plugins/superheroes/lib/task_list_cli.py
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import definition_doc, docload, task_list

ap = argparse.ArgumentParser()
ap.add_argument("--work-item", required=True)
a = ap.parse_args()
root = os.getcwd()
try:
    _fm, body = docload.load_doc(definition_doc.doc_path(a.work_item, "tasks", root))
except (OSError, ValueError):          # missing/malformed tasks doc -> fail closed (empty)
    print(json.dumps({"tasks": []}))
    sys.exit(0)
print(json.dumps({"tasks": task_list.parse(body)}))
