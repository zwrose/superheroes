"""Canonical review-findings JSON Schema path for dispatch-review (#949)."""
import os

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
REVIEW_FINDINGS_SCHEMA_REL = os.path.join("schemas", "review-findings.schema.json")
REVIEW_FINDINGS_SCHEMA_PATH = os.path.join(_LIB_DIR, REVIEW_FINDINGS_SCHEMA_REL)


def review_findings_schema_path():
    """Return the absolute path to the shipped canonical review-findings schema."""
    return REVIEW_FINDINGS_SCHEMA_PATH
