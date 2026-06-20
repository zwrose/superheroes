# eval/lib/tests/test_skills.py
import skills

SAMPLE = "---\nname: demo\ndescription: Does a thing. Use when X.\n---\n# Demo\n\nBody line.\n"

def test_parse_skill_splits_description_and_body():
    desc, body = skills.parse_skill(SAMPLE)
    assert desc == "Does a thing. Use when X."
    assert body.startswith("# Demo")

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
