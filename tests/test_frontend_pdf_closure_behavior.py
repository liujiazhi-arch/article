import json

from tests.test_frontend_app_behavior import PDF_REVIEW_URL, _run_node


def test_pdf_empty_state_uses_only_backend_readiness_evidence():
    _run_node(
        f"""
const {{ renderPdfReview }} = await import({json.dumps(PDF_REVIEW_URL)});
const list = new FakeElement();
const stage = new FakeElement();
const detail = new FakeElement();
const root = {{
  querySelector(selector) {{
    return {{
      "[data-pdf-issues]": list,
      "[data-pdf-stage]": stage,
      "[data-pdf-detail]": detail,
    }}[selector] || null;
  }},
}};

const base = {{
  render_evidence_status: "render-evidence-ready",
  evidence_source: "manual-pdf",
  evidence_trust: "user-confirmed",
  evidence_authoritative: false,
  layout_decision_eligible: true,
}};
renderPdfReview(root, {{ summary: base, evidence_items: [] }});
assert.match(list.innerHTML, /版本对应关系待确认/);

renderPdfReview(root, {{
  summary: {{ ...base, pdf_matches_docx_confirmed: true }},
  evidence_items: [],
}});
assert.match(list.innerHTML, /没有发现需要确认的位置/);

renderPdfReview(root, {{
  summary: {{
    render_evidence_status: "render-evidence-ready",
    evidence_source: "word-pdf",
    evidence_trust: "authoritative",
    evidence_authoritative: true,
    layout_decision_eligible: true,
  }},
  evidence_items: [],
}});
assert.match(list.innerHTML, /没有发现需要确认的位置/);

renderPdfReview(root, {{
  summary: {{ ...base, pdf_matches_docx_confirmed: true, render_evidence_status: "render-review-required" }},
  evidence_items: [],
}});
assert.match(stage.innerHTML, /暂不能判断页面结果/);
"""
    )


def test_pdf_screenshot_uses_real_bbox_and_handles_load_failure():
    _run_node(
        f"""
const {{ renderPdfReview }} = await import({json.dumps(PDF_REVIEW_URL)});
const list = new FakeElement();
const stage = new FakeElement();
const detail = new FakeElement();
const root = {{
  querySelector(selector) {{
    return {{
      "[data-pdf-issues]": list,
      "[data-pdf-stage]": stage,
      "[data-pdf-detail]": detail,
    }}[selector] || null;
  }},
}};

renderPdfReview(root, {{
  evidence_items: [{{
    page: 3,
    screenshot_url: "/render-evidence/screenshot/missing",
    rule_id: "render.toc_page_mismatch",
    message: "目录页码需要确认",
    severity: "warning",
    next_action: "重新导出 PDF",
    bbox: {{ x: 0.1, y: 0.2, w: 0.3, h: 0.1 }},
  }}],
}});

const frame = stage.firstElementChild;
assert.equal(frame.className, "pdf-page-frame");
const highlight = frame.children[1];
assert.equal(highlight.className, "evidence-highlight");
assert.deepEqual({{
  left: highlight.style.left,
  top: highlight.style.top,
  width: highlight.style.width,
  height: highlight.style.height,
}}, {{
  left: "10%",
  top: "20%",
  width: "30%",
  height: "10%",
}});
const image = frame.firstElementChild;
await image.emit("error");

const emptyState = stage.firstElementChild;
assert.equal(emptyState.className, "empty-state");
assert.equal(emptyState.children[0].textContent, "页面截图已不可用");
assert.equal(emptyState.children[1].textContent, "请重新复核 PDF");
"""
    )


def test_toc_finalization_shows_generated_status_and_download():
    _run_node(
        f"""
const {{ renderPdfReview }} = await import({json.dumps(PDF_REVIEW_URL)});
const list = new FakeElement();
const stage = new FakeElement();
const detail = new FakeElement();
const action = new FakeElement();
action.hidden = true;
const title = new FakeElement();
const message = new FakeElement();
const next = new FakeElement();
const button = new FakeElement();
const root = {{
  querySelector(selector) {{
    return {{
      "[data-pdf-issues]": list,
      "[data-pdf-stage]": stage,
      "[data-pdf-detail]": detail,
      "[data-toc-output-action]": action,
      "[data-toc-output-title]": title,
      "[data-toc-output-message]": message,
      "[data-toc-output-next-action]": next,
      "[data-download-role='toc-output']": button,
    }}[selector] || null;
  }},
}};

renderPdfReview(root, {{
  evidence_items: [],
  toc_finalization: {{
    status: "generated",
    available: true,
    entry_count: 26,
    mapped_count: 26,
    message: "静态目录版已生成",
    next_action: "下载后重新导出 PDF 并再次复核",
  }},
}}, {{
  job_id: "render-1",
  artifacts: [{{ role: "toc-output", available: true }}],
}});

assert.equal(action.hidden, false);
assert.equal(title.textContent, "静态目录版已生成");
assert.equal(message.textContent, "已对应 26 项 共 26 项");
assert.equal(next.textContent, "下载后重新导出 PDF 并再次复核");
assert.equal(button.disabled, false);
assert.equal(button.dataset.downloadUrl, "/jobs/render-1/artifacts/toc-output/download");

renderPdfReview(root, {{
  evidence_items: [],
  toc_finalization: {{ status: "generated", available: true }},
}}, {{
  job_id: "render-1",
  artifacts: [{{ role: "toc-output", available: true }}],
}});
assert.equal(message.textContent, "目录页码已经写入新副本");
"""
    )


def test_toc_finalization_explains_incomplete_mapping_without_technical_fields():
    _run_node(
        f"""
const {{ renderPdfReview }} = await import({json.dumps(PDF_REVIEW_URL)});
const action = new FakeElement();
action.hidden = true;
const title = new FakeElement();
const message = new FakeElement();
const next = new FakeElement();
const button = new FakeElement();
const root = {{
  querySelector(selector) {{
    return {{
      "[data-toc-output-action]": action,
      "[data-toc-output-title]": title,
      "[data-toc-output-message]": message,
      "[data-toc-output-next-action]": next,
      "[data-download-role='toc-output']": button,
    }}[selector] || null;
  }},
}};

renderPdfReview(root, {{
  toc_finalization: {{
    status: "incomplete",
    available: false,
    entry_count: 4,
    mapped_count: 3,
    unmatched_titles: ["参考文献"],
    message: "目录与正文没有完整对应 本次不会写入文件",
    next_action: "请在 Word 或 WPS 中人工确认目录",
  }},
}});

assert.equal(action.hidden, false);
assert.equal(title.textContent, "静态目录版未生成");
assert.equal(message.textContent, "已对应 3 项 共 4 项");
assert.equal(next.textContent, "请在 Word 或 WPS 中人工确认目录");
assert.equal(button.disabled, true);
assert.doesNotMatch(`${{title.textContent}} ${{message.textContent}} ${{next.textContent}}`, /incomplete|unmatched_titles/);
"""
    )


def test_toc_finalization_explains_rejection_and_hides_exception_details():
    _run_node(
        f"""
const {{ renderPdfReview }} = await import({json.dumps(PDF_REVIEW_URL)});

function render(finalization) {{
  const action = new FakeElement();
  action.hidden = true;
  const title = new FakeElement();
  const message = new FakeElement();
  const next = new FakeElement();
  const button = new FakeElement();
  const root = {{
    querySelector(selector) {{
      return {{
        "[data-toc-output-action]": action,
        "[data-toc-output-title]": title,
        "[data-toc-output-message]": message,
        "[data-toc-output-next-action]": next,
        "[data-download-role='toc-output']": button,
      }}[selector] || null;
    }},
  }};
  renderPdfReview(root, {{ toc_finalization: finalization }});
  return {{ action, title, message, next, button }};
}}

const blocked = render({{
  status: "blocked",
  available: false,
  message: "请先确认 PDF 与当前论文来自同一版本",
  next_action: "确认后重新复核 PDF",
}});
assert.equal(blocked.action.hidden, false);
assert.equal(blocked.title.textContent, "暂不能生成静态目录版");
assert.equal(blocked.message.textContent, "PDF 与当前论文需要先确认");
assert.equal(blocked.next.textContent, "确认后重新复核 PDF");

const failed = render({{
  status: "error",
  available: false,
  message: "Traceback KeyError word/document.xml",
  next_action: "retry endpoint with JSON payload",
}});
assert.equal(failed.action.hidden, false);
assert.equal(failed.title.textContent, "静态目录版未生成");
assert.equal(failed.message.textContent, "本次目录处理没有完成");
assert.equal(failed.next.textContent, "请在 Word 或 WPS 中人工确认目录");
assert.doesNotMatch(`${{failed.title.textContent}} ${{failed.message.textContent}} ${{failed.next.textContent}}`, /Traceback|KeyError|JSON|endpoint/);
"""
    )


def test_unavailable_toc_keeps_pdf_results_visible_without_backend_details():
    _run_node(
        f"""
const {{ renderPdfReview }} = await import({json.dumps(PDF_REVIEW_URL)});
const action = new FakeElement();
action.hidden = true;
const title = new FakeElement();
const message = new FakeElement();
const next = new FakeElement();
const button = new FakeElement();
const root = {{
  querySelector(selector) {{
    return {{
      "[data-toc-output-action]": action,
      "[data-toc-output-title]": title,
      "[data-toc-output-message]": message,
      "[data-toc-output-next-action]": next,
      "[data-download-role='toc-output']": button,
    }}[selector] || null;
  }},
}};

renderPdfReview(root, {{
  toc_finalization: {{
    status: "unavailable",
    available: false,
    reason: "content-verification-error",
    detail: "KeyError word/document.xml",
  }},
}});

assert.equal(action.hidden, false);
assert.equal(title.textContent, "静态目录暂不可生成");
assert.equal(message.textContent, "PDF 复核结果仍可查看");
assert.equal(next.textContent, "请先查看页面问题");
assert.equal(button.disabled, true);
assert.doesNotMatch(`${{title.textContent}} ${{message.textContent}} ${{next.textContent}}`, /content-verification-error|KeyError|document[.]xml/);
"""
    )


def test_generated_toc_without_artifact_explains_why_download_is_unavailable():
    _run_node(
        f"""
const {{ renderPdfReview }} = await import({json.dumps(PDF_REVIEW_URL)});
const action = new FakeElement();
action.hidden = true;
const title = new FakeElement();
const message = new FakeElement();
const next = new FakeElement();
const button = new FakeElement();
const root = {{
  querySelector(selector) {{
    return {{
      "[data-toc-output-action]": action,
      "[data-toc-output-title]": title,
      "[data-toc-output-message]": message,
      "[data-toc-output-next-action]": next,
      "[data-download-role='toc-output']": button,
    }}[selector] || null;
  }},
}};

renderPdfReview(root, {{
  toc_finalization: {{ status: "generated", available: true }},
}}, {{ job_id: "render-1", artifacts: [] }});

assert.equal(action.hidden, false);
assert.equal(title.textContent, "目录文件暂不可下载");
assert.equal(message.textContent, "静态目录版没有可下载文件");
assert.equal(next.textContent, "请重新复核 PDF");
assert.equal(button.disabled, true);
"""
    )


def test_manual_pdf_issue_goes_to_supported_workbench_scope_with_honest_status():
    _run_node(
        """
exposeScopeOption = true;
scopeInput.checked = false;
scopeInput.disabled = false;
const target = {
  dataset: { action: "repair-scope", scope: "toc", fixMode: "manual" },
  closest(selector) {
    return selector === "[data-action]" ? this : null;
  },
};

await document.emit("click", { target });

assert.equal(scopeInput.checked, true);
assert.equal(scopeState.textContent, "已选择");
assert.equal(workbenchScreen.classList.contains("active"), true);
assert.equal(statusTitle.textContent, "已定位目录范围");
assert.equal(statusMessage.textContent, "这个问题仍需在 Word 或 WPS 中确认");
"""
    )


def test_auto_pdf_issue_selects_the_backend_supported_scope():
    _run_node(
        """
exposeScopeOption = true;
scopeInput.checked = false;
scopeInput.disabled = false;
const target = {
  dataset: { action: "repair-scope", scope: "toc", fixMode: "auto" },
  closest(selector) {
    return selector === "[data-action]" ? this : null;
  },
};

await document.emit("click", { target });

assert.equal(scopeInput.checked, true);
assert.equal(scopeState.textContent, "已选择");
assert.equal(workbenchScreen.classList.contains("active"), true);
assert.equal(statusTitle.textContent, "已选择目录范围");
assert.equal(statusMessage.textContent, "可以检查后生成修正结果");
"""
    )


def test_history_pdf_issue_requires_its_matching_docx_before_selecting_scope():
    _run_node(
        """
exposeScopeOption = true;
scopeInput.checked = false;
scopeInput.disabled = false;
setState({ pdfReviewRequiresFreshDocx: true });
const target = {
  dataset: { action: "repair-scope", scope: "toc", fixMode: "auto" },
  closest(selector) {
    return selector === "[data-action]" ? this : null;
  },
};

await document.emit("click", { target });

assert.equal(scopeInput.checked, false);
assert.equal(workbenchScreen.classList.contains("active"), true);
assert.equal(statusTitle.textContent, "请先上传对应论文");
assert.equal(statusMessage.textContent, "历史复核结果不会用于当前论文");
"""
    )


def test_pdf_issue_does_not_select_a_scope_the_backend_plan_disabled():
    _run_node(
        """
exposeScopeOption = true;
scopeInput.checked = false;
scopeInput.disabled = true;
const target = {
  dataset: { action: "repair-scope", scope: "toc", fixMode: "auto" },
  closest(selector) {
    return selector === "[data-action]" ? this : null;
  },
};

await document.emit("click", { target });

assert.equal(scopeInput.checked, false);
assert.equal(workbenchScreen.classList.contains("active"), true);
assert.equal(statusTitle.textContent, "目录范围暂不能自动修复");
assert.equal(statusMessage.textContent, "请按页面提示在 Word 或 WPS 中处理");
"""
    )


def test_pdf_repair_action_is_an_explicit_go_fix_command():
    _run_node(
        f"""
const {{ renderPdfReview }} = await import({json.dumps(PDF_REVIEW_URL)});
const list = new FakeElement();
const stage = new FakeElement();
const detail = new FakeElement();
const root = {{
  querySelector(selector) {{
    return {{
      "[data-pdf-issues]": list,
      "[data-pdf-stage]": stage,
      "[data-pdf-detail]": detail,
    }}[selector] || null;
  }},
}};

renderPdfReview(root, {{
  evidence_items: [{{
    page: 4,
    screenshot_url: "/render-evidence/screenshot/toc-line",
    suggested_scope: "toc",
    fix_mode: "manual",
  }}],
}});

const button = detail.children[2].children[2];
assert.equal(detail.children[2].children[1].textContent, "这个问题需要在 Word 或 WPS 中确认");
assert.equal(button.dataset.action, "repair-scope");
assert.equal(button.dataset.scope, "toc");
assert.equal(button.dataset.fixMode, "manual");
assert.equal(button.textContent, "去修复");
"""
    )


def test_invalid_pdf_bbox_degrades_to_a_clear_page_level_notice():
    _run_node(
        f"""
const {{ renderPdfReview }} = await import({json.dumps(PDF_REVIEW_URL)});
const list = new FakeElement();
const stage = new FakeElement();
const detail = new FakeElement();
const root = {{
  querySelector(selector) {{
    return {{
      "[data-pdf-issues]": list,
      "[data-pdf-stage]": stage,
      "[data-pdf-detail]": detail,
    }}[selector] || null;
  }},
}};

renderPdfReview(root, {{
  evidence_items: [{{
    page: 6,
    screenshot_url: "/render-evidence/screenshot/page-6",
    bbox: {{ x: 0.1, y: 0.2, w: null, h: 0.1 }},
  }}],
}});

const frame = stage.firstElementChild;
assert.equal(frame.children.length, 2);
assert.equal(frame.children[1].className, "page-notice");
assert.equal(frame.children[1].textContent, "这一页需要整体确认");
"""
    )
