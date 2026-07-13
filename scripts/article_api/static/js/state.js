const state = {
  theme: "snow",
  docxUpload: null,
  pdfUpload: null,
  activeJob: null,
  workbenchPlan: null,
  applyResultPayload: null,
  jobHistory: [],
  selectedHistoryJob: null,
  renderResult: null,
  renderResultPayload: null,
  activeEvidenceIndex: 0,
  highlightVisible: true,
  applyRunning: false,
};

const listeners = new Set();

export function getState() {
  return { ...state };
}

export function setState(patch) {
  Object.assign(state, patch);
  for (const listener of listeners) {
    listener(getState());
  }
}

export function subscribe(listener) {
  listeners.add(listener);
  listener(getState());
  return () => listeners.delete(listener);
}
