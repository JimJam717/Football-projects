// Module-level state
let allPlayers = [];
let activeTeam = 'All';
let searchQuery = '';
let activePlayerId = null;
let battingRadarInstance = null;
let bowlingRadarInstance = null;
let imageMap = {};
let TEAM_LOGOS = {};

const METRIC_TOOLTIPS = {
    'Batting Average':      'Runs scored per dismissal. Higher = better.',
    'Strike Rate':          'Runs scored per 100 balls faced. Higher = better.',
    'Boundary Percentage':  'Percentage of balls hit for 4 or 6. Higher = better.',
    'Six-Hitting Rate':     'Percentage of balls hit for 6. Higher = better.',
    'Dot Ball %':           'Percentage of balls faced with no run scored. Lower = better.',
    'Economy Rate':         'Runs conceded per over. Lower = better.',
    'Bowling Average':      'Runs conceded per wicket. Lower = better.',
    'Bowling Strike Rate':  'Balls bowled per wicket. Lower = better.',
    'Boundary %':           'Percentage of legal balls hit for 4 or 6 off this bowler. Lower = better.',
    'Extra Rate':           'Percentage of deliveries that were wides or no-balls. Lower = better.'
};

// Phase 2 Fix 1 — Number formatting
function formatValue(val) {
    if (val === null || val === undefined) return '—';
    if (val === 9999) return '—';
    if (Number.isInteger(val)) return val.toString();
    return parseFloat(val.toFixed(2)).toString();
}

function getInitials(name) {
  const parts = name.split(' ');
  if (parts.length === 1) return parts[0][0].toUpperCase();
  return (parts[0][0] + parts[parts.length-1][0]).toUpperCase();
}

// On load
document.addEventListener('DOMContentLoaded', async () => {
    try {
        // Fetch player data first - this is critical
        const playersRes = await fetch('all_players_data.json');
        if (!playersRes.ok) throw new Error(`HTTP ${playersRes.status}: ${playersRes.statusText}`);
        allPlayers = await playersRes.json();

        // Fetch imagery second - this is optional/secondary
        try {
            const imagesRes = await fetch('player_images.csv');
            if (imagesRes.ok) {
                const csvText = await imagesRes.text();
                const rows = csvText.trim().split('\n').slice(1);
                rows.forEach(row => {
                    const columns = row.split(',');
                    if (columns.length >= 3) {
                        const name = columns[0].trim();
                        const team = columns[1].trim();
                        const url = columns[2].trim();
                        if (url) {
                            if (name.endsWith(' Logo')) TEAM_LOGOS[team] = url;
                            else imageMap[name] = url;
                        }
                    }
                });
            }
        } catch (csvErr) {
            console.warn('Imagery load failed:', csvErr);
        }
        
        setupEventListeners();
        buildTeamPills();
        renderSidebar();
        
        const filtered = getFilteredPlayers();
        if (filtered.length > 0) renderPlayer(filtered[0]);

    } catch (err) {
        console.error('Data load error:', err);
        document.getElementById('report-container').innerHTML = `
            <div class="empty-state">
                <div style="text-align: center; max-width: 500px;">
                    <p style="color: var(--accent-red); font-weight: bold; margin-bottom: 1rem; font-size: 1.2rem;">FETCH ERROR</p>
                    <p style="margin-bottom: 1rem;">The browser failed to load <strong>all_players_data.json</strong>.</p>
                    <div style="background: #1a1a1a; padding: 1rem; border-radius: 4px; text-align: left; font-size: 0.8rem; border: 1px solid var(--border);">
                        <code>Error: ${err.message}</code>
                    </div>
                    <p style="margin-top: 1.5rem; font-size: 0.85rem;"><strong>Common Fixes:</strong></p>
                    <ul style="text-align: left; font-size: 0.8rem; margin: 0.5rem 0 0 1.5rem; color: var(--text-secondary);">
                        <li>Run a local server (e.g., Live Server or <code>python -m http.server</code>).</li>
                        <li>Ensure you aren't just double-clicking <code>index.html</code> (browsers block data loading from <code>file://</code>).</li>
                        <li>Check if <code>all_players_data.json</code> is in the same folder.</li>
                    </ul>
                </div>
            </div>
        `;
    }
});

function setupEventListeners() {
    const searchInput = document.getElementById('player-search');
    searchInput.addEventListener('input', (e) => {
        searchQuery = e.target.value;
        renderSidebar();
        handleFilterChange();
    });

    const mobileSelect = document.getElementById('playerSelectMobile');
    mobileSelect.addEventListener('change', (e) => {
        const player = allPlayers.find(p => p.player_name === e.target.value);
        if (player) renderPlayer(player);
    });

    // Tooltip behavior
    const tooltip = document.getElementById('tooltip');
    document.addEventListener('mouseover', (e) => {
        if (e.target.classList.contains('info-icon')) {
            const metricName = e.target.dataset.metric;
            if (METRIC_TOOLTIPS[metricName]) {
                tooltip.textContent = METRIC_TOOLTIPS[metricName];
                tooltip.style.display = 'block';
                
                const rect = e.target.getBoundingClientRect();
                const tooltipRect = tooltip.getBoundingClientRect();
                
                tooltip.style.left = (rect.left + (rect.width / 2) - (tooltipRect.width / 2)) + 'px';
                tooltip.style.top = (rect.top - tooltipRect.height - 10) + 'px';
            }
        }
    });

    document.addEventListener('mouseout', (e) => {
        if (e.target.classList.contains('info-icon')) {
            tooltip.style.display = 'none';
        }
    });
}

function handleFilterChange() {
    // Phase 2C — Active player scroll/auto-select
    const filtered = getFilteredPlayers();
    const isActiveStillInList = filtered.some(p => p.player_name === activePlayerId);
    
    if (!isActiveStillInList && filtered.length > 0) {
        renderPlayer(filtered[0]);
        // Scroll sidebar to top
        document.getElementById('sidebar-player-list').scrollTop = 0;
    }
}

function getFilteredPlayers() {
    return allPlayers
        .filter(p => activeTeam === 'All' || p.team === activeTeam)
        .filter(p => p.player_name.toLowerCase().includes(searchQuery.toLowerCase()))
        .sort((a, b) => a.player_name.localeCompare(b.player_name));
}

function buildTeamPills() {
    const teams = ['All', ...new Set(allPlayers.map(p => p.team))].sort();
    const container = document.getElementById('team-pills');
    container.innerHTML = '';

    teams.forEach(team => {
        if (!team || team === 'Unknown') return;
        const pill = document.createElement('div');
        pill.className = `team-pill ${team === activeTeam ? 'active' : ''}`;
        pill.textContent = team;
        pill.onclick = () => {
            activeTeam = team;
            updatePillStyles();
            renderSidebar();
            handleFilterChange();
        };
        container.appendChild(pill);
    });
}

function updatePillStyles() {
    const pills = document.querySelectorAll('.team-pill');
    pills.forEach(pill => {
        if (pill.textContent === activeTeam) {
            pill.classList.add('active');
        } else {
            pill.classList.remove('active');
        }
    });
}

function renderSidebar() {
    const players = getFilteredPlayers();
    const container = document.getElementById('sidebar-player-list');
    const countBadge = document.getElementById('player-count');
    const mobileSelect = document.getElementById('playerSelectMobile');
    
    // Phase 2C — Player count badge
    countBadge.textContent = `Showing ${players.length} of ${allPlayers.length} players`;
    
    container.innerHTML = '';
    mobileSelect.innerHTML = '<option value="" disabled>Select Player...</option>';

    if (players.length === 0) {
        container.innerHTML = '<div class="empty-state" style="padding: 2rem; font-size: 0.8rem;">No players found</div>';
        return;
    }

    players.forEach(player => {
        // Sidebar item
        const item = document.createElement('div');
        item.className = `player-item ${player.player_name === activePlayerId ? 'active' : ''}`;
        item.innerHTML = `
            <span class="name">${player.player_name}</span>
            <span class="team">${player.team}</span>
        `;
        item.onclick = () => renderPlayer(player);
        container.appendChild(item);

        // Mobile Select option
        const option = document.createElement('option');
        option.value = player.player_name;
        option.textContent = player.player_name;
        if (player.player_name === activePlayerId) option.selected = true;
        mobileSelect.appendChild(option);
    });
}

function renderPlayer(playerData) {
    activePlayerId = playerData.player_name;
    const container = document.getElementById('report-container');
    const mobileSelect = document.getElementById('playerSelectMobile');
    
    // Update active states
    renderSidebar(); 
    if (mobileSelect) mobileSelect.value = activePlayerId;

    const isAllRounder = playerData.bowling !== null;
    
    const matchesB = playerData.batting?.matches || 0;
    const matchesW = playerData.bowling?.matches || 0;
    const totalMatches = Math.max(matchesB, matchesW);
    const totalRuns = playerData.batting?.runs || 0;
    const totalWickets = playerData.bowling?.wickets || 0;

    let specialistStat = '';
    if (!isAllRounder) {
        const avg = playerData.batting.metrics.find(m => m.name === 'Batting Average')?.raw_value;
        specialistStat = `
            <div class="stat-box">
                <div class="number">${formatValue(avg)}</div>
                <div class="label">Batting Avg</div>
            </div>
        `;
    } else {
        const econ = playerData.bowling.metrics.find(m => m.name === 'Economy Rate')?.raw_value;
        specialistStat = `
            <div class="stat-box">
                <div class="number">${formatValue(econ)}</div>
                <div class="label">Economy</div>
            </div>
        `;
    }

    const heroStats = `
        <div class="stat-box">
            <div class="number">${totalMatches}</div>
            <div class="label">Matches</div>
        </div>
        <div class="stat-box">
            <div class="number">${formatValue(totalRuns)}</div>
            <div class="label">Total Runs</div>
        </div>
        <div class="stat-box">
            <div class="number">${formatValue(totalWickets)}</div>
            <div class="label">Total Wickets</div>
        </div>
        ${specialistStat}
    `;

    const playerImageUrl = imageMap[playerData.player_name];
    const teamLogoUrl = TEAM_LOGOS[playerData.team];

    const avatarHtml = playerImageUrl 
        ? `<img src="${playerImageUrl}" class="player-avatar" alt="${playerData.player_name}">`
        : `<div class="player-avatar-initials">${getInitials(playerData.player_name)}</div>`;

    const teamLogoHtml = teamLogoUrl
        ? `<img src="${teamLogoUrl}" class="team-logo-small" alt="${playerData.team} logo">`
        : '';

    container.innerHTML = `
        <div class="hero-header">
            <div class="player-profile-row">
                ${avatarHtml}
                <div class="player-info-main">
                    <h2 class="player-name">${playerData.player_name}</h2>
                    <div class="team-badge">
                        ${teamLogoHtml}
                        <span>${playerData.team}</span>
                    </div>
                </div>
            </div>
            <div class="stat-grid">
                ${heroStats}
            </div>
        </div>

        <div class="stats-container">
            <section class="section-group">
                <h3 class="section-header">BATTING</h3>
                <p class="comparison-text">${playerData.comparison_group}</p>
                <div class="metrics-list">
                    ${playerData.batting.metrics.map(m => renderMetricRow(m)).join('')}
                </div>
            </section>

            <section class="section-group">
                <h3 class="section-header">BOWLING</h3>
                ${isAllRounder ? `
                    <p class="comparison-text">IPL 2025 Bowlers (Min 12 balls bowled)</p>
                    <div class="metrics-list">
                        ${playerData.bowling.metrics.map(m => renderMetricRow(m, true)).join('')}
                    </div>
                ` : `
                    <div class="bowling-placeholder">No bowling data for IPL 2025</div>
                `}
            </section>
        </div>

        <div class="radar-section">
            <div class="radar-container" id="batting-radar-container">
                <h3 class="section-header">BATTING RADAR</h3>
                <canvas id="battingRadarChart"></canvas>
            </div>
            <div class="radar-container" id="bowling-radar-container">
                <h3 class="section-header">BOWLING RADAR</h3>
                <canvas id="bowlingRadarChart"></canvas>
            </div>
        </div>
    `;

    // Trigger radar and bar animations after DOM update
    requestAnimationFrame(() => {
        renderRadars(playerData);
        animateBars();
    });
}

// Phase 2A — Separate Radar Rendering
function renderRadarChart(canvasId, labels, data, color) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'radar',
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: `${color}26`, // ~15% opacity hex variant
                borderColor: color,
                borderWidth: 2,
                pointBackgroundColor: color,
                pointRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: { legend: { display: false } },
            scales: {
                r: {
                    min: 0,
                    max: 100,
                    ticks: { display: false },
                    grid: { color: '#1E2D45' },
                    angleLines: { color: '#1E2D45' },
                    pointLabels: {
                        color: '#8899AA',
                        font: { family: 'DM Sans', size: 11 }
                    }
                }
            }
        }
    });
}

function renderRadars(playerData) {
    // Destroy previous instances
    if (battingRadarInstance) { battingRadarInstance.destroy(); battingRadarInstance = null; }
    if (bowlingRadarInstance) { bowlingRadarInstance.destroy(); bowlingRadarInstance = null; }

    // Batting radar — always render if batting metrics exist
    const bMetrics = playerData.batting?.metrics?.filter(m => m.percentile !== null) || [];
    if (bMetrics.length > 0) {
        document.getElementById('batting-radar-container').style.display = 'block';
        battingRadarInstance = renderRadarChart(
            'battingRadarChart',
            bMetrics.map(m => m.name),
            bMetrics.map(m => m.percentile ?? 0),
            '#00C9A7'
        );
    } else {
        document.getElementById('batting-radar-container').style.display = 'none';
    }

    // Bowling radar — only render if player has bowling data
    const wMetrics = playerData.bowling?.metrics?.filter(m => m.percentile !== null) || [];
    if (wMetrics.length > 0) {
        document.getElementById('bowling-radar-container').style.display = 'block';
        bowlingRadarInstance = renderRadarChart(
            'bowlingRadarChart',
            wMetrics.map(m => m.name),
            wMetrics.map(m => m.percentile ?? 0),
            '#F5A623'
        );
    } else {
        document.getElementById('bowling-radar-container').style.display = 'none';
    }
}

function renderMetricRow(metric, isBowling = false) {
    const higherIsBetter = ['Batting Average', 'Strike Rate', 'Boundary Percentage', 'Six-Hitting Rate'];
    const lowerIsBetter = ['Economy Rate', 'Bowling Average', 'Bowling Strike Rate', 'Boundary %', 'Extra Rate'];
    
    let directionLabel = '';
    if (isBowling) {
        if (metric.name === 'Dot Ball %' || higherIsBetter.includes(metric.name)) {
            directionLabel = '↑ BETTER';
        } else if (lowerIsBetter.includes(metric.name)) {
            directionLabel = '↓ BETTER';
        }
    } else {
        if (metric.name === 'Dot Ball %') {
            directionLabel = '↓ BETTER';
        } else if (higherIsBetter.includes(metric.name)) {
            directionLabel = '↑ BETTER';
        }
    }
    
    // Phase 2C — Null percentile handling
    const isNull = metric.percentile === null || metric.percentile === undefined;
    const displayPercentile = isNull ? 20 : metric.percentile;
    const percentileLabel = isNull ? 'N/A' : `${metric.percentile.toFixed(1)}%`;
    const barColor = isNull ? 'var(--text-muted)' : getBarColor(metric.percentile);

    return `
        <div class="metric-row">
            <div class="metric-info">
                <div class="metric-label-container">
                    <span class="metric-name">${metric.name}</span>
                    ${directionLabel ? `<span class="better-indicator">${directionLabel}</span>` : ''}
                    <span class="info-icon" data-metric="${metric.name}">ⓘ</span>
                </div>
                <span class="metric-value">${formatValue(metric.raw_value)}</span>
            </div>
            <div class="bar-track">
                <div class="bar-fill" 
                     data-percentile="${displayPercentile}" 
                     style="width: 0%; background-color: ${barColor}">
                    <span class="percentile-label">${percentileLabel}</span>
                </div>
            </div>
        </div>
    `;
}

function animateBars() {
    const bars = document.querySelectorAll('.bar-fill');
    bars.forEach((bar, index) => {
        const targetWidth = bar.dataset.percentile || 0;
        
        setTimeout(() => {
            bar.classList.add('animating');
            // Ensure a minimum visual width of 10% so the label (e.g. 0.0%) is visible
            const visualWidth = Math.max(parseFloat(targetWidth), 10);
            bar.style.width = visualWidth + '%';
        }, index * 60);
    });
}

function getBarColor(percentile) {
    if (percentile === null || percentile === undefined) return 'var(--text-muted)';
    if (percentile >= 70) return 'var(--accent-teal)';
    if (percentile >= 40) return 'var(--accent-amber)';
    return 'var(--accent-red)';
}
