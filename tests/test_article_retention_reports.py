from article_api.retention_reports import build_retention_sweep_report, with_cleanup_result


def test_build_retention_sweep_report_uses_fresh_items_and_optional_blocked_counter():
    report = build_retention_sweep_report(
        max_age_seconds=12.5,
        reference_time="2099-01-01T00:00:00Z",
        dry_run=True,
        inspected_count=3,
        include_blocked_count=True,
    )
    second_report = build_retention_sweep_report(
        max_age_seconds=1,
        reference_time="2099-01-02T00:00:00Z",
        dry_run=False,
        inspected_count=0,
    )

    report["items"].append({"job_id": "job-1"})

    assert report == {
        "policy": "retention",
        "dry_run": True,
        "max_age_seconds": 12.5,
        "reference_time": "2099-01-01T00:00:00Z",
        "inspected_count": 3,
        "eligible_count": 0,
        "cleaned_count": 0,
        "noop_count": 0,
        "blocked_count": 0,
        "skipped_count": 0,
        "items": [{"job_id": "job-1"}],
    }
    assert second_report["items"] == []
    assert "blocked_count" not in second_report


def test_with_cleanup_result_returns_new_report_and_counts_cleanup_state():
    base_report = build_retention_sweep_report(
        max_age_seconds=1,
        reference_time="2099-01-01T00:00:00Z",
        dry_run=False,
        inspected_count=1,
    )
    item = {"job_id": "job-1", "age_seconds": 2.0}
    cleanup = {"state": "cleaned", "removed_paths": ["/tmp/job-1"]}

    updated = with_cleanup_result(base_report, item, cleanup)
    cleanup["removed_paths"].append("/tmp/mutated")
    item["job_id"] = "changed"
    noop_updated = with_cleanup_result(updated, {"upload_id": "upload-1"}, {"state": "noop"})

    assert base_report["items"] == []
    assert base_report["cleaned_count"] == 0
    assert updated["cleaned_count"] == 1
    assert updated["noop_count"] == 0
    assert updated["items"] == [
        {
            "job_id": "job-1",
            "age_seconds": 2.0,
            "action": "cleaned",
            "cleanup": {"state": "cleaned", "removed_paths": ["/tmp/job-1"]},
        }
    ]
    assert noop_updated["cleaned_count"] == 1
    assert noop_updated["noop_count"] == 1
    assert noop_updated["items"][-1] == {
        "upload_id": "upload-1",
        "action": "cleaned",
        "cleanup": {"state": "noop"},
    }
