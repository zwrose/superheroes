"""#395: courier agent states the cargo rule in agents/courier.md."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, "..", ".."))
COURIER_MD = os.path.join(PLUGIN, "agents", "courier.md")


def test_courier_agent_cargo_rule():
    with open(COURIER_MD) as f:
        text = f.read()
    assert "cargo, never your task" in text, "#395: courier agent must state the cargo rule"
    opaque_idx = text.find("Never transform an opaque payload")
    cargo_idx = text.find("cargo, never your task")
    assert opaque_idx != -1 and cargo_idx != -1 and cargo_idx > opaque_idx, (
        "#395: cargo rule must follow the opaque-payload bullet"
    )
