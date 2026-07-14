async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const detail = payload && payload.detail ? payload.detail : payload;
    const message = detail && detail.user_message ? detail.user_message : "操作没有完成";
    const nextAction = detail && detail.next_action ? detail.next_action : "请稍后重试";
    const error = new Error(message);
    error.nextAction = nextAction;
    error.status = response.status;
    throw error;
  }

  return payload;
}

const finishedJobStates = new Set(["succeeded", "failed"]);

export async function waitForJob(jobId, isCurrent = () => true) {
  while (isCurrent()) {
    const job = await getJob(jobId);
    if (!isCurrent()) return null;
    if (finishedJobStates.has(job.status)) {
      if (job.status === "failed") throw new Error("处理没有完成");
      return job;
    }
    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
  return null;
}

export async function uploadDocx(file) {
  const body = new FormData();
  body.append("file", file);
  return requestJson("/uploads/docx", { method: "POST", body });
}

export async function uploadPdf(file) {
  const body = new FormData();
  body.append("file", file);
  return requestJson("/uploads/pdf", { method: "POST", body });
}

export async function createApplyJob(uploadId, body = {}) {
  return requestJson(`/uploads/${encodeURIComponent(uploadId)}/jobs/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function createRenderReviewJob(docxUploadId, pdfUploadId, pdfMatchesDocxConfirmed) {
  return requestJson(`/uploads/${encodeURIComponent(docxUploadId)}/render-review-jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      pdf_upload_id: pdfUploadId,
      pdf_matches_docx_confirmed: pdfMatchesDocxConfirmed === true,
      generate_static_toc: true,
    }),
  });
}

export async function createUploadPlan(uploadId, body = {}) {
  return requestJson(`/uploads/${encodeURIComponent(uploadId)}/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function getJob(jobId) {
  return requestJson(`/jobs/${encodeURIComponent(jobId)}`);
}

export async function getJobResult(jobId) {
  return requestJson(`/jobs/${encodeURIComponent(jobId)}/result`);
}

export async function listJobs({ limit = 10 } = {}) {
  return requestJson("/jobs?limit=" + encodeURIComponent(limit));
}

export function downloadJobArtifactUrl(jobId, role) {
  return `/jobs/${encodeURIComponent(jobId)}/artifacts/${encodeURIComponent(role)}/download`;
}
