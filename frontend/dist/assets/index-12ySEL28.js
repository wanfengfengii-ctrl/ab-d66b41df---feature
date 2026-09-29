(function(){const e=document.createElement("link").relList;if(e&&e.supports&&e.supports("modulepreload"))return;for(const s of document.querySelectorAll('link[rel="modulepreload"]'))n(s);new MutationObserver(s=>{for(const d of s)if(d.type==="childList")for(const r of d.addedNodes)r.tagName==="LINK"&&r.rel==="modulepreload"&&n(r)}).observe(document,{childList:!0,subtree:!0});function o(s){const d={};return s.integrity&&(d.integrity=s.integrity),s.referrerPolicy&&(d.referrerPolicy=s.referrerPolicy),s.crossOrigin==="use-credentials"?d.credentials="include":s.crossOrigin==="anonymous"?d.credentials="omit":d.credentials="same-origin",d}function n(s){if(s.ep)return;s.ep=!0;const d=o(s);fetch(s.href,d)}})();const T={reject:{label:"拒收演示：读数全合格、途中升温",records:[{time:0,box_temp:4,ambient_temp:25,lid_open:!1},{time:60,box_temp:7.806654,ambient_temp:25,lid_open:!1},{time:1560,box_temp:7.254505,ambient_temp:3,lid_open:!1},{time:2460,box_temp:3.211819,ambient_temp:3,lid_open:!1},{time:3360,box_temp:3.010546,ambient_temp:3,lid_open:!1}],parameters:{tau_closed:300,tau_open:90,box_temp_limit:8,exposure_limit_seconds:600}},pass:{label:"放行演示：全程低温",records:[{time:0,box_temp:4,ambient_temp:3,lid_open:!1},{time:300,box_temp:3.551819,ambient_temp:3.5,lid_open:!1},{time:600,box_temp:3.703003,ambient_temp:4,lid_open:!1},{time:900,box_temp:3.817165,ambient_temp:3.8,lid_open:!1},{time:1200,box_temp:3.585587,ambient_temp:3.2,lid_open:!1},{time:1500,box_temp:3.268274,ambient_temp:3,lid_open:!1},{time:1800,box_temp:3.025116,ambient_temp:2.8,lid_open:!1},{time:2100,box_temp:2.772452,ambient_temp:2.5,lid_open:!1},{time:2400,box_temp:2.41629,ambient_temp:2,lid_open:!1}],parameters:{tau_closed:300,tau_open:90,box_temp_limit:8,exposure_limit_seconds:600}},short:{label:"短时超温：有暴露但不足时长",records:[{time:0,box_temp:4,ambient_temp:4,lid_open:!1},{time:600,box_temp:15.92102,ambient_temp:25,lid_open:!0},{time:1200,box_temp:23.771294,ambient_temp:25,lid_open:!1},{time:1800,box_temp:12.912692,ambient_temp:4,lid_open:!1}],parameters:{tau_closed:300,tau_open:90,box_temp_limit:8,exposure_limit_seconds:3600}},core:{label:"箱体放行但核心拒收：探头合格、油样未降温",records:[{time:0,box_temp:4,ambient_temp:7.5,lid_open:!1},{time:600,box_temp:7.026327,ambient_temp:7.5,lid_open:!1},{time:1200,box_temp:7.435895,ambient_temp:7.5,lid_open:!1},{time:1800,box_temp:7.491324,ambient_temp:7.5,lid_open:!1},{time:2400,box_temp:7.498826,ambient_temp:7.5,lid_open:!1}],parameters:{tau_closed:300,tau_open:90,box_temp_limit:8,exposure_limit_seconds:600},coreReview:{enabled:!0,sample_initial_temp:4,tau_sample_seconds:900,core_temp_limit:6}}},i={records:structuredClone(T.reject.records),parameters:{...T.reject.parameters},coreReview:{enabled:!1,sample_initial_temp:4,tau_sample_seconds:300,core_temp_limit:8},result:null,error:null,loading:!1},J=document.getElementById("app");function f(t){const e=Math.round(t),o=Math.floor(e/3600),n=Math.floor(e%3600/60),s=e%60;return o>0?`${o}:${String(n).padStart(2,"0")}:${String(s).padStart(2,"0")}`:`${n}:${String(s).padStart(2,"0")}`}function c(t){return Number(t).toFixed(2)}function b(t){const e=Number(t),o=Math.floor(e/3600),n=Math.floor(e%3600/60),s=Math.round(e%60);return o>0?`${o} 小时 ${n} 分 ${s} 秒`:n>0?`${n} 分 ${s} 秒`:`${s} 秒`}function K(){const t=i.parameters;return`
  <div class="panel">
    <h2>① 运输记录（按时间严格递增，4–30 条）</h2>
    <div style="max-height:340px;overflow:auto">
    <table class="records">
      <thead><tr>
        <th style="width:26%"># 时间(秒或ISO)</th><th>箱温℃</th><th>环境温℃</th><th>箱盖开启</th><th></th>
      </tr></thead>
      <tbody>
        ${i.records.map((e,o)=>`
        <tr>
          <td><input data-k="time" data-i="${o}" value="${e.time}" /></td>
          <td><input data-k="box_temp" data-i="${o}" type="number" step="0.01" value="${e.box_temp}" /></td>
          <td><input data-k="ambient_temp" data-i="${o}" type="number" step="0.01" value="${e.ambient_temp}" /></td>
          <td style="text-align:center"><input data-k="lid_open" data-i="${o}" type="checkbox" ${e.lid_open?"checked":""} /></td>
          <td><button class="row-btn" data-del="${o}" title="删除该行">✕</button></td>
        </tr>`).join("")}
      </tbody>
    </table>
    </div>
    <div class="count-note">当前 ${i.records.length} 条（须 4–30 条）</div>

    <h2 style="margin-top:18px">② 模型参数与保存要求</h2>
    <div class="params-grid">
      <label class="field"><span>箱盖关闭热惯性 τ关闭（秒）</span>
        <input id="tau_closed" type="number" step="any" value="${t.tau_closed}" /></label>
      <label class="field"><span>箱盖开启热惯性 τ开启（秒）</span>
        <input id="tau_open" type="number" step="any" value="${t.tau_open}" /></label>
      <label class="field"><span>允许箱温（℃）</span>
        <input id="box_temp_limit" type="number" step="0.1" value="${t.box_temp_limit}" /></label>
      <label class="field"><span>允许连续暴露时长（秒）</span>
        <input id="exposure_limit_seconds" type="number" step="any" value="${t.exposure_limit_seconds}" /></label>
    </div>
    <div class="hint">约定：相邻记录之间环境温度按<b>线性变化</b>；箱温按一阶模型
      <code>dT/dt=(T_env−T)/τ</code> 逐段闭式求解；箱盖状态在记录时刻切换 τ。</div>

    <h2 style="margin-top:18px">③ 核心温度复核（可选，默认不启用）</h2>
    <label class="field check-field">
      <input id="core_enabled" type="checkbox" ${i.coreReview.enabled?"checked":""} />
      <span>启用“核心温度复核”：以连续箱温闭式曲线驱动样品一阶响应，跨记录传递核心温度，
      不在每条记录处重新锚定</span>
    </label>
    <div class="params-grid" id="core-fields" style="${i.coreReview.enabled?"":"display:none"}">
      <label class="field"><span>首条记录时的样品温度（℃）</span>
        <input id="sample_initial_temp" type="number" step="any" value="${i.coreReview.sample_initial_temp}" /></label>
      <label class="field"><span>样品对箱温的热惯性 τ样品（秒，&gt;0）</span>
        <input id="tau_sample_seconds" type="number" step="any" value="${i.coreReview.tau_sample_seconds}" /></label>
      <label class="field"><span>核心温度上限（℃）</span>
        <input id="core_temp_limit" type="number" step="any" value="${i.coreReview.core_temp_limit}" /></label>
    </div>
    <div class="hint" id="core-off-hint" style="${i.coreReview.enabled?"display:none":""}">
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
    ${i.error?`<div class="error-box">${i.error}</div>`:""}
  </div>`}function R(){const t=i.records.map((s,d)=>{const r=document.querySelector(`[data-k="time"][data-i="${d}"]`).value.trim();return{time:/^-?\d+(\.\d+)?$/.test(r)?Number(r):r,box_temp:Number(document.querySelector(`[data-k="box_temp"][data-i="${d}"]`).value),ambient_temp:Number(document.querySelector(`[data-k="ambient_temp"][data-i="${d}"]`).value),lid_open:document.querySelector(`[data-k="lid_open"][data-i="${d}"]`).checked}}),e={tau_closed:Number(document.getElementById("tau_closed").value),tau_open:Number(document.getElementById("tau_open").value),box_temp_limit:Number(document.getElementById("box_temp_limit").value),exposure_limit_seconds:Number(document.getElementById("exposure_limit_seconds").value)},n={enabled:document.getElementById("core_enabled").checked,sample_initial_temp:Number(document.getElementById("sample_initial_temp").value),tau_sample_seconds:Number(document.getElementById("tau_sample_seconds").value),core_temp_limit:Number(document.getElementById("core_temp_limit").value)};return{recs:t,params:e,coreReview:n}}async function V(){const{recs:t,params:e,coreReview:o}=R();i.records=t,i.parameters=e,i.coreReview=o,i.loading=!0,i.error=null,i.result=null,h();const n={records:t,parameters:e};o.enabled&&(n.core_temperature_review=o);try{const d=await(await fetch("/api/audit",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(n)})).json();d.status==="invalid"?i.error=d.errors.map(r=>`<div><code>${r.code}</code> ${r.message}${r.field?`（字段：${r.field}）`:""}</div>`).join(""):i.result=d}catch(s){i.error=`无法连接审计 API：${s.message}`}finally{i.loading=!1,h()}}function X(t){if(i.loading)return`<div class="verdict"><div class="badge">…</div><div class="sub">正在连续求解各段箱温${i.coreReview.enabled?"与样品核心温度":""}…</div></div>`;if(i.error)return`<div class="verdict invalid"><div class="badge">数据不合法</div>
      <div class="sub">服务端拒绝裁决，请依据右侧字段提示修正后重新提交。</div></div>`;if(!t)return`<div class="verdict"><div class="badge" style="background:var(--panel-2);color:var(--muted)">待提交</div>
      <div class="sub">填写记录与参数后点击「提交审计」，服务端将以一阶热响应模型逐段解析求解。</div></div>`;const e=t.core_temperature_review,o=(t.box_status??t.status)==="reject";if(t.status==="pass")return`<div class="verdict pass"><div class="badge">放 行</div>
      <div class="sub">箱温连续曲线全程未形成达到 <strong>${b(t.parameters.exposure_limit_seconds)}</strong> 的连续超温区间。<br/>
      累计超温时长 <strong>${b(t.total_exceedance_seconds)}</strong>，
      连续超温区间 <strong>${t.exceedance_intervals.length}</strong> 个。
      ${e?`<br/>核心温度复核：<strong>未越限</strong>（核心最高 ${c(e.core_max_temp)}℃ ≤ 上限 ${c(e.core_temp_limit)}℃）。`:""}</div></div>`;const n=e&&!o?"核心拒收":"拒 收",s=[];if(o){const d=t.first_failure_time;s.push(`箱体探头超限：存在连续超温达到 <strong>${b(t.parameters.exposure_limit_seconds)}</strong> 的区间，油样自 <strong>${d.time}</strong>
      （距首条记录 ${f(d.elapsed_seconds)}）起失效。`)}else s.push("箱体探头裁决：<strong>放行</strong>（箱温读数与连续曲线均未触发箱体拒收）。");if(e)if(e.status==="reject"){const d=e.first_risk_time;s.push(`<strong style="color:var(--core)">核心温度超限</strong>：探头合格不代表油样内部已降温，
        样品核心温度最早于 <strong>${d.time}</strong>（距首条记录 ${f(d.elapsed_seconds)}）
        越过上限 ${c(e.core_temp_limit)}℃；核心最高 ${c(e.core_max_temp)}℃。`)}else s.push(`核心温度复核：<strong>未越限</strong>（核心最高 ${c(e.core_max_temp)}℃）。`);return`<div class="verdict ${e&&!o?"core":"reject"}">
    <div class="badge">${n}</div>
    <div class="sub">${s.join("<br/>")}<br/>
    共 ${t.exceedance_intervals.length} 个箱体连续超温区间，累计箱温超温 ${b(t.total_exceedance_seconds)}。</div></div>`}function Y(t){const e=t.box_status??t.status;if(!t||e!=="reject"||!t.first_failure_time)return"";const o=t.first_failure_time,n=t.exceedance_intervals[o.interval_index];return`<div class="failure-card">
    <h3>最早失效时刻证据</h3>
    <div class="kv">
      超温区间起点：<b>${n.start_time}</b>（${f(n.elapsed_start_seconds)}）<br/>
      连续超温区间终点：<b>${n.end_time}</b>（${f(n.elapsed_end_seconds)}）<br/>
      该区间持续：<b>${b(n.duration_seconds)}</b> ≥ 允许 ${b(t.parameters.exposure_limit_seconds)}<br/>
      最早失效时刻 = 区间起点 + 允许暴露时长 = <b>${o.time}</b>
      （距首条记录 ${f(o.elapsed_seconds)}）
    </div></div>`}function G(t){const p=t.curve,_=t.core_temperature_review,$=(_==null?void 0:_.curve)??null,j=p[p.length-1].elapsed_seconds,k=p.flatMap(a=>[a.box_temp,a.ambient_temp]).concat([t.parameters.box_temp_limit]);$&&($.forEach(a=>k.push(a.core_temp)),k.push(_.core_temp_limit));let v=Math.min(...k),w=Math.max(...k);const L=Math.max(1,(w-v)*.08);v-=L,w+=L;const l=a=>56+a/j*846,u=a=>336-(a-v)/(w-v)*318,E=[];let x=null;for(let a=0;a<p.length;a++)if(p[a].lid_open&&x===null&&(x=p[a].elapsed_seconds),(!p[a].lid_open||a===p.length-1)&&x!==null){const m=p[a].lid_open?p[a].elapsed_seconds:p[a-1].elapsed_seconds;E.push([x,m]),x=null}const S=a=>p.map((m,D)=>`${D===0?"M":"L"}${l(m.elapsed_seconds).toFixed(2)},${u(m[a]).toFixed(2)}`).join(" "),C=$?$.map((a,m)=>`${m===0?"M":"L"}${l(a.elapsed_seconds).toFixed(2)},${u(a.core_temp).toFixed(2)}`).join(" "):"",q=t.exceedance_intervals.map(a=>`<rect x="${l(a.elapsed_start_seconds)}" y="18" width="${l(a.elapsed_end_seconds)-l(a.elapsed_start_seconds)}" height="318" fill="#ff5d5d" fill-opacity="0.12" />`).join(""),O=$?_.exceedance_intervals.map(a=>`<rect x="${l(a.elapsed_start_seconds)}" y="18" width="${l(a.elapsed_end_seconds)-l(a.elapsed_start_seconds)}" height="318" fill="#c78dff" fill-opacity="0.16" />`).join(""):"",W=E.map(([a,m])=>`<rect x="${l(a)}" y="18" width="${l(m)-l(a)}" height="318" fill="#f5a623" fill-opacity="0.10" />`).join(""),I=[],F=5;for(let a=0;a<=F;a++){const m=v+(w-v)*a/F;I.push(`<line x1="56" y1="${u(m)}" x2="902" y2="${u(m)}" stroke="#22303f" stroke-width="1"/>
      <text x="48" y="${u(m)+4}" fill="#93a4b5" font-size="11" text-anchor="end">${m.toFixed(1)}</text>`)}const N=[],B=6;for(let a=0;a<=B;a++){const m=j*a/B;N.push(`<line x1="${l(m)}" y1="336" x2="${l(m)}" y2="341" stroke="#93a4b5"/>
      <text x="${l(m)}" y="356" fill="#93a4b5" font-size="11" text-anchor="middle">${f(m)}</text>`)}const M=t.parameters.box_temp_limit,P=t.records_echo.map(a=>`<circle cx="${l(a.elapsed_seconds)}" cy="${u(a.box_temp)}" r="4.5" fill="#0f1720" stroke="#e6edf3" stroke-width="2">
          <title>记录 ${a.time}：箱温 ${c(a.box_temp)}℃，环境 ${c(a.ambient_temp)}℃，箱盖${a.lid_open?"开启":"关闭"}</title></circle>`).join(""),y=t.first_failure_time,z=y?`<line x1="${l(y.elapsed_seconds)}" y1="18" x2="${l(y.elapsed_seconds)}" y2="336"
        stroke="#ff5d5d" stroke-width="1.6" stroke-dasharray="6 4"/>
      <text x="${l(y.elapsed_seconds)}" y="30" fill="#ff5d5d" font-size="11" text-anchor="middle">最早失效 ${y.time}</text>`:"",A=$?`<line x1="56" y1="${u(_.core_temp_limit)}" x2="902" y2="${u(_.core_temp_limit)}" stroke="#c78dff" stroke-width="1.4" stroke-dasharray="2 5"/>
      <text x="902" y="${u(_.core_temp_limit)+14}" fill="#c78dff" font-size="11" text-anchor="end">核心温度上限 ${_.core_temp_limit}℃</text>`:"",g=(_==null?void 0:_.first_risk_time)??null,H=g?`<line x1="${l(g.elapsed_seconds)}" y1="18" x2="${l(g.elapsed_seconds)}" y2="336"
        stroke="#c78dff" stroke-width="1.6" stroke-dasharray="6 4"/>
      <text x="${l(g.elapsed_seconds)}" y="44" fill="#c78dff" font-size="11" text-anchor="middle">最早风险 ${g.time}</text>`:"";return`<svg viewBox="0 0 920 380" role="img" aria-label="箱温与样品核心温度连续曲线">
    ${W}${q}${O}
    ${I.join("")}${N.join("")}
    <line x1="56" y1="${u(M)}" x2="902" y2="${u(M)}" stroke="#f5a623" stroke-width="1.6" stroke-dasharray="8 4"/>
    <text x="902" y="${u(M)-5}" fill="#f5a623" font-size="11" text-anchor="end">允许箱温 ${M}℃</text>
    <path d="${S("ambient_temp")}" fill="none" stroke="#7d8fa1" stroke-width="1.6" stroke-dasharray="3 3"/>
    <path d="${S("box_temp")}" fill="none" stroke="#4da3ff" stroke-width="2.4"/>
    ${$?`<path d="${C}" fill="none" stroke="#c78dff" stroke-width="2.4"/>`:""}
    ${A}
    ${P}${z}${H}
    <line x1="56" y1="336" x2="902" y2="336" stroke="#93a4b5"/>
    <line x1="56" y1="18" x2="56" y2="336" stroke="#93a4b5"/>
    <text x="56" y="374" fill="#93a4b5" font-size="11">经过时间（时:分:秒） →</text>
  </svg>
  <div class="legend">
    <span class="swatch"><i style="background:#4da3ff"></i>箱温连续曲线（闭式解析解）</span>
    <span class="swatch"><i style="background:#7d8fa1"></i>环境温（段间线性）</span>
    <span class="swatch"><i style="background:#f5a623"></i>允许箱温</span>
    ${$?`<span class="swatch"><i style="background:#c78dff"></i>样品核心温度（叠加）</span>
    <span class="swatch"><i style="background:#c78dff;opacity:.5"></i>核心温度上限</span>
    <span class="swatch"><i style="background:rgba(199,141,255,.25);border:1px solid #c78dff"></i>核心超限区间</span>`:""}
    <span class="swatch"><i style="background:var(--hot);border:1px solid #ff5d5d"></i>箱温连续超温区间</span>
    <span class="swatch"><i style="background:var(--lid);border:1px solid #f5a623"></i>箱盖开启时段</span>
    <span class="swatch">◦ 空心圆点为录入的箱温读数</span>
  </div>`}function Q(t){return t.exceedance_intervals.length?`<table class="data">
    <thead><tr><th>#</th><th>起始时刻</th><th>结束时刻</th><th class="num">持续时长(秒)</th><th>是否达到暴露限额</th></tr></thead>
    <tbody>${t.exceedance_intervals.map(e=>`<tr>
        <td>${e.index+1}</td><td>${e.start_time}</td><td>${e.end_time}</td>
        <td class="num">${b(e.duration_seconds)}（${e.duration_seconds.toFixed(1)}s）</td>
        <td><span class="tag ${e.reaches_limit?"yes":"no"}">${e.reaches_limit?"达到 → 拒收":"未达到"}</span></td>
      </tr>`).join("")}</tbody></table>`:'<div class="hint">无任何箱温超过允许值的连续区间。</div>'}function U(t){return`<table class="data">
    <thead><tr>
      <th>#</th><th>段起→止(s)</th><th>箱盖</th><th class="num">τ(秒)</th>
      <th class="num">段内最高℃</th><th>最高位置</th>
      <th class="num">段内最低℃</th><th>穿越(相对秒)</th>
    </tr></thead>
    <tbody>${t.segments.map(e=>{const o=e.crossings.map(n=>`<span class="${n.direction}">${n.direction==="up"?"↑上穿":"↓下穿"}@${n.elapsed_seconds.toFixed(1)}</span>`).join("，");return`<tr>
        <td>${e.index+1}</td>
        <td>${e.elapsed_start_seconds} → ${e.elapsed_end_seconds}<br/><span class="hint" style="margin:0">${e.duration_seconds.toFixed(0)}s</span></td>
        <td><span class="tag ${e.lid_open?"open":"closed"}">${e.lid_open?"开启":"关闭"}</span></td>
        <td class="num">${e.tau_seconds}</td>
        <td class="num">${c(e.max_temp.value)}</td>
        <td>${e.max_temp.kind==="interior"?"段内 "+e.max_temp.elapsed_seconds.toFixed(1)+"s":e.max_temp.kind==="start"?"段起点":"段终点"}</td>
        <td class="num">${c(e.min_temp.value)}</td>
        <td>${o||"—"}</td>
      </tr>`}).join("")}</tbody></table>`}function Z(t){const e=t.core_temperature_review;if(!e)return"";if(e.status==="pass")return`<div class="core-card pass">
      <h3>核心温度复核：未越限</h3>
      <div class="kv">
        首条记录时样品温度 <b>${c(e.sample_initial_temp)}℃</b>，
        样品热惯性 τ样品 <b>${e.tau_sample_seconds}s</b>，核心温度上限 <b>${c(e.core_temp_limit)}℃</b>。<br/>
        全程核心温度区间 <b>${c(e.core_min_temp)}℃ ~ ${c(e.core_max_temp)}℃</b>，
        末条记录时核心温度 <b>${c(e.sample_final_temp)}℃</b>，<b>未越过上限</b>，最早风险时刻：无。
      </div></div>`;const o=e.first_risk_time,n=e.exceedance_intervals[o.interval_index];return`<div class="core-card reject">
    <h3>核心温度复核：核心超限（探头合格 ≠ 油样已降温）</h3>
    <div class="kv">
      样品热惯性 τ样品 <b>${e.tau_sample_seconds}s</b>，核心温度上限 <b>${c(e.core_temp_limit)}℃</b>。<br/>
      核心温度最早于 <b>${o.time}</b>（距首条记录 ${f(o.elapsed_seconds)}）
      越过上限；全程核心最高 <b>${c(e.core_max_temp)}℃</b>。<br/>
      首个核心超限区间：<b>${n.start_time}</b> → <b>${n.end_time}</b>
      （持续 ${b(n.duration_seconds)}）。
    </div></div>`}function ee(t){return t.exceedance_intervals.length?`<table class="data">
    <thead><tr><th>#</th><th>起始时刻</th><th>结束时刻</th><th class="num">持续时长(秒)</th></tr></thead>
    <tbody>${t.exceedance_intervals.map(e=>`<tr>
        <td>${e.index+1}</td><td>${e.start_time}</td><td>${e.end_time}</td>
        <td class="num">${b(e.duration_seconds)}（${e.duration_seconds.toFixed(1)}s）</td>
      </tr>`).join("")}</tbody></table>`:'<div class="hint">核心温度全程未超过上限。</div>'}function te(t){return`<table class="data">
    <thead><tr>
      <th>#</th><th>段起→止(s)</th><th>箱盖</th>
      <th class="num">τ箱/τ样品(秒)</th>
      <th class="num">核心起℃</th><th class="num">核心止℃</th>
      <th class="num">段内最高℃</th><th class="num">段内最低℃</th>
      <th>核心穿越(相对秒)</th>
    </tr></thead>
    <tbody>${t.segments.map(e=>{const o=e.crossings.map(s=>`<span class="${s.direction==="up"?"core-up":"core-down"}">${s.direction==="up"?"↑上穿":"↓下穿"}@${s.elapsed_seconds.toFixed(1)}</span>`).join("，"),n=e.degenerate_equal_tau?' <span class="tag open" title="样品热惯性等于箱体热惯性，采用极限闭式解">等τ</span>':"";return`<tr>
        <td>${e.index+1}</td>
        <td>${e.elapsed_start_seconds} → ${e.elapsed_end_seconds}<br/><span class="hint" style="margin:0">${e.duration_seconds.toFixed(0)}s</span></td>
        <td><span class="tag ${e.lid_open?"open":"closed"}">${e.lid_open?"开启":"关闭"}</span></td>
        <td class="num">${e.tau_box_seconds} / ${e.tau_sample_seconds}${n}</td>
        <td class="num">${c(e.core_temp_start)}</td>
        <td class="num">${c(e.core_temp_end)}</td>
        <td class="num">${c(e.max_temp.value)}<br/><span class="hint" style="margin:0">${e.max_temp.kind==="interior"?"段内"+e.max_temp.elapsed_seconds.toFixed(0)+"s":e.max_temp.kind==="start"?"段起点":"段终点"}</span></td>
        <td class="num">${c(e.min_temp.value)}</td>
        <td>${o||"—"}</td>
      </tr>`}).join("")}</tbody></table>`}function se(t){if(!t)return"";const e=t.core_temperature_review;return`
  <div class="model-note">
    求解方式：<code>${t.model.equation}</code>；${t.model.ambient_assumption}；${t.model.solver}。<br/>
    每段以记录时刻实测箱温为初值锚定（段末模型值与下一读数偏差见审计数据），
    ${t.model.tau_switching}。${t.model.exceedance_rule}。
    ${e?`<br/><b style="color:var(--core)">核心温度复核已启用</b>：${e.model.equation}；${e.model.driver}；${e.model.initial_condition}`:""}
  </div>
  ${Y(t)}
  ${Z(t)}
  <div class="chart-wrap">${G(t)}</div>

  <div class="section-title">箱体连续超温区间（跨记录取并集）</div>
  ${Q(t)}

  <div class="section-title">各段箱温解析极值与阈值穿越</div>
  ${U(t)}

  ${e?`<div class="section-title core-title">核心温度连续超限区间（首个上穿即最早风险时刻）</div>
  ${ee(e)}

  <div class="section-title core-title">各段核心温度起止状态、解析极值与阈值穿越</div>
  ${te(e)}`:""}`}function h(){J.innerHTML=`
  <header>
    <h1>海上平台油样运输箱 · 温控审计</h1>
    <p>一阶热响应模型逐段闭式解析 · 阈值穿越精确定位 · 跨记录连续暴露累计 —— 拒绝"只看离散读数"的误放行</p>
  </header>
  <div class="layout">
    ${K()}
    <div>
      ${X(i.result)}
      ${i.result?se(i.result):'<div class="chart-wrap"><div class="hint">提交后在此展示箱温连续曲线、各段解析极值、累计暴露区间与最早失效时刻。</div></div>'}
    </div>
  </div>`,ae()}function ae(){var t,e,o;(t=document.getElementById("submit"))==null||t.addEventListener("click",V),(e=document.getElementById("core_enabled"))==null||e.addEventListener("change",()=>{const{recs:n,params:s,coreReview:d}=R();i.records=n,i.parameters=s,i.coreReview=d,h()}),(o=document.getElementById("addRow"))==null||o.addEventListener("click",()=>{const{recs:n,params:s,coreReview:d}=R();if(n.length>=30)return;const r=n[n.length-1];n.push({time:typeof r.time=="number"?r.time+600:r.time,box_temp:r.box_temp,ambient_temp:r.ambient_temp,lid_open:!1}),i.records=n,i.parameters=s,i.coreReview=d,h()}),document.querySelectorAll("[data-del]").forEach(n=>n.addEventListener("click",()=>{const{recs:s,params:d,coreReview:r}=R();s.splice(Number(n.dataset.del),1),i.records=s,i.parameters=d,i.coreReview=r,h()})),document.querySelectorAll("[data-preset]").forEach(n=>{n.addEventListener("click",()=>{const s=T[n.dataset.preset];i.records=structuredClone(s.records),i.parameters={...s.parameters},i.coreReview=s.coreReview?structuredClone(s.coreReview):{...i.coreReview,enabled:!1},i.result=null,i.error=null,h()})})}h();
