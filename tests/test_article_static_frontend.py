import hashlib
import re
from pathlib import Path

from fastapi.testclient import TestClient

from article_api.app import create_app


LAYOUT_BASELINE_SHA256 = "e404b51d64378834832c2abd6b892b3b6396702abeecc21f7c0eec7a741d1ae7"


def test_static_frontend_serves_index_at_root():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-cache"
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

    assert css_response.status_code == 200
    assert css_response.headers["cache-control"] == "no-cache"
    assert "--text-base: 16px" in css_response.text
    assert js_response.status_code == 200
    assert js_response.headers["cache-control"] == "no-cache"
    assert "initWorkbench" in js_response.text


def test_static_stylesheets_preserve_the_versioned_visual_baseline():
    client = TestClient(create_app())

    html = client.get("/").text
    versioned_hrefs = re.findall(r'<link rel="stylesheet" href="([^"]+)">', html)
    assert all("?v=" in href for href in versioned_hrefs)
    hrefs = [href.split("?", 1)[0] for href in versioned_hrefs]
    expected = [
        "/static/styles/tokens.css",
        "/static/styles/themes.css",
        "/static/styles/layout.css",
        "/static/styles/format-radar.css",
    ]

    assert hrefs == expected
    styles = {path: client.get(path).text for path in expected}
    assert all(client.get(path).status_code == 200 for path in expected)
    layout_digest = hashlib.sha256(styles["/static/styles/layout.css"].encode("utf-8")).hexdigest()
    assert layout_digest == LAYOUT_BASELINE_SHA256
    assert "--text-base: 16px" in styles["/static/styles/tokens.css"]
    assert "--font-ui" in styles["/static/styles/layout.css"]
    assert "--radius-xl" in styles["/static/styles/layout.css"]
    assert "--asset-workflow-board" in styles["/static/styles/layout.css"]
    assert '[data-theme="snow"]' in styles["/static/styles/layout.css"]
    assert ".cover-grid" in styles["/static/styles/layout.css"]
    assert ".workbench-layout" in styles["/static/styles/layout.css"]
    assert ".pdf-layout" in styles["/static/styles/layout.css"]
    assert re.search(
        r"\.pdf-layout\s*\{[^}]*grid-template-columns:\s*360px minmax\(0, 1fr\)",
        styles["/static/styles/layout.css"],
        re.S,
    )
    assert ".history-layout" in styles["/static/styles/layout.css"]
    assert ".result-layout" in styles["/static/styles/layout.css"]


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


def test_feature_cards_are_real_screen_navigation_buttons():
    client = TestClient(create_app())

    html = client.get("/").text
    kit = html[html.index('<div class="kit-list">') : html.index("</aside>", html.index('<div class="kit-list">'))]
    targets = re.findall(r'<button type="button" data-screen-target="([^"]+)">', kit)

    assert targets == ["workbench", "workbench", "pdf-review", "history", "result", "result"]


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


def test_pdf_review_relies_on_automatic_results_without_a_redundant_refresh_action():
    client = TestClient(create_app())

    html = client.get("/").text

    assert 'data-action="refresh-render-result"' not in html


def test_pdf_review_explains_manual_image_adjustment_without_fake_evidence():
    client = TestClient(create_app())

    html = client.get("/").text
    css = client.get("/static/styles/layout.css").text
    pdf_review = html[html.index('<section class="screen" data-screen="pdf-review">') : html.index("</section>", html.index('<section class="screen" data-screen="pdf-review">'))]

    assert "图片留白优先人工调整" in pdf_review
    assert "等比例微调图片尺寸" in pdf_review
    assert 'class="ruler-page"' not in pdf_review
    assert 'class="pdf-evidence-box"' not in pdf_review
    assert 'class="film-frame"' not in pdf_review
    assert 'id="pdf-evidence-stage"' in pdf_review
    assert 'role="region"' in pdf_review
    assert 'role="group"' in pdf_review
    assert re.search(r"\.pdf-guidance span\s*\{[^}]*color: var\(--pdf-ink\)", css, re.S)
    assert re.search(r"\.finding p\s*\{[^}]*color: var\(--pdf-ink\)[^}]*font-size: 15px", css, re.S)


def test_result_screen_keeps_a_clear_path_back_to_the_workbench():
    client = TestClient(create_app())

    html = client.get("/").text
    result = html[html.index('<section class="screen" data-screen="result">') : html.index("</section>", html.index('<section class="screen" data-screen="result">'))]

    assert 'data-action="enter-workbench"' in result
    assert "返回工作台" in result


def test_result_screen_hides_detail_blocks_until_results_exist():
    client = TestClient(create_app())

    html = client.get("/").text
    css = client.get("/static/styles/layout.css").text
    result = html[html.index('<section class="screen" data-screen="result">') : html.index("</section>", html.index('<section class="screen" data-screen="result">'))]

    assert 'data-result-empty' in result
    assert "结果生成后会显示在这里" in result
    assert "[data-result-detail][hidden]" in css
    assert "[data-result-empty][hidden]" in css


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
    layout_response = client.get("/static/styles/layout.css")

    assert response.status_code == 200
    assert layout_response.status_code == 200
    html = response.text
    assert 'class="theme-action pdf-action-button"' in html
    assert 'class="theme-action result-download-button"' in html
    assert 'data-download-role="output"' in html
    assert ".theme-action" in layout_response.text
    assert ".pdf-action-button" in layout_response.text
    assert ".result-download-button" in layout_response.text
    assert ".pdf-action button {" not in layout_response.text


def test_workbench_upload_actions_are_embedded_in_glass_rail():
    client = TestClient(create_app())

    response = client.get("/")
    layout_response = client.get("/static/styles/layout.css")
    app_response = client.get("/static/js/app.js")

    assert response.status_code == 200
    assert layout_response.status_code == 200
    assert app_response.status_code == 200
    html = response.text
    css = layout_response.text
    assert 'class="upload-action-rail"' in html
    assert 'class="upload-action primary"' in html
    assert 'class="upload-action"' in html
    assert 'data-action="choose-docx"><b>选择论文</b></button>' in html
    assert 'data-action="create-apply-job" disabled><b>生成结果</b></button>' in html
    assert 'data-action="create-plan"><b>修复方案</b></button>' in html
    assert "<input id=\"docx-input\" class=\"visually-hidden\" type=\"file\" accept=\".docx\" hidden>" in html
    assert 'layout.css?v=20260714-style-restore' in html
    assert 'app.js?v=20260714-module-ownership' in html
    assert 'state.js?v=20260714-module-ownership' in app_response.text
    assert 'pdfReview.js?v=20260714-module-ownership' in app_response.text
    assert 'workflowView.js?v=20260714-module-ownership' in app_response.text
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
    assert ".visually-hidden" in layout_response.text
    assert "display: none !important" in layout_response.text
    assert "clip-path: inset(50%)" in layout_response.text
    assert ".doc-aperture::before" not in css
    assert ".doc-aperture::after" not in css
    assert ".upload-action::after" not in css
    assert ".upload-action.primary::before" in css
    assert "width: 14px" in css
    assert "height: 14px" in css
    assert "border-radius: 50%" in css


def test_desktop_workbench_places_the_ledger_beside_the_tall_scope_rail():
    client = TestClient(create_app())

    css = client.get("/static/styles/layout.css").text
    left_rail = css[css.index(".left-rail {") : css.index("}", css.index(".left-rail {"))]
    ledger = css[css.index(".ledger {") : css.index("}", css.index(".ledger {"))]
    compact = css[css.index("@media (max-width: 980px)") :]

    assert "grid-row: 1 / span 2" in left_rail
    assert "grid-column: 2 / -1" in ledger
    assert "grid-row: auto" in compact
    assert "grid-column: 1 / -1" in compact


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
    css_response = client.get("/static/styles/format-radar.css")

    assert response.status_code == 200
    assert css_response.status_code == 200
    html = response.text
    css = css_response.text
    assert 'href="/static/styles/format-radar.css' in html
    assert 'data-format-radar-panel' in html
    assert 'class="format-radar-dial"' in html
    assert 'data-format-radar' in html
    assert 'data-format-radar-label' in html
    assert 'data-format-radar-conclusion' in html
    assert 'data-format-radar-note' in html
    assert 'data-format-radar-unknown' in html
    assert 'data-format-radar-status' in html
    assert 'class="format-radar-live-status"' in html
    assert '<dt>方案范围</dt><dd data-format-radar-metric="scope-count">' in html
    assert html.count('data-format-radar-metric') == 5
    assert "--radar-progress" in css
    assert ".format-radar-metrics" in css
    assert ".format-radar-note" in css
    radar_start = css.index(".format-radar-dial {")
    radar_rule = css[radar_start : css.index("}", radar_start)]
    assert "width: 168px" in radar_rule
    assert "aspect-ratio: 1" in radar_rule
    assert "border-radius: 50%" in radar_rule
    live_start = css.index(".format-radar-live-status {")
    live_rule = css[live_start : css.index("}", live_start)]
    assert "clip-path: inset(50%)" in live_rule
    assert "display:" not in live_rule
    value_label_start = css.index(".format-radar-value span {")
    value_label_rule = css[value_label_start : css.index("}", value_label_start)]
    metric_label_start = css.index(".format-radar-metric dt {")
    metric_label_rule = css[metric_label_start : css.index("}", metric_label_start)]
    assert "font-size: 0.8125rem" in value_label_rule
    assert "font-size: 0.8125rem" in metric_label_rule
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
