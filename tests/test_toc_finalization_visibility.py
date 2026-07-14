from article_api.job_payloads import build_result_summary
from article_api.response_payloads import build_render_verify_payload


EXPECTED_TOC_SUMMARY = {
    "toc_finalization_status": "generated",
    "toc_output_available": True,
    "toc_entry_count": 26,
    "toc_mapped_count": 26,
}


def test_render_verify_response_summary_exposes_toc_finalization():
    payload = build_render_verify_payload(
        file_path="/tmp/demo.docx",
        rendered_pdf="/tmp/demo.pdf",
        render_verify_fn=lambda *_args, **_kwargs: {
            "summary": dict(EXPECTED_TOC_SUMMARY),
        },
    )

    assert {key: payload["summary"].get(key) for key in EXPECTED_TOC_SUMMARY} == EXPECTED_TOC_SUMMARY


def test_render_verify_job_summary_exposes_toc_finalization():
    summary = build_result_summary(
        "render-verify",
        {
            "summary": dict(EXPECTED_TOC_SUMMARY),
            "toc_finalization": {
                "status": "not-requested",
                "available": False,
                "entry_count": 0,
                "mapped_count": 0,
            },
        },
        {"source_display_name": "论文.docx", "workflow_mode": "default_user"},
    )

    assert {key: summary.get(key) for key in EXPECTED_TOC_SUMMARY} == EXPECTED_TOC_SUMMARY


def test_render_verify_response_extends_engine_summary_without_mutating_it():
    engine_payload = {
        "summary": {"render_finding_count": 7, "engine_marker": "kept"},
        "render_findings": [],
        "evidence_items": [],
    }

    payload = build_render_verify_payload(
        file_path="/tmp/demo.docx",
        rendered_pdf="/tmp/demo.pdf",
        render_verify_fn=lambda *_args, **_kwargs: engine_payload,
    )

    assert payload["summary"]["render_finding_count"] == 7
    assert payload["summary"]["engine_marker"] == "kept"
    assert payload["summary"] == {
        "render_finding_count": 7,
        "engine_marker": "kept",
        "render_workflow_mode": "default_user",
    }
    assert engine_payload == {
        "summary": {"render_finding_count": 7, "engine_marker": "kept"},
        "render_findings": [],
        "evidence_items": [],
    }
