"""By-construction proof that disclosure and record-path vocabularies have one home."""
import receipt_disclosures
import record_paths
import round_certification
import round_driver
import round_records


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
