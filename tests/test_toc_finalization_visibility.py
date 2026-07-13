from article_api.job_payloads import build_result_summary
from article_api.response_payloads import build_render_verify_payload


TOC_FINALIZATION = {
    "status": "generated",
    "available": True,
    "entry_count": 26,
    "mapped_count": 26,
}
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
            "toc_finalization": dict(TOC_FINALIZATION),
        },
    )

    assert {key: payload["summary"].get(key) for key in EXPECTED_TOC_SUMMARY} == EXPECTED_TOC_SUMMARY


def test_render_verify_job_summary_exposes_toc_finalization():
    summary = build_result_summary(
        "render-verify",
        {"toc_finalization": dict(TOC_FINALIZATION)},
        {"source_display_name": "论文.docx", "workflow_mode": "default_user"},
    )

    assert {key: summary.get(key) for key in EXPECTED_TOC_SUMMARY} == EXPECTED_TOC_SUMMARY
