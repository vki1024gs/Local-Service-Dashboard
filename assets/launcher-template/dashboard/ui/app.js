let token = "";
let baseTitle = "Local Service Launcher";
let previous = new Map();
let eventItems = [];
let shuttingDown = false;
let serviceMarkupSignature = "";
const servicesEl = document.querySelector("#services");
const summaryEl = document.querySelector("#summary");
const connectionEl = document.querySelector("#connection");
const logDialog = document.querySelector("#logDialog");
const quitDialog = document.querySelector("#quitDialog");

async function api(path, options={}) {
  options.headers = {...options.headers, "X-Launcher-Token": token};
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function esc(value="") { const node=document.createElement("span"); node.textContent=String(value); return node.innerHTML; }
function pad(value) { return String(value).padStart(2, "0"); }
function dateParts(value=Date.now()/1000) {
  const date = typeof value === "number" ? new Date(value*1000) : new Date(value);
  if (Number.isNaN(date.getTime())) return {date:"—", time:"—"};
  return {
    date: `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}`,
    time: `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  };
}
function dateTime(value) { const stamp=dateParts(value); return `${stamp.date} ${stamp.time}`; }
function delay(ms) { return new Promise(resolve=>setTimeout(resolve, ms)); }

const labels = {
  ready: "健康运行", starting: "启动中", stopping: "停止中", stopped: "已停止",
  unhealthy: "健康检查失败", "stopped-unexpectedly": "意外停止", "startup-timeout": "启动超时"
};
const problemLabels = {"health-check-failed":"健康检查失败", "stopped-unexpectedly":"意外停止", "startup-timeout":"启动超时"};
function hasIssue(service) { return Boolean(service.problem || service.port_conflicts?.length); }
function card(service) {
  const state = service.state || (service.ready ? "ready" : service.running ? "starting" : "stopped");
  const ports = service.ports?.length ? service.ports : (service.port == null ? [] : [{name:"端口", port:service.port}]);
  const portTags = ports.map(port => {
    const detail = port.conflict ? `，与 ${port.conflicts_with.join("、")} 冲突` : "";
    return `<span class="kind ${port.conflict?"port-conflict":""}" title="${esc(`${port.name} ${port.port}${detail}`)}">${esc(port.name)} ${esc(port.port)}</span>`;
  }).join("");
  const alerts = [
    service.problem ? (problemLabels[service.problem] || service.problem) : "",
    ...(service.port_conflicts || []).map(conflict => `端口冲突：${conflict.port} 同时由 ${conflict.with.join("、")} 使用`)
  ].filter(Boolean).map(message => `<div class="service-alert">${esc(message)}</div>`).join("");
  const checks = service.health && service.health.checks ? `<div class="health-mini">${Object.values(service.health.checks).map(check => `<span class="${esc(check.status || "unknown")}">${esc(check.name)}: ${esc(check.status)}</span>`).join("")}</div>` : "";
  const openAction = service.url ? (service.ready
    ? `<a class="link primary-action" href="${esc(service.url)}" target="_blank" rel="noreferrer">打开</a>`
    : `<button class="primary-action" disabled>打开</button>`) : "";
  const startAction = !service.running ? `<button class="${service.url ? "" : "primary"}" data-action="start">启动</button>` : "";
  const menuActions = [
    `<button data-action="logs">查看日志</button>`,
    service.running ? `<button data-action="restart">重启</button>` : "",
    service.running ? `<button class="danger-action" data-action="stop">停止</button>` : "",
    service.can_update && !service.running ? `<button data-action="update">更新</button>` : ""
  ].join("");
  return `<article class="card state-${esc(state)} ${hasIssue(service)?"has-problem":""}" data-id="${esc(service.id)}">
    <div class="top"><div class="card-title"><div class="port-list">${portTags}</div><h3>${esc(service.name)}</h3></div><span class="status ${esc(state)}"><i class="dot"></i>${esc(labels[state] || state)}</span></div>
    <p class="desc">${esc(service.description || "")}</p>${alerts}${checks}
    <div class="meta"><span><small>最近变更</small><strong>${service.last_change_at ? dateTime(service.last_change_at) : "—"}</strong></span></div>
    <div class="actions">${openAction}${startAction}<details class="action-menu"><summary aria-label="更多操作">更多</summary><div class="action-menu-panel">${menuActions}</div></details></div>
  </article>`;
}

function cardRenderSignature(services) {
  return JSON.stringify(services.map(service => ({
    id: service.id, name: service.name, description: service.description, ports: service.ports,
    url: service.url, can_update: service.can_update, running: service.running, ready: service.ready,
    state: service.state, problem: service.problem, port_conflicts: service.port_conflicts, last_change_at: service.last_change_at,
    checks: Object.values(service.health?.checks || {}).map(check => ({name: check.name, status: check.status}))
  })));
}

function recordChanges(services, observedAt) {
  if (!previous.size) return;
  for (const service of services) {
    const old = previous.get(service.id); if (!old) continue;
    if (old.state !== service.state || old.problem !== service.problem) {
      const recovered = old.problem && !service.problem;
      eventItems.unshift({time: observedAt, name: service.name, state: service.state,
                          problem: service.problem, recovered});
    }
  }
  eventItems = eventItems.slice(0, 60);
}

function renderEvents() {
  const el = document.querySelector("#events");
  const panel = document.querySelector("#eventsPanel");
  const clearButton = document.querySelector("#clearEvents");
  panel.classList.toggle("is-empty", !eventItems.length);
  clearButton.disabled = !eventItems.length;
  if (!eventItems.length) { el.innerHTML = `<li class="empty"><i aria-hidden="true"></i><strong>暂无状态变化</strong><span>服务启动、停止或恢复后会显示在这里</span></li>`; return; }
  el.innerHTML = eventItems.map(item=>{const stamp=dateParts(item.time); return `<li class="${item.problem?"bad":item.recovered?"good":""}"><time><span>${stamp.date}</span><strong>${stamp.time}</strong></time><div><strong>${esc(item.name)}</strong><span>${item.recovered?"服务已恢复":esc(labels[item.state] || item.state)}</span></div></li>`;}).join("");
}

function applySnapshot(snapshot) {
  const services = snapshot.services || [];
  recordChanges(services, snapshot.observed_at);
  previous = new Map(services.map(item=>[item.id, item]));
  const nextMarkupSignature = cardRenderSignature(services);
  if (nextMarkupSignature !== serviceMarkupSignature) {
    servicesEl.innerHTML = services.map(card).join("");
    serviceMarkupSignature = nextMarkupSignature;
  }
  const healthy = services.filter(item=>item.ready && !hasIssue(item)).length;
  const problems = services.filter(hasIssue).length;
  const stopped = services.filter(item=>!item.running && !hasIssue(item)).length;
  document.querySelector("#healthyCount").textContent = healthy;
  document.querySelector("#problemCount").textContent = problems;
  document.querySelector("#stoppedCount").textContent = stopped;
  const sampleStamp = dateParts(snapshot.observed_at);
  document.querySelector("#lastSample").innerHTML = `<span class="sample-date">${sampleStamp.date}</span><span class="sample-time">${sampleStamp.time}</span>`;
  summaryEl.textContent = `${healthy} 个健康 · ${problems} 个异常 · 共 ${services.length} 个`;
  const banner = document.querySelector("#alertBanner");
  banner.hidden = problems === 0;
  document.querySelector("#alertText").textContent = problems ? services.filter(hasIssue).map(item=>item.name).join("、") : "";
  document.title = problems ? `⚠ ${problems} · ${baseTitle}` : baseTitle;
  renderEvents();
}

function setConnection(online, text) {
  connectionEl.className = `connection ${online?"online":"offline"}`;
  connectionEl.querySelector("span").textContent = text;
}

async function monitor() {
  while (!shuttingDown) {
    try {
      setConnection(false, "正在连接监控流");
      const response = await fetch("/api/events", {headers:{"X-Launcher-Token":token}, cache:"no-store"});
      if (!response.ok || !response.body) throw new Error(`monitor HTTP ${response.status}`);
      setConnection(true, "实时监控已连接");
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = "";
      while (true) {
        const {value, done} = await reader.read(); if (done) throw new Error("monitor stream closed");
        buffer += decoder.decode(value, {stream:true});
        const lines = buffer.split("\n"); buffer = lines.pop();
        for (const line of lines) if (line.trim()) applySnapshot(JSON.parse(line));
      }
    } catch (error) {
      if (shuttingDown) return;
      setConnection(false, "监控中断，正在重连");
      await delay(1000);
    }
  }
}

servicesEl.addEventListener("click", async event => {
  const button = event.target.closest("button[data-action]"); if (!button) return;
  button.closest("details")?.removeAttribute("open");
  const id = button.closest(".card").dataset.id; const action = button.dataset.action;
  if (action === "logs") {
    const data = await api(`/api/logs/${id}`); document.querySelector("#logTitle").textContent=`${id} 日志`; document.querySelector("#logText").textContent=data.log || "暂无日志"; logDialog.showModal(); return;
  }
  button.disabled = true;
  try { await api(`/api/${action}/${id}`, {method:"POST"}); }
  catch (error) { alert(error.message); button.disabled=false; }
});

document.addEventListener("click", event => {
  document.querySelectorAll("details.action-menu[open]").forEach(menu => {
    if (!menu.contains(event.target)) menu.removeAttribute("open");
  });
});

document.querySelector("#clearEvents").addEventListener("click", ()=>{eventItems=[]; renderEvents();});
document.querySelector("#quitDashboard").addEventListener("click", ()=>quitDialog.showModal());
document.querySelector("#confirmQuit").addEventListener("click", async event => {
  event.preventDefault();
  const button = event.currentTarget;
  button.disabled = true;
  button.textContent = "正在退出…";
  try {
    await api("/api/shutdown", {method:"POST"});
    shuttingDown = true;
    quitDialog.close();
    document.querySelector("main").hidden = true;
    document.querySelector("#shutdownScreen").hidden = false;
  } catch (error) {
    button.disabled = false;
    button.textContent = "确认退出";
    alert(`退出失败：${error.message}`);
  }
});
document.querySelector("#closePage").addEventListener("click", ()=>window.close());

(async()=>{const bootstrap=await fetch("/api/bootstrap", {cache:"no-store"}).then(r=>r.json()); token=bootstrap.token; baseTitle=bootstrap.title; document.querySelector("#title").textContent=baseTitle; document.title=baseTitle; monitor();})();
