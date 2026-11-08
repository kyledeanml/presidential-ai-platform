// Frontend Application Logic for 48th Presidential AI Persona & Civic Pulse UI

let currentSessionId = "sess-" + Math.random().toString(36).slice(2, 10);
let allPolicies = [];
let latestBriefingMarkdown = "";

const WELCOME_MESSAGE = (
    "Welcome to our **Digital Town Hall** for the **48th Presidency of the United States**.\n\n" +
    "I am the campaign's official AI Persona—powered by quantized open-weights **GGUF** architecture and strictly grounded in our verified policy platform.\n\n" +
    "- **Say hello** or ask **\"What are your policies?\"** for an overview.\n" +
    "- **Ask about any issue**—grocery prices, childcare, AI & jobs, healthcare, nuclear energy, congressional stock trading, or border security.\n" +
    "- **Ask follow-ups** like *\"What are your redlines?\"* or *\"Tell me more\"*, or share an unaddressed local concern so our **Policy Synthesis Engine** can flag it."
);

document.addEventListener("DOMContentLoaded", () => {
    renderInitialGreeting();
    loadPlatformStatus();
    loadPolicies();
    runSynthesis(true);
});

function switchTab(tabName) {
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.tab === tabName);
    });
    document.querySelectorAll(".tab-panel").forEach(panel => {
        panel.classList.toggle("active", panel.id === `tab-${tabName}`);
    });
    if (tabName === "pulse") {
        runSynthesis(true);
    }
}

function escapeHtml(raw) {
    return String(raw)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function renderMarkdown(text) {
    const escaped = escapeHtml(text);
    const lines = escaped.split("\n");
    let html = "";
    let inUl = false;
    let inOl = false;

    const formatInline = (line) => line
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
        .replace(/\*([^*]+)\*/g, "<em>$1</em>");

    for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line) {
            if (inUl) { html += "</ul>"; inUl = false; }
            if (inOl) { html += "</ol>"; inOl = false; }
            continue;
        }
        if (line.startsWith("- ")) {
            if (inOl) { html += "</ol>"; inOl = false; }
            if (!inUl) { html += "<ul>"; inUl = true; }
            html += `<li>${formatInline(line.slice(2))}</li>`;
        } else if (/^\d+\.\s+/.test(line)) {
            if (inUl) { html += "</ul>"; inUl = false; }
            if (!inOl) { html += "<ol>"; inOl = true; }
            html += `<li>${formatInline(line.replace(/^\d+\.\s+/, ""))}</li>`;
        } else {
            if (inUl) { html += "</ul>"; inUl = false; }
            if (inOl) { html += "</ol>"; inOl = false; }
            html += `<p>${formatInline(line)}</p>`;
        }
    }
    if (inUl) html += "</ul>";
    if (inOl) html += "</ol>";
    return html;
}

function renderInitialGreeting() {
    const stream = document.getElementById("chatStream");
    stream.innerHTML = "";
    appendAssistantMessage({
        response: WELCOME_MESSAGE,
        matched_policy: "PLATFORM-READY",
        is_outlier: false,
        sentiment: "Civic Welcome",
        pii_redacted: {}
    });
}

function appendUserMessage(text) {
    const stream = document.getElementById("chatStream");
    const row = document.createElement("div");
    row.className = "message-row user";
    row.innerHTML = `
        <div class="avatar citizen" title="Citizen">YOU</div>
        <div class="bubble-wrap">
            <div class="bubble"><p>${escapeHtml(text)}</p></div>
        </div>
    `;
    stream.appendChild(row);
    stream.scrollTop = stream.scrollHeight;
}

function showTypingIndicator() {
    const stream = document.getElementById("chatStream");
    const row = document.createElement("div");
    row.className = "message-row assistant";
    row.id = "typingIndicatorRow";
    row.innerHTML = `
        <div class="avatar persona" title="48th Presidential Persona">48</div>
        <div class="bubble-wrap">
            <div class="bubble">
                <div class="typing-dots"><span></span><span></span><span></span></div>
            </div>
        </div>
    `;
    stream.appendChild(row);
    stream.scrollTop = stream.scrollHeight;
}

function removeTypingIndicator() {
    const el = document.getElementById("typingIndicatorRow");
    if (el) el.remove();
}

function appendAssistantMessage(data) {
    const stream = document.getElementById("chatStream");
    const row = document.createElement("div");
    row.className = "message-row assistant" + (data.is_outlier ? " is-outlier" : "");

    let metaTags = "";
    if (data.matched_policy && data.matched_policy !== "PLATFORM-READY") {
        if (data.is_outlier) {
            metaTags += `<span class="tag outlier">⚡ Outlier Logged to Policy Council</span>`;
        } else {
            metaTags += `<span class="tag policy">📌 ${escapeHtml(data.matched_policy)}</span>`;
        }
    }
    if (data.sentiment && data.sentiment !== "Civic Welcome") {
        metaTags += `<span class="tag sentiment">Tone: ${escapeHtml(data.sentiment)}</span>`;
    }
    const piiKeys = Object.keys(data.pii_redacted || {});
    if (piiKeys.length > 0) {
        const count = Object.values(data.pii_redacted).reduce((a, b) => a + b, 0);
        metaTags += `<span class="tag pii">🛡️ ${count} PII Redacted (${escapeHtml(piiKeys.join(", "))})</span>`;
    }

    row.innerHTML = `
        <div class="avatar persona" title="48th Presidential Persona">48</div>
        <div class="bubble-wrap">
            <div class="bubble">${renderMarkdown(data.response)}</div>
            ${metaTags ? `<div class="msg-meta">${metaTags}</div>` : ""}
        </div>
    `;
    stream.appendChild(row);
    stream.scrollTop = stream.scrollHeight;
}

function handleInputKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

function usePrompt(promptText) {
    const input = document.getElementById("chatInput");
    input.value = promptText;
    sendMessage();
}

async function sendMessage() {
    const input = document.getElementById("chatInput");
    const sendBtn = document.getElementById("sendBtn");
    const state = document.getElementById("stateSelect").value;
    const text = input.value.trim();
    if (!text) return;

    appendUserMessage(text);
    input.value = "";
    sendBtn.disabled = true;
    showTypingIndicator();

    try {
        const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: text,
                state: state,
                session_id: currentSessionId
            })
        });
        const data = await res.json();
        removeTypingIndicator();
        appendAssistantMessage(data);
        updateInspector(data);
        loadPlatformStatus();
    } catch (err) {
        removeTypingIndicator();
        appendAssistantMessage({
            response: "Connection error reaching the Presidential AI API server. Please ensure `python3 api/server.py` is running.",
            is_outlier: false
        });
    } finally {
        sendBtn.disabled = false;
        input.focus();
    }
}

async function resetConversation() {
    try {
        await fetch("/api/session/reset", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: currentSessionId })
        });
    } catch (_) {}
    currentSessionId = "sess-" + Math.random().toString(36).slice(2, 10);
    renderInitialGreeting();
    document.getElementById("turnCounterBadge").innerText = "Turn 0";
    document.getElementById("inspPolicyTitle").innerText = "Awaiting Citizen Inquiry";
    document.getElementById("inspPolicyCategory").innerText = "New session started — memory cleared";
    document.getElementById("inspConfidenceBar").style.width = "0%";
    document.getElementById("inspConfidenceLabel").innerText = "BM25 Relevance Score: —";
    document.getElementById("inspOutlierStatus").innerText = "Standby";
    document.getElementById("inspPillarsList").style.display = "none";
    document.getElementById("inspPillarsEmpty").style.display = "block";
}

function updateInspector(data) {
    document.getElementById("turnCounterBadge").innerText = `Turn ${data.turn_count || 1}`;

    if (data.engine_mode) {
        document.getElementById("engineStatusText").innerText = data.engine_mode;
    }

    // Policy Grounding block
    const score = Number(data.rag_score || 0);
    const pct = Math.min(100, Math.round((score / 10) * 100));
    if (data.policy_details) {
        document.getElementById("inspPolicyTitle").innerText = `[${data.policy_details.id}] ${data.policy_details.title}`;
        document.getElementById("inspPolicyCategory").innerText = data.policy_details.category;
        document.getElementById("inspConfidenceBar").style.width = `${Math.max(pct, 25)}%`;
        document.getElementById("inspConfidenceBar").style.background = "#1d4ed8";
        document.getElementById("inspConfidenceLabel").innerText = `BM25 Grounding Score: ${score.toFixed(2)} (Verified Match)`;

        const listEl = document.getElementById("inspPillarsList");
        listEl.innerHTML = "";
        (data.policy_details.key_pillars || []).slice(0, 3).forEach(p => {
            const li = document.createElement("li");
            li.innerText = p;
            listEl.appendChild(li);
        });
        (data.policy_details.redlines || []).slice(0, 1).forEach(r => {
            const li = document.createElement("li");
            li.innerHTML = `<strong style="color:#b91c1c;">Redline:</strong> ${escapeHtml(r)}`;
            listEl.appendChild(li);
        });
        listEl.style.display = "block";
        document.getElementById("inspPillarsEmpty").style.display = "none";
    } else if (data.is_outlier) {
        document.getElementById("inspPolicyTitle").innerText = "No Published Plank Found";
        document.getElementById("inspPolicyCategory").innerText = "Anti-Hallucination Guardrail Triggered";
        document.getElementById("inspConfidenceBar").style.width = "18%";
        document.getElementById("inspConfidenceBar").style.background = "#d97706";
        document.getElementById("inspConfidenceLabel").innerText = `BM25 Score: ${score.toFixed(2)} (Unaddressed Topic)`;
        document.getElementById("inspPillarsList").style.display = "none";
        document.getElementById("inspPillarsEmpty").style.display = "block";
        document.getElementById("inspPillarsEmpty").innerText = "Zero-Fabrication Guardrail: Persona prevented from inventing unauthorized policy promises.";
    } else {
        document.getElementById("inspPolicyTitle").innerText = "Conversational Civic Turn";
        document.getElementById("inspPolicyCategory").innerText = `Intent: ${data.intent || "dialogue"}`;
        document.getElementById("inspConfidenceBar").style.width = "100%";
        document.getElementById("inspConfidenceBar").style.background = "#059669";
        document.getElementById("inspConfidenceLabel").innerText = "Direct Persona Engagement";
    }

    // Outlier Classifier block
    if (data.is_outlier) {
        document.getElementById("inspOutlierStatus").innerHTML = `<span style="color:#d97706;">⚡ Emergent Outlier Flagged</span>`;
        document.getElementById("inspOutlierDesc").innerText = "Queued for National Policy Advisory Council foundational report.";
    } else if (data.log_to_telemetry) {
        document.getElementById("inspOutlierStatus").innerHTML = `<span style="color:#059669;">✓ Mainstream Platform Issue</span>`;
        document.getElementById("inspOutlierDesc").innerText = "Logged to national consensus distribution.";
    } else {
        document.getElementById("inspOutlierStatus").innerText = "Greeting / Overview Turn";
        document.getElementById("inspOutlierDesc").innerText = "Excluded from policy telemetry to keep analytics clean.";
    }

    // Sentiment & PII block
    document.getElementById("inspSentiment").innerText = `${data.sentiment || "Neutral"} (Valence: ${data.valence ?? 0})`;
    const pii = data.pii_redacted || {};
    const piiKeys = Object.keys(pii);
    if (piiKeys.length > 0) {
        document.getElementById("inspPiiStatus").innerHTML =
            `<strong style="color:#059669;">🛡️ Scrubbed before logging:</strong> ${escapeHtml(JSON.stringify(pii))}`;
    } else {
        document.getElementById("inspPiiStatus").innerText = "🛡️ PII Scrubber active — no personal identifiers detected";
    }
}

async function loadPlatformStatus() {
    try {
        const res = await fetch("/api/status");
        const status = await res.json();
        document.getElementById("engineStatusText").innerText = status.engine_mode;
        document.getElementById("dialogueCounterText").innerText = `${status.total_dialogues} Dialogues Indexed`;
        document.getElementById("plankCountBadge").innerText = status.policy_count;
        document.getElementById("outlierCountBadge").innerText = status.outlier_count;
    } catch (_) {}
}

async function loadPolicies() {
    try {
        const res = await fetch("/api/policies");
        allPolicies = await res.json();
        renderPolicies();
    } catch (_) {}
}

function renderPolicies() {
    const query = (document.getElementById("policySearchInput")?.value || "").toLowerCase().trim();
    const grid = document.getElementById("policiesGrid");
    grid.innerHTML = "";

    const filtered = allPolicies.filter(p => {
        if (!query) return true;
        const blob = `${p.id} ${p.category} ${p.title} ${p.summary} ${(p.key_pillars || []).join(" ")}`.toLowerCase();
        return blob.includes(query);
    });

    filtered.forEach(p => {
        const card = document.createElement("div");
        card.className = "card policy-card";
        const pillarsHtml = (p.key_pillars || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
        const redlineText = (p.redlines && p.redlines[0]) ? p.redlines[0] : "";

        card.innerHTML = `
            <div>
                <div class="policy-card-top">
                    <span class="policy-id">${escapeHtml(p.id)}</span>
                    <span class="policy-cat">${escapeHtml(p.category)}</span>
                </div>
                <h3>${escapeHtml(p.title)}</h3>
                <p class="policy-summary">${escapeHtml(p.summary)}</p>
                <div class="policy-section-label">Key Platform Pillars</div>
                <ul class="pillar-mini-list">${pillarsHtml}</ul>
                ${redlineText ? `<div class="redline-box"><strong>Veto Redline:</strong> ${escapeHtml(redlineText)}</div>` : ""}
            </div>
            <div>
                <button class="btn-secondary" style="width:100%;" onclick="askAboutPolicy('${escapeHtml(p.title)}')">
                    💬 Ask Persona About ${escapeHtml(p.id)}
                </button>
            </div>
        `;
        grid.appendChild(card);
    });
}

function askAboutPolicy(title) {
    switchTab("townhall");
    usePrompt(`Walk me through your ${title} plan and how it helps everyday Americans.`);
}

async function runSynthesis(silent = false) {
    const btn = document.getElementById("synthesizeBtn");
    const viewer = document.getElementById("briefingMarkdownViewer");
    if (!silent && btn) {
        btn.disabled = true;
        btn.innerText = "Synthesizing...";
    }

    try {
        const res = await fetch("/api/synthesize", { method: "POST" });
        const payload = await res.json();
        const meta = payload.metadata || {};
        latestBriefingMarkdown = payload.report_preview || "";

        const total = meta.total_analyzed || 0;
        const outliersCount = meta.outliers_count || 0;
        const mainstreamCount = Math.max(0, total - outliersCount);

        document.getElementById("kpiTotal").innerText = total;
        document.getElementById("kpiMainstream").innerText = `${mainstreamCount} (${total ? Math.round((mainstreamCount / total) * 100) : 0}%)`;
        document.getElementById("kpiOutliers").innerText = outliersCount;
        document.getElementById("outlierCountBadge").innerText = outliersCount;
        document.getElementById("dialogueCounterText").innerText = `${total} Dialogues Indexed`;

        // Render Topic Bars
        const topicBox = document.getElementById("topicBarsContainer");
        topicBox.innerHTML = "";
        (meta.topics || []).forEach(([cat, count]) => {
            const pct = total ? Math.round((count / total) * 100) : 0;
            const isEmergent = cat.includes("Emergent") || cat.includes("Novel");
            topicBox.innerHTML += `
                <div class="bar-row">
                    <div class="bar-header">
                        <span>${escapeHtml(cat)}</span>
                        <span>${count} (${pct}%)</span>
                    </div>
                    <div class="bar-bg">
                        <div class="bar-fg ${isEmergent ? "amber" : ""}" style="width:${Math.max(pct, 6)}%;"></div>
                    </div>
                </div>
            `;
        });

        // Render Sentiment Bars
        const sentBox = document.getElementById("sentimentBarsContainer");
        sentBox.innerHTML = "";
        const sentiments = meta.sentiment_breakdown || {};
        Object.entries(sentiments).forEach(([label, count]) => {
            const pct = total ? Math.round((count / total) * 100) : 0;
            let colorCls = "";
            if (label.includes("Urgent") || label.includes("Critical")) colorCls = "crimson";
            else if (label.includes("Supportive")) colorCls = "emerald";
            sentBox.innerHTML += `
                <div class="bar-row">
                    <div class="bar-header">
                        <span>${escapeHtml(label)}</span>
                        <span>${count} (${pct}%)</span>
                    </div>
                    <div class="bar-bg">
                        <div class="bar-fg ${colorCls}" style="width:${Math.max(pct, 4)}%;"></div>
                    </div>
                </div>
            `;
        });

        // Render Outliers Feed
        const outliersFeed = document.getElementById("outliersFeedContainer");
        outliersFeed.innerHTML = "";
        (meta.outliers || []).forEach(out => {
            outliersFeed.innerHTML += `
                <div class="outlier-item">
                    <div class="outlier-head">
                        <span>⚡ Signal #${out.index}: ${escapeHtml(out.focus)}</span>
                        <span>State: ${escapeHtml(out.state)}</span>
                    </div>
                    <p class="outlier-quote">"${escapeHtml(out.quote)}"</p>
                </div>
            `;
        });

        viewer.textContent = latestBriefingMarkdown;
        document.getElementById("downloadBriefBtn").style.display = "inline-block";
    } catch (err) {
        viewer.textContent = "Unable to generate briefing: " + err;
    } finally {
        if (!silent && btn) {
            btn.disabled = false;
            btn.innerText = "⚡ Synthesize Executive Briefing";
        }
    }
}

function downloadBriefing() {
    if (!latestBriefingMarkdown) return;
    const blob = new Blob([latestBriefingMarkdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "candidate_pulse_report.md";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
}
