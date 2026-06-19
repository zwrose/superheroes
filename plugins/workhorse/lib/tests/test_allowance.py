"""Codex single-use approval allowance (issue #14). The deny-only Codex hook can't
prompt, so a gated action becomes: hook-issued challenge (nonce) → owner approves →
single-use, short-TTL, command-scoped allowance the very next matching call consumes.
These tests pin the un-forgeability + freshness properties the gate rests on."""
import os

import allowance
import pytest

CMD = "gh pr merge 42 --squash"
TTL = allowance.DEFAULT_TTL


@pytest.fixture(autouse=True)
def _isolated_store(monkeypatch, tmp_path):
    # Never touch the real ~/.claude/workhorse during tests.
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path))
    allowance.clear_all()
    yield


def test_default_ttl_is_90s():
    # The owner-chosen value (issue #14). A change here is a deliberate policy change.
    assert allowance.DEFAULT_TTL == 90


def test_happy_path_challenge_approve_consume():
    nonce = allowance.challenge(CMD, "merge-pr", now=1000)
    assert nonce  # a non-empty token
    h = allowance.command_hash(CMD)
    assert allowance.approve(h, nonce, now=1001, ttl=TTL) is True
    assert allowance.consume(CMD, now=1002, ttl=TTL) is True


def test_single_use_second_consume_fails():
    nonce = allowance.challenge(CMD, "merge-pr", now=1000)
    allowance.approve(allowance.command_hash(CMD), nonce, now=1000, ttl=TTL)
    assert allowance.consume(CMD, now=1000, ttl=TTL) is True
    assert allowance.consume(CMD, now=1000, ttl=TTL) is False  # consumed → gone


def test_forged_nonce_rejected():
    allowance.challenge(CMD, "merge-pr", now=1000)
    assert allowance.approve(allowance.command_hash(CMD), "not-the-nonce",
                             now=1000, ttl=TTL) is False
    assert allowance.consume(CMD, now=1000, ttl=TTL) is False


def test_approve_without_challenge_is_rejected():
    # No hook-issued challenge exists → an agent cannot self-mint from nothing.
    assert allowance.approve(allowance.command_hash(CMD), "anything",
                             now=1000, ttl=TTL) is False
    assert allowance.consume(CMD, now=1000, ttl=TTL) is False


def test_expired_challenge_cannot_be_approved():
    nonce = allowance.challenge(CMD, "merge-pr", now=1000)
    assert allowance.approve(allowance.command_hash(CMD), nonce,
                             now=1000 + TTL + 1, ttl=TTL) is False


def test_consume_ttl_boundary_inclusive_then_expired():
    nonce = allowance.challenge(CMD, "merge-pr", now=1000)
    allowance.approve(allowance.command_hash(CMD), nonce, now=1000, ttl=TTL)
    # exactly at the boundary still consumes...
    assert allowance.consume(CMD, now=1000 + TTL, ttl=TTL) is True


def test_consume_after_ttl_is_rejected():
    nonce = allowance.challenge(CMD, "merge-pr", now=1000)
    allowance.approve(allowance.command_hash(CMD), nonce, now=1000, ttl=TTL)
    assert allowance.consume(CMD, now=1000 + TTL + 1, ttl=TTL) is False


def test_consume_requires_approval_not_just_challenge():
    allowance.challenge(CMD, "merge-pr", now=1000)
    assert allowance.consume(CMD, now=1000, ttl=TTL) is False  # challenged, not approved


def test_consume_is_command_scoped():
    nonce = allowance.challenge(CMD, "merge-pr", now=1000)
    allowance.approve(allowance.command_hash(CMD), nonce, now=1000, ttl=TTL)
    # A DIFFERENT command must not consume this allowance.
    assert allowance.consume("gh pr merge 99", now=1000, ttl=TTL) is False
    # The original still consumes.
    assert allowance.consume(CMD, now=1000, ttl=TTL) is True


def test_clear_all_wipes_pending_allowances():
    nonce = allowance.challenge(CMD, "merge-pr", now=1000)
    allowance.approve(allowance.command_hash(CMD), nonce, now=1000, ttl=TTL)
    allowance.clear_all()  # the PreCompact wipe
    assert allowance.consume(CMD, now=1000, ttl=TTL) is False


def test_consume_unknown_command_is_false():
    assert allowance.consume("git status", now=1000, ttl=TTL) is False


def test_fresh_challenge_resets_prior_approval():
    # Re-challenging the same command invalidates a prior approval (a new gate-deny
    # means the old approval is stale) — the agent must re-approve the new nonce.
    nonce1 = allowance.challenge(CMD, "merge-pr", now=1000)
    allowance.approve(allowance.command_hash(CMD), nonce1, now=1000, ttl=TTL)
    allowance.challenge(CMD, "merge-pr", now=1001)  # new deny → new challenge
    assert allowance.consume(CMD, now=1001, ttl=TTL) is False


def test_clear_all_safe_when_empty():
    allowance.clear_all()
    allowance.clear_all()  # idempotent / no raise


def test_allowance_is_per_checkout_no_cross_consume(tmp_path):
    # Two distinct checkouts (cwds) must NOT share an approval — a concurrent loop in
    # checkout B cannot consume an approval the owner granted in checkout A.
    a = str(tmp_path / "repo_a")
    b = str(tmp_path / "repo_b")
    os.makedirs(a); os.makedirs(b)
    nonce = allowance.challenge(CMD, "merge-pr", cwd=a, now=1000)
    assert allowance.approve(allowance.command_hash(CMD), nonce, cwd=a, now=1000, ttl=TTL) is True
    # Same command string, different checkout → no record → cannot consume.
    assert allowance.consume(CMD, cwd=b, now=1000, ttl=TTL) is False
    # The owning checkout still consumes its own approval.
    assert allowance.consume(CMD, cwd=a, now=1000, ttl=TTL) is True


def test_clear_all_scoped_to_checkout_leaves_other_intact(tmp_path):
    a = str(tmp_path / "repo_a")
    b = str(tmp_path / "repo_b")
    os.makedirs(a); os.makedirs(b)
    for cwd in (a, b):
        n = allowance.challenge(CMD, "merge-pr", cwd=cwd, now=1000)
        allowance.approve(allowance.command_hash(CMD), n, cwd=cwd, now=1000, ttl=TTL)
    allowance.clear_all(cwd=a)  # PreCompact in checkout A only
    assert allowance.consume(CMD, cwd=a, now=1000, ttl=TTL) is False  # wiped
    assert allowance.consume(CMD, cwd=b, now=1000, ttl=TTL) is True   # untouched


def test_store_root_honors_env(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "custom"))
    assert os.path.realpath(str(tmp_path / "custom")) == allowance.store_root()
