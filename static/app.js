let sampleCases = [];
let currentScenario = null;
let energyChart = null;

document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    loadSampleCases();

    document.getElementById('btn-optimize').addEventListener('click', runOptimization);
});

async function checkHealth() {
    const dot = document.getElementById('health-dot');
    const text = document.getElementById('health-text');

    try {
        const res = await fetch('/health');
        if (res.ok) {
            dot.classList.add('online');
            text.textContent = 'API Ready • GET /health 200 OK';
        } else {
            text.textContent = 'API Error';
        }
    } catch (e) {
        text.textContent = 'Backend Offline';
    }
}

async function loadSampleCases() {
    try {
        const res = await fetch('/static/sample_cases_ui.json');
        let data;
        if (res.ok) {
            data = await res.json();
        } else {
            // Fallback fetch root sample_cases.json if served
            const res2 = await fetch('/sample_cases.json');
            data = await res2.json();
        }
        
        sampleCases = data.cases || [];
        renderScenarioSelector();
        if (sampleCases.length > 0) {
            selectScenario(sampleCases[0].id);
        }
    } catch (e) {
        console.error('Failed to load sample cases', e);
    }
}

function renderScenarioSelector() {
    const container = document.getElementById('scenario-selector');
    container.innerHTML = '';

    sampleCases.forEach(c => {
        const btn = document.createElement('button');
        btn.className = 'btn-scenario';
        btn.id = `btn-${c.id}`;
        btn.innerHTML = `<strong>${c.id}</strong>: ${c.label}`;
        btn.addEventListener('click', () => selectScenario(c.id));
        container.appendChild(btn);
    });
}

function selectScenario(caseId) {
    document.querySelectorAll('.btn-scenario').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById(`btn-${caseId}`);
    if (btn) btn.classList.add('active');

    currentScenario = sampleCases.find(c => c.id === caseId);
    if (!currentScenario) return;

    // Render operator notes
    const notesContainer = document.getElementById('notes-container');
    notesContainer.innerHTML = '';
    currentScenario.input.operator_notes.forEach(note => {
        const div = document.createElement('div');
        div.className = 'note-box';
        div.textContent = `"${note}"`;
        notesContainer.appendChild(div);
    });
}

async function runOptimization() {
    if (!currentScenario) return;

    const btn = document.getElementById('btn-optimize');
    btn.disabled = true;
    btn.innerHTML = '<span>⚡ Running Solver...</span>';

    try {
        const res = await fetch('/optimize-energy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentScenario.input)
        });

        if (!res.ok) {
            alert('Optimization Error: ' + res.statusText);
            return;
        }

        const data = await res.json();
        renderResults(data);
    } catch (e) {
        alert('Optimization failed: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>⚡ Run GridWise Optimizer</span>';
    }
}

function renderResults(data) {
    // Metrics
    document.getElementById('val-cost').innerHTML = `${data.total_cost_bdt.toLocaleString()} <span class="metric-unit">BDT</span>`;
    document.getElementById('val-grid').innerHTML = `${data.total_grid_kwh.toLocaleString()} <span class="metric-unit">kWh</span>`;
    document.getElementById('val-peak').innerHTML = `${data.peak_grid_kwh.toLocaleString()} <span class="metric-unit">kWh</span>`;
    
    // Directives
    const dirContainer = document.getElementById('directives-display');
    dirContainer.innerHTML = '';
    data.directive_interpretation.forEach(d => {
        const item = document.createElement('div');
        item.className = `directive-item ${d.applies ? '' : 'no-op'}`;
        
        let details = '';
        if (d.applies && d.structured_adjustment) {
            details = JSON.stringify(d.structured_adjustment);
        }

        item.innerHTML = `
            <div>
                <strong>Note ${d.note_index}:</strong> ${d.explanation}
                ${details ? `<div style="font-size:11px; color:#9ca3af; font-family:var(--font-mono); margin-top:4px;">${details}</div>` : ''}
            </div>
            <span class="directive-tag ${d.applies ? '' : 'no-op'}">${d.directive_type}</span>
        `;
        dirContainer.appendChild(item);
    });

    // Summary
    document.getElementById('plan-summary-text').textContent = data.plan_summary;

    // Table
    const tbody = document.getElementById('plan-table-body');
    tbody.innerHTML = '';
    data.hourly_plan.forEach((h, idx) => {
        const origHour = currentScenario.input.hours[idx];
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>Hour ${h.hour}:00</strong></td>
            <td>${origHour.demand_kwh}</td>
            <td>${h.solar_used_kwh}</td>
            <td><span class="badge-action badge-${h.battery_action}">${h.battery_action}</span></td>
            <td>${h.battery_kwh}</td>
            <td>${h.battery_energy_after_kwh}</td>
            <td><strong>${h.grid_kwh}</strong></td>
            <td>${origHour.tariff_bdt_per_kwh}</td>
        `;
        tbody.appendChild(tr);
    });

    // Render Chart
    renderChart(data.hourly_plan, currentScenario.input.hours);
}

function renderChart(plan, origHours) {
    const ctx = document.getElementById('energyChart').getContext('2d');
    if (energyChart) energyChart.destroy();

    const labels = plan.map(h => `${h.hour}:00`);
    const demandData = origHours.map(h => h.demand_kwh);
    const gridData = plan.map(h => h.grid_kwh);
    const solarData = plan.map(h => h.solar_used_kwh);
    const socData = plan.map(h => h.battery_energy_after_kwh);

    energyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Campus Demand (kWh)',
                    data: demandData,
                    type: 'line',
                    borderColor: '#f59e0b',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.3
                },
                {
                    label: 'Battery SOC (kWh)',
                    data: socData,
                    type: 'line',
                    borderColor: '#10b981',
                    borderDash: [5, 5],
                    borderWidth: 2,
                    fill: false,
                    tension: 0.2
                },
                {
                    label: 'Grid Import (kWh)',
                    data: gridData,
                    backgroundColor: 'rgba(59, 130, 246, 0.7)'
                },
                {
                    label: 'Solar Used (kWh)',
                    data: solarData,
                    backgroundColor: 'rgba(16, 185, 129, 0.7)'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: '#f3f4f6', font: { family: 'Outfit' } } }
            },
            scales: {
                x: { ticks: { color: '#9ca3af' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                y: { ticks: { color: '#9ca3af' }, grid: { color: 'rgba(255,255,255,0.05)' } }
            }
        }
    });
}
