# plugins/superheroes/lib/phase_step_cli.py
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phase_step

ap = argparse.ArgumentParser()
ap.add_argument("--result", required=True)   # JSON {confidence, assumptions}
ap.add_argument("--gate", default=None)
a = ap.parse_args()
try:
    result = json.loads(a.result)
except ValueError:                                 # malformed phase JSON -> fail closed (park)
    print(json.dumps({"action": "park_unexpected_gate", "reason": "malformed --result phase JSON"}))
    sys.exit(0)
print(json.dumps(phase_step.decide(result, a.gate)))
