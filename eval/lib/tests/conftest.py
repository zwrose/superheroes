import os
import sys

# Put eval/lib (parent of tests/) on sys.path so tests can `import identifiers`,
# mirroring the review-crew eval conftest.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
