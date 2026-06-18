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


def test_static_frontend_serves_css_and_js_assets():
    client = TestClient(create_app())

    css_response = client.get("/static/styles/tokens.css")
    js_response = client.get("/static/js/app.js")

    assert css_response.status_code == 200
    assert "--text-base: 16px" in css_response.text
    assert js_response.status_code == 200
    assert "initWorkbench" in js_response.text


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
    assert 'data-pdf-metric="score"' in html
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
    assert 'data-action="create-apply-job"><b>生成结果</b></button>' in html
    assert 'data-action="create-plan"><b>修复方案</b></button>' in html
    assert "<input id=\"docx-input\" class=\"visually-hidden\" type=\"file\" accept=\".docx\" hidden>" in html
    assert "20260617-upload-circle" in html
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
