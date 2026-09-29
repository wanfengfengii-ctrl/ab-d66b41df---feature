import "./styles.css";

const PRESETS = {
  reject: {
    label: "拒收演示：读数全合格、途中升温",
    records: [
      { time: 0, box_temp: 4.0, ambient_temp: 25, lid_open: false },
      { time: 60, box_temp: 7.806654, ambient_temp: 25, lid_open: false },
      { time: 1560, box_temp: 7.254505, ambient_temp: 3, lid_open: false },
      { time: 2460, box_temp: 3.211819, ambient_temp: 3, lid_open: false },
      { time: 3360, box_temp: 3.010546, ambient_temp: 3, lid_open: false },
    ],
    parameters: { tau_closed: 300, tau_open: 90, box_temp_limit: 8, exposure_limit_seconds: 600 },
  },
  pass: {
    label: "放行演示：全程低温",
    records: [
      { time: 0, box_temp: 4.0, ambient_temp: 3.0, lid_open: false },
      { time: 300, box_temp: 3.551819, ambient_temp: 3.5, lid_open: false },
      { time: 600, box_temp: 3.703003, ambient_temp: 4.0, lid_open: false },
      { time: 900, box_temp: 3.817165, ambient_temp: 3.8, lid_open: false },
      { time: 1200, box_temp: 3.585587, ambient_temp: 3.2, lid_open: false },
      { time: 1500, box_temp: 3.268274, ambient_temp: 3.0, lid_open: false },
      { time: 1800, box_temp: 3.025116, ambient_temp: 2.8, lid_open: false },
      { time: 2100, box_temp: 2.772452, ambient_temp: 2.5, lid_open: false },
      { time: 2400, box_temp: 2.41629, ambient_temp: 2.0, lid_open: false },
    ],
    parameters: { tau_closed: 300, tau_open: 90, box_temp_limit: 8, exposure_limit_seconds: 600 },
  },
  short: {
    label: "短时超温：有暴露但不足时长",
    records: [
      { time: 0, box_temp: 4.0, ambient_temp: 4, lid_open: false },
      { time: 600, box_temp: 15.92102, ambient_temp: 25, lid_open: true },
      { time: 1200, box_temp: 23.771294, ambient_temp: 25, lid_open: false },
      { time: 1800, box_temp: 12.912692, ambient_temp: 4, lid_open: false },
    ],
    parameters: { tau_closed: 300, tau_open: 90, box_temp_limit: 8, exposure_limit_seconds: 3600 },
  },
  core: {
    label: "箱体放行但核心拒收：探头合格、油样未降温",
    records: [
      { time: 0, box_temp: 4.0, ambient_temp: 7.5, lid_open: false },
      { time: 600, box_temp: 7.026327, ambient_temp: 7.5, lid_open: false },
      { time: 1200, box_temp: 7.435895, ambient_temp: 7.5, lid_open: false },
      { time: 1800, box_temp: 7.491324, ambient_temp: 7.5, lid_open: false },
      { time: 2400, box_temp: 7.498826, ambient_temp: 7.5, lid_open: false },
    ],
    parameters: { tau_closed: 300, tau_open: 90, box_temp_limit: 8, exposure_limit_seconds: 600 },
    coreReview: {
      enabled: true,
      sample_initial_temp: 4.0,
      tau_sample_seconds: 900,
      core_temp_limit: 6.0,
    },
  },
};

const state = {
  records: structuredClone(PRESETS.reject.records),
  parameters: { ...PRESETS.reject.parameters },
  // 核心温度复核（可选；默认不启用，请求/结论/证据保持原样）
  coreReview: {
    enabled: false,
    sample_initial_temp: 4.0,
    tau_sample_seconds: 300,
    core_temp_limit: 8.0,
  },
  result: null,
  error: null,
  loading: false,
};

const app = document.getElementById("app");

function fmtElapsed(sec) {
  const s = Math.round(sec);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  return `${m}:${String(r).padStart(2, "0")}`;
}
function fmtTemp(v) {
  return Number(v).toFixed(2);
}
function fmtDuration(sec) {
  const s = Number(sec);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = Math.round(s % 60);
  if (h > 0) return `${h} 小时 ${m} 分 ${r} 秒`;
  if (m > 0) return `${m} 分 ${r} 秒`;
  return `${r} 秒`;
}

/* ---------------- 录入区 ---------------- */

function renderForm() {
  const p = state.parameters;
  return `
  <div class="panel">
    <h2>① 运输记录（按时间严格递增，4–30 条）</h2>
    <div style="max-height:340px;overflow:auto">
    <table class="records">
      <thead><tr>
        <th style="width:26%"># 时间(秒或ISO)</th><th>箱温℃</th><th>环境温℃</th><th>箱盖开启</th><th></th>
      </tr></thead>
      <tbody>
        ${state.records
          .map(
            (r, i) => `
        <tr>
          <td><input data-k="time" data-i="${i}" value="${r.time}" /></td>
          <td><input data-k="box_temp" data-i="${i}" type="number" step="0.01" value="${r.box_temp}" /></td>
          <td><input data-k="ambient_temp" data-i="${i}" type="number" step="0.01" value="${r.ambient_temp}" /></td>
          <td style="text-align:center"><input data-k="lid_open" data-i="${i}" type="checkbox" ${r.lid_open ? "checked" : ""} /></td>
          <td><button class="row-btn" data-del="${i}" title="删除该行">✕</button></td>
        </tr>`
          )
          .join("")}
      </tbody>
    </table>
    </div>
    <div class="count-note">当前 ${state.records.length} 条（须 4–30 条）</div>

    <h2 style="margin-top:18px">② 模型参数与保存要求</h2>
    <div class="params-grid">
      <label class="field"><span>箱盖关闭热惯性 τ关闭（秒）</span>
        <input id="tau_closed" type="number" step="any" value="${p.tau_closed}" /></label>
      <label class="field"><span>箱盖开启热惯性 τ开启（秒）</span>
        <input id="tau_open" type="number" step="any" value="${p.tau_open}" /></label>
      <label class="field"><span>允许箱温（℃）</span>
        <input id="box_temp_limit" type="number" step="0.1" value="${p.box_temp_limit}" /></label>
      <label class="field"><span>允许连续暴露时长（秒）</span>
        <input id="exposure_limit_seconds" type="number" step="any" value="${p.exposure_limit_seconds}" /></label>
    </div>
    <div class="hint">约定：相邻记录之间环境温度按<b>线性变化</b>；箱温按一阶模型
      <code>dT/dt=(T_env−T)/τ</code> 逐段闭式求解；箱盖状态在记录时刻切换 τ。</div>

    <h2 style="margin-top:18px">③ 核心温度复核（可选，默认不启用）</h2>
    <label class="field check-field">
      <input id="core_enabled" type="checkbox" ${state.coreReview.enabled ? "checked" : ""} />
      <span>启用“核心温度复核”：以连续箱温闭式曲线驱动样品一阶响应，跨记录传递核心温度，
      不在每条记录处重新锚定</span>
    </label>
    <div class="params-grid" id="core-fields" style="${state.coreReview.enabled ? "" : "display:none"}">
      <label class="field"><span>首条记录时的样品温度（℃）</span>
        <input id="sample_initial_temp" type="number" step="any" value="${state.coreReview.sample_initial_temp}" /></label>
      <label class="field"><span>样品对箱温的热惯性 τ样品（秒，&gt;0）</span>
        <input id="tau_sample_seconds" type="number" step="any" value="${state.coreReview.tau_sample_seconds}" /></label>
      <label class="field"><span>核心温度上限（℃）</span>
        <input id="core_temp_limit" type="number" step="any" value="${state.coreReview.core_temp_limit}" /></label>
    </div>
    <div class="hint" id="core-off-hint" style="${state.coreReview.enabled ? "display:none" : ""}">
      未启用时，原请求、结论与证据保持不变（仅做箱体探头裁决）。</div>

    <div class="btn-row">
      <button class="action" id="submit">提交审计</button>
      <button class="ghost" id="addRow">+ 增加记录</button>
    </div>
    <div class="btn-row">
      <button class="ghost" data-preset="reject">拒收演示数据</button>
      <button class="ghost" data-preset="pass">放行演示数据</button>
      <button class="ghost" data-preset="short">短时超温数据</button>
      <button class="ghost" data-preset="core">箱体放行·核心拒收</button>
    </div>
    ${state.error ? `<div class="error-box">${state.error}</div>` : ""}
  </div>`;
}

function collectInputs() {
  const recs = state.records.map((r, i) => {
    const t = document.querySelector(`[data-k="time"][data-i="${i}"]`).value.trim();
    return {
      time: /^-?\d+(\.\d+)?$/.test(t) ? Number(t) : t,
      box_temp: Number(document.querySelector(`[data-k="box_temp"][data-i="${i}"]`).value),
      ambient_temp: Number(document.querySelector(`[data-k="ambient_temp"][data-i="${i}"]`).value),
      lid_open: document.querySelector(`[data-k="lid_open"][data-i="${i}"]`).checked,
    };
  });
  const params = {
    tau_closed: Number(document.getElementById("tau_closed").value),
    tau_open: Number(document.getElementById("tau_open").value),
    box_temp_limit: Number(document.getElementById("box_temp_limit").value),
    exposure_limit_seconds: Number(document.getElementById("exposure_limit_seconds").value),
  };
  const coreEnabled = document.getElementById("core_enabled").checked;
  const coreReview = {
    enabled: coreEnabled,
    sample_initial_temp: Number(document.getElementById("sample_initial_temp").value),
    tau_sample_seconds: Number(document.getElementById("tau_sample_seconds").value),
    core_temp_limit: Number(document.getElementById("core_temp_limit").value),
  };
  return { recs, params, coreReview };
}

async function submitAudit() {
  const { recs, params, coreReview } = collectInputs();
  state.records = recs;
  state.parameters = params;
  state.coreReview = coreReview;
  state.loading = true;
  state.error = null;
  state.result = null;
  render();
  // 仅在启用时上送核心温度复核；未启用时请求与原先完全一致
  const payload = { records: recs, parameters: params };
  if (coreReview.enabled) payload.core_temperature_review = coreReview;
  try {
    const resp = await fetch("/api/audit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await resp.json();
    if (body.status === "invalid") {
      state.error = body.errors
        .map((e) => `<div><code>${e.code}</code> ${e.message}${e.field ? `（字段：${e.field}）` : ""}</div>`)
        .join("");
    } else {
      state.result = body;
    }
  } catch (e) {
    state.error = `无法连接审计 API：${e.message}`;
  } finally {
    state.loading = false;
    render();
  }
}

/* ---------------- 结果区 ---------------- */

function renderVerdict(r) {
  if (state.loading) return `<div class="verdict"><div class="badge">…</div><div class="sub">正在连续求解各段箱温${state.coreReview.enabled ? "与样品核心温度" : ""}…</div></div>`;
  if (state.error)
    return `<div class="verdict invalid"><div class="badge">数据不合法</div>
      <div class="sub">服务端拒绝裁决，请依据右侧字段提示修正后重新提交。</div></div>`;
  if (!r)
    return `<div class="verdict"><div class="badge" style="background:var(--panel-2);color:var(--muted)">待提交</div>
      <div class="sub">填写记录与参数后点击「提交审计」，服务端将以一阶热响应模型逐段解析求解。</div></div>`;

  const cb = r.core_temperature_review;
  // 未启用复核时响应无 box_status，箱体结论即顶层 status
  const boxReject = (r.box_status ?? r.status) === "reject";

  if (r.status === "pass") {
    return `<div class="verdict pass"><div class="badge">放 行</div>
      <div class="sub">箱温连续曲线全程未形成达到 <strong>${fmtDuration(
        r.parameters.exposure_limit_seconds
      )}</strong> 的连续超温区间。<br/>
      累计超温时长 <strong>${fmtDuration(r.total_exceedance_seconds)}</strong>，
      连续超温区间 <strong>${r.exceedance_intervals.length}</strong> 个。
      ${cb ? `<br/>核心温度复核：<strong>未越限</strong>（核心最高 ${fmtTemp(cb.core_max_temp)}℃ ≤ 上限 ${fmtTemp(cb.core_temp_limit)}℃）。` : ""}</div></div>`;
  }

  // 总体拒收：区分箱体拒收 / 核心拒收 / 两者
  const badgeText = cb && !boxReject ? "核心拒收" : "拒 收";
  const lines = [];
  if (boxReject) {
    const ff = r.first_failure_time;
    lines.push(`箱体探头超限：存在连续超温达到 <strong>${fmtDuration(
      r.parameters.exposure_limit_seconds
    )}</strong> 的区间，油样自 <strong>${ff.time}</strong>
      （距首条记录 ${fmtElapsed(ff.elapsed_seconds)}）起失效。`);
  } else {
    lines.push(`箱体探头裁决：<strong>放行</strong>（箱温读数与连续曲线均未触发箱体拒收）。`);
  }
  if (cb) {
    if (cb.status === "reject") {
      const rk = cb.first_risk_time;
      lines.push(`<strong style="color:var(--core)">核心温度超限</strong>：探头合格不代表油样内部已降温，
        样品核心温度最早于 <strong>${rk.time}</strong>（距首条记录 ${fmtElapsed(rk.elapsed_seconds)}）
        越过上限 ${fmtTemp(cb.core_temp_limit)}℃；核心最高 ${fmtTemp(cb.core_max_temp)}℃。`);
    } else {
      lines.push(`核心温度复核：<strong>未越限</strong>（核心最高 ${fmtTemp(cb.core_max_temp)}℃）。`);
    }
  }
  return `<div class="verdict ${cb && !boxReject ? "core" : "reject"}">
    <div class="badge">${badgeText}</div>
    <div class="sub">${lines.join("<br/>")}<br/>
    共 ${r.exceedance_intervals.length} 个箱体连续超温区间，累计箱温超温 ${fmtDuration(
    r.total_exceedance_seconds
  )}。</div></div>`;
}

function renderFailureCard(r) {
  // 仅在箱体探头本身拒斥时展示箱温失效卡；箱体放行但核心拒收由核心卡呈现
  const boxStatus = r.box_status ?? r.status;
  if (!r || boxStatus !== "reject" || !r.first_failure_time) return "";
  const ff = r.first_failure_time;
  const iv = r.exceedance_intervals[ff.interval_index];
  return `<div class="failure-card">
    <h3>最早失效时刻证据</h3>
    <div class="kv">
      超温区间起点：<b>${iv.start_time}</b>（${fmtElapsed(iv.elapsed_start_seconds)}）<br/>
      连续超温区间终点：<b>${iv.end_time}</b>（${fmtElapsed(iv.elapsed_end_seconds)}）<br/>
      该区间持续：<b>${fmtDuration(iv.duration_seconds)}</b> ≥ 允许 ${fmtDuration(
    r.parameters.exposure_limit_seconds
  )}<br/>
      最早失效时刻 = 区间起点 + 允许暴露时长 = <b>${ff.time}</b>
      （距首条记录 ${fmtElapsed(ff.elapsed_seconds)}）
    </div></div>`;
}

/* ---------------- SVG 连续曲线 ---------------- */

function buildChart(r) {
  const W = 920, H = 380, ML = 56, MR = 18, MT = 18, MB = 44;
  const iw = W - ML - MR, ih = H - MT - MB;
  const curve = r.curve;
  const cb = r.core_temperature_review;
  const coreCurve = cb?.curve ?? null;
  const xmax = curve[curve.length - 1].elapsed_seconds;
  const allT = curve.flatMap((p) => [p.box_temp, p.ambient_temp]).concat([r.parameters.box_temp_limit]);
  if (coreCurve) {
    coreCurve.forEach((p) => allT.push(p.core_temp));
    allT.push(cb.core_temp_limit);
  }
  let ymin = Math.min(...allT), ymax = Math.max(...allT);
  const pad = Math.max(1, (ymax - ymin) * 0.08);
  ymin -= pad; ymax += pad;
  const X = (t) => ML + (t / xmax) * iw;
  const Y = (v) => MT + ih - ((v - ymin) / (ymax - ymin)) * ih;

  // 箱盖开启背景（由连续曲线点合并相邻同状态）
  const lidRects = [];
  let start = null;
  for (let i = 0; i < curve.length; i++) {
    if (curve[i].lid_open && start === null) start = curve[i].elapsed_seconds;
    if ((!curve[i].lid_open || i === curve.length - 1) && start !== null) {
      const end = curve[i].lid_open ? curve[i].elapsed_seconds : curve[i - 1].elapsed_seconds;
      lidRects.push([start, end]);
      start = null;
    }
  }

  const path = (key) =>
    curve.map((p, i) => `${i === 0 ? "M" : "L"}${X(p.elapsed_seconds).toFixed(2)},${Y(p[key]).toFixed(2)}`).join(" ");

  // 核心温度曲线（叠加）：x 网格与箱温一致，按 elapsed 对齐
  const corePath = coreCurve
    ? coreCurve
        .map((p, i) => `${i === 0 ? "M" : "L"}${X(p.elapsed_seconds).toFixed(2)},${Y(p.core_temp).toFixed(2)}`)
        .join(" ")
    : "";

  // 箱温超温区间红色遮罩
  const hotRects = r.exceedance_intervals
    .map(
      (iv) =>
        `<rect x="${X(iv.elapsed_start_seconds)}" y="${MT}" width="${
          X(iv.elapsed_end_seconds) - X(iv.elapsed_start_seconds)
        }" height="${ih}" fill="#ff5d5d" fill-opacity="0.12" />`
    )
    .join("");

  // 核心超限区间紫色遮罩（叠加在箱温图上）
  const coreRects = coreCurve
    ? cb.exceedance_intervals
        .map(
          (iv) =>
            `<rect x="${X(iv.elapsed_start_seconds)}" y="${MT}" width="${
              X(iv.elapsed_end_seconds) - X(iv.elapsed_start_seconds)
            }" height="${ih}" fill="#c78dff" fill-opacity="0.16" />`
        )
        .join("")
    : "";

  const lid = lidRects
    .map(
      ([a, b]) =>
        `<rect x="${X(a)}" y="${MT}" width="${X(b) - X(a)}" height="${ih}" fill="#f5a623" fill-opacity="0.10" />`
    )
    .join("");

  // 坐标轴与网格
  const yTicks = [];
  const steps = 5;
  for (let k = 0; k <= steps; k++) {
    const v = ymin + ((ymax - ymin) * k) / steps;
    yTicks.push(`<line x1="${ML}" y1="${Y(v)}" x2="${W - MR}" y2="${Y(v)}" stroke="#22303f" stroke-width="1"/>
      <text x="${ML - 8}" y="${Y(v) + 4}" fill="#93a4b5" font-size="11" text-anchor="end">${v.toFixed(1)}</text>`);
  }
  const xTicks = [];
  const nx = 6;
  for (let k = 0; k <= nx; k++) {
    const t = (xmax * k) / nx;
    xTicks.push(`<line x1="${X(t)}" y1="${MT + ih}" x2="${X(t)}" y2="${MT + ih + 5}" stroke="#93a4b5"/>
      <text x="${X(t)}" y="${MT + ih + 20}" fill="#93a4b5" font-size="11" text-anchor="middle">${fmtElapsed(t)}</text>`);
  }

  const limit = r.parameters.box_temp_limit;
  const dots = r.records_echo
    .map(
      (rec) =>
        `<circle cx="${X(rec.elapsed_seconds)}" cy="${Y(rec.box_temp)}" r="4.5" fill="#0f1720" stroke="#e6edf3" stroke-width="2">
          <title>记录 ${rec.time}：箱温 ${fmtTemp(rec.box_temp)}℃，环境 ${fmtTemp(
          rec.ambient_temp
        )}℃，箱盖${rec.lid_open ? "开启" : "关闭"}</title></circle>`
    )
    .join("");

  const ff = r.first_failure_time;
  const ffLine = ff
    ? `<line x1="${X(ff.elapsed_seconds)}" y1="${MT}" x2="${X(ff.elapsed_seconds)}" y2="${MT + ih}"
        stroke="#ff5d5d" stroke-width="1.6" stroke-dasharray="6 4"/>
      <text x="${X(ff.elapsed_seconds)}" y="${MT + 12}" fill="#ff5d5d" font-size="11" text-anchor="middle">最早失效 ${ff.time}</text>`
    : "";

  const coreLimitLine = coreCurve
    ? `<line x1="${ML}" y1="${Y(cb.core_temp_limit)}" x2="${W - MR}" y2="${Y(cb.core_temp_limit)}" stroke="#c78dff" stroke-width="1.4" stroke-dasharray="2 5"/>
      <text x="${W - MR}" y="${Y(cb.core_temp_limit) + 14}" fill="#c78dff" font-size="11" text-anchor="end">核心温度上限 ${cb.core_temp_limit}℃</text>`
    : "";

  const rk = cb?.first_risk_time ?? null;
  const riskLine = rk
    ? `<line x1="${X(rk.elapsed_seconds)}" y1="${MT}" x2="${X(rk.elapsed_seconds)}" y2="${MT + ih}"
        stroke="#c78dff" stroke-width="1.6" stroke-dasharray="6 4"/>
      <text x="${X(rk.elapsed_seconds)}" y="${MT + 26}" fill="#c78dff" font-size="11" text-anchor="middle">最早风险 ${rk.time}</text>`
    : "";

  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="箱温与样品核心温度连续曲线">
    ${lid}${hotRects}${coreRects}
    ${yTicks.join("")}${xTicks.join("")}
    <line x1="${ML}" y1="${Y(limit)}" x2="${W - MR}" y2="${Y(limit)}" stroke="#f5a623" stroke-width="1.6" stroke-dasharray="8 4"/>
    <text x="${W - MR}" y="${Y(limit) - 5}" fill="#f5a623" font-size="11" text-anchor="end">允许箱温 ${limit}℃</text>
    <path d="${path("ambient_temp")}" fill="none" stroke="#7d8fa1" stroke-width="1.6" stroke-dasharray="3 3"/>
    <path d="${path("box_temp")}" fill="none" stroke="#4da3ff" stroke-width="2.4"/>
    ${coreCurve ? `<path d="${corePath}" fill="none" stroke="#c78dff" stroke-width="2.4"/>` : ""}
    ${coreLimitLine}
    ${dots}${ffLine}${riskLine}
    <line x1="${ML}" y1="${MT + ih}" x2="${W - MR}" y2="${MT + ih}" stroke="#93a4b5"/>
    <line x1="${ML}" y1="${MT}" x2="${ML}" y2="${MT + ih}" stroke="#93a4b5"/>
    <text x="${ML}" y="${H - 6}" fill="#93a4b5" font-size="11">经过时间（时:分:秒） →</text>
  </svg>
  <div class="legend">
    <span class="swatch"><i style="background:#4da3ff"></i>箱温连续曲线（闭式解析解）</span>
    <span class="swatch"><i style="background:#7d8fa1"></i>环境温（段间线性）</span>
    <span class="swatch"><i style="background:#f5a623"></i>允许箱温</span>
    ${coreCurve ? `<span class="swatch"><i style="background:#c78dff"></i>样品核心温度（叠加）</span>
    <span class="swatch"><i style="background:#c78dff;opacity:.5"></i>核心温度上限</span>
    <span class="swatch"><i style="background:rgba(199,141,255,.25);border:1px solid #c78dff"></i>核心超限区间</span>` : ""}
    <span class="swatch"><i style="background:var(--hot);border:1px solid #ff5d5d"></i>箱温连续超温区间</span>
    <span class="swatch"><i style="background:var(--lid);border:1px solid #f5a623"></i>箱盖开启时段</span>
    <span class="swatch">◦ 空心圆点为录入的箱温读数</span>
  </div>`;
}

/* ---------------- 表格 ---------------- */

function renderIntervals(r) {
  if (!r.exceedance_intervals.length)
    return `<div class="hint">无任何箱温超过允许值的连续区间。</div>`;
  return `<table class="data">
    <thead><tr><th>#</th><th>起始时刻</th><th>结束时刻</th><th class="num">持续时长(秒)</th><th>是否达到暴露限额</th></tr></thead>
    <tbody>${r.exceedance_intervals
      .map(
        (iv) => `<tr>
        <td>${iv.index + 1}</td><td>${iv.start_time}</td><td>${iv.end_time}</td>
        <td class="num">${fmtDuration(iv.duration_seconds)}（${iv.duration_seconds.toFixed(1)}s）</td>
        <td><span class="tag ${iv.reaches_limit ? "yes" : "no"}">${iv.reaches_limit ? "达到 → 拒收" : "未达到"}</span></td>
      </tr>`
      )
      .join("")}</tbody></table>`;
}

function renderSegments(r) {
  return `<table class="data">
    <thead><tr>
      <th>#</th><th>段起→止(s)</th><th>箱盖</th><th class="num">τ(秒)</th>
      <th class="num">段内最高℃</th><th>最高位置</th>
      <th class="num">段内最低℃</th><th>穿越(相对秒)</th>
    </tr></thead>
    <tbody>${r.segments
      .map((s) => {
        const cross = s.crossings
          .map((c) => `<span class="${c.direction}">${c.direction === "up" ? "↑上穿" : "↓下穿"}@${c.elapsed_seconds.toFixed(1)}</span>`)
          .join("，");
        return `<tr>
        <td>${s.index + 1}</td>
        <td>${s.elapsed_start_seconds} → ${s.elapsed_end_seconds}<br/><span class="hint" style="margin:0">${s.duration_seconds.toFixed(0)}s</span></td>
        <td><span class="tag ${s.lid_open ? "open" : "closed"}">${s.lid_open ? "开启" : "关闭"}</span></td>
        <td class="num">${s.tau_seconds}</td>
        <td class="num">${fmtTemp(s.max_temp.value)}</td>
        <td>${s.max_temp.kind === "interior" ? "段内 " + s.max_temp.elapsed_seconds.toFixed(1) + "s" : s.max_temp.kind === "start" ? "段起点" : "段终点"}</td>
        <td class="num">${fmtTemp(s.min_temp.value)}</td>
        <td>${cross || "—"}</td>
      </tr>`;
      })
      .join("")}</tbody></table>`;
}

function renderCoreCard(r) {
  const cb = r.core_temperature_review;
  if (!cb) return "";
  if (cb.status === "pass") {
    return `<div class="core-card pass">
      <h3>核心温度复核：未越限</h3>
      <div class="kv">
        首条记录时样品温度 <b>${fmtTemp(cb.sample_initial_temp)}℃</b>，
        样品热惯性 τ样品 <b>${cb.tau_sample_seconds}s</b>，核心温度上限 <b>${fmtTemp(cb.core_temp_limit)}℃</b>。<br/>
        全程核心温度区间 <b>${fmtTemp(cb.core_min_temp)}℃ ~ ${fmtTemp(cb.core_max_temp)}℃</b>，
        末条记录时核心温度 <b>${fmtTemp(cb.sample_final_temp)}℃</b>，<b>未越过上限</b>，最早风险时刻：无。
      </div></div>`;
  }
  const rk = cb.first_risk_time;
  const iv = cb.exceedance_intervals[rk.interval_index];
  return `<div class="core-card reject">
    <h3>核心温度复核：核心超限（探头合格 ≠ 油样已降温）</h3>
    <div class="kv">
      样品热惯性 τ样品 <b>${cb.tau_sample_seconds}s</b>，核心温度上限 <b>${fmtTemp(cb.core_temp_limit)}℃</b>。<br/>
      核心温度最早于 <b>${rk.time}</b>（距首条记录 ${fmtElapsed(rk.elapsed_seconds)}）
      越过上限；全程核心最高 <b>${fmtTemp(cb.core_max_temp)}℃</b>。<br/>
      首个核心超限区间：<b>${iv.start_time}</b> → <b>${iv.end_time}</b>
      （持续 ${fmtDuration(iv.duration_seconds)}）。
    </div></div>`;
}

function renderCoreIntervals(cb) {
  if (!cb.exceedance_intervals.length)
    return `<div class="hint">核心温度全程未超过上限。</div>`;
  return `<table class="data">
    <thead><tr><th>#</th><th>起始时刻</th><th>结束时刻</th><th class="num">持续时长(秒)</th></tr></thead>
    <tbody>${cb.exceedance_intervals
      .map(
        (iv) => `<tr>
        <td>${iv.index + 1}</td><td>${iv.start_time}</td><td>${iv.end_time}</td>
        <td class="num">${fmtDuration(iv.duration_seconds)}（${iv.duration_seconds.toFixed(1)}s）</td>
      </tr>`
      )
      .join("")}</tbody></table>`;
}

function renderCoreSegments(cb) {
  return `<table class="data">
    <thead><tr>
      <th>#</th><th>段起→止(s)</th><th>箱盖</th>
      <th class="num">τ箱/τ样品(秒)</th>
      <th class="num">核心起℃</th><th class="num">核心止℃</th>
      <th class="num">段内最高℃</th><th class="num">段内最低℃</th>
      <th>核心穿越(相对秒)</th>
    </tr></thead>
    <tbody>${cb.segments
      .map((s) => {
        const cross = s.crossings
          .map((c) => `<span class="${c.direction === "up" ? "core-up" : "core-down"}">${c.direction === "up" ? "↑上穿" : "↓下穿"}@${c.elapsed_seconds.toFixed(1)}</span>`)
          .join("，");
        const deg = s.degenerate_equal_tau ? ' <span class="tag open" title="样品热惯性等于箱体热惯性，采用极限闭式解">等τ</span>' : "";
        return `<tr>
        <td>${s.index + 1}</td>
        <td>${s.elapsed_start_seconds} → ${s.elapsed_end_seconds}<br/><span class="hint" style="margin:0">${s.duration_seconds.toFixed(0)}s</span></td>
        <td><span class="tag ${s.lid_open ? "open" : "closed"}">${s.lid_open ? "开启" : "关闭"}</span></td>
        <td class="num">${s.tau_box_seconds} / ${s.tau_sample_seconds}${deg}</td>
        <td class="num">${fmtTemp(s.core_temp_start)}</td>
        <td class="num">${fmtTemp(s.core_temp_end)}</td>
        <td class="num">${fmtTemp(s.max_temp.value)}<br/><span class="hint" style="margin:0">${s.max_temp.kind === "interior" ? "段内" + s.max_temp.elapsed_seconds.toFixed(0) + "s" : s.max_temp.kind === "start" ? "段起点" : "段终点"}</span></td>
        <td class="num">${fmtTemp(s.min_temp.value)}</td>
        <td>${cross || "—"}</td>
      </tr>`;
      })
      .join("")}</tbody></table>`;
}

function renderResult(r) {
  if (!r) return "";
  const cb = r.core_temperature_review;
  return `
  <div class="model-note">
    求解方式：<code>${r.model.equation}</code>；${r.model.ambient_assumption}；${r.model.solver}。<br/>
    每段以记录时刻实测箱温为初值锚定（段末模型值与下一读数偏差见审计数据），
    ${r.model.tau_switching}。${r.model.exceedance_rule}。
    ${cb ? `<br/><b style="color:var(--core)">核心温度复核已启用</b>：${cb.model.equation}；${cb.model.driver}；${cb.model.initial_condition}` : ""}
  </div>
  ${renderFailureCard(r)}
  ${renderCoreCard(r)}
  <div class="chart-wrap">${buildChart(r)}</div>

  <div class="section-title">箱体连续超温区间（跨记录取并集）</div>
  ${renderIntervals(r)}

  <div class="section-title">各段箱温解析极值与阈值穿越</div>
  ${renderSegments(r)}

  ${cb ? `<div class="section-title core-title">核心温度连续超限区间（首个上穿即最早风险时刻）</div>
  ${renderCoreIntervals(cb)}

  <div class="section-title core-title">各段核心温度起止状态、解析极值与阈值穿越</div>
  ${renderCoreSegments(cb)}` : ""}`;
}

function render() {
  app.innerHTML = `
  <header>
    <h1>海上平台油样运输箱 · 温控审计</h1>
    <p>一阶热响应模型逐段闭式解析 · 阈值穿越精确定位 · 跨记录连续暴露累计 —— 拒绝"只看离散读数"的误放行</p>
  </header>
  <div class="layout">
    ${renderForm()}
    <div>
      ${renderVerdict(state.result)}
      ${state.result ? renderResult(state.result) : `<div class="chart-wrap"><div class="hint">提交后在此展示箱温连续曲线、各段解析极值、累计暴露区间与最早失效时刻。</div></div>`}
    </div>
  </div>`;
  bind();
}

function bind() {
  document.getElementById("submit")?.addEventListener("click", submitAudit);
  document.getElementById("core_enabled")?.addEventListener("change", () => {
    const { recs, params, coreReview } = collectInputs();
    state.records = recs; state.parameters = params; state.coreReview = coreReview;
    render();
  });
  document.getElementById("addRow")?.addEventListener("click", () => {
    const { recs, params, coreReview } = collectInputs();
    if (recs.length >= 30) return;
    const last = recs[recs.length - 1];
    recs.push({
      time: typeof last.time === "number" ? last.time + 600 : last.time,
      box_temp: last.box_temp, ambient_temp: last.ambient_temp, lid_open: false,
    });
    state.records = recs; state.parameters = params; state.coreReview = coreReview; render();
  });
  document.querySelectorAll("[data-del]").forEach((b) =>
    b.addEventListener("click", () => {
      const { recs, params, coreReview } = collectInputs();
      recs.splice(Number(b.dataset.del), 1);
      state.records = recs; state.parameters = params; state.coreReview = coreReview; render();
    })
  );
  document.querySelectorAll("[data-preset]").forEach((b) => {
    b.addEventListener("click", () => {
      const pre = PRESETS[b.dataset.preset];
      state.records = structuredClone(pre.records);
      state.parameters = { ...pre.parameters };
      state.coreReview = pre.coreReview
        ? structuredClone(pre.coreReview)
        : { ...state.coreReview, enabled: false };
      state.result = null; state.error = null; render();
    });
  });
}

render();
