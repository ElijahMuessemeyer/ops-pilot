const form = document.getElementById("planner-form");
const conversation = document.getElementById("conversation");
const summaryGrid = document.getElementById("summary-grid");
const briefMarkdown = document.getElementById("brief-markdown");
const statusPill = document.getElementById("status-pill");
const sampleButton = document.getElementById("load-sample");

const samplePayload = {
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

sampleButton.addEventListener("click", () => {
  for (const [key, value] of Object.entries(samplePayload)) {
    const input = document.getElementById(key);
    if (input) {
      input.value = value;
    }
  }

  appendMessage(
    "agent",
    "Sample data loaded. Add notes or click Draft pilot brief to generate the recommendation."
  );
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  statusPill.textContent = "Analyzing";
  statusPill.className = "status-pill";

  const payload = await collectPayload();
  appendMessage(
    "user",
    `Analyze "${payload.title}" for ${payload.team_type || "a small team"} and tell me if it is worth piloting.`
  );

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Analysis failed.");
    }
    renderResponse(data);
  } catch (error) {
    statusPill.textContent = "Error";
    statusPill.className = "status-pill muted";
    appendMessage("agent", String(error.message || error));
  }
});

async function collectPayload() {
  const fileInput = document.getElementById("documents");
  const documents = await Promise.all(
    Array.from(fileInput.files || []).map(async (file) => ({
      name: file.name,
      content: await file.text(),
    }))
  );

  return {
    title: document.getElementById("title").value.trim(),
    team_type: document.getElementById("team_type").value.trim(),
    workflow_goal: document.getElementById("workflow_goal").value.trim(),
    current_process: document.getElementById("current_process").value.trim(),
    desired_outcome: document.getElementById("desired_outcome").value.trim(),
    task_volume_per_week: document.getElementById("task_volume_per_week").value.trim(),
    manual_hours_per_week: document.getElementById("manual_hours_per_week").value.trim(),
    average_cycle_time_hours: document.getElementById("average_cycle_time_hours").value.trim(),
    average_error_rate_pct: document.getElementById("average_error_rate_pct").value.trim(),
    cost_per_hour: document.getElementById("cost_per_hour").value.trim(),
    documents,
  };
}

function renderResponse(data) {
  const brief = data.brief;
  const score = brief.opportunity_score;
  const roi = brief.roi_estimate;
  const runtime = data.runtime || null;

  statusPill.textContent = score.recommendation;
  statusPill.className = "status-pill ready";

  summaryGrid.classList.remove("hidden");
  summaryGrid.innerHTML = "";
  [
    ["Recommendation", score.recommendation],
    ["Score", `${score.total}/100`],
    ["Annual savings", formatCurrency(roi.annual_cost_savings)],
    ["Pipeline", runtime ? runtime.mode.toUpperCase() : "DETERMINISTIC"],
  ].forEach(([label, value]) => {
    const card = document.createElement("article");
    card.className = "summary-card";
    card.innerHTML = `<span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong>`;
    summaryGrid.appendChild(card);
  });

  appendMessage(
    "agent",
    `${brief.recommendation}\n\nTop pain points: ${brief.pain_points.map((item) => item.title).join(", ")}.`
  );

  if (data.clarifying_questions.length) {
    appendMessage(
      "agent",
      "Before a real launch, I would still confirm:\n" +
        data.clarifying_questions.map((item) => `- ${item.question}`).join("\n")
    );
  }

  if (runtime && runtime.warnings && runtime.warnings.length) {
    appendMessage(
      "agent",
      "Runtime notes:\n" + runtime.warnings.map((item) => `- ${item}`).join("\n")
    );
  }

  briefMarkdown.textContent = data.markdown;
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
