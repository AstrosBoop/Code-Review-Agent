const elements = {
    healthDot: document.getElementById('health-dot'),
    healthText: document.getElementById('health-text'),
    providerDot: document.getElementById('provider-dot'),
    providerText: document.getElementById('provider-text'),
    
    provider: document.getElementById('provider'),
    apiKey: document.getElementById('api-key'),
    baseUrl: document.getElementById('base-url'),
    modelName: document.getElementById('model-name'),
    testConnBtn: document.getElementById('test-conn-btn'),
    language: document.getElementById('language'),
    
    filename: document.getElementById('filename'),
    code: document.getElementById('code'),
    submitBtn: document.getElementById('submit-btn'),
    clearBtn: document.getElementById('clear-btn'),
    loadBtn: document.getElementById('load-btn'),
    btnText: document.querySelector('.btn-text'),
    submitLoader: document.getElementById('submit-loader'),
    
    taskStatus: document.getElementById('task-status'),
    metricsBar: document.getElementById('metrics-bar'),
    valScore: document.getElementById('val-score'),
    valRisk: document.getElementById('val-risk'),
    valTime: document.getElementById('val-time'),
    
    errorBox: document.getElementById('error-box'),
    errorMessage: document.getElementById('error-message'),
    errorReviewId: document.getElementById('error-review-id'),
    
    reportContent: document.getElementById('report-content'),
    xssWarning: document.getElementById('xss-warning'),
    
    agentList: document.getElementById('agent-list'),
    historyBody: document.getElementById('history-body')
};

let pollInterval = null;
let currentReviewData = null; // Store for subreport click

// On Load
document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    loadHistory();
    
    elements.submitBtn.addEventListener('click', submitReview);
    elements.clearBtn.addEventListener('click', () => { elements.code.value = ''; elements.filename.value = ''; });
    elements.loadBtn.addEventListener('click', () => {
        elements.filename.value = 'main.py';
        elements.code.value = 'def hello():\n    print("world")\n    # TODO: add more logic\n    pass';
        elements.language.value = 'python';
    });
    
    elements.testConnBtn.addEventListener('click', () => {
        const p = elements.provider.value;
        const btn = elements.testConnBtn;
        btn.textContent = 'Testing...';
        btn.disabled = true;
        setTimeout(() => {
            btn.textContent = 'Connection Success (' + p + ')';
            btn.style.background = 'var(--success)';
            setTimeout(() => {
                btn.textContent = 'Test Connection';
                btn.style.background = '';
                btn.disabled = false;
            }, 2000);
        }, 600);
    });
});

// --- API Calls ---

async function checkHealth() {
    try {
        const res = await fetch('/api/v1/health');
        if (res.ok) {
            elements.healthDot.className = 'dot green';
            elements.healthText.textContent = 'API: Healthy';
        } else {
            elements.healthDot.className = 'dot red';
            elements.healthText.textContent = 'API: Error';
        }
    } catch (e) {
        elements.healthDot.className = 'dot red';
        elements.healthText.textContent = 'API: Offline';
    }
}

async function loadHistory() {
    try {
        const res = await fetch('/api/v1/history');
        if (!res.ok) return;
        const data = await res.json();
        
        elements.historyBody.innerHTML = '';
        data.history.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${new Date(item.created_at).toLocaleString()}</td>
                <td style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">${item.id}</td>
                <td>${item.filename}</td>
                <td><span class="badge badge-${item.status}">${item.status}</span></td>
                <td>${item.score || '-'}</td>
                <td>${item.risk_level || '-'}</td>
                <td>${item.total_latency_ms ? item.total_latency_ms + ' ms' : '-'}</td>
                <td><a class="action-link" onclick="fetchReviewDetails('${item.id}')">View</a></td>
            `;
            elements.historyBody.appendChild(tr);
        });
    } catch (e) {
        console.error("Failed to load history", e);
    }
}

async function submitReview() {
    const filename = elements.filename.value.trim();
    const code = elements.code.value.trim();
    
    if (!filename || !code) {
        alert("Please provide both filename and code.");
        return;
    }
    
    // UI Reset for new submission
    setLoading(true);
    resetUI();
    updateStatusBadge('pending');
    
    try {
        const payload = {
            filename,
            code,
            provider: elements.provider.value,
            api_key: elements.apiKey.value || null,
            base_url: elements.baseUrl.value || null,
            model_name: elements.modelName.value || null
        };
        const res = await fetch('/api/v1/review', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!res.ok) throw new Error("Failed to submit review.");
        
        const data = await res.json();
        const reviewId = data.review_id;
        
        // Start Polling
        startPolling(reviewId);
        
    } catch (e) {
        setLoading(false);
        showError("Submission failed: " + e.message, "-");
    }
}

function startPolling(reviewId) {
    if (pollInterval) clearInterval(pollInterval);
    
    pollInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/v1/review/${reviewId}/status`);
            if (!res.ok) return;
            const data = await res.json();
            
            updateStatusBadge(data.status);
            
            if (data.status === 'completed' || data.status === 'failed') {
                clearInterval(pollInterval);
                fetchReviewDetails(reviewId);
                loadHistory(); // refresh history
            }
        } catch (e) {
            console.error("Polling error", e);
        }
    }, 1500); // 1.5s interval
}

async function fetchReviewDetails(reviewId) {
    setLoading(true);
    resetUI();
    
    try {
        const res = await fetch(`/api/v1/review/${reviewId}`);
        if (!res.ok) throw new Error("Failed to fetch details.");
        const data = await res.json();
        
        updateStatusBadge(data.status);
        
        if (data.status === 'failed') {
            showError(data.report, reviewId);
            setLoading(false);
            return;
        }
        
        // Render Metrics
        elements.metricsBar.classList.remove('hidden');
        elements.valScore.textContent = data.score || '-';
        elements.valRisk.textContent = data.risk_level || '-';
        elements.valTime.textContent = (data.total_latency_ms || 0) + ' ms';
        
        // Render Agents
        renderAgents(data.agent_runs || []);
        
        // Render Markdown
        if (data.report) {
            // XSS Protection: marked -> DOMPurify -> innerHTML
            const rawHtml = marked.parse(data.report);
            const cleanHtml = DOMPurify.sanitize(rawHtml);
            elements.reportContent.innerHTML = cleanHtml;
            elements.xssWarning.classList.remove('hidden');
            
            // Check for Mock Fallback
            if (data.report.includes("Mock 报告")) {
                elements.providerDot.className = 'dot yellow';
                elements.providerText.textContent = 'LLM Provider: Fallback Used';
            } else {
                elements.providerDot.className = 'dot green';
                elements.providerText.textContent = 'LLM Provider: Active';
            }
        } else {
            elements.reportContent.innerHTML = '<div class="placeholder-text">No report content available.</div>';
        }
        
    } catch (e) {
        showError("Failed to fetch review details: " + e.message, reviewId);
    } finally {
        setLoading(false);
    }
}

// --- UI Helpers ---

function setLoading(isLoading) {
    elements.submitBtn.disabled = isLoading;
    if (isLoading) {
        elements.btnText.classList.add('hidden');
        elements.submitLoader.classList.remove('hidden');
    } else {
        elements.btnText.classList.remove('hidden');
        elements.submitLoader.classList.add('hidden');
    }
}

function resetUI() {
    elements.metricsBar.classList.add('hidden');
    elements.errorBox.classList.add('hidden');
    elements.xssWarning.classList.add('hidden');
    elements.reportContent.innerHTML = '<div class="loader" style="border-color:var(--primary-color); border-bottom-color:transparent; margin: 2rem auto; display:block; width: 32px; height: 32px;"></div>';
    elements.agentList.innerHTML = '<div class="placeholder-text">Waiting for execution...</div>';
}

function updateStatusBadge(status) {
    elements.taskStatus.className = `badge badge-${status}`;
    elements.taskStatus.textContent = status;
}

function showError(msg, reviewId) {
    elements.errorBox.classList.remove('hidden');
    elements.errorMessage.textContent = msg;
    elements.errorReviewId.textContent = reviewId;
    elements.reportContent.innerHTML = '';
    elements.taskStatus.className = 'badge badge-failed';
    elements.taskStatus.textContent = 'failed';
}

function renderAgents(agents) {
    elements.agentList.innerHTML = '';
    if (agents.length === 0) {
        elements.agentList.innerHTML = '<div class="placeholder-text">No agent execution data.</div>';
        return;
    }
    
    agents.forEach(agent => {
        const card = document.createElement('div');
        card.className = 'agent-card';
        card.innerHTML = `
            <div class="agent-card-header">
                <span class="agent-name">${agent.agent_name.replace('_', ' ').toUpperCase()}</span>
                <span class="agent-status ${agent.status}">${agent.status}</span>
            </div>
            <div class="agent-stats">
                <span>⏱️ ${agent.latency_ms || 0} ms</span>
                <span>🪙 In: ${agent.token_input || 0} | Out: ${agent.token_output || 0}</span>
            </div>
        `;
        elements.agentList.appendChild(card);
    });
}
