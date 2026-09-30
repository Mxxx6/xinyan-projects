var API_URL = '/api';
var TOKEN = '';
var STUDIOS = [];
var CLASSES = [];
var MS = {};

function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }

function toast(msg, type) {
    type = type || 's';
    var d = document.createElement('div');
    d.className = 'tst t' + type;
    d.textContent = msg;
    document.getElementById('tc').appendChild(d);
    setTimeout(function() { d.remove(); }, 2500);
}

async function api(path, opts) {
    opts = opts || {};
    var headers = {'Content-Type': 'application/json'};
    if (TOKEN) headers['Authorization'] = 'Bearer ' + TOKEN;
    var res = await fetch(API_URL + path, {headers: headers});
    if (res.status === 401) { TOKEN = ''; return login(); }
    return res.json();
}

async function login() {
    // 无 Django 版：本地只读，无需登录
    TOKEN = 'nodjango-local';
    document.getElementById('ui').textContent = '本地模式';
    await loadOptions();
    await loadSessions();
    loadSyncStatus();
    loadDashboard();
}

// ---- 考勤式多选筛选组件 ----
function makeMultiSelect(id, options, label, onChange) {
    var wrap = document.getElementById(id);
    if (!wrap) return null;
    wrap.innerHTML = '';
    wrap.className = 'ms-wrap';
    options = options || [];

    var btn = document.createElement('div');
    btn.className = 'ms-btn';
    btn.innerHTML = '<span class="ms-label">' + label + '</span><span class="ms-arrow">▼</span>';

    var dd = document.createElement('div');
    dd.className = 'ms-dd';

    var search = document.createElement('input');
    search.type = 'text';
    search.className = 'ms-search';
    search.placeholder = '搜索...';
    search.oninput = function() {
        var q = search.value.trim().toLowerCase();
        items.forEach(function(lab) {
            lab.style.display = q ? (lab.textContent.toLowerCase().indexOf(q) >= 0 ? 'block' : 'none') : 'block';
        });
    };

    var allLab = document.createElement('label');
    allLab.className = 'ms-item';
    allLab.innerHTML = '<input type="checkbox" class="ms-all" checked> 全部';

    var hr = document.createElement('div');
    hr.className = 'ms-hr';

    var listWrap = document.createElement('div');
    var items = [];
    options.forEach(function(opt) {
        var lab = document.createElement('label');
        lab.className = 'ms-item';
        lab.innerHTML = '<input type="checkbox" value="' + esc(opt) + '" checked> ' + esc(opt);
        listWrap.appendChild(lab);
        items.push(lab);
    });

    dd.appendChild(search);
    dd.appendChild(allLab);
    dd.appendChild(hr);
    dd.appendChild(listWrap);
    wrap.appendChild(btn);
    wrap.appendChild(dd);

    var allCb = allLab.querySelector('input');

    btn.onclick = function(e) {
        e.stopPropagation();
        var open = dd.style.display !== 'block';
        dd.style.display = open ? 'block' : 'none';
        if (open) search.focus();
    };

    allCb.onchange = function() {
        var v = allCb.checked;
        items.forEach(function(lab) { lab.querySelector('input').checked = v; });
        update();
    };

    items.forEach(function(lab) {
        lab.querySelector('input').onchange = function() { update(); };
    });

    function checkedVals() {
        return items.filter(function(lab) { return lab.querySelector('input').checked; })
            .map(function(lab) { return lab.querySelector('input').value; });
    }

    function update() {
        var checked = checkedVals();
        var isAll = checked.length === items.length;
        allCb.checked = isAll;
        var lbl;
        if (isAll) lbl = label;
        else if (!checked.length) lbl = label + ': 未选择';
        else if (checked.length <= 2) lbl = checked.join(', ');
        else lbl = label + ' (' + checked.length + ')';
        btn.querySelector('.ms-label').textContent = lbl;
        if (onChange) onChange(isAll ? '' : checked.join(','));
    }

    document.addEventListener('click', function(e) {
        if (!wrap.contains(e.target)) dd.style.display = 'none';
    });

    update();
    var api = { getValue: function() {
        var checked = checkedVals();
        return checked.length === items.length ? '' : checked.join(',');
    }};
    MS[id] = api;
    return api;
}

async function loadOptions() {
    try {
        var sd = await api('/students/studios/?page_size=10000');
        var cd = await api('/students/classes/?page_size=10000');
        STUDIOS = (sd.results || sd).map(function(r) { return r.name; });
        CLASSES = (cd.results || cd).map(function(r) { return r.name; });

        makeMultiSelect('ds-studio', STUDIOS, '全部工作室');
        makeMultiSelect('ds-class', CLASSES, '全部班级');
        makeMultiSelect('rs-ms', STUDIOS, '全部工作室');
        makeMultiSelect('bs-studio', STUDIOS, '全部工作室');
        makeMultiSelect('bs-class', CLASSES, '全部班级');
        makeMultiSelect('js-studio', STUDIOS, '全部工作室');
        makeMultiSelect('js-class', CLASSES, '全部班级');
    } catch(e) { console.error(e); }
}

// ---- Session / Province helpers ----
var SESSIONS = {monthly: [], joint: []};
var SESSION_BY_DATE = {};

function resolveSession(dateVal) {
    var hit = SESSION_BY_DATE[dateVal];
    if (hit) return hit;
    // 未精确命中：按月份回退（纯月份场次如 6月/7月/9月）
    return {month: (dateVal || '').slice(0, 7), session: ''};
}

function setDefaultDate(id, list) {
    var el = document.getElementById(id);
    if (!el || !list.length) return;
    el.value = list[list.length - 1].date;   // 默认最新一场
    el.min = list[0].date;
    el.max = list[list.length - 1].date;
}

async function loadSessions() {
    try {
        SESSIONS.monthly = await api('/analysis/sessions/?exam_type=monthly');
        SESSIONS.joint = await api('/analysis/sessions/?exam_type=joint');
        SESSION_BY_DATE = {};
        GROUP_SESSION_LIST = [];
        SESSIONS.monthly.concat(SESSIONS.joint).forEach(function(s) {
            SESSION_BY_DATE[s.date] = {month: s.exam_month, session: s.exam_session};
        });
        setDefaultDate('rm', SESSIONS.monthly);
        setDefaultDate('am', SESSIONS.monthly);
        setDefaultDate('bm', SESSIONS.monthly);
        setDefaultDate('dm', SESSIONS.monthly);
        setDefaultDate('js', SESSIONS.joint);
        var provs = await api('/analysis/provinces/?exam_type=joint');
        document.getElementById('jp').innerHTML =
            '<option value="">全部省份</option>' + provs.map(function(p) { return '<option>' + p + '</option>'; }).join('');
    } catch(e) { console.error(e); }
}

// ---- Band logic ----
var BANDS = ['A+','A','A-','B+','B','B-','C+','C','C-','D'];
var BAND_WEIGHT = {'A+':9,'A':8,'A-':7,'B+':6,'B':5,'B-':4,'C+':3,'C':2,'C-':1,'D':0};
var BAND_CLASS = {'A+':'bap','A':'ba','A-':'bam','B+':'bbp','B':'bb','B-':'bbm','C+':'bcp','C':'bc','C-':'bcm','D':'bd'};

function gradeBand(s) {
    if (s === null || s === undefined) return '-';
    if (s <= 9 && s >= 0) {
        var m = {9:'A+',8:'A',7:'A-',6:'B+',5:'B',4:'B-',3:'C+',2:'C',1:'C-',0:'D'};
        return m[Math.round(s)] || 'D';
    }
    if (s >= 95) return 'A+'; if (s >= 90) return 'A'; if (s >= 85) return 'A-';
    if (s >= 80) return 'B+'; if (s >= 75) return 'B'; if (s >= 70) return 'B-';
    if (s >= 65) return 'C+'; if (s >= 60) return 'C'; if (s >= 50) return 'C-';
    return 'D';
}

// ---- Navigation ----
document.querySelectorAll('nav a').forEach(function(a) {
    a.addEventListener('click', function(e) {
        e.preventDefault();
        document.querySelectorAll('nav a').forEach(function(x) { x.classList.remove('active'); });
        a.classList.add('active');
        document.querySelectorAll('.content').forEach(function(x) { x.classList.remove('active'); });
        var p = document.getElementById('page-' + a.dataset.p);
        if (p) p.classList.add('active');
        document.getElementById('bc').textContent = a.textContent.trim();
        if (a.dataset.p === 'dashboard') loadDashboard();
        if (a.dataset.p === 'ranking') loadRanking();
        if (a.dataset.p === 'averages') loadAverages();
        if (a.dataset.p === 'bands') loadBands();
        if (a.dataset.p === 'joint') loadJoint();
        if (a.dataset.p === 'groups') loadGroups();
    });
});

// ---- Dashboard ----
async function loadDashboard() {
    if (!TOKEN) return;
    try {
        // 首次从简道云拉取约需数十秒，先给出提示
        document.getElementById('ds').innerHTML =
            '<div class="sc"><div class="l">正在加载简道云数据…</div><div class="v">…</div></div>';
        var sv = resolveSession(document.getElementById('dm').value);
        var studios = MS['ds-studio'] ? MS['ds-studio'].getValue() : '';
        var classes = MS['ds-class'] ? MS['ds-class'].getValue() : '';
        var base = 'exam_type=monthly&exam_month=' + sv.month + '&exam_session=' + encodeURIComponent(sv.session);
        var f = '';
        if (studios) f += '&studios=' + encodeURIComponent(studios);
        if (classes) f += '&classes=' + encodeURIComponent(classes);
        var rank = await api('/analysis/ranking/?' + base + f);
        var avg = await api('/analysis/averages/?' + base + '&group_by=studio' + f);
        var idx = await api('/analysis/teaching-index/?' + base + f);

        var total = rank.length;
        var aplus = 0;
        rank.forEach(function(r) {
            if (gradeBand(r.sketch_score) === 'A+') aplus++;
            if (gradeBand(r.color_score) === 'A+') aplus++;
            if (gradeBand(r.quick_score) === 'A+') aplus++;
        });

        document.getElementById('ds').innerHTML =
            '<div class="sc"><div class="l">参考人数</div><div class="v">' + total + '</div></div>' +
            '<div class="sc"><div class="l">A+ 人次</div><div class="v">' + aplus + '</div></div>' +
            '<div class="sc"><div class="l">工作室数</div><div class="v">' + avg.length + '</div></div>' +
            '<div class="sc"><div class="l">最高教学指数</div><div class="v">' + (idx.length ? idx[0].teaching_index : '-') + '</div></div>';

        var c1 = echarts.init(document.getElementById('c1'));
        c1.setOption({
            tooltip: {trigger: 'axis'},
            legend: {data: ['素描','色彩','速写'], bottom: 0},
            grid: {left: 50, right: 20, top: 20, bottom: 40},
            xAxis: {type: 'category', data: avg.map(function(d) { return d.label; }), axisLabel: {fontSize: 9, rotate: 30}},
            yAxis: {type: 'value', name: '均分'},
            series: [
                {name: '素描', type: 'bar', data: avg.map(function(d) { return parseFloat(d.avg_sketch) || 0; }), color: '#f59e0b'},
                {name: '色彩', type: 'bar', data: avg.map(function(d) { return parseFloat(d.avg_color) || 0; }), color: '#0d9488'},
                {name: '速写', type: 'bar', data: avg.map(function(d) { return parseFloat(d.avg_quick) || 0; }), color: '#1a73e8'}
            ]
        });

        var c2 = echarts.init(document.getElementById('c2'));
        var sd = idx.slice(0, 15).reverse();
        c2.setOption({
            tooltip: {trigger: 'axis'},
            grid: {left: 80, right: 20, top: 10, bottom: 20},
            xAxis: {type: 'value', name: '教学指数'},
            yAxis: {type: 'category', data: sd.map(function(d) { return d.studio; }), axisLabel: {fontSize: 10}},
            series: [{type: 'bar', data: sd.map(function(d) { return d.teaching_index; }), label: {show: true, position: 'right'},
                itemStyle: {color: function(p) { return p.value >= 7 ? '#0d9488' : p.value >= 5 ? '#1a73e8' : '#f59e0b'; }}}
            ]
        });
    } catch(e) { console.error(e); }
}

// ---- Ranking with pagination ----
var rankingData = [], rankingPage = 0, pageSize = 50;

async function loadRanking() {
    try {
        document.getElementById('rl').style.display = 'block';
        document.getElementById('re').style.display = 'none';
        document.getElementById('rt').style.display = 'none';
        document.getElementById('rp').innerHTML = '';
        var sv = resolveSession(document.getElementById('rm').value);
        var st = MS['rs-ms'] ? MS['rs-ms'].getValue() : '';
        var pr = document.getElementById('rprov').value;
        var nm = document.getElementById('rname').value.trim();
        var u = '/analysis/ranking/?exam_type=monthly&exam_month=' + sv.month + '&exam_session=' + encodeURIComponent(sv.session);
        if (st) u += '&studios=' + encodeURIComponent(st);
        if (pr) u += '&province=' + encodeURIComponent(pr);
        if (nm) u += '&student_name=' + encodeURIComponent(nm);
        rankingData = await api(u);
        rankingPage = 0;
        document.getElementById('rl').style.display = 'none';
        if (!rankingData.length) { document.getElementById('re').style.display = 'block'; return; }
        renderRankingPage();
        document.getElementById('rt').style.display = '';
    } catch(e) { console.error(e); }
}

function renderRankingPage() {
    var tbody = document.querySelector('#rt tbody');
    var totalPages = Math.max(1, Math.ceil(rankingData.length / pageSize));
    if (rankingPage >= totalPages) rankingPage = totalPages - 1;
    if (rankingPage < 0) rankingPage = 0;
    var start = rankingPage * pageSize;
    var end = Math.min(start + pageSize, rankingData.length);
    var page = rankingData.slice(start, end);

    tbody.innerHTML = page.map(function(s) {
        var sb = gradeBand(s.sketch_score);
        var cb = gradeBand(s.color_score);
        var qb = gradeBand(s.quick_score);
        var bw = BAND_WEIGHT, bc = BAND_CLASS;
        return '<tr><td><b>' + s.rank + '</b></td>' +
            '<td>' + s.student_name + '</td>' +
            '<td>' + s.student_code + '</td>' +
            '<td>' + (s.studio_name || '-') + '</td>' +
            '<td>' + (s.province || '-') + '</td>' +
            '<td>' + (s.sketch_score != null ? s.sketch_score : '-') + ' <span class="band ' + bc[sb] + '">' + sb + bw[sb] + '</span></td>' +
            '<td>' + (s.color_score != null ? s.color_score : '-') + ' <span class="band ' + bc[cb] + '">' + cb + bw[cb] + '</span></td>' +
            '<td>' + (s.quick_score != null ? s.quick_score : '-') + ' <span class="band ' + bc[qb] + '">' + qb + bw[qb] + '</span></td>' +
            '<td><b>' + (s.total_score != null ? s.total_score : '-') + '</b></td></tr>';
    }).join('');

    var rp = document.getElementById('rp');
    if (rankingData.length > pageSize) {
        rp.innerHTML =
            '<span>共' + rankingData.length + '条</span>' +
            '<button onclick="rankingPage--;renderRankingPage()"' + (rankingPage <= 0 ? ' disabled' : '') + '>‹</button>' +
            '<input type="number" id="rpj" min="1" max="' + totalPages + '" value="' + (rankingPage + 1) + '" style="width:56px;text-align:center" onchange="jumpPage(this.value)">' +
            '<span>/ ' + totalPages + '</span>' +
            '<button onclick="rankingPage++;renderRankingPage()"' + (rankingPage >= totalPages - 1 ? ' disabled' : '') + '>›</button>';
    } else {
        rp.innerHTML = '';
    }
}

function jumpPage(v) {
    v = parseInt(v, 10);
    var totalPages = Math.ceil(rankingData.length / pageSize);
    if (!v || v < 1) v = 1;
    if (v > totalPages) v = totalPages;
    rankingPage = v - 1;
    renderRankingPage();
}

// ---- Averages ----
async function loadAverages() {
    try {
        document.getElementById('al').style.display = 'block';
        document.getElementById('at').style.display = 'none';
        var g = document.getElementById('ag').value;
        var sv = resolveSession(document.getElementById('am').value);
        var d = await api('/analysis/averages/?exam_type=monthly&exam_month=' + sv.month + '&exam_session=' + encodeURIComponent(sv.session) + '&group_by=' + g);
        document.querySelector('#at tbody').innerHTML = d.map(function(r) {
            return '<tr><td>' + r.label + '</td><td>' + r.student_count + '</td><td>' + r.avg_sketch + '</td><td>' + r.avg_color + '</td><td>' + r.avg_quick + '</td><td><b>' + r.avg_total + '</b></td></tr>';
        }).join('');
        document.getElementById('al').style.display = 'none';
        document.getElementById('at').style.display = '';
    } catch(e) { console.error(e); }
}

// ---- Score Bands ----
async function loadBands() {
    try {
        var subj = document.getElementById('bs').value;
        var sv = resolveSession(document.getElementById('bm').value);
        var studios = MS['bs-studio'] ? MS['bs-studio'].getValue() : '';
        var classes = MS['bs-class'] ? MS['bs-class'].getValue() : '';
        var base = 'exam_type=monthly&exam_month=' + sv.month + '&exam_session=' + encodeURIComponent(sv.session);
        var f = '';
        if (studios) f += '&studios=' + encodeURIComponent(studios);
        if (classes) f += '&classes=' + encodeURIComponent(classes);
        var data = await api('/analysis/score-distribution/?' + base + '&subject=' + subj + f);
        var idx = await api('/analysis/teaching-index/?' + base + f);

        var sm = {};
        data.forEach(function(d) {
            if (!sm[d.studio]) sm[d.studio] = {};
            sm[d.studio][d.grade] = (sm[d.studio][d.grade] || 0) + d.count;
        });
        var ss = Object.keys(sm);

        var c = echarts.init(document.getElementById('c3'));
        c.setOption({
            tooltip: {trigger: 'axis', axisPointer: {type: 'shadow'}},
            legend: {data: BANDS, bottom: 0, textStyle: {fontSize: 9}},
            grid: {left: 50, right: 20, top: 10, bottom: 50},
            xAxis: {type: 'category', data: ss, axisLabel: {fontSize: 10, rotate: 30}},
            yAxis: {type: 'value', name: '人次'},
            series: BANDS.map(function(b) {
                return {name: b, type: 'bar', stack: 't', data: ss.map(function(st) { return sm[st][b] || 0; })};
            })
        });

        document.querySelector('#tt tbody').innerHTML = idx.map(function(d) {
            var b = sm[d.studio] || {};
            var t = Object.values(b).reduce(function(a, b) { return a + b; }, 0) || 1;
            var pct = function(g) { return ((b[g] || 0) / t * 100).toFixed(1) + '%'; };
            var low = ((b['C+'] || 0) + (b['C'] || 0) + (b['C-'] || 0) + (b['D'] || 0)) / t * 100;
            return '<tr><td>' + d.studio + '</td><td><b>' + d.teaching_index + '</b></td>' +
                '<td>' + pct('A+') + '</td><td>' + pct('A') + '</td><td>' + pct('A-') + '</td>' +
                '<td>' + pct('B+') + '</td><td>' + pct('B') + '</td><td>' + low.toFixed(1) + '%</td></tr>';
        }).join('');
    } catch(e) { console.error(e); }
}

// ---- Joint Exam ----
async function loadJoint() {
    try {
        document.getElementById('jl').style.display = 'block';
        var sv = resolveSession(document.getElementById('js').value);
        var pr = document.getElementById('jp').value;
        var st = MS['js-studio'] ? MS['js-studio'].getValue() : '';
        var cl = MS['js-class'] ? MS['js-class'].getValue() : '';
        var u = '/analysis/ranking/?exam_type=joint&exam_month=' + sv.month + '&exam_session=' + encodeURIComponent(sv.session);
        if (pr) u += '&province=' + encodeURIComponent(pr);
        if (st) u += '&studios=' + encodeURIComponent(st);
        if (cl) u += '&classes=' + encodeURIComponent(cl);
        var d = await api(u);
        document.querySelector('#jt tbody').innerHTML = d.map(function(r) {
            return '<tr><td><b>' + r.rank + '</b></td><td>' + (r.student_name || '') + '</td><td>' + (r.student_code || '') + '</td><td>' + (r.province || '-') + '</td><td>' + (r.studio_name || '-') + '</td><td>' + (r.sketch_score != null ? r.sketch_score : '-') + '</td><td>' + (r.color_score != null ? r.color_score : '-') + '</td><td>' + (r.quick_score != null ? r.quick_score : '-') + '</td><td><b>' + (r.total_score != null ? r.total_score : '-') + '</b></td></tr>';
        }).join('');
        document.getElementById('jl').style.display = 'none';
    } catch(e) { console.error(e); }
}

// ---- Groups ----
var GROUP_TYPE = 'monthly';
var GROUP_SESSION_LIST = [];

function populateGroupSessions() {
    var el = document.getElementById('gs');
    if (!el) return;
    GROUP_SESSION_LIST = SESSIONS[GROUP_TYPE] || [];
    // 时间筛选（date input）只能表达真实日期场次，过滤掉各省模考等命名场次
    var dates = GROUP_SESSION_LIST.filter(function(s) {
        return /^\d{4}-\d{2}-\d{2}$/.test(s.date || '');
    });
    if (!dates.length) {
        el.value = ''; el.min = ''; el.max = '';
        return;
    }
    el.min = dates[0].date;
    el.max = dates[dates.length - 1].date;
    // 默认选人数最多的日期场次（团体生成绩分散，人数最多的场次覆盖最全）
    var best = dates[0];
    dates.forEach(function(s) {
        if ((s.count || 0) > (best.count || 0)) best = s;
    });
    el.value = best.date;
}

function switchGroupType(type) {
    GROUP_TYPE = type;
    var mt = document.getElementById('gtab-monthly');
    var jt = document.getElementById('gtab-joint');
    if (mt) mt.classList.toggle('active', type === 'monthly');
    if (jt) jt.classList.toggle('active', type === 'joint');
    populateGroupSessions();
    loadGroups();
}

async function loadGroups() {
    try {
        var gl = document.getElementById('gl');
        var gt = document.getElementById('gt');
        if (!gl || !gt) return;
        gl.style.display = 'block';
        gl.textContent = '加载中...';
        gt.style.display = 'none';
        // 日期筛选未初始化时（首次进入）先填充
        if (!GROUP_SESSION_LIST.length) populateGroupSessions();
        var sv = resolveSession(document.getElementById('gs').value);
        var d = await api('/analysis/groups/?exam_type=' + GROUP_TYPE +
            '&exam_month=' + encodeURIComponent(sv.month) +
            '&exam_session=' + encodeURIComponent(sv.session));
        var list = d.results || d;
        if (!list.length) {
            gl.textContent = '暂无团体生数据';
            return;
        }
        document.querySelector('#gt tbody').innerHTML = list.map(function(g) {
            return '<tr><td>' + esc(g.name) + '</td><td>' + g.count + '</td>' +
                '<td>' + (g.avg_sketch != null ? g.avg_sketch : '-') + '</td>' +
                '<td>' + (g.avg_color != null ? g.avg_color : '-') + '</td>' +
                '<td>' + (g.avg_quick != null ? g.avg_quick : '-') + '</td>' +
                '<td><b>' + (g.avg_total != null ? g.avg_total : '-') + '</b></td></tr>';
        }).join('');
        gl.style.display = 'none';
        gt.style.display = '';
    } catch(e) { console.error(e); }
}

// ---- Import ----
async function handleExcel(input) {
    if (input.files[0]) {
        toast('上传: ' + input.files[0].name);
        var fd = new FormData();
        fd.append('file', input.files[0]);
        try {
            var r = await fetch(API_URL + '/exams/import/excel/', {
                method: 'POST',
                headers: {'Authorization': 'Bearer ' + TOKEN},
                body: fd
            });
            var d = await r.json();
            var errCount = d.errors ? d.errors.length : 0;
            toast('导入: 新增' + d.created + '条, 更新' + (d.updated || 0) + '条, 错误' + errCount + '条');
            if (d.errors && d.errors.length) console.warn('导入错误:', d.errors);
            // 导入后自动刷新筛选与当前页数据
            await loadOptions();
            await loadSessions();
            var active = document.querySelector('nav a.active');
            if (active) {
                var loaders = {dashboard: loadDashboard, ranking: loadRanking, averages: loadAverages,
                               bands: loadBands, joint: loadJoint, groups: loadGroups};
                var fn = loaders[active.dataset.p];
                if (fn) fn();
            }
        } catch(e) { toast('导入失败', 'e'); }
    }
    input.value = '';
}

async function loadSyncStatus() {
    var el = document.getElementById('sr2');
    if (!el) return;
    try {
        var d = await api('/jdy/status/');
        if (d.syncing) {
            el.innerHTML = '<span style="color:var(--tm)">正在后台同步简道云数据…</span>';
        } else if (d.status === 'ok') {
            el.innerHTML = '<span style="color:var(--s)">已同步：学生 ' + d.student_count +
                '，成绩 ' + d.score_count + ' · ' + esc(d.last_success_at || '') + '</span>';
        } else if (d.status === 'incomplete') {
            el.innerHTML = '<span style="color:var(--w)">' + esc(d.message || '上次同步不完整，数据为上次成功结果') + '</span>';
        } else {
            el.innerHTML = '<span style="color:var(--tm)">正在后台同步简道云数据…</span>';
        }
    } catch(e) { console.error(e); }
}

// 轮询同步状态，直到后台同步结束（syncing=false），返回最终状态；超时返回 null
async function waitSync(timeoutMs) {
    var t0 = Date.now();
    timeoutMs = timeoutMs || 600000;
    while (Date.now() - t0 < timeoutMs) {
        try {
            var d = await api('/jdy/status/');
            if (!d.syncing) return d;
        } catch(e) {}
        await new Promise(function(r) { setTimeout(r, 2000); });
    }
    return null;
}

// 同步结束后重新加载筛选与当前页数据
async function reloadCurrent() {
    await loadOptions();
    await loadSessions();
    var active = document.querySelector('nav a.active');
    if (active) {
        var loaders = {dashboard: loadDashboard, ranking: loadRanking, averages: loadAverages,
                       bands: loadBands, joint: loadJoint, groups: loadGroups};
        var fn = loaders[active.dataset.p];
        if (fn) fn();
    }
}

async function refreshData() {
    var btn = document.getElementById('br2');
    var el = document.getElementById('sr2');
    btn.disabled = true;
    if (el) el.innerHTML = '<span style="color:var(--tm)">正在同步简道云数据…</span>';
    try {
        var r = await fetch(API_URL + '/jdy/refresh/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN},
            body: JSON.stringify({})
        });
        await r.json();
        var st = await waitSync();
        await loadSyncStatus();
        if (st && st.status === 'ok') {
            toast('同步完成');
        } else if (st) {
            toast('同步不完整（保留上次数据）', 'e');
        } else {
            toast('同步超时，请稍后在数据导入页查看状态', 'e');
        }
        await reloadCurrent();
    } catch(e) { toast('失败', 'e'); }
    btn.disabled = false;
}

// ---- Transition ----
async function doMigrate() {
    var t = document.getElementById('nt').value.trim();
    var c = document.getElementById('cf').value;
    if (!t) { toast('输入新届名称', 'e'); return; }
    if (c !== '确认换届') { toast('输入确认换届', 'e'); return; }
    if (!confirm('确认换届到' + t + '？此操作不可逆！')) return;
    var btn = document.getElementById('mb');
    btn.disabled = true; btn.textContent = '执行中...';
    try {
        var r = await fetch(API_URL + '/transition/migrate/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN},
            body: JSON.stringify({new_term: t, confirm: c})
        });
        var d = await r.json();
        if (d.ok) {
            toast('换届完成，正在后台同步新届数据…');
            document.getElementById('nt').value = '';
            document.getElementById('cf').value = '';
            var st = await waitSync();
            await loadSyncStatus();
            if (st && st.status === 'ok') toast('同步完成');
            else if (st) toast('同步不完整（保留上次数据）', 'e');
            await reloadCurrent();
        } else toast(d.error || '失败', 'e');
    } catch(e) { toast('失败', 'e'); }
    btn.disabled = false; btn.textContent = '执行换届';
}

// ---- Init ----
login();
