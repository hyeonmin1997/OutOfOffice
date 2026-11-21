const $ = (id) => document.getElementById(id);

const LABELS = {
  read_mail: "Read mail",
  lookup_user: "Look up employee",
  create_event: "Add personal calendar event",
  send_email: "Send welcome email",
  grant_access: "Grant project access",
};

const STATUSES = {
  executed: "Executed",
  pending: "Awaiting approval",
  blocked: "Blocked by policy",
  rejected: "Rejected",
};

const ARG_LABELS = {
  mail_id: "Mail ID",
  user_id: "User",
  owner: "Event owner",
  title: "Event title",
  time: "Time",
  recipient: "Recipient",
  subject: "Subject",
  body: "Body",
  project: "Project",
  role: "Role to grant",
};

let mailbox = [];
let examples = {};
let busy = false;
let countdownTimer = null;

async function request(path, data) {
  const response = await fetch(path, data === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const result = await response.json();
  if (!response.ok || result.error) throw new Error(result.error || "Request failed.");
  return result;
}

function buildKVList(obj) {
  const dl = document.createElement("dl");
  dl.className = "kv-list";
  Object.entries(obj || {}).forEach(([key, value]) => {
    const dt = document.createElement("dt");
    dt.textContent = ARG_LABELS[key] || key;
    const dd = document.createElement("dd");
    dd.textContent = String(value);
    dl.append(dt, dd);
  });
  return dl;
}

function renderActionCard(action, outcome) {
  const status = outcome.status || "";
  const card = document.createElement("div");
  card.className = `card ${status}`;

  const top = document.createElement("div");
  top.className = "card-top";

  const title = document.createElement("span");
  title.className = "card-title";
  title.textContent = LABELS[action.tool] || action.tool;

  const pill = document.createElement("span");
  pill.className = `status-pill ${status}`;
  pill.textContent = STATUSES[status] || status;

  top.append(title, pill);
  card.append(top);

  if (status === "pending") {
    const note = document.createElement("p");
    note.className = "note";
    note.textContent = "Passed the policy check. It runs only after M approves it in 'M's approval queue' below.";
    card.append(note);
  } else {
    card.append(buildKVList(action.args));
  }

  if (outcome.reason) {
    const reason = document.createElement("div");
    reason.className = "reason-box";
    reason.textContent = status === "blocked" ? `Block reason: ${outcome.reason}` : outcome.reason;
    card.append(reason);
  }

  return card;
}

function renderEmpty(container, text) {
  container.replaceChildren();
  const empty = document.createElement("div");
  empty.className = "empty-state";
  empty.textContent = text;
  container.append(empty);
}

function renderDbItems(containerId, countId, rows, emptyText, renderFn) {
  const container = $(containerId);
  $(countId).textContent = String(rows.length);
  if (!rows.length) {
    renderEmpty(container, emptyText);
    return;
  }
  container.replaceChildren();
  rows.forEach((row) => {
    const item = document.createElement("div");
    item.className = "db-item";
    const { heading, lines } = renderFn(row);
    const strong = document.createElement("strong");
    strong.textContent = heading;
    item.append(strong);
    lines.forEach((line) => {
      const span = document.createElement("span");
      span.textContent = line;
      item.append(span);
    });
    container.append(item);
  });
}

function updateScenarioHint() {
  const text = $("mail").value;
  const hint = $("scenarioHint");
  hint.className = "scenario-hint";
  if (text.includes("give B") || text.includes("Finance") || text.includes("already approved")) {
    hint.textContent = "Attack example mail (a keyword hint on screen, not a defense): it claims the request was already approved and tells the assistant to give B admin access to Finance. The server policy decides what is blocked.";
  } else if (text.trim()) {
    hint.classList.add("normal");
    hint.textContent = "Normal mail: within the allowed scope (M / A / Alpha / member), the assistant adds the meeting to the calendar and prepares the welcome mail and access request for approval.";
  } else {
    hint.classList.add("hidden");
  }
}

function selectMail() {
  const selected = mailbox.find((mail) => mail.id === $("savedMail").value);
  $("mail").value = selected?.body || "";
  updateScenarioHint();
}

function startCountdown(pendingRows) {
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
  if (!pendingRows.length) return;

  const update = () => {
    const now = Date.now();
    let anyLeft = false;
    document.querySelectorAll("[data-expires]").forEach((el) => {
      const expiresMs = Number(el.dataset.expires);
      const sec = Math.max(0, Math.ceil((expiresMs - now) / 1000));
      el.textContent = sec > 0 ? `Expires in ${sec}s` : "Expired";
      if (sec > 0) anyLeft = true;
    });
    if (!anyLeft && countdownTimer) {
      clearInterval(countdownTimer);
      countdownTimer = null;
    }
  };
  update();
  countdownTimer = setInterval(update, 1000);
}

async function refresh() {
  const state = await request("/state");
  $("state").textContent = JSON.stringify(state, null, 2);

  const previous = $("savedMail").value;
  mailbox = state.mails.filter((mail) => mail.owner === "M");
  $("savedMail").replaceChildren();
  mailbox.forEach((mail) => {
    const option = document.createElement("option");
    option.value = mail.id;
    option.textContent = `${mail.id} — ${mail.body.slice(0, 50)}`;
    $("savedMail").append(option);
  });
  if (mailbox.some((mail) => mail.id === previous)) {
    $("savedMail").value = previous;
  }

  renderDbItems("grants", "grantsCount", state.grants, "No access granted", (row) => ({
    heading: `${row.user_id} → ${row.project}`,
    lines: [`Role: ${row.role}`],
  }));

  renderDbItems("events", "eventsCount", state.events, "No events", (row) => ({
    heading: row.title,
    lines: [`Owner: ${row.owner}`, `Time: ${row.time}`],
  }));

  renderDbItems("outbox", "outboxCount", state.outbox, "No mail sent", (row) => ({
    heading: row.subject,
    lines: [`Recipient: ${row.recipient}`, row.body],
  }));

  const approvalsEl = $("approvals");
  const pending = state.approvals.filter((row) => !row.used && row.expires * 1000 > Date.now());
  if (!pending.length) {
    renderEmpty(approvalsEl, "No requests are waiting for approval.");
    startCountdown([]);
    return;
  }

  approvalsEl.replaceChildren();
  pending.forEach((row) => {
    const action = JSON.parse(row.action);
    const card = document.createElement("div");
    card.className = "card pending";

    const top = document.createElement("div");
    top.className = "card-top";

    const title = document.createElement("span");
    title.className = "card-title";
    title.textContent = LABELS[action.tool] || action.tool;

    const timer = document.createElement("span");
    timer.className = "timer-pill";
    timer.dataset.expires = String(row.expires * 1000);

    top.append(title, timer);
    card.append(top, buildKVList(action.args));

    const btnRow = document.createElement("div");
    btnRow.className = "card-actions";

    const approveBtn = document.createElement("button");
    approveBtn.type = "button";
    approveBtn.className = "btn-approve";
    approveBtn.textContent = "Approve and run";
    approveBtn.disabled = busy;
    approveBtn.onclick = () => perform(async () => {
      const result = await request("/approve", { id: row.id, accept: true });
      $("message").textContent = `Approval result: ${STATUSES[result.status] || result.status}${result.reason ? ` (${result.reason})` : ""}`;
    });

    const rejectBtn = document.createElement("button");
    rejectBtn.type = "button";
    rejectBtn.className = "btn-reject";
    rejectBtn.textContent = "Reject";
    rejectBtn.disabled = busy;
    rejectBtn.onclick = () => perform(async () => {
      const result = await request("/approve", { id: row.id, accept: false });
      $("message").textContent = `Rejection result: ${STATUSES[result.status] || result.status}`;
    });

    btnRow.append(approveBtn, rejectBtn);
    card.append(btnRow);
    approvalsEl.append(card);
  });

  startCountdown(pending);
}

async function perform(operation) {
  if (busy) return;
  busy = true;
  document.querySelectorAll("button").forEach((button) => { button.disabled = true; });
  try {
    await operation();
  } catch (error) {
    $("message").textContent = error.message;
  } finally {
    busy = false;
    try {
      await refresh();
    } catch (error) {
      $("message").textContent = error.message;
    }
    document.querySelectorAll("button").forEach((button) => { button.disabled = false; });
  }
}

$("savedMail").onchange = selectMail;
$("mail").oninput = updateScenarioHint;

$("normal").onclick = () => {
  $("mail").value = examples.normal || "";
  updateScenarioHint();
};

$("attack").onclick = () => {
  $("mail").value = examples.attack || "";
  updateScenarioHint();
};

const GOALS = { exfil: "Send to an external address", task_overwrite: "Overwrite the saved task", grant: "Forbidden access grant", read: "Read another user's mail" };

function renderBaselineButtons() {
  const container = $("baselineButtons");
  container.replaceChildren();
  (examples.baseline || []).forEach((example) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn-attack";
    button.textContent = `${GOALS[example.goal] || example.goal} (${example.split})`;
    button.title = example.id;
    button.onclick = () => {
      $("mail").value = example.mail;
      const hint = $("scenarioHint");
      hint.className = "scenario-hint";
      hint.textContent = `Evaluation case ${example.id}: this attack succeeded with Defense OFF. Run the same mail with Defense OFF and ON to compare. (Results can vary with the model's response.)`;
    };
    container.append(button);
  });
}

function updateDefenseWarning() {
  $("defenseWarning").classList.toggle("hidden", $("defense").value !== "off");
}

$("defense").onchange = updateDefenseWarning;

$("run").onclick = () => perform(async () => {
  $("message").textContent = "Reading the mail and checking each requested action…";
  $("actions").replaceChildren();
  const defense = $("defense").value !== "off";
  const result = await request("/plan", {
    mail: $("mail").value,
    mail_id: $("savedMail").value,
    mode: $("mode").value,
    defense,
  });
  const label = result.defense === false ? "Defense OFF (baseline)" : "Defense ON";
  $("message").classList.toggle("defense-off", result.defense === false);
  $("message").textContent = `[${label}] ${result.mode}: ${result.text || ""}`;
  result.actions.forEach((action, index) => {
    $("actions").append(renderActionCard(action, result.results[index]));
  });
});

$("reload").onclick = () => perform(async () => {
  await request("/import", {});
  await refresh();
  selectMail();
  $("message").textContent = "Reloaded the initial JSON data.";
});

$("reset").onclick = () => {
  if (!confirm("Clear the run results, approvals and logs and go back to the initial data?")) return;
  perform(async () => {
    await request("/reset", {});
    await refresh();
    selectMail();
    $("actions").replaceChildren();
    $("message").classList.remove("defense-off");
    $("message").textContent = "Reset to the initial state.";
  });
};

(async () => {
  examples = await request("/examples");
  renderBaselineButtons();
  updateDefenseWarning();
  await refresh();
  selectMail();
})().catch((error) => {
  $("message").textContent = error.message;
});
