"""In-memory module neutralization for bite-proofs — never writes to disk."""
import types


def patched_module(module, edits, name=None):
    """Compile a neutralized in-memory copy of `module`. Never writes to disk.

    `edits` is a sequence of (old, new) pairs, each applied exactly once, in order.
    Raises AssertionError if an `old` target is absent, or occurs more than once.
    """
    if isinstance(edits, tuple) and len(edits) == 2 and isinstance(edits[0], str):
        edits = (edits,)
    with open(module.__file__, encoding="utf-8") as fh:
        src = fh.read()
    patched = src
    for old, new in edits:
        count = patched.count(old)
        if count == 0:
            raise AssertionError("neutralization target not found: %r" % (old,))
        if count != 1:
            raise AssertionError(
                "neutralization target %r occurs %d times (expected 1)" % (old, count)
            )
        patched = patched.replace(old, new, 1)
    mod = types.ModuleType(name or module.__name__ + "__patched")
    mod.__file__ = module.__file__
    exec(compile(patched, module.__file__, "exec"), mod.__dict__)
    return mod
