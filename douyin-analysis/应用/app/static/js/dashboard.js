/**
 * 抖音数据分析仪表盘 — ECharts Dashboard
 *
 * Renders: KPI cards, trend line chart, video bar chart,
 * engagement donut, and posting-hour heatmap.
 */

// ── Utilities ────────────────────────────────────────────────────────
const fmt = new Intl.NumberFormat("zh-CN", { notation: "compact", maximumFractionDigits: 1 });
const fmtFull = new Intl.NumberFormat("zh-CN");

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${url}`);
    return res.json();
}

// ── KPI Cards ────────────────────────────────────────────────────────
async function loadKPIs() {
    try {
        const data = await fetchJSON("/api/overview");
        setKPI("kpi-plays", data.total_plays);
        setKPI("kpi-likes", data.total_likes);
        setKPI("kpi-comments", data.total_comments);
        setKPI("kpi-shares", data.total_shares);
        setKPI("kpi-engagement", data.avg_engagement_rate, "%");
    } catch (err) {
        console.error("Failed to load KPIs:", err);
    }
}

function setKPI(id, value, suffix = "") {
    const el = document.getElementById(id);
    if (!el) return;
    if (suffix === "%") {
        el.textContent = Number(value).toFixed(2) + suffix;
    } else if (value >= 10000) {
        el.textContent = fmt.format(value);
    } else {
        el.textContent = fmtFull.format(value);
    }
}

// ── Trend Line Chart ─────────────────────────────────────────────────
async function loadTrendChart() {
    const container = document.getElementById("trend-chart");
    if (!container) return;

    const chart = echarts.init(container);

    try {
        const data = await fetchJSON("/api/trends?days=30");
        const dates = data.map(d => d.date);
        const plays = data.map(d => d.plays);
        const likes = data.map(d => d.likes);
        const comments = data.map(d => d.comments);

        const option = {
            tooltip: {
                trigger: "axis",
                backgroundColor: "rgba(255,255,255,0.95)",
                borderColor: "#e5e7eb",
                textStyle: { color: "#374151" },
            },
            legend: {
                data: ["播放量", "点赞", "评论"],
                bottom: 0,
                textStyle: { fontSize: 12 },
            },
            grid: { left: "3%", right: "4%", bottom: "12%", top: "8%", containLabel: true },
            xAxis: {
                type: "category",
                data: dates,
                axisLabel: {
                    formatter: v => v.slice(5), // show MM-DD
                    fontSize: 11,
                },
                boundaryGap: false,
            },
            yAxis: {
                type: "value",
                axisLabel: {
                    formatter: v => fmt.format(v),
                    fontSize: 11,
                },
                splitLine: { lineStyle: { color: "#f3f4f6" } },
            },
            series: [
                {
                    name: "播放量",
                    type: "line",
                    smooth: true,
                    data: plays,
                    lineStyle: { color: "#6366f1", width: 2 },
                    areaStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: "rgba(99,102,241,0.2)" },
                            { offset: 1, color: "rgba(99,102,241,0.0)" },
                        ]),
                    },
                    itemStyle: { color: "#6366f1" },
                    symbol: "none",
                },
                {
                    name: "点赞",
                    type: "line",
                    smooth: true,
                    data: likes,
                    lineStyle: { color: "#f43f5e", width: 2 },
                    symbol: "none",
                },
                {
                    name: "评论",
                    type: "line",
                    smooth: true,
                    data: comments,
                    lineStyle: { color: "#10b981", width: 2 },
                    symbol: "none",
                },
            ],
        };

        chart.setOption(option);

        // Responsive resize
        window.addEventListener("resize", () => chart.resize());

        // Toggle series on legend click handled by ECharts default
    } catch (err) {
        console.error("Failed to load trend chart:", err);
        container.innerHTML = '<div class="flex items-center justify-center h-full text-gray-400">图表加载失败</div>';
    }
}

// ── Top Videos Bar Chart ─────────────────────────────────────────────
async function loadTopVideosChart() {
    const container = document.getElementById("top-videos-chart");
    if (!container) return;

    const chart = echarts.init(container);

    try {
        const data = await fetchJSON("/api/videos?sort=plays&limit=10");
        // Reverse so highest is at top
        const videos = [...data].reverse();
        const titles = videos.map(v => v.title.length > 15 ? v.title.slice(0, 15) + "..." : v.title);
        const plays = videos.map(v => v.total_plays);

        const option = {
            tooltip: {
                trigger: "axis",
                axisPointer: { type: "shadow" },
                backgroundColor: "rgba(255,255,255,0.95)",
                borderColor: "#e5e7eb",
                textStyle: { color: "#374151" },
                formatter: params => {
                    const p = params[0];
                    return `${p.name}<br/>播放量: <b>${fmtFull.format(p.value)}</b>`;
                },
            },
            grid: { left: "3%", right: "12%", top: "3%", bottom: "3%", containLabel: true },
            xAxis: {
                type: "value",
                axisLabel: { formatter: v => fmt.format(v), fontSize: 11 },
                splitLine: { lineStyle: { color: "#f3f4f6" } },
            },
            yAxis: {
                type: "category",
                data: titles,
                axisLabel: { fontSize: 11, width: 120, overflow: "truncate" },
                axisTick: { show: false },
            },
            series: [
                {
                    type: "bar",
                    data: plays.map((v, i) => ({
                        value: v,
                        itemStyle: {
                            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                                { offset: 0, color: "#818cf8" },
                                { offset: 1, color: "#6366f1" },
                            ]),
                            borderRadius: [0, 4, 4, 0],
                        },
                    })),
                    barWidth: 16,
                },
            ],
        };

        chart.setOption(option);
        window.addEventListener("resize", () => chart.resize());
    } catch (err) {
        console.error("Failed to load top videos chart:", err);
        container.innerHTML = '<div class="flex items-center justify-center h-full text-gray-400">图表加载失败</div>';
    }
}

// ── Engagement Donut Chart ────────────────────────────────────────────
async function loadEngagementDonut() {
    const container = document.getElementById("engagement-donut");
    if (!container) return;

    const chart = echarts.init(container);

    try {
        const overview = await fetchJSON("/api/overview");
        const total = overview.total_likes + overview.total_comments + overview.total_shares;

        const option = {
            tooltip: {
                trigger: "item",
                formatter: "{b}: {c} ({d}%)",
            },
            legend: {
                bottom: 0,
                textStyle: { fontSize: 12 },
            },
            series: [
                {
                    type: "pie",
                    radius: ["50%", "75%"],
                    center: ["50%", "45%"],
                    avoidLabelOverlap: false,
                    itemStyle: {
                        borderRadius: 6,
                        borderColor: "#fff",
                        borderWidth: 3,
                    },
                    label: { show: false },
                    emphasis: {
                        label: {
                            show: true,
                            fontSize: 16,
                            fontWeight: "bold",
                        },
                    },
                    data: [
                        {
                            value: overview.total_likes,
                            name: "点赞",
                            itemStyle: { color: "#f43f5e" },
                        },
                        {
                            value: overview.total_comments,
                            name: "评论",
                            itemStyle: { color: "#10b981" },
                        },
                        {
                            value: overview.total_shares,
                            name: "分享",
                            itemStyle: { color: "#f59e0b" },
                        },
                    ],
                },
            ],
        };

        chart.setOption(option);
        window.addEventListener("resize", () => chart.resize());
    } catch (err) {
        console.error("Failed to load engagement donut:", err);
        container.innerHTML = '<div class="flex items-center justify-center h-full text-gray-400">图表加载失败</div>';
    }
}

// ── Posting Hour Heatmap ─────────────────────────────────────────────
async function loadPostingHourChart() {
    const container = document.getElementById("posting-hour-chart");
    if (!container) return;

    const chart = echarts.init(container);

    try {
        const data = await fetchJSON("/api/posting-hours");
        const hours = data.map(d => `${d.hour}:00`);
        const values = data.map(d => d.engagement);

        const option = {
            tooltip: {
                trigger: "axis",
                formatter: params => {
                    const p = params[0];
                    return `${p.name}<br/>互动量指数: <b>${p.value}</b>`;
                },
            },
            grid: { left: "3%", right: "4%", top: "8%", bottom: "8%", containLabel: true },
            xAxis: {
                type: "category",
                data: hours,
                axisLabel: {
                    fontSize: 10,
                    interval: 2,
                },
            },
            yAxis: {
                type: "value",
                axisLabel: { fontSize: 11 },
                splitLine: { lineStyle: { color: "#f3f4f6" } },
            },
            series: [
                {
                    type: "bar",
                    data: values.map((v, i) => ({
                        value: v,
                        itemStyle: {
                            color: i >= 17 && i <= 22
                                ? "#6366f1"   // evening peak
                                : i >= 11 && i <= 13
                                    ? "#818cf8"   // lunch peak
                                    : "#c7d2fe",  // off-peak
                            borderRadius: [4, 4, 0, 0],
                        },
                    })),
                    barWidth: "70%",
                },
            ],
        };

        chart.setOption(option);
        window.addEventListener("resize", () => chart.resize());
    } catch (err) {
        console.error("Failed to load posting hour chart:", err);
        container.innerHTML = '<div class="flex items-center justify-center h-full text-gray-400">图表加载失败</div>';
    }
}

// ── Top Videos Table ─────────────────────────────────────────────────
async function loadTopVideosTable() {
    const tbody = document.getElementById("top-videos-tbody");
    if (!tbody) return;

    try {
        const data = await fetchJSON("/api/videos?sort=engagement&limit=10");

        tbody.innerHTML = data.map((v, i) => {
            const rank = i + 1;
            const rankClass = rank <= 3 ? `rank-${rank}` : "";
            const engColor = v.engagement_rate > 10
                ? "text-green-600" : v.engagement_rate > 5
                    ? "text-amber-600" : "text-gray-500";

            return `
                <tr>
                    <td>
                        ${rankClass
                            ? `<span class="rank-badge ${rankClass}">${rank}</span>`
                            : `<span class="text-gray-400 pl-2">${rank}</span>`
                        }
                    </td>
                    <td>
                        <span class="video-title-cell" title="${escapeHTML(v.title)}">
                            ${escapeHTML(v.title.length > 30 ? v.title.slice(0, 30) + "..." : v.title)}
                        </span>
                    </td>
                    <td class="tabular-nums">${fmtFull.format(v.total_plays)}</td>
                    <td class="tabular-nums">${fmtFull.format(v.total_likes)}</td>
                    <td class="tabular-nums">${fmtFull.format(v.total_comments)}</td>
                    <td class="${engColor} font-semibold tabular-nums">
                        ${v.engagement_rate.toFixed(2)}%
                    </td>
                    <td>
                        <span class="text-xs px-2 py-0.5 rounded-full
                            ${v.trend_direction === 'up' ? 'bg-green-100 text-green-700' :
                              v.trend_direction === 'down' ? 'bg-red-100 text-red-700' :
                              'bg-gray-100 text-gray-600'}">
                            ${v.trend_direction === 'up' ? '📈 上升' :
                              v.trend_direction === 'down' ? '📉 下降' : '➡ 平稳'}
                        </span>
                    </td>
                </tr>
            `;
        }).join("");
    } catch (err) {
        console.error("Failed to load top videos table:", err);
    }
}

function escapeHTML(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// ── Video List Page ──────────────────────────────────────────────────
async function loadVideoList() {
    const tbody = document.getElementById("video-list-tbody");
    if (!tbody) return;

    try {
        const data = await fetchJSON("/api/videos?sort=plays&limit=50");

        tbody.innerHTML = data.map((v, i) => `
            <tr class="border-b border-gray-100 hover:bg-indigo-50/30 transition-colors">
                <td class="py-3 px-4 text-gray-400">${i + 1}</td>
                <td class="py-3 px-4 font-medium" title="${escapeHTML(v.title)}">
                    ${escapeHTML(v.title.length > 40 ? v.title.slice(0, 40) + "..." : v.title)}
                </td>
                <td class="py-3 px-4 tabular-nums">${v.duration}s</td>
                <td class="py-3 px-4 tabular-nums">${fmtFull.format(v.total_plays)}</td>
                <td class="py-3 px-4 tabular-nums">${fmtFull.format(v.total_likes)}</td>
                <td class="py-3 px-4 tabular-nums">${fmtFull.format(v.total_comments)}</td>
                <td class="py-3 px-4 tabular-nums">${fmtFull.format(v.total_shares)}</td>
                <td class="py-3 px-4">
                    <div class="flex items-center space-x-2">
                        <div class="engagement-bar w-20">
                            <div class="fill" style="width: ${Math.min(v.engagement_rate * 6, 100)}%"></div>
                        </div>
                        <span class="text-sm font-medium tabular-nums">${v.engagement_rate.toFixed(1)}%</span>
                    </div>
                </td>
            </tr>
        `).join("");
    } catch (err) {
        console.error("Failed to load video list:", err);
    }
}

function searchVideos() {
    const query = document.getElementById("video-search")?.value.toLowerCase() || "";
    const rows = document.querySelectorAll("#video-list-tbody tr");
    rows.forEach(row => {
        const title = row.querySelector("td:nth-child(2)")?.textContent.toLowerCase() || "";
        row.style.display = title.includes(query) ? "" : "none";
    });
}

function sortVideoList(sort) {
    // Update active button
    document.querySelectorAll(".sort-btn").forEach(b => b.classList.remove("active"));
    const activeBtn = document.querySelector(`[data-sort="${sort}"]`);
    if (activeBtn) activeBtn.classList.add("active");

    // Re-fetch sorted data
    const tbody = document.getElementById("video-list-tbody");
    if (!tbody) return;

    fetchJSON(`/api/videos?sort=${sort}&limit=50`).then(data => {
        tbody.innerHTML = data.map((v, i) => `
            <tr class="border-b border-gray-100 hover:bg-indigo-50/30 transition-colors">
                <td class="py-3 px-4 text-gray-400">${i + 1}</td>
                <td class="py-3 px-4 font-medium" title="${escapeHTML(v.title)}">
                    ${escapeHTML(v.title.length > 40 ? v.title.slice(0, 40) + "..." : v.title)}
                </td>
                <td class="py-3 px-4 tabular-nums">${v.duration}s</td>
                <td class="py-3 px-4 tabular-nums">${fmtFull.format(v.total_plays)}</td>
                <td class="py-3 px-4 tabular-nums">${fmtFull.format(v.total_likes)}</td>
                <td class="py-3 px-4 tabular-nums">${fmtFull.format(v.total_comments)}</td>
                <td class="py-3 px-4 tabular-nums">${fmtFull.format(v.total_shares)}</td>
                <td class="py-3 px-4">
                    <div class="flex items-center space-x-2">
                        <div class="engagement-bar w-20">
                            <div class="fill" style="width: ${Math.min(v.engagement_rate * 6, 100)}%"></div>
                        </div>
                        <span class="text-sm font-medium tabular-nums">${v.engagement_rate.toFixed(1)}%</span>
                    </div>
                </td>
            </tr>
        `).join("");
    });
}

// ── Refresh Data ─────────────────────────────────────────────────────
async function refreshData() {
    const btn = document.getElementById("refresh-btn");
    if (btn) {
        btn.textContent = "刷新中...";
        btn.disabled = true;
    }

    try {
        const res = await fetch("/api/refresh", { method: "POST" });
        const data = await res.json();
        if (data.success) {
            // Reload all data on the dashboard
            await Promise.all([
                loadKPIs(),
                loadTrendChart(),
                loadTopVideosChart(),
                loadEngagementDonut(),
                loadPostingHourChart(),
                loadTopVideosTable(),
                loadVideoList(),
            ]);
            document.getElementById("last-refresh").textContent = new Date().toLocaleString("zh-CN");
            alert(data.message);
        }
    } catch (err) {
        console.error("Failed to refresh data:", err);
        alert("刷新失败，请检查网络连接");
    } finally {
        if (btn) {
            btn.textContent = "刷新数据";
            btn.disabled = false;
        }
    }
}

// ── Init ─────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    // Main dashboard
    loadKPIs();
    loadTrendChart();
    loadTopVideosChart();
    loadEngagementDonut();
    loadPostingHourChart();
    loadTopVideosTable();

    // Video list page
    loadVideoList();
});
