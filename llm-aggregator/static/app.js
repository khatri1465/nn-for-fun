const SESSION_KEY = "llm_hub_session_id";

const state = {
  sessionId: null,
  tokenBudget: 0,
  tokensUsed: 0,
  selectedModel: null,
  models: [],
  messages: [], // {role, content}
  loading: false,
};

// DOM refs
const $ = (id) => document.getElementById(id);
const tokenCount = $("tokenCount");
const tokenBar = $("tokenBar");
const tokenSub = $("tokenSub");
const modelList = $("modelList");
const systemPrompt = $("systemPrompt");
const messages = $("messages");
const userInput = $("userInput");
const sendBtn = $("sendBtn");
const newSessionBtn = $("newSessionBtn");
const sessionIdDisplay = $("sessionIdDisplay");
const chatHeaderModel = $("chatHeaderModel");
const inputFooter = $("inputFooter");

// ── API helpers ──

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

// ── Session management ──

async function initSession() {
  let id = localStorage.getItem(SESSION_KEY);

  if (id) {
    try {
      const info = await api(`/api/sessions/${id}`);
      state.sessionId = info.session_id;
      state.tokenBudget = info.token_budget;
      state.tokensUsed = info.tokens_used;
    } catch {
      id = null;
    }
  }

  if (!id) {
    await createNewSession();
  }

  sessionIdDisplay.textContent = `ID: ${state.sessionId.slice(0, 8)}…`;
  updateTokenDisplay();
}

async function createNewSession() {
  const data = await api("/api/sessions", { method: "POST" });
  state.sessionId = data.session_id;
  state.tokenBudget = data.token_budget;
  state.tokensUsed = 0;
  localStorage.setItem(SESSION_KEY, state.sessionId);
}

// ── Token display ──

function updateTokenDisplay() {
  const remaining = state.tokenBudget - state.tokensUsed;
  const pct = Math.max(0, (remaining / state.tokenBudget) * 100);

  tokenCount.textContent = remaining.toLocaleString();
  tokenBar.style.width = `${pct}%`;

  const warn = pct < 20;
  const danger = pct < 5;

  tokenCount.className = "token-count" + (danger ? " danger" : warn ? " warn" : "");
  tokenBar.className = "token-bar" + (danger ? " danger" : warn ? " warn" : "");
  tokenSub.textContent = `${state.tokensUsed.toLocaleString()} used of ${state.tokenBudget.toLocaleString()}`;

  if (danger) {
    tokenSub.textContent += " — critically low!";
  } else if (warn) {
    tokenSub.textContent += " — running low";
  }
}

// ── Model list ──

async function loadModels() {
  state.models = await api("/api/models");
  renderModelList();
}

function renderModelList() {
  modelList.innerHTML = "";

  const byProvider = {};
  for (const m of state.models) {
    if (!byProvider[m.provider]) byProvider[m.provider] = [];
    byProvider[m.provider].push(m);
  }

  for (const [provider, models] of Object.entries(byProvider)) {
    for (const m of models) {
      const el = document.createElement("div");
      el.className = `model-item provider-${provider}${m.available ? "" : " disabled"}`;
      if (state.selectedModel === m.id) el.classList.add("active");

      el.innerHTML = `
        <div class="model-dot"></div>
        <div class="model-info">
          <div class="model-name">${m.label}</div>
          <div class="model-desc">${m.description}</div>
          ${!m.available ? `<div class="model-unavail">API key not set</div>` : ""}
        </div>
      `;

      if (m.available) {
        el.addEventListener("click", () => selectModel(m.id));
      }

      modelList.appendChild(el);
    }
  }
}

function selectModel(modelId) {
  state.selectedModel = modelId;
  renderModelList();

  const m = state.models.find((x) => x.id === modelId);
  const badge = `<span class="provider-badge badge-${m.provider}">${m.provider}</span>`;
  chatHeaderModel.innerHTML = `${m.label} ${badge}`;
  updateSendState();
}

// ── Chat ──

function updateSendState() {
  const canSend =
    !state.loading &&
    state.selectedModel !== null &&
    userInput.value.trim().length > 0 &&
    state.tokenBudget - state.tokensUsed > 0;
  sendBtn.disabled = !canSend;
}

function renderWelcome() {
  messages.innerHTML = `
    <div class="welcome">
      <div class="welcome-icon">⬡</div>
      <h2>LLM Aggregator</h2>
      <p>Chat with GPT, Claude, or Grok — all in one place.<br/>Select a model from the sidebar to begin.</p>
    </div>`;
}

function appendMessage(role, content, meta = {}) {
  // Remove welcome screen on first message
  const welcome = messages.querySelector(".welcome");
  if (welcome) welcome.remove();

  const el = document.createElement("div");
  el.className = `msg ${role}`;

  let metaHtml = "";
  if (role === "assistant" && meta.model) {
    const m = state.models.find((x) => x.id === meta.model);
    const label = m ? m.label : meta.model;
    const provider = m ? m.provider : "openai";
    metaHtml = `
      <div class="msg-meta">
        <span class="provider-badge badge-${provider}">${provider}</span>
        <span>${label}</span>
        ${meta.tokens ? `<span class="msg-tokens">· ${meta.tokens.toLocaleString()} tokens</span>` : ""}
      </div>`;
  }

  el.innerHTML = `
    ${metaHtml}
    <div class="msg-bubble">${escapeHtml(content)}</div>
  `;

  messages.appendChild(el);
  messages.scrollTop = messages.scrollHeight;
  return el;
}

function showTyping() {
  const el = document.createElement("div");
  el.className = "msg assistant";
  el.id = "typingIndicator";
  el.innerHTML = `
    <div class="typing-indicator">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>`;
  messages.appendChild(el);
  messages.scrollTop = messages.scrollHeight;
}

function removeTyping() {
  const el = $("typingIndicator");
  if (el) el.remove();
}

async function sendMessage() {
  const text = userInput.value.trim();
  if (!text || !state.selectedModel || state.loading) return;

  state.messages.push({ role: "user", content: text });
  appendMessage("user", text);
  userInput.value = "";
  autoResize();

  state.loading = true;
  updateSendState();
  showTyping();
  inputFooter.textContent = "";

  try {
    const res = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        session_id: state.sessionId,
        model: state.selectedModel,
        messages: state.messages,
        system_prompt: systemPrompt.value.trim() || null,
      }),
    });

    removeTyping();
    state.messages.push({ role: "assistant", content: res.reply });
    appendMessage("assistant", res.reply, {
      model: res.model,
      tokens: res.total_tokens,
    });

    state.tokensUsed = state.tokenBudget - res.tokens_remaining;
    updateTokenDisplay();
    inputFooter.textContent = `Last call: ${res.total_tokens.toLocaleString()} tokens (in: ${res.input_tokens.toLocaleString()}, out: ${res.output_tokens.toLocaleString()})`;
  } catch (err) {
    removeTyping();
    showError(err.message);
  } finally {
    state.loading = false;
    updateSendState();
  }
}

// ── Utilities ──

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function showError(msg) {
  const el = document.createElement("div");
  el.className = "error-toast";
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 5000);
}

function autoResize() {
  userInput.style.height = "auto";
  userInput.style.height = Math.min(userInput.scrollHeight, 200) + "px";
}

// ── Event listeners ──

userInput.addEventListener("input", () => {
  autoResize();
  updateSendState();
});

userInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener("click", sendMessage);

newSessionBtn.addEventListener("click", async () => {
  if (!confirm("Start a new session? This will reset your conversation.")) return;
  await createNewSession();
  state.messages = [];
  state.selectedModel = null;
  chatHeaderModel.textContent = "Select a model to start";
  renderWelcome();
  sessionIdDisplay.textContent = `ID: ${state.sessionId.slice(0, 8)}…`;
  updateTokenDisplay();
  renderModelList();
  inputFooter.textContent = "";
});

// ── Boot ──

(async () => {
  try {
    await initSession();
    await loadModels();
  } catch (err) {
    showError("Failed to connect to server: " + err.message);
  }
})();
