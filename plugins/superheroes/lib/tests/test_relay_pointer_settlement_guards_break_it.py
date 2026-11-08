"""Settlement doctrine guards must reject unsafe retry instructions independently."""

import pytest

import test_relay_pointer_doctrine_2368 as doctrine


@pytest.mark.parametrize("which", ["cleanup-initial", "cleanup-resume", "send-back"])
def test_each_settlement_instruction_rejects_retry_on_unconfirmed_delivery(monkeypatch, which):
    # axis: the initial cleanup settlement, resumed cleanup settlement, and send-back retry instruction must each reject treating delivered:false as proof that nothing reached the builder.
    original_read = doctrine._read
    if which == "send-back":
        path = doctrine._ORCHESTRATION
        needle = "a `point` refusal or `nothingReached: true`, do not run `sent`."
        replacement = "a `point` refusal or `delivered: false`, do not run `sent`."
        detector = doctrine.test_the_send_back_bullets_settle_by_nothing_reached
    else:
        path = doctrine._MERGE_TRAIN
        detector = doctrine.test_merge_train_step_2_settles_by_nothing_reached
        if which == "cleanup-initial":
            needle = "`failed` when it reads `nothingReached: true`, otherwise"
            replacement = "`failed` when it reads `delivered: false`, otherwise"
        else:
            needle = "`failed` when it reads `nothingReached: true` (nothing reached the"
            replacement = "`failed` when it reads `delivered: false` (nothing reached the"
    source = original_read(path)
    assert source.count(needle) == 1
    unsafe = source.replace(needle, replacement, 1)

    def read_with_unsafe_instruction(candidate):
        return unsafe if candidate == path else original_read(candidate)

    monkeypatch.setattr(doctrine, "_read", read_with_unsafe_instruction)
    with pytest.raises(AssertionError):
        detector()
