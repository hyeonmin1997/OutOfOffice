const $ = (id) => document.getElementById(id);
const labels = {read_mail: "메일 읽기", lookup_user: "직원 정보 확인", create_event: "개인 일정 등록", send_email: "안내 메일 발송", grant_access: "프로젝트 권한 부여"};
const statuses = {executed: "실행 완료", pending: "승인 대기 · 아직 실행 안 됨", blocked: "차단", rejected: "승인 거절"};
let mailbox = [];
let examples = {};
let busy = false;

async function request(path, data) {
  const response = await fetch(path, data === undefined ? {} : {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)
  });
  const result = await response.json();
  if (!response.ok || result.error) throw new Error(result.error || "요청 실패");
  return result;
}
function card(parent, title, detail, status = "") {
  const item = document.createElement("div");
  item.className = "card " + status;
  const heading = document.createElement("strong");
  heading.textContent = title;
  const body = document.createElement("pre");
  body.textContent = typeof detail === "string" ? detail : JSON.stringify(detail, null, 2);
  item.append(heading, body);
  parent.append(item);
  return item;
}
function renderRows(id, rows, describe) {
  $(id).replaceChildren();
  if (!rows.length) $(id).textContent = "아직 없습니다.";
  rows.forEach((row) => card($(id), describe(row), row));
}
function selectMail() {
  const selected = mailbox.find((mail) => mail.id === $("savedMail").value);
  $("mail").value = selected?.body || "";
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
    option.textContent = `${mail.id} — ${mail.body.slice(0, 55)}`;
    $("savedMail").append(option);
  });
  if (mailbox.some((mail) => mail.id === previous)) $("savedMail").value = previous;
  renderRows("grants", state.grants, (row) => `${row.user_id} → ${row.project} / ${row.role}`);
  renderRows("events", state.events, (row) => `${row.owner}: ${row.title}`);
  renderRows("outbox", state.outbox, (row) => `수신자: ${row.recipient}`);
  $("approvals").replaceChildren();
  const pending = state.approvals.filter((row) => !row.used && row.expires * 1000 > Date.now());
  if (!pending.length) $("approvals").textContent = "유효한 승인 대기 요청이 없습니다.";
  pending.forEach((row) => {
    const action = JSON.parse(row.action);
    const item = card($("approvals"), labels[action.tool], action.args, "pending");
    [true, false].forEach((accept) => {
      const button = document.createElement("button");
      button.textContent = accept ? "이 행동 승인" : "거절";
      button.disabled = busy;
      button.onclick = () => perform(async () => {
        const result = await request("/approve", {id: row.id, accept});
        $("message").textContent = statuses[result.status] + (result.reason ? `: ${result.reason}` : "");
      });
      item.append(button);
    });
  });
}
async function perform(operation) {
  if (busy) return;
  busy = true;
  document.querySelectorAll("button").forEach((button) => button.disabled = true);
  try { await operation(); }
  catch (error) { $("message").textContent = error.message; }
  finally {
    busy = false;
    try { await refresh(); } catch (error) { $("message").textContent = error.message; }
    document.querySelectorAll("button").forEach((button) => button.disabled = false);
  }
}
$("savedMail").onchange = selectMail;
$("normal").onclick = () => $("mail").value = examples.normal;
$("attack").onclick = () => $("mail").value = examples.attack;
$("run").onclick = () => perform(async () => {
  $("message").textContent = "메일을 참고해 행동을 준비하고 검사하고 있습니다…";
  $("actions").replaceChildren();
  const result = await request("/plan", {mail: $("mail").value, mail_id: $("savedMail").value, mode: $("mode").value});
  $("message").textContent = `${result.mode}: ${result.text || ""}`;
  result.actions.forEach((action, index) => {
    const outcome = result.results[index];
    card($("actions"), `${labels[action.tool] || action.tool} — ${statuses[outcome.status] || outcome.status}`,
      {request: action.args, reason: outcome.reason || ""}, outcome.status);
  });
});
$("reload").onclick = () => perform(async () => {
  await request("/import", {}); await refresh(); selectMail();
  $("message").textContent = "JSON 데이터 반영 완료";
});
$("reset").onclick = () => {
  if (!confirm("실행 결과와 승인·로그를 지우고 초기 데이터로 돌아갈까요?")) return;
  perform(async () => {
    await request("/reset", {}); await refresh(); selectMail();
    $("actions").replaceChildren(); $("message").textContent = "초기화 완료";
  });
};
(async () => { examples = await request("/examples"); await refresh(); selectMail(); })()
  .catch((error) => $("message").textContent = error.message);
