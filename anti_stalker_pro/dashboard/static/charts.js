/**
 * Chart.js visualization module for the Anti-Stalker Dashboard.
 * All charts use dark theme colors for consistency with the UI.
 */

const CHART_COLORS = {
    primary: 'rgb(99, 102, 241)',
    danger: 'rgb(239, 68, 68)',
    warning: 'rgb(245, 158, 11)',
    success: 'rgb(34, 197, 94)',
    info: 'rgb(6, 182, 212)',
    purple: 'rgb(168, 85, 247)',
    pink: 'rgb(236, 72, 153)',
    gray: 'rgb(107, 114, 128)',
};

const CHART_DEFAULTS = {
    color: '#e5e7eb',
    borderColor: 'rgba(75, 85, 99, 0.3)',
    backgroundColor: 'rgba(17, 24, 39, 0.8)',
};

Chart.defaults.color = CHART_DEFAULTS.color;
Chart.defaults.borderColor = CHART_DEFAULTS.borderColor;

/**
 * Render an activity heatmap as a grid visualization.
 * @param {HTMLCanvasElement} canvas - Target canvas element
 * @param {number[][]} data - 7x24 matrix of activity counts
 * @returns {Chart} Chart.js instance
 */
function renderHeatmap(canvas, data) {
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const datasets = [];
    const maxVal = Math.max(...data.flat(), 1);

    for (let day = 0; day < 7; day++) {
        const pointData = [];
        for (let hour = 0; hour < 24; hour++) {
            const value = data[day][hour];
            if (value > 0) {
                pointData.push({ x: hour, y: day, v: value });
            }
        }
        datasets.push({
            label: days[day],
            data: pointData.map(p => ({ x: p.x, y: p.y })),
            backgroundColor: `rgba(99, 102, 241, ${0.3 + 0.7 * (pointData.reduce((s, p) => s + p.v, 0) / (maxVal * 24))})`,
            pointRadius: pointData.map(p => 3 + (p.v / maxVal) * 12),
            pointStyle: 'rect',
        });
    }

    return new Chart(canvas, {
        type: 'scatter',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    type: 'linear',
                    min: 0,
                    max: 23,
                    title: { display: true, text: 'Hour of Day' },
                    ticks: { stepSize: 1 },
                },
                y: {
                    type: 'linear',
                    min: -0.5,
                    max: 6.5,
                    title: { display: true, text: 'Day' },
                    ticks: {
                        callback: (val) => days[Math.round(val)] || '',
                        stepSize: 1,
                    },
                },
            },
            plugins: {
                legend: { display: false },
                title: { display: true, text: 'Activity Heatmap (7 Days)' },
            },
        },
    });
}

/**
 * Render score history as a line chart.
 * @param {HTMLCanvasElement} canvas - Target canvas element
 * @param {Object[]} data - Array of {date, score, pattern_type}
 * @returns {Chart} Chart.js instance
 */
function renderScoreHistory(canvas, data) {
    const labels = data.map(d => new Date(d.date).toLocaleDateString());
    const scores = data.map(d => d.score);

    return new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Suspicion Score',
                data: scores,
                borderColor: CHART_COLORS.danger,
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 4,
                pointBackgroundColor: CHART_COLORS.danger,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    min: 0,
                    max: 100,
                    title: { display: true, text: 'Score' },
                },
                x: {
                    title: { display: true, text: 'Date' },
                },
            },
            plugins: {
                title: { display: true, text: 'Score History' },
                legend: { position: 'top' },
            },
        },
    });
}

/**
 * Render daily event distribution as a bar chart.
 * @param {HTMLCanvasElement} canvas - Target canvas element
 * @param {number[]} data - Array of 24 hourly counts
 * @returns {Chart} Chart.js instance
 */
function renderDailyDistribution(canvas, data) {
    const labels = Array.from({ length: 24 }, (_, i) => `${i}:00`);

    return new Chart(canvas, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Events per Hour',
                data,
                backgroundColor: data.map((v, i) =>
                    (i >= 0 && i < 5) ? 'rgba(239, 68, 68, 0.7)' : 'rgba(99, 102, 241, 0.7)'
                ),
                borderColor: data.map((v, i) =>
                    (i >= 0 && i < 5) ? CHART_COLORS.danger : CHART_COLORS.primary
                ),
                borderWidth: 1,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Event Count' },
                },
                x: {
                    title: { display: true, text: 'Hour' },
                },
            },
            plugins: {
                title: { display: true, text: 'Daily Activity Distribution' },
                legend: { display: false },
            },
        },
    });
}

/**
 * Render device type distribution as a pie chart.
 * @param {HTMLCanvasElement} canvas - Target canvas element
 * @param {Object} data - Object with device type keys and count values
 * @returns {Chart} Chart.js instance
 */
function renderDevicePieChart(canvas, data) {
    const labels = Object.keys(data);
    const values = Object.values(data);
    const colors = [
        CHART_COLORS.primary,
        CHART_COLORS.danger,
        CHART_COLORS.warning,
        CHART_COLORS.success,
        CHART_COLORS.purple,
        CHART_COLORS.pink,
    ];

    return new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: colors.slice(0, labels.length),
                borderColor: 'rgb(31, 41, 55)',
                borderWidth: 2,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: { display: true, text: 'Bio Link Visitors by Device' },
                legend: { position: 'bottom' },
            },
        },
    });
}

/**
 * Render event timeline chart.
 * @param {HTMLCanvasElement} canvas - Target canvas element
 * @param {Object[]} data - Array of {date, story_views, online_events, alerts}
 * @returns {Chart} Chart.js instance
 */
function renderTimelineChart(canvas, data) {
    const labels = data.map(d => d.date);

    return new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Story Views',
                    data: data.map(d => d.story_views || 0),
                    borderColor: CHART_COLORS.primary,
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    fill: false,
                    tension: 0.2,
                },
                {
                    label: 'Online Events',
                    data: data.map(d => d.online_events || 0),
                    borderColor: CHART_COLORS.success,
                    backgroundColor: 'rgba(34, 197, 94, 0.1)',
                    fill: false,
                    tension: 0.2,
                },
                {
                    label: 'Alerts',
                    data: data.map(d => d.alerts || 0),
                    borderColor: CHART_COLORS.danger,
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    fill: false,
                    tension: 0.2,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Count' },
                },
                x: {
                    title: { display: true, text: 'Date' },
                },
            },
            plugins: {
                title: { display: true, text: 'Event Timeline' },
                legend: { position: 'top' },
            },
        },
    });
}
