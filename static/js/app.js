/**
 * FBA Wholesale System - Main JavaScript
 */

// Toggle sidebar on mobile
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('show');
}

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// Show alert
function showAlert(message, type = 'info') {
    const container = document.getElementById('alerts-container');
    if (!container) return;
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `${message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
    container.appendChild(alert);
    setTimeout(() => alert.remove(), 5000);
}

// Calculator
function openCalculator() {
    new bootstrap.Modal(document.getElementById('calcModal')).show();
}

async function runCalculator() {
    const sell = parseFloat(document.getElementById('calc-sell').value) || 0;
    const buy = parseFloat(document.getElementById('calc-buy').value) || 0;
    const weight = parseFloat(document.getElementById('calc-weight').value) || 1;
    const category = document.getElementById('calc-category').value;
    const ship = parseFloat(document.getElementById('calc-ship').value) || 0.50;

    // Client-side calculation (mirrors backend logic)
    const referralPct = {
        home: 15, toys: 15, beauty: 15, health: 15,
        electronics: 8, sports: 15, pet: 15, other: 15,
        grocery: 15, office: 15, tools: 15, clothing: 17,
    }[category] || 15;

    const referral = Math.max(sell * referralPct / 100, 0.30);

    let fba;
    const weightOz = weight * 16;
    if (weightOz <= 6) fba = 3.06;
    else if (weightOz <= 8) fba = 4.25;
    else if (weightOz <= 16) fba = 5.40;
    else if (weightOz <= 32) fba = 5.77;
    else if (weightOz <= 48) fba = 6.14;
    else fba = 6.14 + (weight - 3) * 0.16;

    const storage = 0.30;
    const inbound = 0.40;
    const totalFees = referral + fba + storage + inbound;
    const totalCost = buy + ship;
    const totalExpenses = totalCost + totalFees;
    const profit = sell - totalExpenses;
    const roi = totalCost > 0 ? (profit / totalCost * 100) : 0;
    const margin = sell > 0 ? (profit / sell * 100) : 0;

    const resultDiv = document.getElementById('calc-result');
    resultDiv.style.display = 'block';

    const roiColor = roi >= 20 ? 'success' : roi >= 10 ? 'warning' : 'danger';
    const rec = roi >= 20 && profit >= 3 ? 'COMPRAR' : roi >= 10 ? 'MARGINAL' : 'NO COMPRAR';
    const recColor = roi >= 20 && profit >= 3 ? 'success' : roi >= 10 ? 'warning' : 'danger';

    resultDiv.innerHTML = `
        <div class="row g-2 text-center mb-3">
            <div class="col-4">
                <div class="p-2 rounded bg-${recColor} bg-opacity-10">
                    <small class="text-muted">Ganancia</small>
                    <h4 class="text-${profit > 0 ? 'success' : 'danger'} mb-0">$${profit.toFixed(2)}</h4>
                </div>
            </div>
            <div class="col-4">
                <div class="p-2 rounded bg-${roiColor} bg-opacity-10">
                    <small class="text-muted">ROI</small>
                    <h4 class="text-${roiColor} mb-0">${roi.toFixed(1)}%</h4>
                </div>
            </div>
            <div class="col-4">
                <div class="p-2 rounded bg-${roiColor} bg-opacity-10">
                    <small class="text-muted">Margen</small>
                    <h4 class="text-${roiColor} mb-0">${margin.toFixed(1)}%</h4>
                </div>
            </div>
        </div>
        <div class="small text-muted">
            Referral ($${referral.toFixed(2)}) + FBA ($${fba.toFixed(2)}) + Storage ($${storage.toFixed(2)}) + Inbound ($${inbound.toFixed(2)}) = <strong>$${totalFees.toFixed(2)}</strong> en fees
        </div>
        <div class="alert alert-${recColor} mt-2 mb-0 text-center fw-bold">${rec}</div>
    `;
}

// API helper
async function apiCall(url, method = 'GET', data = null) {
    const options = { method, headers: {} };
    if (data) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(data);
    }
    const resp = await fetch(url, options);
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    return resp.json();
}
