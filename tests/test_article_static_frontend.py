import re
from pathlib import Path

from fastapi.testclient import TestClient

from article_api.app import create_app


def test_static_frontend_serves_index_at_root():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "辽宁大学" in response.text
    assert "data-app=\"lnu-thesis-workbench\"" in response.text
    assert "data-screen=\"workbench\"" in response.text
    assert "data-screen=\"pdf-review\"" in response.text
    assert "data-screen=\"history\"" in response.text
    assert "data-screen=\"result\"" in response.text


def test_static_frontend_declares_a_reachable_favicon():
    client = TestClient(create_app())

    response = client.get("/")
    favicon = client.get("/static/assets/lnu-emblem.jpg")

    assert '<link rel="icon" href="/static/assets/lnu-emblem.jpg" type="image/jpeg">' in response.text
    assert favicon.status_code == 200
    assert favicon.headers["content-type"] == "image/jpeg"


def test_static_frontend_serves_css_and_js_assets():
    client = TestClient(create_app())

    css_response = client.get("/static/styles/tokens.css")
    js_response = client.get("/static/js/app.js")
    actions_response = client.get("/static/js/globalActions.js")

    assert css_response.status_code == 200
    assert "--text-base: 16px" in css_response.text
    assert js_response.status_code == 200
    assert "initWorkbench" in js_response.text
    assert actions_response.status_code == 200
    assert "bindGlobalActions" in actions_response.text


def test_static_frontend_contains_four_theme_controls():
    client = TestClient(create_app())

    response = client.get("/")

    assert 'data-theme-choice="snow"' in response.text
    assert 'data-theme-choice="rain"' in response.text
    assert 'data-theme-choice="morning"' in response.text
    assert 'data-theme-choice="ginkgo"' in response.text


def test_static_frontend_preserves_prototype_screen_markers():
    client = TestClient(create_app())

    response = client.get("/")
    css_response = client.get("/static/styles/layout.css")

    assert response.status_code == 200
    assert css_response.status_code == 200
    html = response.text
    css = css_response.text
    assert 'class="shell cover-grid"' in html
    assert 'class="asset-board"' in html
    assert 'class="runway"' in html
    assert 'class="timeline glass"' in html
    assert 'class="pdf-lens glass"' in html
    assert 'class="result-hero glass"' in html
    assert "--asset-workflow-board" in css
    assert "--asset-pdf-board" in css
    assert "--asset-result-board" in css


def test_static_frontend_exposes_real_result_history_and_metric_hooks():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert 'data-history-list' in html
    assert 'data-result-file-name' in html
    assert 'data-result-scope' in html
    assert 'data-result-time' in html
    assert 'data-download-role="output"' in html
    assert 'data-download-role="report"' in html
    assert 'data-download-role="toc-output"' in html
    assert 'data-toc-output-action' in html
    assert 'data-toc-output-title' in html
    assert 'data-toc-output-message' in html
    assert 'data-toc-output-next-action' in html
    assert "下载静态目录版" in html
    assert "重新导出 PDF 并再次复核" in html
    assert '<div class="metric"><b>结论</b><strong data-pdf-metric="conclusion">' in html
    assert 'data-pdf-metric="score"' not in html
    assert 'data-pdf-metric="pages"' in html
    assert 'data-pdf-metric="issues"' in html


def test_static_frontend_exposes_workbench_plan_hooks_without_fake_counts():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert 'data-workbench-metric="autofixable-scopes"' in html
    assert 'data-workbench-metric="manual-confirmation"' in html
    assert 'data-workbench-metric="output-kind"' in html
    assert "data-workbench-ledger" in html
    assert "06:18:01" not in html
    assert "发现 7 类可修复范围" not in html
    assert ">7</strong>" not in html
    assert ">3</strong>" not in html


def test_static_frontend_real_action_buttons_use_theme_action_style():
    client = TestClient(create_app())

    response = client.get("/")
    css_response = client.get("/static/styles/layout.css")

    assert response.status_code == 200
    assert css_response.status_code == 200
    html = response.text
    css = css_response.text
    assert 'class="theme-action pdf-action-button"' in html
    assert 'class="theme-action result-download-button"' in html
    assert 'data-download-role="output"' in html
    assert ".theme-action" in css
    assert ".pdf-action-button" in css
    assert ".result-download-button" in css
    assert ".pdf-action button {" not in css


def test_workbench_upload_actions_are_embedded_in_glass_rail():
    client = TestClient(create_app())

    response = client.get("/")
    css_response = client.get("/static/styles/layout.css")

    assert response.status_code == 200
    assert css_response.status_code == 200
    html = response.text
    css = css_response.text
    assert 'class="upload-action-rail"' in html
    assert 'class="upload-action primary"' in html
    assert 'class="upload-action"' in html
    assert 'data-action="choose-docx"><b>选择论文</b></button>' in html
    assert 'data-action="create-apply-job" disabled><b>生成结果</b></button>' in html
    assert 'data-action="create-plan"><b>修复方案</b></button>' in html
    assert "<input id=\"docx-input\" class=\"visually-hidden\" type=\"file\" accept=\".docx\" hidden>" in html
    assert html.count("20260712-contract-closeout") == 2
    upload_start = html.index('<div class="doc-aperture">')
    upload_end = html.index('<div class="repair-preview">')
    upload_html = html[upload_start:upload_end]
    assert "<small>1</small>" not in upload_html
    assert "<small>2</small>" not in upload_html
    assert "<small>3</small>" not in upload_html
    assert 'class="runway-tools"' not in upload_html
    assert "action-row" not in html
    assert "run-button" not in html
    assert 'class="token">初步检查</span>' not in html
    assert 'class="token">修复方案</span>' not in html
    assert 'class="token">开始修正</span>' not in html
    assert '<button class="upload-action" type="button" data-action="create-apply-job"><small>3</small><b>修复方案</b></button>' not in html
    assert ".upload-action-rail" in css
    assert ".visually-hidden" in css
    assert "display: none !important" in css
    assert "clip-path: inset(50%)" in css
    assert ".doc-aperture::before" not in css
    assert ".doc-aperture::after" not in css
    assert ".upload-action::after" not in css
    assert ".upload-action.primary::before" in css
    assert "width: 14px" in css
    assert "height: 14px" in css
    assert "border-radius: 50%" in css


def test_static_frontend_uses_migrated_action_hooks_not_legacy_console_ids():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert 'data-action="choose-docx"' in html
    assert 'data-action="create-plan"' in html
    assert 'data-action="create-apply-job"' in html
    assert 'data-download-role="output"' in html
    assert 'data-history-list' in html
    assert 'data-result-heatmap' in html
    assert 'label for="paper-file"' not in html
    assert 'id="paper-file"' not in html
    assert 'id="run-all-button"' not in html
    assert 'id="report-action-button"' not in html
    assert 'id="report-output"' not in html


def test_local_browser_smoke_does_not_reference_removed_frontend_selectors():
    smoke = Path("scripts/local_browser_smoke.py").read_text(encoding="utf-8")

    assert "label[for='paper-file']" not in smoke
    assert "#run-all-button" not in smoke
    assert "#report-action-button" not in smoke
    assert "#report-output" not in smoke
    assert "[data-action='enter-workbench']" in smoke
    assert "[data-action='choose-docx']" in smoke
    assert "[data-action='create-apply-job']" in smoke
    assert "[data-download-role='output']" in smoke


def test_format_radar_exposes_real_state_hooks():
    client = TestClient(create_app())

    response = client.get("/")
    css_response = client.get("/static/styles/layout.css")

    assert response.status_code == 200
    assert css_response.status_code == 200
    html = response.text
    css = css_response.text
    assert 'class="radar"' in html
    assert 'data-format-radar' in html
    assert 'data-format-radar-label' in html
    assert "--radar-progress" in css
    radar_start = css.index(".radar {")
    radar_rule = css[radar_start : css.index("}", radar_start)]
    assert "width: 168px" in radar_rule
    assert "aspect-ratio: 1" in radar_rule
    assert "border-radius: 50%" in radar_rule
    assert "overflow: hidden" in radar_rule


def test_frontend_structure_and_copy_do_not_promise_static_or_unsupported_results():
    client = TestClient(create_app())

    html = client.get("/").text

    assert "论文问题索引" in html
    assert 'aria-label="论文问题索引"' in html
    assert html.count("data-structure-count") == 6
    assert "PDF 问题复核" in html
    assert "任务报告" in html
    assert "图题距离" not in html
    assert "原稿 修复稿 审查报告 和 PDF 复核记录都保存在这里" not in html
    assert "PDF 问题证据 等待检测结果" not in html
    assert "等待复核结果" not in html
    assert "等待 PDF 页数" not in html
    assert "等待可行动项" not in html
    assert html.count('<span class="token">本地处理</span>') == 1
    for fake_count in ("<small>7</small>", "<small>3</small>", "<small>2</small>", "<small>1</small>", "<small>0</small>"):
        assert fake_count not in html


def test_cover_fields_expose_native_required_semantics():
    client = TestClient(create_app())

    html = client.get("/").text
    cover_inputs = re.findall(r'<input[^>]+data-cover-field="[^"]+"[^>]*>', html)

    assert len(cover_inputs) == 6
    assert all(" required" in input_tag for input_tag in cover_inputs)
    assert all('aria-required="true"' in input_tag for input_tag in cover_inputs)


def test_pdf_review_evidence_image_and_highlight_have_layout_styles():
    client = TestClient(create_app())

    css = client.get("/static/styles/layout.css").text

    def rule(selector):
        start = css.index(f"{selector} {{")
        return css[start : css.index("}", start)]

    frame = rule(".pdf-page-frame")
    image = rule(".pdf-page-frame img")
    highlight = rule(".evidence-highlight")
    notice = rule(".page-notice")

    assert "position: relative" in frame
    assert "max-width" in frame
    assert "max-height" in frame
    assert "object-fit: contain" in image
    assert "position: absolute" in highlight
    assert "position: absolute" in notice


def test_mobile_theme_switch_uses_the_screen_bottom_spacing_instead_of_covering_controls():
    client = TestClient(create_app())

    css = client.get("/static/styles/layout.css").text
    mobile_css = css[css.index("@media (max-width: 680px)") :]

    assert "position: relative" in mobile_css
    assert "margin: -78px auto 16px" in mobile_css


def test_desktop_theme_switch_stays_in_document_flow_instead_of_covering_pdf_details():
    client = TestClient(create_app())

    css = client.get("/static/styles/layout.css").text
    start = css.index(".theme-strip {")
    rule = css[start : css.index("}", start)]

    assert "position: relative" in rule
    assert "position: fixed" not in rule
    assert "margin: -78px auto 16px" in rule


def test_result_download_file_name_and_note_use_separate_lines():
    client = TestClient(create_app())

    css = client.get("/static/styles/layout.css").text
    selector = ".download-ribbon b,\n    .download-ribbon span {"
    start = css.index(selector)
    rule = css[start : css.index("}", start)]

    assert "display: block" in rule


def test_scope_status_text_remains_readable_when_a_scope_is_unavailable():
    client = TestClient(create_app())

    css = client.get("/static/styles/layout.css").text
    disabled_css = css[css.index(".scope-chip:has(input:disabled)") : css.index(".scope-chip::after")]
    status_start = css.index(".scope-chip small")
    status_css = css[status_start : css.index("}", status_start)]

    assert "opacity: 0.72" in disabled_css
    assert "color: rgba(255, 255, 255, 0.76)" in status_css
    assert "font-size: 12px" in status_css
    assert "letter-spacing: 0" in status_css
