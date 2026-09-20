# order_lint fixtures — C11 layer 3's order-quality reworks (issue #1339)

Verbatim copies of three implementer orders the C11 layer 3 build (issue #1270, PR #1332)
dispatched on 2026-09-18/19, taken from that lane's dispatch records. Nothing is redacted
because nothing in them needed it (scratch `pycache_prefix` paths only). They are the
real specimens behind the three order-quality reworks the build record attributes:

| fixture | dispatched as | the rework it caused | the defect, as the build record states it |
|---|---|---|---|
| `c11_l3_wo_a.md` | WO-A | WO-A2 | the probe's claim named a plugin-only file (`plugins/superheroes/lib/engine_result_channel.py`) as if it existed in every repository the probe runs in |
| `c11_l3_wo_a.md` | WO-A | WO-A3 | the same order asked the seat for the native channel's root shape (`{"result": {"resultKind": …}}`) while stating the marker channel expects the object on stdout — **semantic half** item (b); the deterministic half does not fire on prose aliases |
| `c11_l3_wo_c.md` | WO-C | WO-C2 | the order supplied the phrases the prose standard forbids on a shipped surface ("after this layer lands", "did not pass its trial") |

`c11_l3_wo_a3.md` is the WO-A3 rework order itself: it quotes the wrong shape as evidence — the
mixed-shape defect is **named for the semantic half** (item (b)); the deterministic half does not
fire without the protocol literals. Not demonstrated: the recorded semantic-seat runs
(`lib/tests/bite_proofs/order_lint_1339.md` § The semantic half) cover a planted order, its clean
twin, and `c11_l3_wo_c.md` — none covers WO-A or this fixture — so item (b) on these two orders is a
reading the prompt asks for, not one a recorded run has shown.

`test_order_lint.py` states, per fixture, which half of the lint catches which defect at which
repository root, and where a defect is not caught, why.
