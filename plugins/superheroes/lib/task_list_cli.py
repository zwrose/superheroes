# plugins/superheroes/lib/task_list_cli.py
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docload, task_list


def raw_task_heading_count(body):
    """Fence-aware count of lines that LOOK like task headings (any separator) — used by
    build_phase.js to distinguish "doc has zero task headings" from "format mismatch / silent parse
    failure". Delegates to task_list so the raw count and the parse count are computed over the SAME
    (unfenced) lines: a fenced `### Task N` example does not inflate the count (C-I2)."""
    return task_list.raw_heading_count(body)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--work-item", required=True)
    a = ap.parse_args(argv[1:])
    root = os.getcwd()
    try:
        _fm, body = docload.load_doc(docload.tasks_doc_path(a.work_item, root))
    except (OSError, ValueError):      # missing/malformed tasks doc -> fail closed (empty)
        print(json.dumps({"tasks": [], "raw_task_heading_count": 0}))
        return 0
    raw_count = raw_task_heading_count(body)
    print(json.dumps({"tasks": task_list.parse(body), "raw_task_heading_count": raw_count}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
