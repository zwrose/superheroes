import os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
_EVAL_LIB = os.path.dirname(_HERE)
_PLUGIN_LIB = os.path.join(os.path.dirname(os.path.dirname(_EVAL_LIB)), "plugins", "superheroes", "lib")
for p in (_EVAL_LIB, _PLUGIN_LIB):
    if p not in sys.path:
        sys.path.insert(0, p)
