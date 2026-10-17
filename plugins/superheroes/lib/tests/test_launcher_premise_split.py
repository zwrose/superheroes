import importlib.util
import inspect
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_MOD = os.path.join(_HERE, "..", "launcher.py")


def _load_launcher():
    spec = importlib.util.spec_from_file_location("launcher", _MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


L = _load_launcher()


def test_premise_helpers_never_bypass_refusal_accounting():
    # axis: a pre-reservation refusal goes through `_refuse_unreserved`, never a bare `_fail`
    for name in ("_check_premises", "_refuse_unreserved"):
        bare = [
            line.strip()
            for line in inspect.getsource(getattr(L, name)).splitlines()
            if "return _fail(" in line
        ]
        assert bare == [], "%s returns a refusal without accounting: %r" % (name, bare)
