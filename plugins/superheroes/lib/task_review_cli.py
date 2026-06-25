# plugins/superheroes/lib/task_review_cli.py
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import task_review

ap = argparse.ArgumentParser()
ap.add_argument("--verdicts", required=True)
ap.add_argument("--findings", required=True)
ap.add_argument("--round", type=int, required=True)
ap.add_argument("--max-rounds", type=int, default=3)
ap.add_argument("--history", default="[]")
a = ap.parse_args()
try:
    verdicts = json.loads(a.verdicts)
    findings = json.loads(a.findings)
    history = json.loads(a.history)
except ValueError:                                 # malformed JSON -> fail closed (park)
    print(json.dumps({"action": "park", "reason": "malformed JSON arg"}))
    sys.exit(0)
print(json.dumps(task_review.decide(verdicts, findings, a.round, a.max_rounds, history)))
