# eval/lib/tests/test_skills.py
import skills

SAMPLE = "---\nname: demo\ndescription: Does a thing. Use when X.\n---\n# Demo\n\nBody line.\n"

def test_parse_skill_splits_description_and_body():
    desc, body = skills.parse_skill(SAMPLE)
    assert desc == "Does a thing. Use when X."
    assert body.startswith("# Demo")

def test_parse_skill_unwraps_quoted_description_with_bare_colon():
    # A description with a bare "colon: space" must be quoted for yaml.safe_load; the
    # structural parser must see the same logical value the YAML loader would, so a digest
    # or size keyed to it does not shift just because the value gained surrounding quotes.
    raw = '---\nname: demo\ndescription: "records `gates.review: passed` then stops."\n---\n# Demo\n'
    desc, _ = skills.parse_skill(raw)
    assert desc == "records `gates.review: passed` then stops."

def test_parse_skill_unwraps_single_quoted_description():
    raw = "---\nname: demo\ndescription: 'it''s fine: really'\n---\n# Demo\n"
    desc, _ = skills.parse_skill(raw)
    assert desc == "it's fine: really"

def test_unquote_leaves_plain_and_mismatched_values_untouched():
    assert skills._unquote("plain value") == "plain value"
    assert skills._unquote('"unterminated') == '"unterminated'
    assert skills._unquote("'mismatched\"") == "'mismatched\""
    assert skills._unquote('""') == ""

def test_unquote_decodes_double_quoted_escapes():
    # Pin the double-quoted branch (\" -> " and \\ -> \) so a mutation dropping the
    # unescaping is caught here, not only if a shipped SKILL.md happens to use an escape.
    assert skills._unquote(r'"a\"b"') == 'a"b'
    assert skills._unquote(r'"a\\b"') == 'a\\b'

def test_skill_digest_is_stable_and_changes_with_content():
    d1 = skills.skill_digest("Does a thing. Use when X.", "# Demo\n\nBody line.\n")
    d2 = skills.skill_digest("Does a thing. Use when X.", "# Demo\n\nBody line.\n")
    d3 = skills.skill_digest("Does a thing. Use when X.", "# Demo\n\nBody changed.\n")
    assert d1 == d2 and d1 != d3 and len(d1) == 16

def test_digest_normalizes_trailing_whitespace_and_crlf():
    a = skills.skill_digest("D", "x\r\ny   \n")
    b = skills.skill_digest("D", "x\ny\n")
    assert a == b

def test_normalization_stays_in_lockstep_with_identifiers():
    # the digest's normalization must match the conventions-pinned content_hash
    # normalization, so the UFR-6 carve-out key cannot silently drift
    import identifiers
    sample = "café\r\nline  \n"
    assert skills._normalize(sample) == identifiers._normalize_body(sample)
