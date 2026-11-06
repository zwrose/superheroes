"""Tests for where the cloud check's git identity comes from (#2371): the identity part still passes
an identity that git resolves from git config, but the judgment then warns that an identity a setup
command wrote there does not survive a worker restart and names the identity variables that are not
set. An identity from all four variables carries no warning; a report that does not say where the
identity came from reads unknown and warns; a missing identity still fails as before.

The judgment tests use the fixture projects of test_cloud_check and pass the cloud session's
environment to `report` directly, so no real git or cloud session runs.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_check as CC  # noqa: E402
import cloud_pass  # noqa: E402
from test_cloud_check import ENV_ID, NONCE, _confirm, _judge, _pair  # noqa: E402

FOUR = ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")
HEADING = "**A warning about the git identity.**"
RESTART = "does not survive a worker restart"
BOTH = {"author": True, "committer": True}


def _report(cloud, variables=(), identity=BOTH, values=None, **over):
    env = {cloud_pass.ENVIRONMENT_ENV: ENV_ID}
    for name in variables:
        env[name] = (values or {}).get(name, "set")
    obj = CC.report(env=env, cwd=cloud.cwd, root=cloud.root, nonce=NONCE, confirm_fn=_confirm(),
                    identity_fn=lambda cwd: dict(identity))
    obj.update(over)
    return obj


def _passed(result):
    assert result["action"] == "passed", result
    assert result["failedParts"] == [] and result["results"]["identityPresent"] is True
    return result


def test_the_four_names_are_the_ones_git_reads():
    # axis: the variables the check looks for are exactly git's four identity variables
    assert CC.IDENTITY_VARIABLES == FOUR


def test_report_names_the_set_variables_and_never_their_values(tmp_path):
    local, cloud = _pair(tmp_path)
    obj = _report(cloud, FOUR, values={"GIT_AUTHOR_NAME": "Owner Person",
                                       "GIT_AUTHOR_EMAIL": "owner@example.invalid"})
    # axis: the report says which identity variables are set, by name only, never their values
    assert obj[CC.IDENTITY_SOURCE_FIELD] == {"variables": list(FOUR)}
    line = CC.report_line(obj)
    assert "Owner Person" not in line and "owner@example.invalid" not in line


def test_report_does_not_count_an_empty_variable(tmp_path):
    local, cloud = _pair(tmp_path)
    obj = _report(cloud, FOUR, values={"GIT_COMMITTER_EMAIL": "  "})
    # axis: a variable set to blank text is not set
    assert obj[CC.IDENTITY_SOURCE_FIELD] == {"variables": list(FOUR[:3])}


def test_identity_from_git_config_alone_passes_with_the_warning_naming_all_four(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _passed(_judge(local, _report(cloud)))
    warning = result["identityWarning"]
    # axis: an identity from git config alone warns and names all four variables
    assert warning["source"] == "config" and warning["missing"] == list(FOUR)
    assert warning["message"] in result["message"]
    assert HEADING in result["message"] and RESTART in result["message"]
    assert "comes only from git config" in result["message"]
    assert ("GIT_AUTHOR_NAME, GIT_AUTHOR_EMAIL, GIT_COMMITTER_NAME and GIT_COMMITTER_EMAIL"
            in result["message"])
    # the record is still written: the warning gates nothing
    assert result["recordWritten"] is True


def test_identity_from_the_four_variables_passes_with_no_warning(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _passed(_judge(local, _report(cloud, FOUR)))
    # axis: an identity from the four variables carries no warning
    assert result["identityWarning"] is None
    assert HEADING not in result["message"] and RESTART not in result["message"]


def test_a_mixed_identity_warns_and_names_only_the_missing_variables(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _passed(_judge(local, _report(cloud, ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL"))))
    warning = result["identityWarning"]
    # axis: a mixed identity warns and names the missing variables, and only those
    assert warning["source"] == "mixed"
    assert warning["missing"] == ["GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"]
    assert "GIT_COMMITTER_NAME and GIT_COMMITTER_EMAIL are not set" in result["message"]
    assert "GIT_AUTHOR_NAME" not in result["message"]
    assert RESTART in result["message"]


def test_a_mixed_identity_missing_one_variable_names_it_in_the_singular(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _passed(_judge(local, _report(cloud, FOUR[:3])))
    assert result["identityWarning"]["missing"] == ["GIT_COMMITTER_EMAIL"]
    assert "GIT_COMMITTER_EMAIL is not set" in result["message"]


def test_no_identity_still_fails_and_carries_no_warning(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _report(cloud, identity={"author": False, "committer": False}))
    # axis: no identity still fails as before, and the warning is not added to the failure
    assert result["action"] == "failed" and result["failedParts"] == ["identity"]
    assert result["identityWarning"] is None
    assert HEADING not in result["message"]


def test_a_report_that_does_not_say_where_reads_unknown_and_warns(tmp_path):
    local, cloud = _pair(tmp_path)
    obj = _report(cloud, FOUR)
    del obj[CC.IDENTITY_SOURCE_FIELD]
    result = _passed(_judge(local, obj))
    warning = result["identityWarning"]
    # axis: a report that does not say where the identity came from reads unknown and warns
    assert warning["source"] == "unknown" and warning["missing"] == list(FOUR)
    assert "did not say where its git identity comes from" in result["message"]
    assert RESTART in result["message"]


def test_a_source_of_the_wrong_shape_reads_unknown(tmp_path):
    local, cloud = _pair(tmp_path)
    for source in (None, "variables", {"variables": "GIT_AUTHOR_NAME"}, {"variables": [1]},
                   {"variables": list(FOUR) + ["GIT_OTHER"]}, {}):
        obj = _report(cloud, FOUR, **{CC.IDENTITY_SOURCE_FIELD: source})
        result = _passed(_judge(local, obj))
        # axis: a source that is not the reported shape is never read as the four variables
        assert result["identityWarning"]["source"] == "unknown", source


def test_a_check_failing_elsewhere_still_says_where_a_passing_identity_came_from(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _report(cloud, environment="env_01Other"))
    assert result["action"] == "failed" and "identity" not in result["failedParts"]
    # axis: a passing identity part says where it came from even when another part fails
    assert result["identityWarning"]["source"] == "config"
    assert result["message"].endswith(result["identityWarning"]["message"])


def test_an_unread_report_carries_no_warning(tmp_path):
    local, _cloud = _pair(tmp_path)
    result = _judge(local, "no report here")
    assert result["action"] == "unread" and result["identityWarning"] is None
