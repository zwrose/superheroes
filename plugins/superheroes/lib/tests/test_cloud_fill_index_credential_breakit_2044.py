"""Private-index credentials must not escape through the dependency-fill launcher."""
import json

from test_cloud_setup_text import _compose, _inside
from test_cloud_setup_dependency_fill_2044 import _requirements, _set_core


def test_in_repo_fill_does_not_export_a_private_index_password(tmp_path):
    # axis: exporting launcher arguments must not disclose literal URL credentials.
    world = _inside(tmp_path)
    credential = "fill-canary-" + "a1B2" * 5
    launcher = (
        "uv run --index-url https://builder:" + credential
        + "@packages.example.invalid/simple python"
    )
    _set_core(world, verify="npm test", interpreter=launcher)
    _requirements(world)
    result = _compose(world)
    assert result["action"] in ("written", "refused")
    assert credential not in json.dumps(result)
