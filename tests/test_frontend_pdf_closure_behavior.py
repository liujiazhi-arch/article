import json

from tests.frontend_app_harness import PDF_REVIEW_URL, run_node as _run_node


def test_pdf_review_module_owns_shell_context_and_reset_rendering():
    _run_node(
        f"""
const {{ isPdfMatchConfirmed, renderPdfReviewContext, resetPdfReview }} = await import({json.dumps(PDF_REVIEW_URL)});
const confirmation = new FakeElement();
confirmation.checked = true;
const documentName = new FakeElement();
const pdfName = new FakeElement();
const shellRenderState = new FakeElement();
const shellConclusion = new FakeElement();
const shellPages = new FakeElement();
const shellIssues = new FakeElement();
const list = new FakeElement();
const stage = new FakeElement();
const detail = new FakeElement();
const root = {{
  querySelector(selector) {{
    return {{
      "#pdf-match-confirmation": confirmation,
      "[data-pdf-docx-file]": documentName,
      "[data-pdf-file]": pdfName,
      "[data-render-state]": shellRenderState,
      '[data-pdf-metric="conclusion"]': shellConclusion,
      '[data-pdf-metric="pages"]': shellPages,
      '[data-pdf-metric="issues"]': shellIssues,
      "[data-pdf-issues]": list,
      "[data-pdf-stage]": stage,
      "[data-pdf-detail]": detail,
    }}[selector] || null;
  }},
}};

assert.equal(isPdfMatchConfirmed(root), true);
renderPdfReviewContext(root, {{
  documentName: "paper.docx",
  pdfName: "paper.pdf",
  status: "已完成",
  confirmationChecked: false,
}});
assert.equal(documentName.textContent, "paper.docx");
assert.equal(pdfName.textContent, "paper.pdf");
assert.equal(shellRenderState.textContent, "已完成");
assert.equal(confirmation.checked, false);

resetPdfReview(root, {{
  renderState: "复核中",
  conclusion: "待确认",
  title: "正在复核 PDF",
  message: "完成后显示页面问题",
}});
assert.equal(isPdfMatchConfirmed(root), false);
assert.equal(pdfName.textContent, "等待上传对应 PDF");
assert.equal(shellRenderState.textContent, "复核中");
assert.equal(shellConclusion.textContent, "待确认");
assert.equal(shellPages.textContent, "--");
assert.equal(shellIssues.textContent, "--");
assert.equal(stage.firstElementChild.children[0].textContent, "正在复核 PDF");
assert.equal(stage.firstElementChild.children[1].textContent, "完成后显示页面问题");
"""
    )


def test_pdf_review_reset_returns_new_evidence_to_the_first_issue():
    _run_node(
        f"""
const {{ bindPdfReview, renderPdfReview, resetPdfReview }} = await import({json.dumps(PDF_REVIEW_URL)});
const list = new FakeElement();
const stage = new FakeElement();
const detail = new FakeElement();
const root = new FakeElement();
root.querySelector = (selector) => ({{
  "[data-pdf-issues]": list,
  "[data-pdf-stage]": stage,
  "[data-pdf-detail]": detail,
}}[selector] || null);
const result = {{ summary: {{ evidence_source: "word-pdf", layout_decision_eligible: true }},
  evidence_items: [
    {{ page: 2, rule_id: "render.line_overflow" }},
    {{ page: 5, rule_id: "render.heading_orphan_at_page_bottom" }},
  ],
}};
let currentResult = result;
bindPdfReview(root, () => renderPdfReview(root, currentResult));

renderPdfReview(root, currentResult);
const secondIssue = list.children[1];
await root.emit("click", {{
  target: {{
    closest(selector) {{
      return selector === "[data-issue-index]" ? secondIssue : null;
    }},
  }},
}});
assert.equal(list.children[1].ariaPressed, "true");

resetPdfReview(root);
currentResult = {{ ...result, evidence_items: [...result.evidence_items] }};
renderPdfReview(root, currentResult);
assert.equal(list.children[0].ariaPressed, "true");
assert.equal(list.children[1].ariaPressed, "false");
"""
    )


def test_pdf_metrics_preserve_legacy_count_only_when_evidence_items_are_absent():
    _run_node(
        f"""
const {{ renderPdfReview }} = await import({json.dumps(PDF_REVIEW_URL)});
const issues = new FakeElement();
const list = new FakeElement();
const stage = new FakeElement();
const detail = new FakeElement();
const root = {{
  querySelector(selector) {{
    return {{
      '[data-pdf-metric="issues"]': issues,
      "[data-pdf-issues]": list,
      "[data-pdf-stage]": stage,
      "[data-pdf-detail]": detail,
    }}[selector] || null;
  }},
}};

renderPdfReview(root, {{ summary: {{ evidence_source: "word-pdf", layout_decision_eligible: true }}, render_summary: {{ actionable_finding_count: 3 }} }});
assert.equal(issues.textContent, "3");

renderPdfReview(root, {{ summary: {{ evidence_source: "word-pdf", layout_decision_eligible: true }},
  evidence_items: [],
  render_summary: {{ actionable_finding_count: 3 }},
}});
assert.equal(issues.textContent, "0");
"""
    )


def test_pdf_evidence_use_requires_canonical_backend_eligibility():
    _run_node(
        f"""
const {{ isPdfEvidenceUsable }} = await import({json.dumps(PDF_REVIEW_URL)});

const manual = {{
  summary: {{
    evidence_source: "manual-pdf",
    layout_decision_eligible: true,
  }},
}};

assert.equal(isPdfEvidenceUsable({{
  summary: {{ ...manual.summary, layout_decision_eligible: false, pdf_content_match_status: "matched" }},
}}), false);
assert.equal(isPdfEvidenceUsable(manual), true);
assert.equal(isPdfEvidenceUsable({{
  summary: {{ ...manual.summary, pdf_content_match_status: "mismatch" }},
}}), true);
assert.equal(isPdfEvidenceUsable({{
  summary: {{ ...manual.summary, pdf_content_match_status: "matched" }},
}}), true);
assert.equal(isPdfEvidenceUsable({{
  summary: {{ evidence_source: "word-pdf", layout_decision_eligible: true }},
}}), true);
assert.equal(isPdfEvidenceUsable({{
  summary: {{ evidence_source: "word-pdf", layout_decision_eligible: false }},
}}), false);
assert.equal(isPdfEvidenceUsable({{
  render_engine: "word-pdf",
  layout_decision_eligible: true,
}}), true);
"""
    )


def test_ineligible_pdf_never_renders_or_keeps_evidence_items():
    _run_node(
        f"""
const {{ renderPdfReview }} = await import({json.dumps(PDF_REVIEW_URL)});
const conclusion = new FakeElement();
const pages = new FakeElement();
const issues = new FakeElement();
const list = new FakeElement();
const stage = new FakeElement();
const detail = new FakeElement();
const root = {{
  querySelector(selector) {{
    return {{
      '[data-pdf-metric="conclusion"]': conclusion,
      '[data-pdf-metric="pages"]': pages,
      '[data-pdf-metric="issues"]': issues,
      "[data-pdf-issues]": list,
      "[data-pdf-stage]": stage,
      "[data-pdf-detail]": detail,
    }}[selector] || null;
  }},
}};
const item = {{
  page: 9,
  screenshot_url: "/render-evidence/screenshot/page-9",
  rule_id: "render.formula_number_split_page",
  suggested_scope: "body_paragraphs",
  fix_mode: "manual",
}};

renderPdfReview(root, {{
  summary: {{
    evidence_source: "word-pdf",
    layout_decision_eligible: true,
    render_evidence_status: "render-review-required",
    page_count: 9,
  }},
  evidence_items: [item],
}});
assert.equal(stage.firstElementChild.className, "pdf-evidence-view single");
assert.equal(detail.children[2].children[2].textContent, "去修复");

renderPdfReview(root, {{
  summary: {{
    evidence_source: "manual-pdf",
    layout_decision_eligible: false,
    pdf_content_match_status: "mismatch",
    render_evidence_status: "unsupported-evidence",
    page_count: 9,
  }},
  evidence_items: [item],
}});

assert.equal(list.children.length, 1);
assert.equal(list.firstElementChild.className, "empty-state");
assert.equal(list.firstElementChild.children[0].textContent, "版本对应关系待确认");
assert.equal(stage.children.length, 1);
assert.equal(stage.firstElementChild.className, "empty-state");
assert.equal(detail.children.length, 1);
assert.equal(detail.firstElementChild.className, "finding");
assert.equal(detail.firstElementChild.children.length, 2);
assert.equal(conclusion.textContent, "待确认");
assert.equal(pages.textContent, "--");
assert.equal(issues.textContent, "--");
"""
    )


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
  layout_decision_eligible: false,
  pdf_content_match_status: "mismatch",
}};
renderPdfReview(root, {{ summary: base, evidence_items: [] }});
assert.equal(list.firstElementChild.children[0].textContent, "版本对应关系待确认");

renderPdfReview(root, {{
  summary: {{
    render_evidence_status: "render-evidence-ready",
    evidence_source: "word-pdf",
    layout_decision_eligible: true,
  }},
  evidence_items: [],
}});
assert.match(list.innerHTML, /没有发现需要确认的位置/);

renderPdfReview(root, {{
  summary: {{
    render_evidence_status: "render-review-required",
    evidence_source: "word-pdf",
    layout_decision_eligible: true,
  }},
  evidence_items: [],
}});
assert.match(list.innerHTML, /没有返回可定位的位置/);
assert.match(stage.innerHTML, /不能确认页面没有问题/);
assert.match(detail.innerHTML, /页面和结构/);
assert.doesNotMatch(stage.innerHTML, /暂无页面问题/);
assert.doesNotMatch(detail.innerHTML, /仍有结构项需要人工确认/);
assert.doesNotMatch(list.innerHTML, /版本对应关系待确认/);
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

renderPdfReview(root, {{ summary: {{ evidence_source: "word-pdf", layout_decision_eligible: true }},
  evidence_items: [{{
    page: 3,
    screenshot_url: "/render-evidence/screenshot/missing",
    rule_id: "render.toc_page_number_mismatch",
    message: "目录页码需要确认",
    severity: "warning",
    next_action: "重新导出 PDF",
    bbox: {{ x: 0.1, y: 0.2, w: 0.3, h: 0.1 }},
  }}],
}});

const issueButton = list.firstElementChild;
assert.equal(issueButton.children[0].textContent, "第 3 页");
assert.equal(issueButton.children[1].textContent, "目录页码疑似错位");
assert.equal(issueButton.ariaPressed, "true");

const view = stage.firstElementChild;
assert.equal(view.className, "pdf-evidence-view");
const frame = view.children[0];
assert.equal(frame.className, "pdf-page-frame");
const highlight = frame.children[1];
assert.equal(highlight.className, "evidence-highlight");
assert.equal(highlight.dataset.label, "问题位置");
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
const zoom = view.children[1];
assert.equal(zoom.className, "pdf-evidence-zoom");
assert.equal(zoom.children[0].textContent, "问题片段");
assert.equal(zoom.children[1].className, "pdf-evidence-crop");
assert.equal(zoom.children[1].style.backgroundImage, 'url("/render-evidence/screenshot/missing")');
assert.equal(zoom.children[1].style.backgroundPosition, "25% 25%");
const image = frame.firstElementChild;
await image.emit("error");

const emptyState = stage.firstElementChild;
assert.equal(emptyState.className, "empty-state");
assert.equal(emptyState.children[0].textContent, "页面截图已不可用");
assert.equal(emptyState.children[1].textContent, "请重新复核 PDF");

renderPdfReview(root, {{ summary: {{ evidence_source: "word-pdf", layout_decision_eligible: true }},
  evidence_items: [{{
    page: 4,
    screenshot_url: "/render-evidence/screenshot/page-4",
    rule_id: "render.line_overflow",
    bbox: {{ x: 0, y: 0, w: 1, h: 1 }},
  }}],
}});

const pageView = stage.firstElementChild;
assert.equal(pageView.className, "pdf-evidence-view single");
assert.equal(pageView.children.length, 1);
const pageFrame = pageView.firstElementChild;
assert.equal(pageFrame.children.length, 2);
assert.equal(pageFrame.children[1].className, "page-notice");
assert.equal(pageFrame.children[1].textContent, "这一页需要整体确认");
"""
    )


def test_pdf_text_spans_override_legacy_bbox_and_render_multiple_real_boxes():
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

renderPdfReview(root, {{ summary: {{ evidence_source: "word-pdf", layout_decision_eligible: true }},
  evidence_items: [{{
    page: 8,
    screenshot_url: "/render-evidence/screenshot/page-8",
    rule_id: "render.heading_orphan_at_page_bottom",
    bbox: {{ x: 0, y: 0, w: 1, h: 1 }},
    text_spans: [
      {{ text: "1.1", bbox: {{ x: 0.1, y: 0, w: 0.2, h: 0.1 }} }},
      {{ text: "研究背景", bbox: {{ x: 0.1, y: 0.2, w: 0.2, h: 0.1 }} }},
      {{ text: "bad", bbox: {{ x: 1.2, y: 0.4, w: 0.2, h: 0.1 }} }},
    ],
  }}],
}});

const view = stage.firstElementChild;
assert.equal(view.className, "pdf-evidence-view multiple");
const frame = view.firstElementChild;
assert.equal(frame.children.length, 3);
const first = frame.children[1];
const second = frame.children[2];
assert.equal(first.className, "evidence-highlight");
assert.equal(first.dataset.label, "问题位置");
assert.equal(first.ariaHidden, "true");
assert.equal(second.className, "evidence-highlight");
assert.equal(second.dataset.label, undefined);
assert.deepEqual({{ left: first.style.left, top: first.style.top }}, {{ left: "10%", top: "0%" }});
assert.deepEqual({{ left: second.style.left, top: second.style.top }}, {{ left: "10%", top: "20%" }});
const zoom = view.children[1];
assert.equal(zoom.children[0].textContent, "问题片段 2 处");
const crop = zoom.children[1];
const image = frame.children[0];
image.naturalWidth = 100;
image.naturalHeight = 200;
crop.getBoundingClientRect = () => ({{ width: 400, height: 320 }});
await image.emit("load");
assert.equal(crop.style.backgroundSize, "93% auto");
assert.equal(crop.style.backgroundPosition, "126px 48px");
assert.equal(crop.role, "img");
assert.match(crop.ariaLabel, /第 8 页/);
assert.equal(list.firstElementChild.getAttribute("aria-controls"), "pdf-evidence-stage");
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

renderPdfReview(root, {{ summary: {{ evidence_source: "word-pdf", layout_decision_eligible: true }},
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

renderPdfReview(root, {{ summary: {{ evidence_source: "word-pdf", layout_decision_eligible: true }},
  evidence_items: [{{
    page: 6,
    screenshot_url: "/render-evidence/screenshot/page-6",
    bbox: {{ x: 0.1, y: 0.2, w: null, h: 0.1 }},
  }}],
}});

const view = stage.firstElementChild;
assert.equal(view.className, "pdf-evidence-view single");
assert.equal(view.children.length, 1);
const frame = view.firstElementChild;
assert.equal(frame.children.length, 2);
assert.equal(frame.children[1].className, "page-notice");
assert.equal(frame.children[1].textContent, "这一页需要整体确认");
"""
    )
