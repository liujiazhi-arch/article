export function renderStructureCounts(plan, root = document) {
  const scopeList = Array.isArray(plan?.scopes) ? plan.scopes : [];
  const scopes = new Map(scopeList.map((scope) => [scope.id, scope]));
  root.querySelectorAll("[data-structure-scopes]").forEach((node) => {
    const counter = node.querySelector("[data-structure-count]");
    if (!counter) return;
    const ids = node.dataset.structureScopes.split(",");
    const count = ids.reduce(
      (total, id) => total + Number(scopes.get(id)?.failed_count || 0),
      0,
    );
    counter.textContent = plan ? String(count) : "--";
  });
}

export function setFlowStage(stage, root = document) {
  root.querySelectorAll("[data-flow-stage]").forEach((step) => {
    step.classList.toggle("active", step.dataset.flowStage === stage);
  });
}
