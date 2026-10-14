#!/usr/bin/env python3
"""The one home of the cloud launch prompt's line labels (C6 FU4). Stdlib only.

`launcher.compose_launch` writes these lines with `format_line`; `cloud_builder.parse_launch` reads
them back with `line_regex`. `Adopts branch:` has its own home (`launcher.ADOPTS_PREFIX`)."""
import re

PLACE = "Place:"
VERSION = "Advisor plugin version:"
ENVIRONMENT = "Cloud environment:"
BASE = "Base commit:"

LABELS = (PLACE, VERSION, ENVIRONMENT, BASE)


def format_line(label, value):
    """The one launch line for `label`: the label, a space, the value."""
    return "%s %s" % (label, value)


def line_regex(label, value_pattern):
    """A compiled regex matching exactly a `format_line(label, <value>)` line, where the value
    matches `value_pattern`; the value is capture group 1."""
    return re.compile("^%s (%s)$" % (re.escape(label), value_pattern))
