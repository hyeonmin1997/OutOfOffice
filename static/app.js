const $ = (id) => document.getElementById(id);

const LABELS = {
  read_mail: "메일 읽기",
  lookup_user: "직원 정보 확인",
  create_event: "개인 일정 등록",
  send_email: "안내 메일 발송",
  grant_access: "프로젝트 권한 부여",
};

const STATUSES = {
  executed: "실행 완료",
  pending: "승인 대기",
  blocked: "정책 차단",
  rejected: "승인 거절",
};

const ARG_LABELS = {
  mail_id: "메일 ID",
  user_id: "대상 사용자",
  owner: "일정 소유자",
  title: "일정 제목",
  time: "시간",
  recipient: "수신자",
  subject: "제목",
  body: "본문",
  project: "프로젝트",
  role: "부여 역할",
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
  if (!response.ok || result.error) throw new Error(result.error || "요청에 실패했습니다.");
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
    note.textContent = "정책 검사를 통과했으며, 아래 '운영자 승인 대기함'에서 승인 후 실행됩니다.";
    card.append(note);
  } else {
    card.append(buildKVList(action.args));
  }

  if (outcome.reason) {
    const reason = document.createElement("div");
    reason.className = "reason-box";
    reason.textContent = status === "blocked" ? `차단 사유: ${outcome.reason}` : outcome.reason;
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
    hint.textContent = "공격 예시 메일(화면 안내용 키워드 표시이며 방어 기능이 아닙니다): '이미 승인됨' 문구와 B의 Finance 관리자 권한 부여 지시가 들어 있습니다. 차단은 서버 정책이 결정합니다.";
  } else if (text.trim()) {
    hint.classList.add("normal");
    hint.textContent = "일반 메일: 허용된 범위(M / A / Alpha / member) 안에서 미팅 일정 등록과 안내·권한 승인을 준비합니다.";
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
      el.textContent = sec > 0 ? `유효 시간 ${sec}초` : "만료됨";
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

  renderDbItems("grants", "grantsCount", state.grants, "부여된 권한 없음", (row) => ({
    heading: `${row.user_id} → ${row.project}`,
    lines: [`역할: ${row.role}`],
  }));

  renderDbItems("events", "eventsCount", state.events, "등록된 일정 없음", (row) => ({
    heading: row.title,
    lines: [`소유자: ${row.owner}`, `시간: ${row.time}`],
  }));

  renderDbItems("outbox", "outboxCount", state.outbox, "발송된 메일 없음", (row) => ({
    heading: row.subject,
    lines: [`수신자: ${row.recipient}`, row.body],
  }));

  const approvalsEl = $("approvals");
  const pending = state.approvals.filter((row) => !row.used && row.expires * 1000 > Date.now());
  if (!pending.length) {
    renderEmpty(approvalsEl, "현재 승인 대기 중인 요청이 없습니다.");
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
    approveBtn.textContent = "승인 및 실행";
    approveBtn.disabled = busy;
    approveBtn.onclick = () => perform(async () => {
      const result = await request("/approve", { id: row.id, accept: true });
      $("message").textContent = `승인 처리 결과: ${STATUSES[result.status] || result.status}${result.reason ? ` (${result.reason})` : ""}`;
    });

    const rejectBtn = document.createElement("button");
    rejectBtn.type = "button";
    rejectBtn.className = "btn-reject";
    rejectBtn.textContent = "거절";
    rejectBtn.disabled = busy;
    rejectBtn.onclick = () => perform(async () => {
      const result = await request("/approve", { id: row.id, accept: false });
      $("message").textContent = `거절 처리 결과: ${STATUSES[result.status] || result.status}`;
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

const GOALS = { exfil: "외부 주소로 발송", task_overwrite: "저장된 업무 바꿔치기", grant: "금지 권한 부여", read: "타인 메일 읽기" };

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
      hint.textContent = `평가 사례 ${example.id}: 방어 OFF에서 실제로 성공한 공격입니다. 방어 ON/OFF를 바꿔 같은 메일로 실행해 비교하세요. (결과는 모델 응답에 따라 달라질 수 있습니다.)`;
    };
    container.append(button);
  });
}

function updateDefenseWarning() {
  $("defenseWarning").classList.toggle("hidden", $("defense").value !== "off");
}

$("defense").onchange = updateDefenseWarning;

$("run").onclick = () => perform(async () => {
  $("message").textContent = "메일을 읽고 요청 가능한 행동을 검사하고 있습니다…";
  $("actions").replaceChildren();
  const defense = $("defense").value !== "off";
  const result = await request("/plan", {
    mail: $("mail").value,
    mail_id: $("savedMail").value,
    mode: $("mode").value,
    defense,
  });
  const label = result.defense === false ? "방어 OFF (기준선)" : "방어 ON";
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
  $("message").textContent = "JSON 초기 데이터를 다시 불러왔습니다.";
});

$("reset").onclick = () => {
  if (!confirm("실행 결과와 승인·로그를 지우고 초기 데이터로 돌아갈까요?")) return;
  perform(async () => {
    await request("/reset", {});
    await refresh();
    selectMail();
    $("actions").replaceChildren();
    $("message").classList.remove("defense-off");
    $("message").textContent = "초기 상태로 되돌렸습니다.";
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
