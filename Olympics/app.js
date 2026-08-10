/* Paris 2024 Olympics Dashboard - App JS */

const COUNTRY_MIN_KNOWN_BIRTHPLACES = 10;
const SPORT_MIN_KNOWN_BIRTHPLACES = 25;
const TOP_COUNTRY_LIMIT = 15;
const TOP_CITY_LIMIT = 10;
const CORRIDOR_TYPE_ORDER = ['refugee-or-neutral', 'post-colonial', 'heritage-return', 'neighbor', 'talent-market', 'post-soviet', 'intra-sovereign', 'unclassified'];
const CITY_COORD_OVERRIDES = {
  'chicago, il|united states': [41.8781, -87.6298],
  'chicago, ill|united states': [41.8781, -87.6298],
  'lagos|nigeria': [6.5244, 3.3792],
  'ikorodu, lagos state|nigeria': [6.6194, 3.5105],
  'london, england|great britain': [51.5074, -0.1278]
};
const COUNTRY_COORD_FALLBACKS = {
  'Russian Federation': [61.524, 105.3188],
  'Russia': [61.524, 105.3188],
  'Belarus': [53.7098, 27.9534],
  'Yugoslavia': [44.0165, 21.0059],
  'Netherlands Antilles': [12.2261, -69.0601],
  'Soviet Union': [55.7558, 37.6173]
};
const CORRIDOR_TYPE_COLORS = {
  'refugee-or-neutral': '#f59e0b',
  'post-colonial': '#0ea5e9',
  'intra-sovereign': '#ef4444',
  'post-soviet': '#c2410c',
  'neighbor': '#10b981',
  'heritage-return': '#8b5cf6',
  'talent-market': '#3b82f6',
  'unclassified': '#64748b',
  'unknown': '#64748b',
  'other': '#64748b'
};
const CORRIDOR_TYPE_LABELS = {
  'refugee-or-neutral': 'Refugee / neutral team',
  'post-colonial': 'Post-colonial',
  'intra-sovereign': 'Within one citizenship',
  'post-soviet': 'Post-Soviet',
  neighbor: 'Neighbor',
  'heritage-return': 'Heritage return',
  'talent-market': 'Talent market',
  unclassified: 'Unclassified',
  unknown: 'Unknown',
  other: 'Other'
};
const CORRIDOR_TYPE_DESCRIPTIONS = {
  'refugee-or-neutral': 'Refugee and neutral teams created by displacement or political exclusion.',
  'post-colonial': 'Routes shaped by former empire, language, and inherited sporting ties.',
  'heritage-return': 'Athletes using ancestry or heritage eligibility to represent another team.',
  neighbor: 'Regional movement between nearby countries.',
  'talent-market': 'Sporting citizenship and recruitment patterns where opportunity drives the route.',
  'post-soviet': 'Routes inside the former Soviet sporting and citizenship space.',
  'intra-sovereign': 'Moves within one citizenship space, such as US territories or associated states.',
  unclassified: 'Small or ambiguous corridors left uncoded rather than force-fitted.'
};

let map;
let trainingMap;
let countryStatsData = {};
let countryStats = [];
let cityStatsData = [];
let sportStatsData = [];
let athleteData = [];
let corridorStatsData = [];
let trainingStatsData = {};
let summaryStats = {};
let representedTeamCityMarkers = [];
let activeLayerGroup;
let migrationFocusLayer;
let trainingHostLayer;
let trainingRouteLayer;
let currentViewMode = 'country';
let currentSizeMode = 'count';
let sportMode = 'share';
let loggedInvalidCityCoords = false;
let corridorSort = { key: 'athlete_count', direction: 'desc' };
let corridorFilters = { types: new Set(), birth: '', rep: '' };
let activeCorridorTypes = new Set();
let corridorBirthFilter = '';
let corridorRepFilter = '';
let trainingHostLimit = 20;
let selectedTrainingHost = null;
let migrationStoryState = createEmptyMigrationStoryState();

/* Detail Drawer Spring Physics & Gesture Constants & Variables */
const SPRING_DAMPING = 0.8;
const SPRING_RESPONSE = 0.3;
const SPRING_STIFFNESS = Math.pow((2 * Math.PI) / SPRING_RESPONSE, 2);
const SPRING_DAMPING_C = (4 * Math.PI * SPRING_DAMPING) / SPRING_RESPONSE;

let drawerPos = null;
let drawerAnimFrame = null;
let isDrawerDragging = false;
let isDrawerPointerDown = false;
let drawerPointerId = null;
let drawerStartX = 0;
let drawerStartY = 0;
let drawerStartPos = 0;
let drawerVelocityQueue = [];

document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  initMap();
  initTrainingMap();
  loadData();
});

function initMap() {
  if (typeof L === 'undefined') {
    document.getElementById('map').innerHTML = '<div class="map-unavailable">Map library unavailable. Rankings and tables remain available.</div>';
    return;
  }

  map = L.map('map', {
    center: [20, 0],
    zoom: 2.5,
    minZoom: 2,
    maxZoom: 9,
    worldCopyJump: true
  });

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    subdomains: 'abcd',
    maxZoom: 19
  }).addTo(map);

  activeLayerGroup = L.layerGroup().addTo(map);
  migrationFocusLayer = L.layerGroup().addTo(map);
  window.addEventListener('resize', () => map.invalidateSize());
}

function initTrainingMap() {
  const container = document.getElementById('training-map');
  if (!container) return;
  if (typeof L === 'undefined') {
    container.innerHTML = '<div class="map-unavailable">Map library unavailable. Residence rankings remain available.</div>';
    return;
  }

  trainingMap = L.map('training-map', {
    center: [20, 0],
    zoom: 2,
    minZoom: 2,
    maxZoom: 7,
    worldCopyJump: true,
    zoomControl: false
  });
  L.control.zoom({ position: 'topright' }).addTo(trainingMap);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    subdomains: 'abcd',
    maxZoom: 19
  }).addTo(trainingMap);
  trainingHostLayer = L.layerGroup().addTo(trainingMap);
  trainingRouteLayer = L.layerGroup().addTo(trainingMap);
  window.addEventListener('resize', () => trainingMap.invalidateSize());
}

async function loadData() {
  try {
    const [countryJson, athleteJson, cityJson, sportJson, corridorJson, summaryJson, trainingJson] = await Promise.all([
      fetchJson('./data/country_stats.json'),
      fetchJson('./data/olympics_diaspora.json'),
      fetchJson('./data/city_stats.json'),
      fetchJson('./data/sport_stats.json'),
      fetchJson('./data/corridor_stats.json', []),
      fetchJson('./data/summary_stats.json', {}),
      fetchJson('./data/training_stats.json', {})
    ]);

    countryStatsData = countryJson || {};
    countryStats = Object.values(countryStatsData || {});
    athleteData = Array.isArray(athleteJson) ? athleteJson : [];
    cityStatsData = Array.isArray(cityJson) ? cityJson : [];
    sportStatsData = Array.isArray(sportJson) ? sportJson : [];
    corridorStatsData = Array.isArray(corridorJson) ? corridorJson : [];
    summaryStats = summaryJson || {};
    trainingStatsData = trainingJson || {};
    representedTeamCityMarkers = buildRepresentedTeamCityMarkers();

    renderIdentityStrip();
    renderRankingsTab();
    renderSportsTab();
    renderTrainingTab();
    renderCorridorsTab();
    renderCurrentMapView();
  } catch (error) {
    console.error('Failed to load dataset files:', error);
    document.getElementById('share-ranking').textContent = 'Data could not be loaded.';
  }
}

async function fetchJson(url, fallback) {
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    const text = await response.text();
    return JSON.parse(text.replace(/\bNaN\b/g, 'null'));
  } catch (error) {
    if (fallback !== undefined) {
      console.info(`Optional dataset unavailable: ${url}`);
      return fallback;
    }
    throw error;
  }
}

function setupEventListeners() {
  document.querySelectorAll('.tab-button').forEach(button => {
    button.addEventListener('click', () => setActiveTab(button.dataset.tab));
  });

  document.getElementById('view-btn-country').addEventListener('click', () => setMapView('country'));
  document.getElementById('view-btn-city').addEventListener('click', () => setMapView('city'));
  document.getElementById('view-btn-corridors').addEventListener('click', () => setMapView('corridors'));
  document.getElementById('corridor-map-toggle').addEventListener('click', () => {
    setActiveTab('map');
    setMapView('corridors');
  });
  document.querySelectorAll('[data-migration-story]').forEach(button => {
    button.addEventListener('click', () => startMigrationStory(button.dataset.migrationStory));
  });
  document.getElementById('migration-story-pause').addEventListener('click', toggleMigrationStoryPause);
  document.getElementById('migration-story-restart').addEventListener('click', () => {
    if (migrationStoryState.mode) startMigrationStory(migrationStoryState.mode);
  });
  document.getElementById('corridor-min-count').addEventListener('input', renderCorridorTable);
  document.getElementById('training-min-count').addEventListener('input', renderTrainingCorridorTable);
  document.querySelectorAll('[data-training-host-limit]').forEach(button => {
    button.addEventListener('click', () => {
      trainingHostLimit = button.dataset.trainingHostLimit === 'all'
        ? Infinity
        : Number(button.dataset.trainingHostLimit);
      selectedTrainingHost = null;
      resetTrainingMapView();
      renderTrainingHostMap();
    });
  });
  document.getElementById('clear-training-host').addEventListener('click', () => {
    selectedTrainingHost = null;
    resetTrainingMapView();
    renderTrainingHostMap();
  });

  document.querySelectorAll('[data-corridor-sort]').forEach(button => {
    button.addEventListener('click', () => {
      const key = button.dataset.corridorSort;
      corridorSort = {
        key,
        direction: corridorSort.key === key && corridorSort.direction === 'desc' ? 'asc' : 'desc'
      };
      renderCorridorTable();
    });
  });

  document.getElementById('filter-diaspora-hubs-only').addEventListener('change', () => {
    if (currentViewMode === 'city') renderCityBubbles();
  });

  document.querySelectorAll('[data-size-mode]').forEach(button => {
    button.addEventListener('click', () => {
      currentSizeMode = button.dataset.sizeMode;
      document.querySelectorAll('[data-size-mode]').forEach(btn => btn.classList.toggle('active', btn === button));
      renderCurrentMapView();
    });
  });

  document.querySelectorAll('[data-sport-mode]').forEach(button => {
    button.addEventListener('click', () => {
      sportMode = button.dataset.sportMode;
      document.querySelectorAll('[data-sport-mode]').forEach(btn => btn.classList.toggle('active', btn === button));
      renderSportChart();
    });
  });

  document.getElementById('close-drawer-btn').addEventListener('click', closeDetailDrawer);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      closeDetailDrawer();
    }
  });

  initDrawerGesture();
}

function setActiveTab(tabName) {
  if (tabName !== 'map') stopMigrationStory();

  document.querySelectorAll('.tab-button').forEach(button => {
    const active = button.dataset.tab === tabName;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
  });

  document.querySelectorAll('.tab-panel').forEach(panel => {
    const active = panel.id === `${tabName}-panel`;
    panel.classList.toggle('active', active);
    panel.hidden = !active;
  });

  if (tabName === 'map') {
    setTimeout(() => {
      if (map) map.invalidateSize();
      renderCurrentMapView();
    }, 60);
  }
  if (tabName === 'training') {
    setTimeout(() => {
      if (trainingMap) trainingMap.invalidateSize();
      renderTrainingHostMap();
    }, 60);
  }
}

function renderIdentityStrip() {
  const total = athleteData.length;
  const known = athleteData.filter(athlete => athlete.birth_country).length;
  const diaspora = athleteData.filter(athlete => athlete.is_diaspora);
  const typeCounts = new Map();

  diaspora.forEach(athlete => {
    const type = getAthleteDiasporaType(athlete);
    typeCounts.set(type, (typeCounts.get(type) || 0) + 1);
  });

  document.getElementById('identity-diaspora-count').textContent = formatNumber(diaspora.length);
  document.getElementById('identity-summary').textContent = `${formatPct(known ? (diaspora.length / known) * 100 : 0)}% of ${formatNumber(known)} athletes with known birthplaces (${formatPct(summaryStats.excluding_eor_ain?.diaspora_share_all_athletes)}% excluding refugee/neutral teams)`;
  document.getElementById('identity-total').textContent = `${formatNumber(total)} total athletes`;

  const container = document.getElementById('identity-decomposition');
  container.innerHTML = '';
  const orderedTypes = CORRIDOR_TYPE_ORDER.filter(type => typeCounts.has(type)).concat(
    Array.from(typeCounts.keys()).filter(type => !CORRIDOR_TYPE_ORDER.includes(type))
  );
  orderedTypes
    .map(type => [type, typeCounts.get(type) || 0])
    .forEach(([type, count]) => {
      const segment = document.createElement('button');
      segment.type = 'button';
      segment.className = 'decomposition-segment';
      segment.style.width = `${Math.max(2, (count / Math.max(diaspora.length, 1)) * 100)}%`;
      segment.style.background = getCorridorTypeColor(type);
      segment.title = `${formatTypeLabel(type)}: ${formatNumber(count)}`;
      segment.innerHTML = `<span>${escapeHtml(formatTypeLabel(type))} ${formatNumber(count)}</span>`;
      segment.addEventListener('click', () => navigateTo({ tab: 'corridors', filters: { type: [type], min: 1 }, focus: { kind: 'module', id: 'corridors-module' } }));
      container.appendChild(segment);
    });

  const legend = document.getElementById('identity-type-legend');
  legend.innerHTML = orderedTypes.map(type => {
    const count = typeCounts.get(type) || 0;
    const label = type === 'unclassified'
      ? `${formatTypeLabel(type)} (${formatNumber(count)} - small corridors left uncoded, not force-fitted)`
      : `${formatTypeLabel(type)} ${formatNumber(count)}`;
    return `
      <button class="type-legend-item" type="button" data-type="${escapeHtml(type)}" title="${escapeHtml(CORRIDOR_TYPE_DESCRIPTIONS[type] || '')}">
        <i style="background:${getCorridorTypeColor(type)}"></i>${escapeHtml(label)}
      </button>
    `;
  }).join('');
  legend.querySelectorAll('[data-type]').forEach(button => {
    button.addEventListener('click', () => navigateTo({ tab: 'corridors', filters: { type: [button.dataset.type], min: 1 }, focus: { kind: 'module', id: 'corridors-module' } }));
  });
}

function renderRankingsTab() {
  renderCountryRankingChart({
    containerId: 'share-ranking',
    metric: 'foreign_born_pct',
    formatter: value => `${formatPct(value)}%`,
    maxValue: 100,
    minKnown: COUNTRY_MIN_KNOWN_BIRTHPLACES
  });

  const maxCount = Math.max(...countryStats.map(row => row.foreign_born_count || 0), 1);
  renderCountryRankingChart({
    containerId: 'count-ranking',
    metric: 'foreign_born_count',
    formatter: value => formatNumber(value),
    maxValue: maxCount,
    minKnown: 1
  });

  renderDependencyScatter();
  renderMedalDumbbell();
  renderCityHubTable();
}

function renderCountryRankingChart({ containerId, metric, formatter, maxValue, minKnown }) {
  const container = document.getElementById(containerId);
  container.innerHTML = '';

  countryStats
    .filter(row => (row.total_records_with_birthplace_data || 0) >= minKnown && (row[metric] || 0) > 0)
    .sort((a, b) => (b[metric] || 0) - (a[metric] || 0))
    .slice(0, TOP_COUNTRY_LIMIT)
    .forEach(row => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'bar-row';
      button.setAttribute('aria-label', `${row.country}, ${formatter(row[metric])}`);
      button.addEventListener('click', () => openDetailDrawer('country', row));

      button.innerHTML = `
        <span class="bar-label">
          <span class="bar-name">${escapeHtml(row.country)}</span>
          <span class="bar-code">${escapeHtml(row.noc)}${isExceptionalNoc(row) ? ' caveat' : ''}</span>
        </span>
        <span class="bar-track"><span class="bar-fill" style="width: ${Math.max(2, ((row[metric] || 0) / maxValue) * 100)}%"></span></span>
        <span class="bar-value">${formatter(row[metric] || 0)}</span>
      `;
      container.appendChild(button);
    });
}

function renderDependencyScatter() {
  const container = document.getElementById('dependency-scatter');
  const rows = countryStats.filter(row => (row.total_records_with_birthplace_data || 0) >= 2 && Number.isFinite(row.foreign_born_pct));
  if (!rows.length) {
    container.innerHTML = '<p class="note">Country statistics unavailable.</p>';
    return;
  }

  const width = 760;
  const height = 320;
  const pad = { top: 24, right: 28, bottom: 44, left: 52 };
  const maxKnown = Math.max(...rows.map(row => row.total_records_with_birthplace_data || 1), 10);
  const xScale = value => pad.left + (Math.log10(Math.max(value, 1)) / Math.log10(maxKnown)) * (width - pad.left - pad.right);
  const yScale = value => pad.top + (1 - Math.min(100, Math.max(0, value || 0)) / 100) * (height - pad.top - pad.bottom);
  const smallRows = rows.filter(row => (row.total_records_with_birthplace_data || 0) <= 29 && !isExceptionalNoc(row));
  const largeRows = rows.filter(row => (row.total_records_with_birthplace_data || 0) >= 100 && !isExceptionalNoc(row));
  const smallMean = mean(smallRows.map(row => row.foreign_born_pct || 0));
  const largeMean = mean(largeRows.map(row => row.foreign_born_pct || 0));
  const outlierLabelConfig = {
    Haiti: { dx: 8, dy: 18, anchor: 'start' },
    Samoa: { dx: 9, dy: -8, anchor: 'start' },
    Palestine: { dx: 9, dy: -10, anchor: 'start' },
    Bahrain: { dx: -10, dy: -10, anchor: 'end' },
    EOR: { dx: 8, dy: 18, anchor: 'start' },
    AIN: { dx: 8, dy: 18, anchor: 'start' }
  };

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" class="chart-svg">
      <line x1="${pad.left}" y1="${height - pad.bottom}" x2="${width - pad.right}" y2="${height - pad.bottom}" class="axis-line"></line>
      <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}" class="axis-line"></line>
      ${Number.isFinite(smallMean) ? `<line x1="${pad.left}" y1="${yScale(smallMean)}" x2="${width - pad.right}" y2="${yScale(smallMean)}" class="mean-line"></line>
        <text x="${pad.left + 8}" y="${yScale(smallMean) - 5}" class="chart-label">small mean ${formatPct(smallMean)}%</text>` : ''}
      ${Number.isFinite(largeMean) ? `<line x1="${pad.left}" y1="${yScale(largeMean)}" x2="${width - pad.right}" y2="${yScale(largeMean)}" class="mean-line muted"></line>
        <text x="${pad.left + 8}" y="${yScale(largeMean) + 14}" class="chart-label">large mean ${formatPct(largeMean)}%</text>` : ''}
      <text x="${width / 2}" y="${height - 8}" class="chart-label centered">known birthplaces, log scale</text>
      <text x="16" y="${height / 2}" class="chart-label rotated" transform="rotate(-90 16 ${height / 2})">foreign-born share</text>
      <text x="${width - 180}" y="22" class="chart-label">gold = EOR/AIN caveat</text>
    </svg>
  `;

  const svg = container.querySelector('svg');
  rows.forEach(row => {
    const circle = createSvgElement('circle', {
      cx: xScale(row.total_records_with_birthplace_data || 1),
      cy: yScale(row.foreign_born_pct || 0),
      r: isExceptionalNoc(row) ? 5.5 : 4,
      class: isExceptionalNoc(row) ? 'scatter-dot exceptional' : 'scatter-dot'
    });
    circle.appendChild(createSvgElement('title', {}, `${row.country} (${row.noc}): ${formatPct(row.foreign_born_pct)}%, ${formatNumber(row.total_records_with_birthplace_data)} with recorded birthplace data`));
    circle.addEventListener('click', () => openDetailDrawer('country', row));
    svg.appendChild(circle);

    const labelConfig = outlierLabelConfig[row.country] || outlierLabelConfig[row.noc];
    if (labelConfig) {
      const label = createSvgElement('text', {
        x: xScale(row.total_records_with_birthplace_data || 1) + labelConfig.dx,
        y: yScale(row.foreign_born_pct || 0) + labelConfig.dy,
        class: isExceptionalNoc(row) ? 'scatter-label exceptional' : 'scatter-label',
        'text-anchor': labelConfig.anchor,
        role: 'button',
        tabindex: '0'
      }, row.noc === 'EOR' || row.noc === 'AIN' ? row.noc : row.country);
      label.addEventListener('click', () => openDetailDrawer('country', row));
      label.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          openDetailDrawer('country', row);
        }
      });
      svg.appendChild(label);
    }
  });
}

function renderMedalDumbbell() {
  const container = document.getElementById('medal-dumbbell');
  const rows = countryStats
    .filter(row => (row.medal_count || row.medal_winning_athletes || 0) > 0 && Number.isFinite(row.diaspora_medal_pct))
    .sort((a, b) => (b.medal_winning_athletes || b.medal_count || 0) - (a.medal_winning_athletes || a.medal_count || 0))
    .slice(0, 15);

  if (!rows.length) {
    container.innerHTML = '<p class="note">Medal join fields are not present in the current JSON yet. This chart will render once Task 3 data is generated.</p>';
    return;
  }

  const width = 760;
  const rowHeight = 24;
  const height = 48 + rows.length * rowHeight;
  const pad = { top: 18, right: 42, bottom: 28, left: 132 };
  const xScale = value => pad.left + (Math.min(100, Math.max(0, value || 0)) / 100) * (width - pad.left - pad.right);

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" class="chart-svg">
      <line x1="${pad.left}" y1="${height - pad.bottom}" x2="${width - pad.right}" y2="${height - pad.bottom}" class="axis-line"></line>
      <text x="${pad.left}" y="${height - 8}" class="chart-label">0%</text>
      <text x="${width - pad.right - 28}" y="${height - 8}" class="chart-label">100%</text>
      <text x="${width - 220}" y="18" class="chart-label">blue = delegation, gold = medalists</text>
      ${rows.map((row, index) => {
        const y = pad.top + 24 + index * rowHeight;
        const delegation = row.foreign_born_pct || 0;
        const medals = row.diaspora_medal_pct || 0;
        return `
          <text x="4" y="${y + 4}" class="chart-label">${escapeHtml(row.noc || row.country)}</text>
          <line x1="${xScale(delegation)}" y1="${y}" x2="${xScale(medals)}" y2="${y}" class="dumbbell-line"></line>
          <circle cx="${xScale(delegation)}" cy="${y}" r="4" class="dumbbell-dot delegation"><title>${escapeHtml(row.country)} delegation: ${formatPct(delegation)}%</title></circle>
          <circle cx="${xScale(medals)}" cy="${y}" r="5" class="dumbbell-dot medals"><title>${escapeHtml(row.country)} medalists: ${formatPct(medals)}%</title></circle>
        `;
      }).join('')}
    </svg>
  `;
}

function renderCityHubTable() {
  const tbody = document.getElementById('city-hubs');
  tbody.innerHTML = '';

  cityStatsData
    .filter(city => (city.diaspora_count || 0) > 0)
    .sort((a, b) => (b.diaspora_count || 0) - (a.diaspora_count || 0))
    .slice(0, TOP_CITY_LIMIT)
    .forEach(city => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td><button class="table-row-button" type="button">${escapeHtml(city.city)}</button></td>
        <td>${escapeHtml(city.birth_country)}</td>
        <td>${formatNumber(city.diaspora_count)}</td>
        <td>${escapeHtml((city.represented_nocs || []).join(', '))}</td>
      `;
      row.querySelector('button').addEventListener('click', () => openDetailDrawer('city', city));
      tbody.appendChild(row);
    });
}

function renderSportsTab() {
  renderSportChart();
}

function renderSportChart() {
  const container = document.getElementById('sport-chart');
  container.innerHTML = '';
  const metric = sportMode === 'share' ? 'diaspora_pct' : 'diaspora_count';
  const rows = sportStatsData
    .filter(row => (row.total_records_with_birthplace_data || 0) >= SPORT_MIN_KNOWN_BIRTHPLACES && (row[metric] || 0) > 0)
    .sort((a, b) => (b[metric] || 0) - (a[metric] || 0));
  const maxValue = Math.max(...rows.map(row => row[metric] || 0), 1);

  rows.forEach(row => {
    const value = row[metric] || 0;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'bar-row';
    button.setAttribute('aria-label', `${row.sport}, ${sportMode === 'share' ? `${formatPct(value)}%` : `${formatNumber(value)} athletes`}`);
    button.addEventListener('click', () => openDetailDrawer('sport', row));
    button.innerHTML = `
      <span class="bar-label"><span class="bar-name">${escapeHtml(row.sport)}</span><span class="bar-code">${formatNumber(row.total_records_with_birthplace_data)} recorded</span></span>
      <span class="bar-track"><span class="bar-fill" style="width: ${Math.max(2, (value / maxValue) * 100)}%"></span></span>
      <span class="bar-value">${sportMode === 'share' ? `${formatPct(value)}%` : formatNumber(value)}</span>
    `;
    container.appendChild(button);
  });
}

function renderTrainingTab() {
  const summary = trainingStatsData.summary || {};
  document.getElementById('training-known-count').textContent = formatNumber(summary.known_residence_count);
  document.getElementById('training-home-count').textContent = formatNumber(summary.home_residence_count);
  document.getElementById('training-abroad-count').textContent = formatNumber(summary.abroad_residence_count);
  document.getElementById('training-abroad-share').textContent = `${formatPct(summary.abroad_residence_pct)}%`;
  renderTrainingHostRanking();
  renderTrainingTeamRanking();
  renderTrainingCorridorTable();
  renderTrainingHostMap();
}

function renderTrainingHostRanking() {
  const container = document.getElementById('training-host-ranking');
  const rows = (trainingStatsData.host_countries || []).slice(0, TOP_COUNTRY_LIMIT);
  const maxValue = Math.max(...rows.map(row => row.athlete_count || 0), 1);
  container.innerHTML = '';

  rows.forEach(row => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'bar-row';
    button.addEventListener('click', () => selectTrainingHost(row.host_country, true));
    button.innerHTML = `
      <span class="bar-label">
        <span class="bar-name">${escapeHtml(row.host_country)}</span>
        <span class="bar-code">${formatNumber(row.represented_team_count)} represented teams</span>
      </span>
      <span class="bar-track"><span class="bar-fill" style="width: ${Math.max(2, ((row.athlete_count || 0) / maxValue) * 100)}%"></span></span>
      <span class="bar-value">${formatNumber(row.athlete_count)}</span>
    `;
    container.appendChild(button);
  });
}

function selectTrainingHost(hostCountry, openDrawer = false) {
  const host = (trainingStatsData.host_countries || []).find(
    row => row.host_country === hostCountry
  );
  if (!host) return;
  selectedTrainingHost = host.host_country;
  renderTrainingHostMap();
  if (openDrawer) openDetailDrawer('trainingHost', host);
}

function getTrainingHostCoords(host) {
  return hasValidCoords(host.coords) ? host.coords : getCountryCoords(host.host_country);
}

function resetTrainingMapView() {
  if (trainingMap) trainingMap.setView([20, 0], 2, { animate: true });
}

function getTrainingHostRadius(count) {
  return Math.min(26, Math.max(7, 5 + Math.sqrt(Math.max(count || 0, 0)) * 0.9));
}

function renderTrainingHostMap() {
  if (!trainingMap || !trainingHostLayer || !trainingRouteLayer) return;
  const allHosts = trainingStatsData.host_countries || [];
  const hosts = allHosts.slice(0, trainingHostLimit);
  const selectedHost = allHosts.find(row => row.host_country === selectedTrainingHost);
  const visibleSelected = selectedHost && hosts.some(row => row.host_country === selectedHost.host_country);

  trainingHostLayer.clearLayers();
  trainingRouteLayer.clearLayers();
  document.querySelectorAll('[data-training-host-limit]').forEach(button => {
    const limit = button.dataset.trainingHostLimit === 'all'
      ? Infinity
      : Number(button.dataset.trainingHostLimit);
    button.classList.toggle('active', limit === trainingHostLimit);
  });
  document.getElementById('clear-training-host').classList.toggle('hidden', !selectedHost);

  hosts.forEach(host => {
    const coords = getTrainingHostCoords(host);
    if (!coords) return;
    const isSelected = host.host_country === selectedTrainingHost;
    const marker = L.circleMarker(coords, {
      radius: getTrainingHostRadius(host.athlete_count),
      fillColor: isSelected ? '#f59e0b' : '#22c55e',
      color: isSelected ? '#fef3c7' : '#bbf7d0',
      weight: isSelected ? 3 : 1.5,
      opacity: selectedHost && !isSelected ? 0.3 : 0.9,
      fillOpacity: selectedHost && !isSelected ? 0.16 : 0.62
    });
    marker.bindTooltip(`
      <strong>${escapeHtml(host.host_country)}</strong><br>
      Athletes based abroad: <strong>${formatNumber(host.athlete_count)}</strong><br>
      Represented teams: <strong>${formatNumber(host.represented_team_count)}</strong><br>
      <em>Click to inspect incoming routes</em>
    `, { className: 'custom-leaflet-tooltip', direction: 'top', offset: [0, -getTrainingHostRadius(host.athlete_count)] });
    marker.on('click', () => selectTrainingHost(host.host_country, true));
    marker.addTo(trainingHostLayer);
  });

  const status = document.getElementById('training-map-status');
  if (!selectedHost) {
    status.textContent = `Showing ${formatNumber(hosts.length)} residence hosts. Select a host country to reveal its five largest incoming routes.`;
    return;
  }

  const routes = (trainingStatsData.corridors || [])
    .filter(row => row.residence_country === selectedHost.host_country)
    .sort((a, b) => (b.athlete_count || 0) - (a.athlete_count || 0))
    .slice(0, 5);
  const destination = getTrainingHostCoords(selectedHost);

  routes.forEach(route => {
    const origin = hasValidCoords(route.from_coords)
      ? route.from_coords
      : getCountryCoords(route.rep_country);
    if (!origin || !destination) return;
    const line = L.polyline(curveBetween(origin, destination), {
      color: '#f59e0b',
      weight: Math.min(7, Math.max(2, Math.sqrt(route.athlete_count || 1))),
      opacity: 0.82,
      lineCap: 'round'
    });
    line.bindTooltip(`
      <strong>${escapeHtml(route.rep_country)} -> ${escapeHtml(route.residence_country)}</strong><br>
      Athletes: <strong>${formatNumber(route.athlete_count)}</strong>
    `, { className: 'custom-leaflet-tooltip' });
    line.on('click', () => openDetailDrawer('trainingCorridor', route));
    line.addTo(trainingRouteLayer);
  });

  status.textContent = `${selectedHost.host_country} selected: showing its top ${formatNumber(routes.length)} incoming routes. The host drawer lists every represented team.`;
  if (visibleSelected && destination) trainingMap.panTo(destination, { animate: true, duration: 0.35 });
}

function renderTrainingTeamRanking() {
  const container = document.getElementById('training-team-ranking');
  const rows = (trainingStatsData.team_stats || [])
    .filter(row => (row.known_residence_count || 0) >= 10)
    .sort((a, b) => (b.abroad_residence_pct || 0) - (a.abroad_residence_pct || 0))
    .slice(0, TOP_COUNTRY_LIMIT);
  container.innerHTML = '';

  rows.forEach(row => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'bar-row';
    button.addEventListener('click', () => openDetailDrawer('trainingTeam', row));
    button.innerHTML = `
      <span class="bar-label">
        <span class="bar-name">${escapeHtml(row.country)}</span>
        <span class="bar-code">${escapeHtml(row.noc)} · ${formatNumber(row.known_residence_count)} known</span>
      </span>
      <span class="bar-track"><span class="bar-fill" style="width: ${Math.max(2, row.abroad_residence_pct || 0)}%"></span></span>
      <span class="bar-value">${formatPct(row.abroad_residence_pct)}%</span>
    `;
    container.appendChild(button);
  });
}

function renderTrainingCorridorTable() {
  const tbody = document.getElementById('training-corridor-rows');
  const input = document.getElementById('training-min-count');
  const minCount = Math.max(1, Number(input?.value || 3));
  const rows = (trainingStatsData.corridors || [])
    .filter(row => (row.athlete_count || 0) >= minCount)
    .sort((a, b) => (b.athlete_count || 0) - (a.athlete_count || 0));

  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="4">No residence corridors match this threshold.</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map((row, index) => `
    <tr>
      <td><button class="table-row-button" type="button" data-training-corridor-index="${index}">${escapeHtml(row.rep_country || 'Unknown')}</button></td>
      <td>${escapeHtml(row.residence_country || 'Unknown')}</td>
      <td>${formatNumber(row.athlete_count)}</td>
      <td>${escapeHtml(topSportsText(row.sports))}</td>
    </tr>
  `).join('');

  tbody.querySelectorAll('[data-training-corridor-index]').forEach((button, index) => {
    button.addEventListener('click', () => openDetailDrawer('trainingCorridor', rows[index]));
  });
}

function renderCorridorsTab() {
  setupCorridorSurface();
  renderCorridorTypeFilters();
  renderCorridorTable();
}

function setupCorridorSurface() {
  const panel = document.getElementById('corridors-panel');
  if (!panel) return;

  const heading = panel.querySelector('.corridor-heading h2');
  const subtitle = panel.querySelector('.corridor-heading p');
  if (heading) heading.textContent = 'Where athletes flow';
  if (subtitle) subtitle.textContent = 'Each row is a one-direction route: born in one country, competed for another. 548 routes total; typed where the pattern is clear.';

  const asymmetryHeader = panel.querySelector('[data-corridor-sort="asymmetry"]');
  if (asymmetryHeader) asymmetryHeader.textContent = 'Reverse flow';

  if (document.getElementById('corridor-filter-panel')) return;

  const tableWrap = panel.querySelector('.table-wrap');
  if (!tableWrap) return;

  const filterPanel = document.createElement('div');
  filterPanel.className = 'corridor-filter-panel';
  filterPanel.id = 'corridor-filter-panel';
  filterPanel.innerHTML = `
    <div>
      <div class="filter-label">Corridor type</div>
      <div class="corridor-chip-row" id="corridor-type-filters" aria-label="Filter by corridor type"></div>
    </div>
    <div class="corridor-country-filters">
      <label class="field-control">
        Born in
        <input type="search" id="corridor-birth-filter" list="corridor-birth-countries" placeholder="Any birth country">
      </label>
      <label class="field-control">
        Competed for
        <input type="search" id="corridor-rep-filter" list="corridor-rep-countries" placeholder="Any represented country">
      </label>
      <datalist id="corridor-birth-countries"></datalist>
      <datalist id="corridor-rep-countries"></datalist>
    </div>
    <div class="corridor-filter-summary" id="corridor-filter-summary"></div>
  `;
  tableWrap.parentNode.insertBefore(filterPanel, tableWrap);

  populateCountryFilterOptions();
  document.getElementById('corridor-birth-filter').addEventListener('input', event => {
    corridorBirthFilter = event.target.value.trim();
    renderCorridorTable();
  });
  document.getElementById('corridor-rep-filter').addEventListener('input', event => {
    corridorRepFilter = event.target.value.trim();
    renderCorridorTable();
  });
}

function populateCountryFilterOptions() {
  const birthList = document.getElementById('corridor-birth-countries');
  const repList = document.getElementById('corridor-rep-countries');
  if (!birthList || !repList) return;

  const birthCountries = uniqueSorted(corridorStatsData.map(row => row.birth_country).filter(Boolean));
  const repCountries = uniqueSorted(corridorStatsData.map(row => row.rep_country).filter(Boolean));
  birthList.innerHTML = birthCountries.map(country => `<option value="${escapeHtml(country)}"></option>`).join('');
  repList.innerHTML = repCountries.map(country => `<option value="${escapeHtml(country)}"></option>`).join('');
}

function renderCorridorTypeFilters() {
  const container = document.getElementById('corridor-type-filters');
  if (!container) return;

  const typeCounts = corridorStatsData.reduce((counts, row) => {
    const type = getCorridorType(row);
    if (!counts[type]) counts[type] = { routes: 0, athletes: 0 };
    counts[type].routes += 1;
    counts[type].athletes += row.athlete_count || 0;
    return counts;
  }, {});
  const typeOrder = Object.keys(CORRIDOR_TYPE_LABELS).filter(type => typeCounts[type]);

  container.innerHTML = typeOrder.map(type => {
    const active = activeCorridorTypes.has(type);
    const count = typeCounts[type];
    return `
      <button class="corridor-type-chip${active ? ' active' : ''}" type="button" data-corridor-type-filter="${escapeHtml(type)}" style="--chip-color: ${getCorridorTypeColor(type)}" aria-pressed="${String(active)}">
        <span>${escapeHtml(formatTypeLabel(type))}</span>
        <strong>${formatNumber(count.routes)}</strong>
      </button>
    `;
  }).join('');

  container.querySelectorAll('[data-corridor-type-filter]').forEach(button => {
    button.addEventListener('click', () => {
      const type = button.dataset.corridorTypeFilter;
      if (activeCorridorTypes.has(type)) activeCorridorTypes.delete(type);
      else activeCorridorTypes.add(type);
      renderCorridorsTab();
    });
  });
}

function renderCorridorTable() {
  const tbody = document.getElementById('corridor-rows');
  const minCount = Math.max(1, Number(document.getElementById('corridor-min-count').value || 3));
  document.querySelectorAll('[data-corridor-sort]').forEach(button => {
    button.classList.toggle('active', button.dataset.corridorSort === corridorSort.key);
  });

  if (!corridorStatsData.length) {
    tbody.innerHTML = '<tr><td colspan="6">No corridor records available.</td></tr>';
    return;
  }

  const rows = getFilteredCorridorRows(minCount).sort(compareCorridors);
  updateCorridorFilterSummary(rows, minCount);

  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="6">No corridor records match the current filters.</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map((row, index) => {
    const type = getCorridorType(row);
    return `
      <tr>
        <td><button class="table-row-button" type="button" data-corridor-index="${index}">${escapeHtml(row.birth_country || 'Unknown')} &rarr; ${escapeHtml(row.rep_country || 'Unknown')}</button></td>
        <td>${typeBadgeHtml(type)}</td>
        <td>${formatNumber(row.athlete_count)}</td>
        <td>${formatNumber(row.medal_count)}</td>
        <td>${reverseFlowHtml(row)}</td>
        <td>${escapeHtml(topSportsText(row.sports))}</td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('[data-corridor-index]').forEach((button, index) => {
    button.addEventListener('click', () => openDetailDrawer('corridor', rows[index]));
  });
}

function getFilteredCorridorRows(minCount) {
  const birthQuery = normalizeFilterText(corridorBirthFilter);
  const repQuery = normalizeFilterText(corridorRepFilter);
  return corridorStatsData.filter(row => {
    const type = getCorridorType(row);
    const matchesType = !activeCorridorTypes.size || activeCorridorTypes.has(type);
    const matchesBirth = !birthQuery || normalizeFilterText(row.birth_country).includes(birthQuery);
    const matchesRep = !repQuery || normalizeFilterText(row.rep_country).includes(repQuery);
    return (row.athlete_count || 0) >= minCount && matchesType && matchesBirth && matchesRep;
  });
}

function updateCorridorFilterSummary(rows, minCount) {
  const summary = document.getElementById('corridor-filter-summary');
  if (!summary) return;
  const athletes = rows.reduce((sum, row) => sum + (row.athlete_count || 0), 0);
  const filters = [];
  if (activeCorridorTypes.size) filters.push(`${activeCorridorTypes.size} type${activeCorridorTypes.size === 1 ? '' : 's'}`);
  if (corridorBirthFilter) filters.push(`born in "${corridorBirthFilter}"`);
  if (corridorRepFilter) filters.push(`competed for "${corridorRepFilter}"`);
  summary.textContent = `${formatNumber(rows.length)} routes, ${formatNumber(athletes)} athletes shown with min ${formatNumber(minCount)}${filters.length ? ` and ${filters.join(', ')}` : ''}.`;
}

function compareCorridors(a, b) {
  const direction = corridorSort.direction === 'asc' ? 1 : -1;
  const key = corridorSort.key;
  const aValue = key === 'corridor' ? `${a.birth_country || ''} ${a.rep_country || ''}` : key === 'corridor_type' ? getCorridorType(a) : Number(a[key] || 0);
  const bValue = key === 'corridor' ? `${b.birth_country || ''} ${b.rep_country || ''}` : key === 'corridor_type' ? getCorridorType(b) : Number(b[key] || 0);
  if (typeof aValue === 'string') return aValue.localeCompare(bValue) * direction;
  return (aValue - bValue) * direction;
}

function setMapView(view) {
  stopMigrationStory();
  currentViewMode = view;
  document.getElementById('view-btn-country').classList.toggle('active', view === 'country');
  document.getElementById('view-btn-city').classList.toggle('active', view === 'city');
  document.getElementById('view-btn-corridors').classList.toggle('active', view === 'corridors');
  document.getElementById('city-filter-container').classList.toggle('hidden', view !== 'city');
  renderCurrentMapView();
}

function renderCurrentMapView() {
  if (!activeLayerGroup) return;
  updateMapLegend();
  if (currentViewMode === 'country') renderCountryBubbles();
  if (currentViewMode === 'city') renderCityBubbles();
  if (currentViewMode === 'corridors') renderCorridorLayer();
}

function updateMapLegend() {
  const legend = document.querySelector('.map-legend');
  if (!legend) return;
  if (migrationStoryState.mode) {
    const isMedalistStory = migrationStoryState.mode === 'medalists';
    legend.innerHTML = `
      <div>Animated routes: ${isMedalistStory ? 'medal-winning cross-border athletes' : 'all cross-border athletes'}</div>
      <div>Direction: birthplace -> represented team</div>
      <div>Arrow + moving point show travel direction</div>
      <div>Line width: athlete count</div>
      <div>Color: ${isMedalistStory ? 'medal gold' : 'corridor type'}</div>
    `;
    return;
  }
  if (currentViewMode === 'corridors') {
    legend.innerHTML = `
      <div>Line width: athlete count</div>
      <div>Color: corridor type</div>
      <div class="corridor-legend">
        ${Object.entries(CORRIDOR_TYPE_LABELS).slice(0, 6).map(([type, label]) => `
          <span><i style="background:${getCorridorTypeColor(type)}"></i>${escapeHtml(label)}</span>
        `).join('')}
      </div>
    `;
    return;
  }
  legend.innerHTML = `
    <div>Marker size: athlete count</div>
    <div>Color: foreign-born share</div>
    <div class="legend-swatches" aria-hidden="true">
      <span></span>
      <span></span>
      <span></span>
    </div>
    <div class="legend-scale"><span>Low</span><span>High</span></div>
  `;
}

function getColorForPct(pct) {
  if (pct < 10) return '#1e3a8a';
  if (pct < 25) return '#2563eb';
  return '#60a5fa';
}

function getRadiusForCount(count) {
  return Math.min(24, Math.max(5, 5 + Math.log2((count || 0) + 1) * 2.8));
}

function getRadiusForShare(pct) {
  return Math.min(24, Math.max(5, 5 + ((pct || 0) / 100) * 22));
}

function buildRepresentedTeamCityMarkers() {
  const markerMap = new Map();
  let skippedCities = 0;
  let skippedAthletes = 0;

  cityStatsData.forEach(city => {
    const coords = resolveCityCoords(city);
    if (!coords) {
      skippedCities += 1;
      skippedAthletes += (city.all_athletes || []).length;
      return;
    }

    (city.all_athletes || []).forEach(athlete => {
      const repNoc = athlete.rep_noc || 'UNKNOWN';
      const key = `${city.id || `${city.city}|${city.birth_country}`}|${repNoc}`;

      if (!markerMap.has(key)) {
        markerMap.set(key, {
          type: 'representedTeamCity',
          city: city.city,
          birth_country: city.birth_country,
          coords,
          rep_noc: repNoc,
          rep_country: athlete.rep_country || repNoc,
          total_athletes: 0,
          foreign_born_count: 0,
          athletes: []
        });
      }

      const marker = markerMap.get(key);
      marker.total_athletes += 1;
      if (athlete.is_diaspora) marker.foreign_born_count += 1;
      marker.athletes.push(athlete);
    });
  });

  if (skippedCities > 0) {
    console.info(`Excluded ${skippedCities} birthplace cities (${skippedAthletes} athletes) from the map because coordinates were missing or invalid.`);
  }

  return Array.from(markerMap.values()).map(marker => ({
    ...marker,
    foreign_born_pct: marker.total_athletes ? (marker.foreign_born_count / marker.total_athletes) * 100 : 0
  }));
}

function hasValidCoords(coords) {
  if (!Array.isArray(coords) || coords.length < 2) return false;
  const [lat, lng] = coords;
  return Number.isFinite(lat) && Number.isFinite(lng) && !(lat === 0 && lng === 0) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
}

function resolveCityCoords(city) {
  const override = CITY_COORD_OVERRIDES[cityKey(city.city, city.birth_country)];
  if (override) return override;
  if (!hasValidCoords(city.coords)) return null;
  if (coordsMatchCountryCentroid(city.coords, city.birth_country)) return null;
  return city.coords;
}

function coordsMatchCountryCentroid(coords, countryName) {
  const country = countryStats.find(row => row.country === countryName);
  if (!country || !hasValidCoords(country.coords)) return false;
  return Math.abs(coords[0] - country.coords[0]) < 0.0001 && Math.abs(coords[1] - country.coords[1]) < 0.0001;
}

function cityKey(city, country) {
  return `${String(city || '').trim().toLowerCase()}|${String(country || '').trim().toLowerCase()}`;
}

function renderCountryBubbles() {
  activeLayerGroup.clearLayers();

  representedTeamCityMarkers.forEach(marker => {
    const foreignPct = marker.foreign_born_pct || 0;
    const foreignCount = marker.foreign_born_count || 0;
    const radius = currentSizeMode === 'share' ? getRadiusForShare(foreignPct) : getRadiusForCount(marker.total_athletes);
    const color = getColorForPct(foreignPct);

    const circleMarker = L.circleMarker(marker.coords, {
      radius,
      fillColor: color,
      color: '#e2e8f0',
      weight: 1,
      opacity: 0.62,
      fillOpacity: 0.56
    });

    circleMarker.bindTooltip(`
      <strong>${escapeHtml(marker.city)}, ${escapeHtml(marker.birth_country)}</strong><br>
      Represented team: <strong>${escapeHtml(marker.rep_country)} (${escapeHtml(marker.rep_noc)})</strong><br>
      Athletes born here: <strong>${formatNumber(marker.total_athletes)}</strong><br>
      Foreign-born: <strong>${formatNumber(foreignCount)} (${formatPct(foreignPct)}%)</strong>
    `, { className: 'custom-leaflet-tooltip', direction: 'top', offset: [0, -radius] });

    circleMarker.on('mouseover', () => circleMarker.setStyle({ color: '#f59e0b', opacity: 1, fillOpacity: 0.78, weight: 2 }));
    circleMarker.on('mouseout', () => circleMarker.setStyle({ color: '#e2e8f0', opacity: 0.62, fillOpacity: 0.56, weight: 1 }));
    circleMarker.on('click', () => openDetailDrawer('representedTeamCity', marker));
    circleMarker.addTo(activeLayerGroup);
  });
}

function renderCityBubbles() {
  activeLayerGroup.clearLayers();
  const hubsOnly = document.getElementById('filter-diaspora-hubs-only').checked;
  const citiesToRender = hubsOnly ? cityStatsData.filter(city => city.diaspora_count > 0) : cityStatsData;
  let skippedCities = 0;
  let skippedAthletes = 0;

  citiesToRender.forEach(city => {
    const coords = resolveCityCoords(city);
    if (!coords) {
      skippedCities += 1;
      skippedAthletes += (city.all_athletes || []).length;
      return;
    }

    const diasporaPct = city.diaspora_pct || 0;
    const diasporaCount = city.diaspora_count || 0;
    const totalBorn = city.total_born || 0;
    const radius = currentSizeMode === 'share' ? getRadiusForShare(diasporaPct) : getRadiusForCount(diasporaCount || totalBorn);
    const color = getColorForPct(diasporaPct);

    const circleMarker = L.circleMarker(coords, {
      radius,
      fillColor: color,
      color: diasporaCount > 0 ? '#f59e0b' : '#94a3b8',
      weight: diasporaCount > 0 ? 1.5 : 1,
      opacity: diasporaCount > 0 ? 0.76 : 0.38,
      fillOpacity: diasporaCount > 0 ? 0.58 : 0.24
    });

    circleMarker.bindTooltip(`
      <strong>${escapeHtml(city.city)}, ${escapeHtml(city.birth_country)}</strong><br>
      Athletes born here: <strong>${formatNumber(totalBorn)}</strong><br>
      Cross-border representation: <strong>${formatNumber(diasporaCount)} (${formatPct(diasporaPct)}%)</strong><br>
      Represented teams: <strong>${escapeHtml((city.represented_nocs || []).join(', '))}</strong>
    `, { className: 'custom-leaflet-tooltip', direction: 'top', offset: [0, -radius] });

    circleMarker.on('mouseover', () => circleMarker.setStyle({ color: '#fbbf24', opacity: 1, fillOpacity: 0.78, weight: 2 }));
    circleMarker.on('mouseout', () => circleMarker.setStyle({
      color: diasporaCount > 0 ? '#f59e0b' : '#94a3b8',
      opacity: diasporaCount > 0 ? 0.76 : 0.38,
      fillOpacity: diasporaCount > 0 ? 0.58 : 0.24,
      weight: diasporaCount > 0 ? 1.5 : 1
    }));
    circleMarker.on('click', () => openDetailDrawer('city', city));
    circleMarker.addTo(activeLayerGroup);
  });

  if (!loggedInvalidCityCoords && skippedCities > 0) {
    console.info(`Excluded ${skippedCities} city records (${skippedAthletes} athletes) from the city map because coordinates were missing or invalid.`);
    loggedInvalidCityCoords = true;
  }
}

function renderCorridorLayer() {
  activeLayerGroup.clearLayers();
  const minCount = Math.max(1, Number(document.getElementById('corridor-min-count').value || 3));
  corridorStatsData
    .filter(row => (row.athlete_count || 0) >= minCount)
    .forEach(row => {
      const from = getCountryCoords(row.birth_country);
      const to = getCountryCoords(row.rep_country);
      if (!from || !to) return;
      const type = getCorridorType(row);
      const line = L.polyline(curveBetween(from, to), {
        color: getCorridorTypeColor(type),
        weight: Math.min(7, Math.max(1.5, Math.log2((row.athlete_count || 1) + 1))),
        opacity: 0.66
      });
      line.bindTooltip(`
        <strong>${escapeHtml(row.birth_country)} -> ${escapeHtml(row.rep_country)}</strong><br>
        ${escapeHtml(formatTypeLabel(type))}<br>
        Athletes: <strong>${formatNumber(row.athlete_count)}</strong><br>
        Medals: <strong>${formatNumber(row.medal_count)}</strong>
      `, { className: 'custom-leaflet-tooltip' });
      line.on('click', () => openDetailDrawer('corridor', row));
      line.addTo(activeLayerGroup);
    });
}

function createEmptyMigrationStoryState() {
  return {
    mode: null,
    rows: [],
    nextIndex: 0,
    featuredCount: 0,
    featuredDuration: 0,
    networkDuration: 0,
    activeFeaturedIndex: -1,
    activeCurve: [],
    movingMarker: null,
    revealedAthletes: 0,
    totalAthletes: 0,
    mappedAthletes: 0,
    duration: 0,
    elapsed: 0,
    startedAt: 0,
    frameId: null,
    paused: false,
    complete: false,
    lastUiUpdate: 0,
    narrationPhase: ''
  };
}

function buildMigrationStoryRows(mode) {
  return corridorStatsData
    .map(row => {
      const athletes = Array.isArray(row.athletes) ? row.athletes : [];
      const storyAthletes = mode === 'medalists'
        ? athletes.filter(athlete => Number(athlete.medal_count || 0) > 0)
        : athletes;
      const storyCount = mode === 'medalists'
        ? storyAthletes.length
        : Number(row.athlete_count || athletes.length);
      const storySports = Array.from(storyAthletes.reduce((counts, athlete) => {
        const sport = athlete.sport || 'Unknown sport';
        counts.set(sport, (counts.get(sport) || 0) + 1);
        return counts;
      }, new Map()).entries())
        .map(([sport, count]) => ({ sport, count }))
        .sort((a, b) => b.count - a.count || a.sport.localeCompare(b.sport));
      return {
        ...row,
        athletes: storyAthletes,
        athlete_count: storyCount,
        story_count: storyCount,
        story_medals: storyAthletes.reduce((sum, athlete) => sum + Number(athlete.medal_count || 0), 0),
        story_sports: storySports,
        from_coords: getCountryCoords(row.birth_country),
        to_coords: getCountryCoords(row.rep_country)
      };
    })
    .filter(row => row.story_count > 0)
    .sort((a, b) => b.story_count - a.story_count || String(a.birth_country).localeCompare(String(b.birth_country)))
    .map((row, storyRank) => ({ ...row, story_rank: storyRank }));
}

function startMigrationStory(mode) {
  if (!map || !activeLayerGroup || !['all', 'medalists'].includes(mode)) return;

  stopMigrationStory();
  currentViewMode = 'corridors';
  document.getElementById('view-btn-country').classList.remove('active');
  document.getElementById('view-btn-city').classList.remove('active');
  document.getElementById('view-btn-corridors').classList.add('active');
  document.getElementById('city-filter-container').classList.add('hidden');

  const allRows = buildMigrationStoryRows(mode);
  const mappedRows = allRows
    .filter(row => row.from_coords && row.to_coords)
    .map((row, storyRank) => ({ ...row, story_rank: storyRank }));
  const totalAthletes = allRows.reduce((sum, row) => sum + row.story_count, 0);
  const mappedAthletes = mappedRows.reduce((sum, row) => sum + row.story_count, 0);
  const featuredCount = Math.min(mode === 'medalists' ? 12 : 15, mappedRows.length);
  const featuredDuration = mode === 'medalists' ? 1600 : 1400;
  const networkDuration = mode === 'medalists' ? 7000 : 9000;

  migrationStoryState = {
    ...createEmptyMigrationStoryState(),
    mode,
    rows: mappedRows,
    featuredCount,
    featuredDuration,
    networkDuration,
    totalAthletes,
    mappedAthletes,
    duration: (featuredCount * featuredDuration) + networkDuration,
    startedAt: performance.now()
  };

  activeLayerGroup.clearLayers();
  migrationFocusLayer.clearLayers();
  map.setView([20, 0], 2.25, { animate: false });
  document.querySelector('.map-frame').classList.add('migration-story-active');
  document.getElementById('migration-story-overlay').hidden = false;
  document.querySelectorAll('[data-migration-story]').forEach(button => {
    const active = button.dataset.migrationStory === mode;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  document.getElementById('migration-story-pause').disabled = false;
  document.getElementById('migration-story-pause').textContent = 'Pause';
  document.getElementById('migration-story-restart').disabled = false;
  document.querySelectorAll('[data-size-mode]').forEach(button => { button.disabled = true; });
  updateMapLegend();
  updateMigrationStoryOverlay(0);

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    migrationStoryState.rows.forEach(row => addMigrationStoryLine(row, row.story_rank < featuredCount));
    migrationStoryState.nextIndex = migrationStoryState.rows.length;
    migrationStoryState.revealedAthletes = mappedAthletes;
    finishMigrationStory();
    return;
  }

  migrationStoryState.frameId = requestAnimationFrame(runMigrationStoryFrame);
}

function runMigrationStoryFrame(now) {
  if (!migrationStoryState.mode || migrationStoryState.paused) return;

  const elapsed = migrationStoryState.elapsed + (now - migrationStoryState.startedAt);
  const progress = Math.min(1, elapsed / migrationStoryState.duration);
  const featuredPhaseDuration = migrationStoryState.featuredCount * migrationStoryState.featuredDuration;

  if (elapsed < featuredPhaseDuration) {
    const featuredIndex = Math.min(
      migrationStoryState.featuredCount - 1,
      Math.floor(elapsed / migrationStoryState.featuredDuration)
    );
    if (featuredIndex !== migrationStoryState.activeFeaturedIndex) {
      focusMigrationStoryRoute(featuredIndex);
    }
    const routeProgress = (elapsed % migrationStoryState.featuredDuration) / migrationStoryState.featuredDuration;
    moveMigrationStoryMarker(routeProgress);
  } else {
    if (migrationStoryState.activeFeaturedIndex !== -2) {
      migrationFocusLayer.clearLayers();
      migrationStoryState.activeFeaturedIndex = -2;
      renderMigrationNetworkSummary();
    }
    const networkProgress = Math.min(1, (elapsed - featuredPhaseDuration) / migrationStoryState.networkDuration);
    const remainingRows = migrationStoryState.rows.length - migrationStoryState.featuredCount;
    const targetIndex = migrationStoryState.featuredCount + Math.ceil(remainingRows * networkProgress);
    while (migrationStoryState.nextIndex < targetIndex) {
      const row = migrationStoryState.rows[migrationStoryState.nextIndex];
      addMigrationStoryLine(row, false);
      migrationStoryState.revealedAthletes += row.story_count;
      migrationStoryState.nextIndex += 1;
    }
  }

  if (now - migrationStoryState.lastUiUpdate >= 80 || progress >= 1) {
    migrationStoryState.lastUiUpdate = now;
    updateMigrationStoryOverlay(progress);
  }
  if (progress >= 1) {
    finishMigrationStory();
    return;
  }
  migrationStoryState.frameId = requestAnimationFrame(runMigrationStoryFrame);
}

function focusMigrationStoryRoute(index) {
  const state = migrationStoryState;
  const row = state.rows[index];
  if (!row) return;

  migrationFocusLayer.clearLayers();
  while (state.nextIndex <= index) {
    const route = state.rows[state.nextIndex];
    addMigrationStoryLine(route, true);
    state.revealedAthletes += route.story_count;
    state.nextIndex += 1;
  }

  state.activeFeaturedIndex = index;
  state.activeCurve = curveBetween(row.from_coords, row.to_coords);
  const normalizedDestination = normalizeDestinationCoords(row.from_coords, row.to_coords);
  addMigrationEndpoint(row.from_coords, 'Born in', row.birth_country, 'birth');
  addMigrationEndpoint(normalizedDestination, 'Competed for', row.rep_country, 'represented');
  state.movingMarker = L.circleMarker(state.activeCurve[0], {
    radius: 6,
    color: '#ffffff',
    weight: 2,
    fillColor: state.mode === 'medalists' ? '#fbbf24' : getCorridorTypeColor(getCorridorType(row)),
    fillOpacity: 1,
    className: 'migration-moving-marker',
    interactive: false
  }).addTo(migrationFocusLayer);
  renderMigrationRouteCard(row, index);
}

function addMigrationEndpoint(coords, label, country, kind) {
  const marker = L.marker(coords, {
    interactive: false,
    icon: L.divIcon({
      className: 'migration-endpoint-icon',
      html: `<span class="${kind}"><small>${escapeHtml(label)}</small>${escapeHtml(country)}</span>`,
      iconSize: [150, 44],
      iconAnchor: [75, 22]
    })
  });
  marker.addTo(migrationFocusLayer);
}

function moveMigrationStoryMarker(progress) {
  const state = migrationStoryState;
  if (!state.movingMarker || !state.activeCurve.length) return;
  const scaled = Math.max(0, Math.min(1, progress)) * (state.activeCurve.length - 1);
  const index = Math.floor(scaled);
  const nextIndex = Math.min(state.activeCurve.length - 1, index + 1);
  const localProgress = scaled - index;
  const current = state.activeCurve[index];
  const next = state.activeCurve[nextIndex];
  state.movingMarker.setLatLng([
    current[0] + ((next[0] - current[0]) * localProgress),
    current[1] + ((next[1] - current[1]) * localProgress)
  ]);
}

function addMigrationStoryLine(row, featured) {
  const isMedalistStory = migrationStoryState.mode === 'medalists';
  const type = getCorridorType(row);
  const line = L.polyline(curveBetween(row.from_coords, row.to_coords), {
    color: isMedalistStory ? '#fbbf24' : getCorridorTypeColor(type),
    weight: featured
      ? Math.min(7, Math.max(2.4, 2 + Math.log2(row.story_count + 1)))
      : Math.min(3.5, Math.max(0.8, 0.8 + Math.log2(row.story_count + 1) * 0.45)),
    opacity: featured ? 0.78 : (isMedalistStory ? 0.34 : 0.22),
    className: `migration-story-line${featured ? ' featured-story-line' : ' background-story-line'}${isMedalistStory ? ' medalist-story-line' : ''}`
  });

  line.bindTooltip(`
    <strong>${escapeHtml(row.birth_country)} -> ${escapeHtml(row.rep_country)}</strong><br>
    ${isMedalistStory ? 'Medal-winning cross-border athletes' : escapeHtml(formatTypeLabel(type))}: <strong>${formatNumber(row.story_count)}</strong>
  `, { className: 'custom-leaflet-tooltip' });
  line.on('click', () => openDetailDrawer('corridor', row));
  line.addTo(activeLayerGroup);

  const path = line.getElement();
  if (path) {
    path.setAttribute('pathLength', '1');
    path.classList.add('is-revealing');
    if (featured) addMigrationDirectionArrow(path, isMedalistStory);
  }
}

function addMigrationDirectionArrow(path, isMedalistStory) {
  const svg = path.ownerSVGElement;
  if (!svg) return;
  const markerId = isMedalistStory ? 'migration-arrow-medalist' : 'migration-arrow';
  if (!svg.querySelector(`#${markerId}`)) {
    const namespace = 'http://www.w3.org/2000/svg';
    let defs = svg.querySelector('defs');
    if (!defs) {
      defs = document.createElementNS(namespace, 'defs');
      svg.prepend(defs);
    }
    const marker = document.createElementNS(namespace, 'marker');
    marker.setAttribute('id', markerId);
    marker.setAttribute('viewBox', '0 0 10 10');
    marker.setAttribute('refX', '9');
    marker.setAttribute('refY', '5');
    marker.setAttribute('markerWidth', '13');
    marker.setAttribute('markerHeight', '13');
    marker.setAttribute('orient', 'auto-start-reverse');
    marker.setAttribute('markerUnits', 'userSpaceOnUse');
    const arrow = document.createElementNS(namespace, 'path');
    arrow.setAttribute('d', 'M 0 0 L 10 5 L 0 10 z');
    arrow.setAttribute('fill', isMedalistStory ? '#fbbf24' : '#f8fafc');
    marker.appendChild(arrow);
    defs.appendChild(marker);
  }
  path.setAttribute('marker-end', `url(#${markerId})`);
}

function toggleMigrationStoryPause() {
  if (!migrationStoryState.mode || migrationStoryState.complete) return;
  const frame = document.querySelector('.map-frame');
  const button = document.getElementById('migration-story-pause');

  if (migrationStoryState.paused) {
    migrationStoryState.paused = false;
    migrationStoryState.startedAt = performance.now();
    frame.classList.remove('migration-story-paused');
    button.textContent = 'Pause';
    migrationStoryState.frameId = requestAnimationFrame(runMigrationStoryFrame);
    return;
  }

  migrationStoryState.elapsed += performance.now() - migrationStoryState.startedAt;
  migrationStoryState.paused = true;
  frame.classList.add('migration-story-paused');
  button.textContent = 'Resume';
  cancelAnimationFrame(migrationStoryState.frameId);
}

function finishMigrationStory() {
  migrationFocusLayer.clearLayers();
  migrationStoryState.complete = true;
  migrationStoryState.elapsed = migrationStoryState.duration;
  migrationStoryState.frameId = null;
  document.getElementById('migration-story-pause').disabled = true;
  document.querySelectorAll('[data-size-mode]').forEach(button => { button.disabled = false; });
  updateMigrationStoryOverlay(1);
}

function stopMigrationStory() {
  if (!migrationStoryState.mode) return;
  cancelAnimationFrame(migrationStoryState.frameId);
  const frame = document.querySelector('.map-frame');
  frame.classList.remove('migration-story-active', 'migration-story-paused');
  migrationFocusLayer.clearLayers();
  document.getElementById('migration-story-overlay').hidden = true;
  document.querySelectorAll('[data-migration-story]').forEach(button => {
    button.classList.remove('active');
    button.setAttribute('aria-pressed', 'false');
  });
  document.getElementById('migration-story-pause').disabled = true;
  document.getElementById('migration-story-pause').textContent = 'Pause';
  document.getElementById('migration-story-restart').disabled = true;
  document.querySelectorAll('[data-size-mode]').forEach(button => { button.disabled = false; });
  migrationStoryState = createEmptyMigrationStoryState();
  updateMapLegend();
}

function updateMigrationStoryOverlay(progress) {
  const state = migrationStoryState;
  if (!state.mode) return;
  const isMedalistStory = state.mode === 'medalists';
  const mappedNote = state.mappedAthletes < state.totalAthletes
    ? ` ${formatNumber(state.mappedAthletes)} have mappable country coordinates.`
    : '';

  document.getElementById('migration-story-kicker').textContent = isMedalistStory
    ? 'Scene 2 - Medal winners'
    : 'Scene 1 - All cross-border athletes';
  document.getElementById('migration-story-heading').textContent = isMedalistStory
    ? `${formatNumber(state.totalAthletes)} medal-winning athletes`
    : `${formatNumber(state.totalAthletes)} cross-border athletes`;
  document.getElementById('migration-story-count').textContent = formatNumber(state.revealedAthletes);
  document.getElementById('migration-story-count-label').textContent = isMedalistStory
    ? 'mapped medal winners revealed'
    : 'mapped athletes revealed';
  document.getElementById('migration-story-progress').style.width = `${Math.round(progress * 100)}%`;
  document.getElementById('migration-story-progressbar').setAttribute('aria-valuenow', String(Math.round(progress * 100)));
  let narration;
  let narrationPhase;
  if (state.activeFeaturedIndex >= 0) {
    narrationPhase = `route-${state.activeFeaturedIndex}`;
    narration = 'Follow the moving point from recorded birthplace to the Olympic team represented. The arrow confirms the direction of the route.';
  } else if (progress < 1) {
    narrationPhase = 'network';
    narration = isMedalistStory
      ? 'The major medal-winning routes remain bright while the complete medalist network fills in behind them.'
      : 'The largest routes remain bright while hundreds of smaller journeys fill in the complete network.';
  } else {
    narrationPhase = 'complete';
    narration = isMedalistStory
      ? `The complete medal-winner network contains ${formatNumber(state.totalAthletes)} athletes across ${formatNumber(state.rows.length)} mappable routes.${mappedNote}`
      : `The complete network contains ${formatNumber(state.totalAthletes)} athletes across ${formatNumber(state.rows.length)} mappable routes.${mappedNote}`;
  }
  document.getElementById('migration-story-narration').textContent = narration;
  if (state.narrationPhase !== narrationPhase) {
    state.narrationPhase = narrationPhase;
    document.getElementById('migration-story-status').textContent = narration;
  }
}

function renderMigrationRouteCard(row, index) {
  const type = getCorridorType(row);
  const sports = (row.story_sports || []).slice(0, 2).map(item => `${item.sport} (${item.count})`).join(' · ');
  const athletes = (row.athletes || []).slice(0, 3).map(athlete => athlete.name).join(' · ');
  document.getElementById('migration-story-route').innerHTML = `
    <div class="story-route-position">Major route ${index + 1} of ${migrationStoryState.featuredCount}</div>
    <div class="story-route-direction">
      <span><small>Born in</small>${escapeHtml(row.birth_country)}</span>
      <b aria-hidden="true">&rarr;</b>
      <span><small>Competed for</small>${escapeHtml(row.rep_country)}</span>
    </div>
    <div class="story-route-metrics">
      <span><strong>${formatNumber(row.story_count)}</strong> athletes</span>
      <span><strong>${escapeHtml(formatTypeLabel(type))}</strong> route</span>
      <span><strong>${formatNumber(row.story_medals)}</strong> medals</span>
    </div>
    ${sports ? `<div class="story-route-detail"><small>Top sports</small>${escapeHtml(sports)}</div>` : ''}
    ${athletes ? `<div class="story-route-detail"><small>Athletes</small>${escapeHtml(athletes)}</div>` : ''}
  `;
}

function renderMigrationNetworkSummary() {
  document.getElementById('migration-story-route').innerHTML = `
    <div class="story-network-summary">
      <strong>From major routes to the full network</strong>
      <span>Bright arrowed lines are the largest corridors. Fainter lines preserve the smaller routes without overpowering the map.</span>
    </div>
  `;
}

function getCountryCoords(countryName) {
  const country = countryStats.find(row => row.country === countryName || row.noc === countryName);
  if (country && hasValidCoords(country.coords)) return country.coords;
  const fallback = COUNTRY_COORD_FALLBACKS[countryName];
  return hasValidCoords(fallback) ? fallback : null;
}

function curveBetween(from, to) {
  const points = [];
  const lat1 = from[0];
  const lng1 = from[1];
  const lat2 = to[0];
  const lng2 = normalizeDestinationCoords(from, to)[1];
  const dx = lng2 - lng1;
  const dy = lat2 - lat1;
  const distance = Math.sqrt(dx * dx + dy * dy);
  const curve = Math.min(18, Math.max(3, distance * 0.18));
  const norm = distance || 1;
  const offsetLat = (-dx / norm) * curve;
  const offsetLng = (dy / norm) * curve;

  for (let step = 0; step <= 24; step += 1) {
    const t = step / 24;
    const lat = (1 - t) * (1 - t) * lat1 + 2 * (1 - t) * t * (lat1 + lat2) / 2 + t * t * lat2 + Math.sin(Math.PI * t) * offsetLat;
    const lng = (1 - t) * (1 - t) * lng1 + 2 * (1 - t) * t * (lng1 + lng2) / 2 + t * t * lng2 + Math.sin(Math.PI * t) * offsetLng;
    points.push([lat, lng]);
  }
  return points;
}

function normalizeDestinationCoords(from, to) {
  let destinationLng = to[1];
  if (destinationLng - from[1] > 180) destinationLng -= 360;
  if (destinationLng - from[1] < -180) destinationLng += 360;
  return [to[0], destinationLng];
}

function isMobileViewport() {
  return window.innerWidth <= 1024;
}

function getDrawerMaxPos() {
  const drawer = document.getElementById('detail-drawer');
  if (!drawer) return 460;
  return isMobileViewport() ? (drawer.offsetHeight || window.innerHeight * 0.8) : (drawer.offsetWidth || 460);
}

function setDrawerTransform(pos) {
  const drawer = document.getElementById('detail-drawer');
  if (!drawer) return;
  drawerPos = pos;
  drawer.style.transition = 'none';
  if (isMobileViewport()) {
    drawer.style.transform = `translateY(${pos}px)`;
  } else {
    drawer.style.transform = `translateX(${pos}px)`;
  }
}

function stopSpringAnimation() {
  if (drawerAnimFrame) {
    cancelAnimationFrame(drawerAnimFrame);
    drawerAnimFrame = null;
  }
}

function animateDrawerTo(targetPos, initialVelocity = 0, onComplete = null) {
  stopSpringAnimation();

  const drawer = document.getElementById('detail-drawer');
  if (!drawer) return;

  const maxPos = getDrawerMaxPos();
  if (drawerPos === null) {
    drawerPos = drawer.classList.contains('open') ? 0 : maxPos;
  }

  let position = drawerPos;
  let velocity = initialVelocity;
  let lastTime = performance.now();

  const step = (now) => {
    let dt = (now - lastTime) / 1000;
    lastTime = now;

    if (dt > 0.064) dt = 0.064;

    const substeps = 8;
    const subDt = dt / substeps;

    for (let i = 0; i < substeps; i++) {
      const displacement = position - targetPos;
      const acc = -SPRING_STIFFNESS * displacement - SPRING_DAMPING_C * velocity;
      velocity += acc * subDt;
      position += velocity * subDt;
    }

    if (Math.abs(position - targetPos) < 0.3 && Math.abs(velocity) < 5) {
      position = targetPos;
      velocity = 0;
      setDrawerTransform(position);
      drawerAnimFrame = null;
      if (onComplete) onComplete();
      return;
    }

    setDrawerTransform(position);
    drawerAnimFrame = requestAnimationFrame(step);
  };

  drawerAnimFrame = requestAnimationFrame(step);
}

function openDetailDrawer(type, record) {
  if (type === 'country') renderCountryDrawer(record);
  if (type === 'city') renderCityDrawer(record);
  if (type === 'sport') renderSportDrawer(record);
  if (type === 'representedTeamCity') renderRepresentedTeamCityDrawer(record);
  if (type === 'corridor') renderCorridorDrawer(record);
  if (type === 'trainingHost') renderTrainingHostDrawer(record);
  if (type === 'trainingTeam') renderTrainingTeamDrawer(record);
  if (type === 'trainingCorridor') renderTrainingCorridorDrawer(record);

  const drawer = document.getElementById('detail-drawer');
  if (!drawer) return;

  const maxPos = getDrawerMaxPos();
  const isAlreadyOpen = drawer.classList.contains('open');

  drawer.classList.add('open');
  drawer.setAttribute('aria-hidden', 'false');

  if (!isAlreadyOpen || drawerPos === null || drawerPos >= maxPos) {
    drawerPos = maxPos;
    setDrawerTransform(maxPos);
  }

  animateDrawerTo(0, 0);
}

function closeDetailDrawer() {
  const drawer = document.getElementById('detail-drawer');
  if (!drawer || !drawer.classList.contains('open')) return;

  const maxPos = getDrawerMaxPos();
  animateDrawerTo(maxPos, 0, () => {
    drawer.classList.remove('open');
    drawer.setAttribute('aria-hidden', 'true');
    drawer.style.transform = '';
    drawer.style.transition = '';
    drawerPos = null;
  });
}

function initDrawerGesture() {
  const drawer = document.getElementById('detail-drawer');
  if (!drawer) return;

  drawer.addEventListener('pointerdown', (e) => {
    // Interruption: cancel active spring loop on pointerdown
    stopSpringAnimation();

    if (!drawer.classList.contains('open')) return;

    // Check if target is inside drawer body and scrolled down
    const drawerBody = e.target.closest('.drawer-body');
    if (drawerBody && drawerBody.scrollTop > 0) {
      return;
    }

    isDrawerPointerDown = true;
    isDrawerDragging = false;
    drawerPointerId = e.pointerId;
    drawerStartX = e.clientX;
    drawerStartY = e.clientY;

    const maxPos = getDrawerMaxPos();
    if (drawerPos === null) {
      drawerPos = 0;
    }
    drawerStartPos = drawerPos;

    drawerVelocityQueue = [
      { pos: drawerStartPos, time: performance.now() }
    ];
  });

  drawer.addEventListener('pointermove', (e) => {
    if (!isDrawerPointerDown || e.pointerId !== drawerPointerId) return;

    const deltaX = e.clientX - drawerStartX;
    const deltaY = e.clientY - drawerStartY;
    const isMobile = isMobileViewport();
    const primaryDelta = isMobile ? deltaY : deltaX;

    if (!isDrawerDragging) {
      const distance = Math.hypot(deltaX, deltaY);
      if (distance > 4) {
        isDrawerDragging = true;
        try {
          drawer.setPointerCapture(e.pointerId);
        } catch (err) {}
      }
    }

    if (isDrawerDragging) {
      const rawPos = drawerStartPos + primaryDelta;
      let pos;

      // Rubber-band resistance when dragging beyond 0 (fully open)
      if (rawPos < 0) {
        pos = rawPos * 0.35;
      } else {
        pos = rawPos;
      }

      setDrawerTransform(pos);

      const now = performance.now();
      drawerVelocityQueue.push({ pos, time: now });
      if (drawerVelocityQueue.length > 3) {
        drawerVelocityQueue.shift();
      }
    }
  });

  const handlePointerEnd = (e) => {
    if (!isDrawerPointerDown || e.pointerId !== drawerPointerId) return;

    isDrawerPointerDown = false;
    if (isDrawerDragging) {
      isDrawerDragging = false;
      try {
        if (drawer.hasPointerCapture(e.pointerId)) {
          drawer.releasePointerCapture(e.pointerId);
        }
      } catch (err) {}

      // Calculate release velocity from last 3 moves in queue (in px/s)
      let releaseVelocity = 0;
      if (drawerVelocityQueue.length >= 2) {
        const first = drawerVelocityQueue[0];
        const last = drawerVelocityQueue[drawerVelocityQueue.length - 1];
        const dt = (last.time - first.time) / 1000;
        if (dt > 0.002) {
          releaseVelocity = (last.pos - first.pos) / dt;
        }
      }

      const maxPos = getDrawerMaxPos();
      const currentPos = drawerPos ?? 0;

      // Momentum projection: projectedEndpoint = position + velocity * decel / (1 - decel)
      const decel = 0.998;
      const projectedEndpoint = currentPos + releaseVelocity * (decel / (1 - decel)) * 0.001;

      // Target is fully closed (maxPos) if projected position is > 50% closed, else fully open (0)
      const isProjectedClosed = projectedEndpoint > maxPos * 0.5;

      if (isProjectedClosed) {
        animateDrawerTo(maxPos, releaseVelocity, () => {
          drawer.classList.remove('open');
          drawer.setAttribute('aria-hidden', 'true');
          drawer.style.transform = '';
          drawer.style.transition = '';
          drawerPos = null;
        });
      } else {
        animateDrawerTo(0, releaseVelocity);
      }
    }
  };

  drawer.addEventListener('pointerup', handlePointerEnd);
  drawer.addEventListener('pointercancel', handlePointerEnd);
}

function renderCountryDrawer(stat) {
  document.getElementById('drawer-kicker').textContent = stat.noc || 'NOC';
  document.getElementById('drawer-title').textContent = stat.country || 'Country';
  const athletes = athleteData.filter(athlete => athlete.rep_noc === stat.noc && athlete.is_diaspora);
  const sources = Object.entries(stat.top_source_countries || {});

  document.getElementById('drawer-body').innerHTML = `
    ${metricsHtml([
      [formatNumber(stat.foreign_born_count), 'Foreign-born'],
      [`${formatPct(stat.foreign_born_pct)}%`, 'Foreign-born share'],
      [formatNumber(stat.total_athletes), 'Total athletes']
    ])}
    ${stat.medal_count !== undefined ? metricsHtml([
      [formatNumber(stat.medal_count), 'Medal athletes'],
      [formatNumber(stat.diaspora_medal_count), 'Diaspora medalists'],
      [`${formatPct(stat.diaspora_medal_pct)}%`, 'Medalist share']
    ]) : ''}
    ${sourceSectionHtml('Top origin countries', sources)}
    ${athleteSectionHtml('Foreign-born athlete roster', athletes, athlete => `Born: ${escapeHtml(athlete.birth_country || 'Unknown')}`)}
  `;
}

function renderRepresentedTeamCityDrawer(marker) {
  document.getElementById('drawer-kicker').textContent = marker.rep_noc;
  document.getElementById('drawer-title').textContent = `${marker.city}, ${marker.birth_country}`;

  document.getElementById('drawer-body').innerHTML = `
    ${metricsHtml([
      [formatNumber(marker.foreign_born_count), 'Foreign-born'],
      [`${formatPct(marker.foreign_born_pct)}%`, 'Foreign-born share'],
      [formatNumber(marker.total_athletes), 'Athletes born here']
    ])}
    ${sourceSectionHtml('Represented team', [[marker.rep_country, marker.total_athletes]])}
    ${athleteSectionHtml('Athlete roster', marker.athletes, athlete => `Represents: ${escapeHtml(athlete.rep_country || athlete.rep_noc || 'Unknown')}`)}
  `;
}

function renderCityDrawer(city) {
  document.getElementById('drawer-kicker').textContent = 'Birth city';
  document.getElementById('drawer-title').textContent = `${city.city}, ${city.birth_country}`;
  const teams = (city.represented_countries || []).map(country => [country, '']);
  const athletes = city.all_athletes || [];

  document.getElementById('drawer-body').innerHTML = `
    ${metricsHtml([
      [formatNumber(city.diaspora_count), 'Diaspora athletes'],
      [`${formatPct(city.diaspora_pct)}%`, 'Diaspora share'],
      [formatNumber(city.total_born), 'Born in city']
    ])}
    ${sourceSectionHtml('Represented teams', teams)}
    ${athleteSectionHtml('Athletes born here', athletes, athlete => `Represents: ${escapeHtml(athlete.rep_country || athlete.rep_noc || 'Unknown')}`)}
  `;
}

function renderSportDrawer(sport) {
  document.getElementById('drawer-kicker').textContent = 'Sport';
  document.getElementById('drawer-title').textContent = sport.sport;
  const sources = Object.entries(sport.top_source_countries || {});
  const represented = Object.entries(sport.top_represented_countries || {});

  document.getElementById('drawer-body').innerHTML = `
    ${metricsHtml([
      [formatNumber(sport.diaspora_count), 'Foreign-born athletes'],
      [`${formatPct(sport.diaspora_pct)}%`, 'Foreign-born share'],
      [formatNumber(sport.total_records_with_birthplace_data), 'Records with birthplace data']
    ])}
    ${sport.medal_count !== undefined ? metricsHtml([
      [formatNumber(sport.medal_count), 'Medal athletes'],
      [formatNumber(sport.diaspora_medal_count), 'Diaspora medalists'],
      [`${formatPct(sport.diaspora_medal_pct)}%`, 'Medalist share']
    ]) : ''}
    ${sourceSectionHtml('Top origin countries', sources)}
    ${sourceSectionHtml('Top represented teams', represented)}
  `;
}

function renderCorridorDrawer(corridor) {
  const type = getCorridorType(corridor);
  const athletes = corridor.athletes || athleteData.filter(athlete => athlete.is_diaspora && athlete.birth_country === corridor.birth_country && athlete.rep_country === corridor.rep_country);
  document.getElementById('drawer-kicker').textContent = formatTypeLabel(type);
  document.getElementById('drawer-title').textContent = `${corridor.birth_country || 'Unknown'} -> ${corridor.rep_country || 'Unknown'}`;

  document.getElementById('drawer-body').innerHTML = `
    ${metricsHtml([
      [formatNumber(corridor.athlete_count || athletes.length), 'Athletes'],
      [formatNumber(corridor.medal_count), 'Medals'],
      [corridor.reverse_count === undefined ? 'n/a' : formatNumber(corridor.reverse_count), 'Reverse flow']
    ])}
    ${sourceSectionHtml('Sport breakdown', (corridor.sports || []).map(item => [item.sport, item.count]))}
    ${athleteSectionHtml('Athlete roster', athletes, athlete => {
      const medalText = formatAthleteMedals(athlete);
      return `${escapeHtml(formatIdentityProfile(athlete.identity_profile))}${medalText ? `, ${medalText}` : ''}`;
    })}
  `;
}

function renderTrainingHostDrawer(host) {
  document.getElementById('drawer-kicker').textContent = 'Residence host';
  document.getElementById('drawer-title').textContent = host.host_country || 'Unknown';
  const athletes = athleteData.filter(
    athlete => athlete.trains_abroad && athlete.residence_country === host.host_country
  );
  document.getElementById('drawer-body').innerHTML = `
    ${metricsHtml([
      [formatNumber(host.athlete_count), 'Athletes based here'],
      [formatNumber(host.represented_team_count), 'Teams represented']
    ])}
    ${sourceSectionHtml('Represented teams', Object.entries(host.top_represented_teams || {}), Infinity)}
    ${sourceSectionHtml('Top sports', Object.entries(host.top_sports || {}))}
    ${athleteSectionHtml('Athletes based here', athletes, athlete => `${escapeHtml(athlete.rep_country || athlete.rep_noc || 'Unknown')} · ${escapeHtml(athlete.sport || 'Unknown sport')}`)}
    <p class="note">Residence country is used as a proxy and does not verify an athlete's training facility.</p>
  `;
}

function renderTrainingTeamDrawer(team) {
  document.getElementById('drawer-kicker').textContent = team.noc || 'Team';
  document.getElementById('drawer-title').textContent = team.country || 'Unknown';
  document.getElementById('drawer-body').innerHTML = `
    ${metricsHtml([
      [formatNumber(team.abroad_residence_count), 'Reside abroad'],
      [`${formatPct(team.abroad_residence_pct)}%`, 'Abroad share'],
      [formatNumber(team.known_residence_count), 'Known residences']
    ])}
    ${sourceSectionHtml('Top residence hosts abroad', Object.entries(team.top_host_countries || {}))}
    <p class="note">Residence country is used as a proxy and does not verify an athlete's training facility.</p>
  `;
}

function renderTrainingCorridorDrawer(corridor) {
  const athletes = corridor.athletes || [];
  document.getElementById('drawer-kicker').textContent = 'Residence corridor';
  document.getElementById('drawer-title').textContent = `${corridor.rep_country || 'Unknown'} -> ${corridor.residence_country || 'Unknown'}`;
  document.getElementById('drawer-body').innerHTML = `
    ${metricsHtml([
      [formatNumber(corridor.athlete_count || athletes.length), 'Athletes'],
      [formatNumber((corridor.sports || []).length), 'Sports']
    ])}
    ${sourceSectionHtml('Sport breakdown', (corridor.sports || []).map(item => [item.sport, item.count]))}
    ${athleteSectionHtml('Athlete roster', athletes, athlete => {
      const place = athlete.residence_place ? `${athlete.residence_place}, ` : '';
      return `${escapeHtml(athlete.sport || 'Unknown sport')} · residence: ${escapeHtml(place + (athlete.residence_country || 'Unknown'))}`;
    })}
    <p class="note">The route uses recorded residence as an approximate training base.</p>
  `;
}

function metricsHtml(metrics) {
  return `
    <div class="drawer-metrics">
      ${metrics.map(([value, label]) => `<div class="metric"><strong>${value}</strong><span>${label}</span></div>`).join('')}
    </div>
  `;
}

function sourceSectionHtml(title, rows, maxRows = 10) {
  if (!rows.length) {
    return `<section class="drawer-section"><h3>${title}</h3><p class="note">No entries in this dataset.</p></section>`;
  }
  const visibleRows = Number.isFinite(maxRows) ? rows.slice(0, maxRows) : rows;
  return `
    <section class="drawer-section">
      <h3>${title}</h3>
      <ul class="source-list">
        ${visibleRows.map(([name, count]) => `
          <li class="source-item"><span>${escapeHtml(name)}</span><span>${count ? `${formatNumber(count)} athlete${count === 1 ? '' : 's'}` : ''}</span></li>
        `).join('')}
      </ul>
    </section>
  `;
}

function athleteSectionHtml(title, athletes, metaFormatter) {
  if (!athletes.length) {
    return `<section class="drawer-section"><h3>${title}</h3><p class="note">No athlete roster entries available.</p></section>`;
  }
  return `
    <section class="drawer-section">
      <h3>${title} (${formatNumber(athletes.length)})</h3>
      <ul class="athlete-list">
        ${athletes.map(athlete => `
          <li class="athlete-row">
            <span>
              <span class="athlete-name">${escapeHtml(athlete.name || 'Unknown athlete')}</span>
              <span class="athlete-sub">${escapeHtml(athlete.sport || 'Unknown sport')}</span>
            </span>
            <span class="athlete-meta">${metaFormatter(athlete)}</span>
          </li>
        `).join('')}
      </ul>
    </section>
  `;
}

function getAthleteDiasporaType(athlete) {
  if (athlete.diaspora_type) return athlete.diaspora_type;
  const corridor = corridorStatsData.find(row => row.birth_country === athlete.birth_country && row.rep_country === athlete.rep_country);
  return corridor ? getCorridorType(corridor) : 'unclassified';
}

function getCorridorType(corridor) {
  if (corridor.corridor_type) return corridor.corridor_type;
  if (corridor.rep_noc === 'EOR' || corridor.rep_noc === 'AIN' || corridor.rep_country === 'AIN') return 'refugee-or-neutral';
  if ((corridor.athlete_count || 0) >= 3) return 'talent-market';
  return 'unclassified';
}

function getCorridorTypeColor(type) {
  return CORRIDOR_TYPE_COLORS[type] || CORRIDOR_TYPE_COLORS.unknown;
}

function formatTypeLabel(type) {
  return CORRIDOR_TYPE_LABELS[type] || titleCase(type || 'unknown');
}

function typeBadgeHtml(type) {
  return `<span class="type-badge" style="--badge-color: ${getCorridorTypeColor(type)}">${escapeHtml(formatTypeLabel(type))}</span>`;
}

function topSportsText(sports) {
  return (sports || []).slice(0, 3).map(item => `${item.sport} ${item.count}`).join(', ') || 'n/a';
}

function formatAsymmetry(corridor) {
  if (corridor.asymmetry === null || corridor.asymmetry === undefined) return corridor.reverse_count ? 'n/a' : 'one-way';
  return `${formatPct(corridor.asymmetry)}x`;
}

function reverseFlowHtml(corridor) {
  const out = corridor.athlete_count || 0;
  const reverse = corridor.reverse_count || 0;
  if (!reverse) return `<span class="one-way-pill">one-way</span><span class="reverse-flow-detail">${formatNumber(out)} &rarr; / 0 &larr;</span>`;
  return `<span class="reverse-flow"><strong>${formatNumber(out)} &rarr;</strong><span>${formatNumber(reverse)} &larr;</span></span>`;
}

function formatIdentityProfile(value) {
  return value ? titleCase(value.replaceAll('_', ' ')) : 'Identity profile pending';
}

function formatAthleteMedals(athlete) {
  if (Array.isArray(athlete.medals) && athlete.medals.length) return `${athlete.medals.length} medal${athlete.medals.length === 1 ? '' : 's'}`;
  if (athlete.medal_count) return `${athlete.medal_count} medal${athlete.medal_count === 1 ? '' : 's'}`;
  return '';
}

function isExceptionalNoc(row) {
  return row.noc === 'EOR' || row.noc === 'AIN' || row.country === 'AIN';
}

function mean(values) {
  if (!values.length) return NaN;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function createSvgElement(tag, attrs, text) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  Object.entries(attrs || {}).forEach(([key, value]) => node.setAttribute(key, value));
  if (text !== undefined) node.textContent = text;
  return node;
}

function titleCase(value) {
  return String(value || '').replace(/\b\w/g, char => char.toUpperCase());
}

function formatNumber(value) {
  return new Intl.NumberFormat('en-US').format(value || 0);
}

function formatPct(value) {
  return Number(value || 0).toLocaleString('en-US', { maximumFractionDigits: 1 });
}

function uniqueSorted(values) {
  return Array.from(new Set(values)).sort((a, b) => String(a).localeCompare(String(b)));
}

function normalizeFilterText(value) {
  return String(value || '').trim().toLowerCase();
}

function navigateTo({ tab = 'rankings', filters = {}, focus = {} } = {}) {
  setActiveTab(tab);

  if (tab === 'corridors') {
    if (filters.type) {
      activeCorridorTypes = new Set(Array.isArray(filters.type) ? filters.type : [filters.type]);
    }
    if (filters.birth !== undefined) corridorBirthFilter = filters.birth || '';
    if (filters.rep !== undefined) corridorRepFilter = filters.rep || '';
    if (filters.min !== undefined) document.getElementById('corridor-min-count').value = filters.min;
    setupCorridorSurface();
    const birthInput = document.getElementById('corridor-birth-filter');
    const repInput = document.getElementById('corridor-rep-filter');
    if (birthInput) birthInput.value = corridorBirthFilter;
    if (repInput) repInput.value = corridorRepFilter;
    renderCorridorTypeFilters();
    renderCorridorTable();
  }

  if (tab === 'map' && filters.view) {
    setMapView(filters.view);
  }

  setTimeout(() => resolveFocus(focus), 80);
}

function resolveFocus(focus = {}) {
  if (!focus.kind) return;
  if (focus.kind === 'module' && focus.id) {
    highlightElement(document.getElementById(focus.id));
    return;
  }
  if (focus.kind === 'city') {
    const city = cityStatsData.find(row =>
      normalizeFilterText(row.city) === normalizeFilterText(focus.city) &&
      (!focus.birth_country || normalizeFilterText(row.birth_country) === normalizeFilterText(focus.birth_country))
    );
    if (city) openDetailDrawer('city', city);
    return;
  }
  if (focus.kind === 'country') {
    const country = countryStats.find(row => row.noc === focus.noc || normalizeFilterText(row.country) === normalizeFilterText(focus.country));
    if (country) openDetailDrawer('country', country);
    return;
  }
  if (focus.kind === 'corridor') {
    const corridor = corridorStatsData.find(row =>
      normalizeFilterText(row.birth_country) === normalizeFilterText(focus.birth_country) &&
      normalizeFilterText(row.rep_country) === normalizeFilterText(focus.rep_country)
    );
    if (corridor) openDetailDrawer('corridor', corridor);
  }
}

function highlightElement(element) {
  if (!element) return;
  element.scrollIntoView({ behavior: 'smooth', block: 'start' });
  element.classList.add('focus-highlight');
  setTimeout(() => element.classList.remove('focus-highlight'), 1700);
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}
