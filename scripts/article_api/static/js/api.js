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

export async function createRenderReviewJob(docxUploadId, pdfUploadId) {
  return requestJson(`/uploads/${encodeURIComponent(docxUploadId)}/render-review-jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pdf_upload_id: pdfUploadId }),
  });
}

export async function createPlan(filePath) {
  return requestJson("/plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_path: filePath }),
  });
}

export async function getJob(jobId) {
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
