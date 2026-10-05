"""Failure reports must contain aggregate context without library input details."""

import importlib
import json

import pandas as pd
import pytest

validation = importlib.import_module("src.validation.run")


@pytest.mark.parametrize("boundary", ["read_source", "table_profile", "verify_raw", "stage_frames"])
@pytest.mark.parametrize("error_type", [ValueError, OSError, TypeError])
def test_failure_reports_do_not_publish_library_exception_details(
    tmp_path, monkeypatch, boundary, error_type
):
    private_detail = "PRIVATE-INPUT-OR-PATH-MUST-NOT-BE-PUBLISHED"
    reports = {}
    monkeypatch.setattr(validation, "verify_raw", lambda root: {"files": {"synthetic.csv": {}}})
    monkeypatch.setattr(
        validation, "TABLES", {"synthetic": type("Spec", (), {"filename": "synthetic.csv"})()}
    )
    monkeypatch.setattr(validation, "read_source", lambda *args: pd.DataFrame({"id": ["1"]}))
    monkeypatch.setattr(validation, "standardize", lambda *args: (args[0], {}))
    monkeypatch.setattr(validation, "table_profile", lambda *args: {})
    monkeypatch.setattr(validation, "validate_frame", lambda *args: [])
    monkeypatch.setattr(validation, "relationship_checks", lambda *args: [])
    monkeypatch.setattr(validation, "contextual_checks", lambda *args: ([], {}))
    monkeypatch.setattr(validation, "join_diagnostics", lambda *args: {})
    monkeypatch.setattr(validation, "stage_frames", lambda *args: {"promoted": True})
    monkeypatch.setattr(validation, "report_markdown", lambda report: json.dumps(report))
    monkeypatch.setattr(validation, "dictionary_markdown", lambda report: json.dumps(report))
    monkeypatch.setattr(
        validation, "write_json", lambda path, value: reports.update({path.name: json.dumps(value)})
    )
    monkeypatch.setattr(
        validation, "write_text", lambda path, value: reports.update({path.name: value})
    )

    def fail(*args):
        raise error_type(private_detail)

    monkeypatch.setattr(validation, boundary, fail)
    report = validation._run(tmp_path)
    assert report["status"] == "FAIL"
    assert report["error_checks"] > 0
    assert report["staging"]["promoted"] is False
    assert len(reports) == 3
    assert private_detail not in json.dumps(report)
    assert all(private_detail not in text for text in reports.values())
