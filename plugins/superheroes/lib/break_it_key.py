"""The one production home of the `breakItInterpreter` calibration key name (#1961).

A leaf: it imports nothing. `core_md` (storage and emission) and `break_it` (session creation and
interpreter resolution) both import the name from here, so the two sides cannot drift apart.
"""

INTERPRETER_KEY = "breakItInterpreter"
