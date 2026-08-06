"""Direct unit tests for source_access_scan — the config-key access chokepoint."""
import pytest

from source_access_scan import source_obj_accesses_key, source_obj_access_keys

_OBJ = "config|cfg"
_KEY = "docMode"


def test_two_argument_get_form_matches():
    """Regression axis: obj.get("key", default) — silently absent twice on this branch."""
    source = 'config.get("docMode", False)'
    assert source_obj_accesses_key(source, _OBJ, _KEY)


@pytest.mark.parametrize("source", [
    'config.get("docMode")',
    "config.get('docMode', False)",
    'config["docMode"]',
    "config['docMode']",
    'config.get(\n    "docMode", False)',
    'config.get( "docMode" )',
    'cfg.get("docMode")',
    'cfg.get("docMode", True)',
])
def test_source_obj_accesses_key_positive(source):
    assert source_obj_accesses_key(source, _OBJ, _KEY)


@pytest.mark.parametrize("source", [
    'myconfig.get("docMode")',
    'self._config["docMode"]',
    '("config.get", "docMode")',
    '["docMode", "other"]',
    '# docMode is retired',
    '"docMode flag"',
])
def test_source_obj_accesses_key_negative(source):
    assert not source_obj_accesses_key(source, _OBJ, _KEY)


def test_source_obj_access_keys_mixed_forms():
    source = '''
    mode = config.get("docMode", False)
    effort = cfg.get("fixerEffort", "medium")
    path = config["outputPath"]
    '''
    keys = source_obj_access_keys(source, _OBJ)
    assert keys == {"docMode", "fixerEffort", "outputPath"}
