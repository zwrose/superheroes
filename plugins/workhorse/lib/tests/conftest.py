import os
import sys

# Put the lib dir (parent of tests/) on sys.path so tests can
# `import enforcer` / `import band_lib` directly (test-pilot / review-crew style).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
