"""The one home of the calibration-read vocabulary (#2311). Imports nothing.

The runner side (``calibration_read``) writes these labels and read states into an engine record's
observation; the record writer (``review_record``) filters every credited calibration list against
them. Both import this leaf, so the contract has one definition and the writer still imports nothing
from the driver or the adapter.
"""

LABEL_CORE = "core"
LABEL_REVIEW_CREW = "review-crew"
LABEL_CLAUDE_MD = "CLAUDE.md"
LABELS = (LABEL_CORE, LABEL_REVIEW_CREW, LABEL_CLAUDE_MD)

READ = "read"
NOT_READ = "not-read"
UNKNOWN = "unknown"
READ_STATES = (READ, NOT_READ, UNKNOWN)
