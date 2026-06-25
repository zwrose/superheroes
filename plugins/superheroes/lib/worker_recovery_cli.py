# plugins/superheroes/lib/worker_recovery_cli.py
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worker_recovery

ap = argparse.ArgumentParser()
ap.add_argument("--attempt", required=True)
ap.add_argument("--signal", required=True)
ap.add_argument("--max-attempts", type=int, default=worker_recovery.DEFAULT_MAX_ATTEMPTS)
a = ap.parse_args()
try:
    attempt = int(a.attempt)
except (TypeError, ValueError):                    # malformed attempt -> fail closed (park)
    print(json.dumps({"action": "park", "reason": "malformed --attempt"}))
    sys.exit(0)
print(json.dumps(worker_recovery.decide(attempt, a.signal, a.max_attempts)))
