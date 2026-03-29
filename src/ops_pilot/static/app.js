const plannerForm = document.getElementById("planner-form");
const reviewForm = document.getElementById("review-form");
const conversation = document.getElementById("conversation");
const summaryGrid = document.getElementById("summary-grid");
const briefMarkdown = document.getElementById("brief-markdown");
const statusPill = document.getElementById("status-pill");
const sampleButton = document.getElementById("load-sample");
const reviewSampleButton = document.getElementById("load-review-sample");
const modeButtons = Array.from(document.querySelectorAll(".mode-button"));
const resultTitle = document.getElementById("results-title");
const artifactTitle = document.getElementById("artifact-title");

let currentMode = "plan";

const planSamplePayload = {
  title: "Student org event follow-up",
  team_type: "Student organization",
  workflow_goal: "Coordinate sponsor follow-up, volunteer recap, and next-step assignments after each weekly event planning meeting.",
  current_process:
    "The president and operations lead review notes, rewrite action items into a spreadsheet, send recap emails, and manually check who responded. Sponsor follow-up often waits for manual approval and people miss deadlines when ownership is unclear.",
  desired_outcome:
    "reduce coordination overhead and make follow-up more reliable without removing the human lead from approvals",
  task_volume_per_week: "22",
  manual_hours_per_week: "6.5",
  average_cycle_time_hours: "48",
  average_error_rate_pct: "15",
  cost_per_hour: "22",
};

const reviewSamplePayload = {
  workflow: {
    title: "Student org event follow-up",
    team_type: "Student organization",
    workflow_goal: "Coordinate sponsor follow-up, volunteer recap, and next-step assignments after each weekly event planning meeting.",
    current_process:
      "The president and operations lead review notes, rewrite action items into a spreadsheet, send recap emails, and manually check who responded.",
    desired_outcome:
      "reduce coordination overhead and make follow-up more reliable without removing the human lead from approvals",
    task_volume_per_week: "22",
    manual_hours_per_week: "6.5",
    average_cycle_time_hours: "48",
    average_error_rate_pct: "15",
    cost_per_hour: "22",
  },
  actuals: {
    pilot_duration_weeks: "4",
    actual_manual_hours_per_week: "3.8",
    actual_cycle_time_hours: "30",
    actual_error_rate_pct: "8",
    actual_on_time_completion_pct: "96",
    adoption_rate_pct: "88",
    blockers: "Sponsor outreach still needed manual approval on edge cases\nOne volunteer report format was inconsistent in week two",
    notes:
      "The pilot reduced recap drafting time quickly. Adoption improved after the second week once the team standardized its meeting note template.",
  },
};

modeButtons.forEach((button) => {
  button.addEventListener("click", () => setMode(button.dataset.mode));
});

sampleButton.addEventListener("click", () => {
  setMode("plan");
  assignValues(planSamplePayload);
  appendMessage(
    "agent",
    "Planning sample loaded. Submit it to generate the pilot brief."
  );
});

reviewSampleButton.addEventListener("click", () => {
  setMode("review");
  assignValues(
    {
      review_title: reviewSamplePayload.workflow.title,
      review_team_type: reviewSamplePayload.workflow.team_type,
      review_workflow_goal: reviewSamplePayload.workflow.workflow_goal,
      review_current_process: reviewSamplePayload.workflow.current_process,
      review_desired_outcome: reviewSamplePayload.workflow.desired_outcome,
      review_task_volume_per_week: reviewSamplePayload.workflow.task_volume_per_week,
      review_manual_hours_per_week: reviewSamplePayload.workflow.manual_hours_per_week,
      review_average_cycle_time_hours: reviewSamplePayload.workflow.average_cycle_time_hours,
      review_average_error_rate_pct: reviewSamplePayload.workflow.average_error_rate_pct,
      review_cost_per_hour: reviewSamplePayload.workflow.cost_per_hour,
      pilot_duration_weeks: reviewSamplePayload.actuals.pilot_duration_weeks,
      actual_manual_hours_per_week: reviewSamplePayload.actuals.actual_manual_hours_per_week,
      actual_cycle_time_hours: reviewSamplePayload.actuals.actual_cycle_time_hours,
      actual_error_rate_pct: reviewSamplePayload.actuals.actual_error_rate_pct,
      actual_on_time_completion_pct: reviewSamplePayload.actuals.actual_on_time_completion_pct,
      adoption_rate_pct: reviewSamplePayload.actuals.adoption_rate_pct,
      review_blockers: reviewSamplePayload.actuals.blockers,
      review_notes: reviewSamplePayload.actuals.notes,
    }
  );
  appendMessage(
    "agent",
    "Review sample loaded. Submit it to compare projected KPI targets against measured pilot outcomes."
  );
});

plannerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  statusPill.textContent = "Analyzing";
  statusPill.className = "status-pill";

  const payload = await collectPlanningPayload();
  appendMessage(
    "user",
    `Analyze "${payload.title}" for ${payload.team_type || "a small team"} and tell me if it is worth piloting.`
  );

  try {
    const data = await postJson("/api/analyze", payload);
    renderPlanningResponse(data);
  } catch (error) {
    renderError(error);
  }
});

reviewForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  statusPill.textContent = "Reviewing";
  statusPill.className = "status-pill";

  const payload = await collectReviewPayload();
  appendMessage(
    "user",
    `Review the completed pilot for "${payload.workflow.title}" and tell me whether to scale, revise, or stop.`
  );

  try {
    const data = await postJson("/api/review-pilot", payload);
    renderReviewResponse(data);
  } catch (error) {
    renderError(error);
  }
});

function setMode(mode) {
  currentMode = mode;
  modeButtons.forEach((button) => {
    const active = button.dataset.mode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  });

  document.querySelectorAll("[data-mode-panel]").forEach((panel) => {
    panel.classList.toggle("hidden", panel.dataset.modePanel !== mode);
  });

  if (mode === "plan") {
    resultTitle.textContent = "Pilot Planning Output";
    artifactTitle.textContent = "Pilot Brief";
  } else {
    resultTitle.textContent = "Post-Pilot Assessment";
    artifactTitle.textContent = "Review Report";
  }
}

async function collectPlanningPayload() {
  return {
    title: readValue("title"),
    team_type: readValue("team_type"),
    workflow_goal: readValue("workflow_goal"),
    current_process: readValue("current_process"),
    desired_outcome: readValue("desired_outcome"),
    task_volume_per_week: readValue("task_volume_per_week"),
    manual_hours_per_week: readValue("manual_hours_per_week"),
    average_cycle_time_hours: readValue("average_cycle_time_hours"),
    average_error_rate_pct: readValue("average_error_rate_pct"),
    cost_per_hour: readValue("cost_per_hour"),
    documents: await collectDocuments("documents"),
  };
}

async function collectReviewPayload() {
  const reviewDocuments = await collectDocuments("review_documents");
  return {
    workflow: {
      title: readValue("review_title"),
      team_type: readValue("review_team_type"),
      workflow_goal: readValue("review_workflow_goal"),
      current_process: readValue("review_current_process"),
      desired_outcome: readValue("review_desired_outcome"),
      task_volume_per_week: readValue("review_task_volume_per_week"),
      manual_hours_per_week: readValue("review_manual_hours_per_week"),
      average_cycle_time_hours: readValue("review_average_cycle_time_hours"),
      average_error_rate_pct: readValue("review_average_error_rate_pct"),
      cost_per_hour: readValue("review_cost_per_hour"),
      documents: [],
    },
    actuals: {
      pilot_duration_weeks: readValue("pilot_duration_weeks"),
      actual_manual_hours_per_week: readValue("actual_manual_hours_per_week"),
      actual_cycle_time_hours: readValue("actual_cycle_time_hours"),
      actual_error_rate_pct: readValue("actual_error_rate_pct"),
      actual_on_time_completion_pct: readValue("actual_on_time_completion_pct"),
      adoption_rate_pct: readValue("adoption_rate_pct"),
      blockers: readValue("review_blockers"),
      notes: readValue("review_notes"),
      documents: reviewDocuments,
    },
  };
}

async function collectDocuments(inputId) {
  const fileInput = document.getElementById(inputId);
  return Promise.all(
    Array.from(fileInput.files || []).map(async (file) => ({
      name: file.name,
      content: await file.text(),
    }))
  );
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed.");
  }
  return data;
}

function renderPlanningResponse(data) {
  const brief = data.brief;
  const score = brief.opportunity_score;
  const roi = brief.roi_estimate;
  const runtime = data.runtime || null;

  resultTitle.textContent = "Pilot Planning Output";
  artifactTitle.textContent = "Pilot Brief";
  statusPill.textContent = score.recommendation;
  statusPill.className = "status-pill ready";

  renderSummaryCards([
    ["Recommendation", score.recommendation],
    ["Score", `${score.total}/100`],
    ["Annual savings", formatCurrency(roi.annual_cost_savings)],
    ["Pipeline", runtime ? runtime.mode.toUpperCase() : "DETERMINISTIC"],
  ]);

  appendMessage(
    "agent",
    `${brief.recommendation}\n\nTop pain points: ${brief.pain_points.map((item) => item.title).join(", ")}.`
  );
  renderClarifyingQuestions(data.clarifying_questions);
  renderRuntimeWarnings(runtime);
  briefMarkdown.textContent = data.markdown;
}

function renderReviewResponse(data) {
  const review = data.review;
  const runtime = data.runtime || null;

  resultTitle.textContent = "Post-Pilot Assessment";
  artifactTitle.textContent = "Review Report";
  statusPill.textContent = review.final_decision;
  statusPill.className = "status-pill ready";

  renderSummaryCards([
    ["Decision", review.final_decision],
    ["KPI attainment", `${Math.round(review.kpi_attainment_pct)}%`],
    ["Actual annualized savings", formatMaybeCurrency(review.actual_annualized_cost_savings)],
    ["Pipeline", runtime ? runtime.mode.toUpperCase() : "DETERMINISTIC"],
  ]);

  appendMessage(
    "agent",
    `${review.final_decision}\n\n${review.decision_rationale}`
  );
  renderClarifyingQuestions(data.clarifying_questions);
  renderRuntimeWarnings(runtime);
  briefMarkdown.textContent = data.markdown;
}

function renderSummaryCards(items) {
  summaryGrid.classList.remove("hidden");
  summaryGrid.innerHTML = "";
  items.forEach(([label, value]) => {
    const card = document.createElement("article");
    card.className = "summary-card";
    card.innerHTML = `<span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong>`;
    summaryGrid.appendChild(card);
  });
}

function renderClarifyingQuestions(questions) {
  if (!questions || !questions.length) {
    return;
  }
  appendMessage(
    "agent",
    "I would still confirm:\n" + questions.map((item) => `- ${item.question}`).join("\n")
  );
}

function renderRuntimeWarnings(runtime) {
  if (runtime && runtime.warnings && runtime.warnings.length) {
    appendMessage(
      "agent",
      "Runtime notes:\n" + runtime.warnings.map((item) => `- ${item}`).join("\n")
    );
  }
}

function renderError(error) {
  statusPill.textContent = "Error";
  statusPill.className = "status-pill muted";
  appendMessage("agent", String(error.message || error));
}

function appendMessage(role, text) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  article.appendChild(paragraph);
  conversation.appendChild(article);
  conversation.scrollTop = conversation.scrollHeight;
}

function readValue(id) {
  return document.getElementById(id).value.trim();
}

function assignValues(mapping) {
  Object.entries(mapping).forEach(([key, value]) => {
    const input = document.getElementById(key);
    if (input) {
      input.value = value;
    }
  });
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function formatCurrency(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatMaybeCurrency(value) {
  if (value === null || value === undefined) {
    return "Not measured";
  }
  return formatCurrency(value);
}

setMode(currentMode);
