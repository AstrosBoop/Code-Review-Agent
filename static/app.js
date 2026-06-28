const elements = {
    healthDot: document.getElementById('health-dot'),
    healthText: document.getElementById('health-text'),
    
    headerProvider: document.getElementById('header-provider'),
    headerModel: document.getElementById('header-model'),
    headerFallback: document.getElementById('header-fallback'),
    
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
    
    taskStatus: document.getElementById('review-status-badge'),
    metricsBar: document.getElementById('metrics-container'),
    valScore: document.getElementById('metric-score'),
    valRisk: document.getElementById('metric-risk'),
    valTime: document.getElementById('metric-time'),
    
    reqIdContainer: document.getElementById('request-id-container'),
    reportReqId: document.getElementById('report-request-id'),
    copyReqId: document.getElementById('copy-req-id'),
    
    reportContent: document.getElementById('report-content'),
    
    agentList: document.getElementById('agent-list'),
    historyBody: document.getElementById('history-body')
};

let pollInterval = null;
let currentReviewData = null; // Store for subreport click

// On Load
document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    loadHistory();
    updateProviderHeader();
    
    elements.provider.addEventListener('change', updateProviderHeader);
    elements.modelName.addEventListener('input', updateProviderHeader);
    
    elements.copyReqId.addEventListener('click', () => {
        const text = elements.reportReqId.textContent;
        if (text) {
            navigator.clipboard.writeText(text);
            const originalText = elements.copyReqId.textContent;
            elements.copyReqId.textContent = 'Copied!';
            setTimeout(() => { elements.copyReqId.textContent = originalText; }, 2000);
        }
    });
    
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
        data.history.slice(0, 5).forEach((item, index) => {
            const shortId = item.id.substring(0, 8) + '...';
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${new Date(item.created_at).toLocaleString()}</td>
                <td style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted); display: flex; align-items: center; gap: 0.5rem; justify-content: flex-start;">
                    <span title="${item.id}">${shortId}</span>
                    <button class="btn-secondary copy-history-id" data-id="${item.id}" style="padding: 0.1rem 0.3rem; font-size: 0.7rem; border-radius: 4px;">Copy</button>
                </td>
                <td>${item.filename}</td>
                <td><span class="badge badge-${item.status}">${item.status}</span></td>
                <td>${item.score || '-'}</td>
                <td>${item.risk_level || '-'}</td>
                <td>${item.total_latency_ms ? item.total_latency_ms + ' ms' : '-'}</td>
                <td><a class="action-link" onclick="fetchReviewDetails('${item.id}')">View</a></td>
            `;
            elements.historyBody.appendChild(tr);
        });
        
        // Add copy listeners
        document.querySelectorAll('.copy-history-id').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const fullId = e.target.getAttribute('data-id');
                navigator.clipboard.writeText(fullId);
                const old = e.target.textContent;
                e.target.textContent = 'Copied!';
                setTimeout(() => { e.target.textContent = old; }, 1500);
            });
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
        
        // Request ID Container
        elements.reqIdContainer.style.display = 'flex';
        elements.reportReqId.textContent = data.id || reviewId;
        
        // Render Agents
        renderAgents(data.agent_runs || []);
        
        // Render Markdown
        if (data.report) {
            const rawHtml = marked.parse(data.report);
            const cleanHtml = DOMPurify.sanitize(rawHtml);
            elements.reportContent.innerHTML = cleanHtml;
            
            // Check for Mock Fallback
            if (data.report.includes("LLM Provider: Fallback Used") || data.report.includes("Mock 报告")) {
                elements.headerFallback.textContent = 'On';
                elements.headerFallback.style.color = 'var(--danger)';
                elements.headerProvider.textContent = 'Mock Fallback';
            } else {
                elements.headerFallback.textContent = 'Off';
                elements.headerFallback.style.color = 'var(--text-main)';
                updateProviderHeader(); // reset to current selections
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

function showReport(data, isClick = false) {
    elements.taskStatus.className = 'badge badge-completed';
    elements.taskStatus.textContent = 'COMPLETED';
    elements.taskStatus.style.display = 'block';
    
    elements.metricsBar.classList.remove('hidden');
    elements.valScore.textContent = data.score !== null ? data.score : 'N/A';
    elements.valRisk.textContent = data.risk_level ? data.risk_level.toUpperCase() : 'N/A';
    elements.valTime.textContent = data.total_latency_ms !== null ? data.total_latency_ms : '--';
    
    // Request ID Container
    elements.reqIdContainer.style.display = 'flex';
    elements.reportReqId.textContent = data.id;

    if (data.report) {
        elements.reportContent.innerHTML = DOMPurify.sanitize(marked.parse(data.report));
        
        // Update header fallback
        if (data.report.includes('LLM Provider: Fallback Used')) {
            elements.headerFallback.textContent = 'On';
            elements.headerFallback.style.color = 'var(--danger)';
            elements.headerProvider.textContent = 'Mock Fallback';
        } else {
            elements.headerFallback.textContent = 'Off';
            elements.headerFallback.style.color = 'var(--text-main)';
            updateProviderHeader(); // reset
        }
    } else {
        elements.reportContent.innerHTML = '<div class="placeholder-text">No report generated.</div>';
    }
    
    renderAgentRuns(data.agent_runs);
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
