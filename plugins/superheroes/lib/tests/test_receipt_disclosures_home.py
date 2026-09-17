"""By-construction proof that disclosure and record-path vocabularies have one home."""
import receipt_disclosures
import record_paths
import round_certification
import round_driver
import round_records
import session_contract


def test_receipt_disclosures_exports_match_driver_and_writer():
    for name in receipt_disclosures.__all__:
        assert getattr(round_driver, name) is getattr(receipt_disclosures, name), name
        if hasattr(round_certification, name):
            assert getattr(round_certification, name) is getattr(receipt_disclosures, name), name


def test_record_paths_exports_match_records_and_writer():
    for name in record_paths.__all__:
        assert getattr(round_records, name) is getattr(record_paths, name), name
        if hasattr(round_certification, name):
            assert getattr(round_certification, name) is getattr(record_paths, name), name


def test_session_contract_exports_match_driver_records_and_writer():
    driver_names = {
        "STATE_FILE",
        "JOURNAL_FILE",
        "JOURNAL_FAULT_FILE",
    }
    records_names = {"META_FILE"}
    writer_names = set(session_contract.__all__)
    for name in session_contract.__all__:
        home = getattr(session_contract, name)
        if name in driver_names:
            assert getattr(round_driver, name) is home, name
        if name in records_names:
            assert getattr(round_records, name) is home, name
        if name in writer_names and hasattr(round_certification, name):
            assert getattr(round_certification, name) is home, name
