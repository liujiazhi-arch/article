const COVER_FIELD_NAMES = [
  "thesis_title",
  "college",
  "major",
  "student_name",
  "advisor",
  "completion_date",
];

function coverOption(root) {
  return root.querySelector("[data-scope-option='cover']");
}

function coverCheckbox(root) {
  return coverOption(root)?.querySelector("input") || null;
}

function fieldValues(root) {
  return new Map(
    Array.from(root.querySelectorAll("[data-cover-field]"), (field) => [
      field.dataset.coverField,
      String(field.value || "").trim(),
    ]),
  );
}

export function collectCoverFields(root = document) {
  const values = fieldValues(root);
  if (!COVER_FIELD_NAMES.every((name) => values.get(name))) return null;
  return Object.fromEntries(COVER_FIELD_NAMES.map((name) => [name, values.get(name)]));
}

export function coverSelectionIsValid(root = document) {
  const checkbox = coverCheckbox(root);
  return !checkbox?.checked || collectCoverFields(root) !== null;
}

export function syncCoverForm(root = document) {
  const option = coverOption(root);
  const checkbox = option?.querySelector("input");
  const state = option?.querySelector("[data-scope-state]");
  const panel = root.querySelector("[data-cover-fields]");
  const revealPanel = Boolean(checkbox?.checked);
  const wasHidden = Boolean(panel?.hidden);
  if (panel) panel.hidden = !revealPanel;
  if (wasHidden && revealPanel) panel.querySelector?.("input")?.focus();
  if (!state) return;
  if (!checkbox?.checked) state.textContent = "填写后可用";
  else state.textContent = collectCoverFields(root) ? "已填写" : "请填完整";
}

export function prepareCoverScope(root = document) {
  const checkbox = coverCheckbox(root);
  if (checkbox) {
    checkbox.disabled = false;
    checkbox.dataset.requiresReview = "false";
  }
  syncCoverForm(root);
}

export function resetCoverForm(root = document) {
  const checkbox = coverCheckbox(root);
  if (checkbox) checkbox.checked = false;
  root.querySelectorAll("[data-cover-field]").forEach((field) => { field.value = ""; });
  syncCoverForm(root);
}

export function bindCoverForm(root, onChange) {
  const notify = () => {
    syncCoverForm(root);
    onChange();
  };
  coverCheckbox(root)?.addEventListener("change", notify);
  root.querySelectorAll("[data-cover-field]").forEach((field) => field.addEventListener("input", notify));
  prepareCoverScope(root);
}
