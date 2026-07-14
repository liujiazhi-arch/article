let state = {
  docxUpload: null,
  workbenchPlan: null,
  renderResult: null,
  renderResultPayload: null,
  applyRunning: false,
  documentEpoch: 0,
  pdfReviewEpoch: 0,
  pdfReviewRequiresFreshDocx: false,
};

export function getState() {
  return { ...state };
}

export function setState(patch) {
  state = { ...state, ...patch };
}
