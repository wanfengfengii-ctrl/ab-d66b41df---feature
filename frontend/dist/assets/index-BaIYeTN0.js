(function(){const e=document.createElement("link").relList;if(e&&e.supports&&e.supports("modulepreload"))return;for(const i of document.querySelectorAll('link[rel="modulepreload"]'))n(i);new MutationObserver(i=>{for(const o of i)if(o.type==="childList")for(const r of o.addedNodes)r.tagName==="LINK"&&r.rel==="modulepreload"&&n(r)}).observe(document,{childList:!0,subtree:!0});function s(i){const o={};return i.integrity&&(o.integrity=i.integrity),i.referrerPolicy&&(o.referrerPolicy=i.referrerPolicy),i.crossOrigin==="use-credentials"?o.credentials="include":i.crossOrigin==="anonymous"?o.credentials="omit":o.credentials="same-origin",o}function n(i){if(i.ep)return;i.ep=!0;const o=s(i);fetch(i.href,o)}})();const R={reject:{label:"拒收演示：读数全合格、途中升温",records:[{time:0,box_temp:4,ambient_temp:25,lid_open:!1},{time:60,box_temp:7.806654,ambient_temp:25,lid_open:!1},{time:1560,box_temp:7.254505,ambient_temp:3,lid_open:!1},{time:2460,box_temp:3.211819,ambient_temp:3,lid_open:!1},{time:3360,box_temp:3.010546,ambient_temp:3,lid_open:!1}],parameters:{tau_closed:300,tau_open:90,box_temp_limit:8,exposure_limit_seconds:600}},pass:{label:"放行演示：全程低温",records:[{time:0,box_temp:4,ambient_temp:3,lid_open:!1},{time:300,box_temp:3.551819,ambient_temp:3.5,lid_open:!1},{time:600,box_temp:3.703003,ambient_temp:4,lid_open:!1},{time:900,box_temp:3.817165,ambient_temp:3.8,lid_open:!1},{time:1200,box_temp:3.585587,ambient_temp:3.2,lid_open:!1},{time:1500,box_temp:3.268274,ambient_temp:3,lid_open:!1},{time:1800,box_temp:3.025116,ambient_temp:2.8,lid_open:!1},{time:2100,box_temp:2.772452,ambient_temp:2.5,lid_open:!1},{time:2400,box_temp:2.41629,ambient_temp:2,lid_open:!1}],parameters:{tau_closed:300,tau_open:90,box_temp_limit:8,exposure_limit_seconds:600}},short:{label:"短时超温：有暴露但不足时长",records:[{time:0,box_temp:4,ambient_temp:4,lid_open:!1},{time:600,box_temp:15.92102,ambient_temp:25,lid_open:!0},{time:1200,box_temp:23.771294,ambient_temp:25,lid_open:!1},{time:1800,box_temp:12.912692,ambient_temp:4,lid_open:!1}],parameters:{tau_closed:300,tau_open:90,box_temp_limit:8,exposure_limit_seconds:3600}},coreReject:{label:"箱体放行但核心拒收：探头合格、样品仍热",records:[{time:0,box_temp:4,ambient_temp:4,lid_open:!1},{time:600,box_temp:12.642411,ambient_temp:25,lid_open:!1},{time:1200,box_temp:20.0694,ambient_temp:25,lid_open:!1},{time:1800,box_temp:10.921607,ambient_temp:4,lid_open:!1}],parameters:{tau_closed:300,tau_open:90,box_temp_limit:8,exposure_limit_seconds:3600},coreReview:{enabled:!0,sample_initial_temp:4,tau_sample_seconds:300,core_temp_limit:7}}},C={enabled:!1,sample_initial_temp:4,tau_sample_seconds:600,core_temp_limit:8},d={records:structuredClone(R.reject.records),parameters:{...R.reject.parameters},coreReview:{...C},result:null,error:null,loading:!1},J=document.getElementById("app");function h(t){const e=Math.round(t),s=Math.floor(e/3600),n=Math.floor(e%3600/60),i=e%60;return s>0?`${s}:${String(n).padStart(2,"0")}:${String(i).padStart(2,"0")}`:`${n}:${String(i).padStart(2,"0")}`}function b(t){return Number(t).toFixed(2)}function u(t){const e=Number(t),s=Math.floor(e/3600),n=Math.floor(e%3600/60),i=Math.round(e%60);return s>0?`${s} 小时 ${n} 分 ${i} 秒`:n>0?`${n} 分 ${i} 秒`:`${i} 秒`}function K(){const t=d.parameters;return`
  <div class="panel">
    <h2>① 运输记录（按时间严格递增，4–30 条）</h2>
    <div style="max-height:340px;overflow:auto">
    <table class="records">
      <thead><tr>
        <th style="width:26%"># 时间(秒或ISO)</th><th>箱温℃</th><th>环境温℃</th><th>箱盖开启</th><th></th>
      </tr></thead>
      <tbody>
        ${d.records.map((e,s)=>`
        <tr>
          <td><input data-k="time" data-i="${s}" value="${e.time}" /></td>
          <td><input data-k="box_temp" data-i="${s}" type="number" step="0.01" value="${e.box_temp}" /></td>
          <td><input data-k="ambient_temp" data-i="${s}" type="number" step="0.01" value="${e.ambient_temp}" /></td>
          <td style="text-align:center"><input data-k="lid_open" data-i="${s}" type="checkbox" ${e.lid_open?"checked":""} /></td>
          <td><button class="row-btn" data-del="${s}" title="删除该行">✕</button></td>
        </tr>`).join("")}
      </tbody>
    </table>
    </div>
    <div class="count-note">当前 ${d.records.length} 条（须 4–30 条）</div>

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

    <h2 style="margin-top:18px">③ 核心温度复核（可选）</h2>
    <label class="field check-field">
      <input id="core_enabled" type="checkbox" ${d.coreReview.enabled?"checked":""} />
      <span>启用核心温度复核：以箱温闭式曲线连续驱动样品一阶响应，跨记录传递核心温度（不逐记录重新锚定）</span>
    </label>
    <div class="params-grid" id="core-fields" style="${d.coreReview.enabled?"":"opacity:.45;pointer-events:none"}">
      <label class="field"><span>首条记录时样品温度（℃）</span>
        <input id="sample_initial_temp" type="number" step="any" value="${d.coreReview.sample_initial_temp}" /></label>
      <label class="field"><span>样品对箱温热惯性 τ样品（秒）</span>
        <input id="tau_sample_seconds" type="number" step="any" value="${d.coreReview.tau_sample_seconds}" /></label>
      <label class="field"><span>核心温度上限（℃）</span>
        <input id="core_temp_limit" type="number" step="0.1" value="${d.coreReview.core_temp_limit}" /></label>
    </div>
    <div class="hint">未启用时，请求、结论与证据与原审计完全一致。</div>

    <div class="btn-row">
      <button class="action" id="submit">提交审计</button>
      <button class="ghost" id="addRow">+ 增加记录</button>
    </div>
    <div class="btn-row">
      <button class="ghost" data-preset="reject">拒收演示数据</button>
      <button class="ghost" data-preset="pass">放行演示数据</button>
      <button class="ghost" data-preset="short">短时超温数据</button>
      <button class="ghost" data-preset="coreReject">箱体放行/核心拒收</button>
    </div>
    ${d.error?`<div class="error-box">${d.error}</div>`:""}
  </div>`}function w(){const t=d.records.map((n,i)=>{const o=document.querySelector(`[data-k="time"][data-i="${i}"]`).value.trim();return{time:/^-?\d+(\.\d+)?$/.test(o)?Number(o):o,box_temp:Number(document.querySelector(`[data-k="box_temp"][data-i="${i}"]`).value),ambient_temp:Number(document.querySelector(`[data-k="ambient_temp"][data-i="${i}"]`).value),lid_open:document.querySelector(`[data-k="lid_open"][data-i="${i}"]`).checked}}),e={tau_closed:Number(document.getElementById("tau_closed").value),tau_open:Number(document.getElementById("tau_open").value),box_temp_limit:Number(document.getElementById("box_temp_limit").value),exposure_limit_seconds:Number(document.getElementById("exposure_limit_seconds").value)},s={enabled:document.getElementById("core_enabled").checked,sample_initial_temp:Number(document.getElementById("sample_initial_temp").value),tau_sample_seconds:Number(document.getElementById("tau_sample_seconds").value),core_temp_limit:Number(document.getElementById("core_temp_limit").value)};return{recs:t,params:e,coreReview:s}}async function U(){const{recs:t,params:e,coreReview:s}=w();d.records=t,d.parameters=e,d.coreReview=s,d.loading=!0,d.error=null,d.result=null,$();try{const n={records:t,parameters:e};s.enabled&&(n.core_review=s);const o=await(await fetch("/api/audit",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(n)})).json();o.status==="invalid"?d.error=o.errors.map(r=>`<div><code>${r.code}</code> ${r.message}${r.field?`（字段：${r.field}）`:""}</div>`).join(""):d.result=o}catch(n){d.error=`无法连接审计 API：${n.message}`}finally{d.loading=!1,$()}}function X(t){if(d.loading)return'<div class="verdict"><div class="badge">…</div><div class="sub">正在连续求解各段箱温…</div></div>';if(d.error)return`<div class="verdict invalid"><div class="badge">数据不合法</div>
      <div class="sub">服务端拒绝裁决，请依据右侧字段提示修正后重新提交。</div></div>`;if(!t)return`<div class="verdict"><div class="badge" style="background:var(--panel-2);color:var(--muted)">待提交</div>
      <div class="sub">填写记录与参数后点击「提交审计」，服务端将以一阶热响应模型逐段解析求解。</div></div>`;const e=t.core_review;if(e){const n=t.final_status==="pass",i=t.box_status==="reject"?"箱体拒收":"箱体放行",o=e.status==="reject"?"核心拒收":"核心放行",r=t.box_status==="reject"?"reject-box":"pass",j=e.status==="reject"?"reject":"pass";return`<div class="verdict ${n?"pass":"reject"}">
      <div class="badge">${n?"放 行":"拒 收"}</div>
      <div class="sub"><b>${t.final_verdict}</b><br/>
        <span class="mini-tag ${r}">${i}</span>
        <span class="mini-tag ${j}">${o}</span>
        ${e.status==="reject"?`<br/>核心温度最早于 <b>${e.first_risk_time.time}</b>
               （距首条记录 ${h(e.first_risk_time.elapsed_seconds)}）越过
               ${e.core_temp_limit}℃ 上限；核心超限累计 ${u(e.total_exceedance_seconds)}。`:`<br/>核心温度全程未越过 ${e.core_temp_limit}℃ 上限。`}
      </div></div>`}if(t.status==="pass")return`<div class="verdict pass"><div class="badge">放 行</div>
      <div class="sub">箱温连续曲线全程未形成达到 <strong>${u(t.parameters.exposure_limit_seconds)}</strong> 的连续超温区间。<br/>
      累计超温时长 <strong>${u(t.total_exceedance_seconds)}</strong>，
      连续超温区间 <strong>${t.exceedance_intervals.length}</strong> 个。</div></div>`;const s=t.first_failure_time;return`<div class="verdict reject"><div class="badge">拒 收</div>
    <div class="sub">存在连续超温达到 <strong>${u(t.parameters.exposure_limit_seconds)}</strong> 的区间，油样自 <strong>${s.time}</strong>
    （距首条记录 ${h(s.elapsed_seconds)}）起失效。<br/>
    共 ${t.exceedance_intervals.length} 个连续超温区间，累计超温 ${u(t.total_exceedance_seconds)}。</div></div>`}function Y(t){if(!t||t.status!=="reject")return"";const e=t.first_failure_time,s=t.exceedance_intervals[e.interval_index];return`<div class="failure-card">
    <h3>最早失效时刻证据（箱体）</h3>
    <div class="kv">
      超温区间起点：<b>${s.start_time}</b>（${h(s.elapsed_start_seconds)}）<br/>
      连续超温区间终点：<b>${s.end_time}</b>（${h(s.elapsed_end_seconds)}）<br/>
      该区间持续：<b>${u(s.duration_seconds)}</b> ≥ 允许 ${u(t.parameters.exposure_limit_seconds)}<br/>
      最早失效时刻 = 区间起点 + 允许暴露时长 = <b>${e.time}</b>
      （距首条记录 ${h(e.elapsed_seconds)}）
    </div></div>`}function G(t){const e=t==null?void 0:t.core_review;return e?`${e.status==="reject"?`<div class="failure-card core"><h3>核心温度复核 · 核心拒收</h3>
         <div class="kv">核心温度上限：<b>${e.core_temp_limit}℃</b>；样品热惯性 τ样品=<b>${e.tau_sample_seconds}s</b>；
         首条记录样品温度 <b>${e.sample_initial_temp}℃</b>（全表唯一锚点）。<br/>
         最早风险时刻（首个核心上穿）：<b>${e.first_risk_time.time}</b>
         （距首条记录 ${h(e.first_risk_time.elapsed_seconds)}）<br/>
         核心超限连续区间 <b>${e.exceedance_intervals.length}</b> 个，
         累计 ${u(e.total_exceedance_seconds)}；运输末刻核心温 ${e.core_temp_end.toFixed(2)}℃。</div></div>`:`<div class="failure-card core-ok"><h3>核心温度复核 · 核心放行</h3>
         <div class="kv">核心温度全程未越过 <b>${e.core_temp_limit}℃</b> 上限
         （τ样品=${e.tau_sample_seconds}s，首条记录样品温度 ${e.sample_initial_temp}℃）；
         运输末刻核心温 ${e.core_temp_end.toFixed(2)}℃。</div></div>`}
  <div class="model-note">核心求解：${e.solver}。<br/>${e.anchoring}。</div>`:""}function Q(t){const p=t.curve,c=t.core_review,T=p[p.length-1].elapsed_seconds,L=p.flatMap(a=>[a.box_temp,a.ambient_temp,...a.core_temp!=null?[a.core_temp]:[]]).concat([t.parameters.box_temp_limit,c?c.core_temp_limit:null]).filter(a=>a!=null);let f=Math.min(...L),g=Math.max(...L);const E=Math.max(1,(g-f)*.08);f-=E,g+=E;const l=a=>56+a/T*846,_=a=>336-(a-f)/(g-f)*318,S=[];let v=null;for(let a=0;a<p.length;a++)if(p[a].lid_open&&v===null&&(v=p[a].elapsed_seconds),(!p[a].lid_open||a===p.length-1)&&v!==null){const m=p[a].lid_open?p[a].elapsed_seconds:p[a-1].elapsed_seconds;S.push([v,m]),v=null}const M=a=>p.map((m,V)=>`${V===0?"M":"L"}${l(m.elapsed_seconds).toFixed(2)},${_(m[a]).toFixed(2)}`).join(" "),O=t.exceedance_intervals.map(a=>`<rect x="${l(a.elapsed_start_seconds)}" y="18" width="${l(a.elapsed_end_seconds)-l(a.elapsed_start_seconds)}" height="318" fill="#ff5d5d" fill-opacity="0.16" />`).join(""),W=c?c.exceedance_intervals.map(a=>`<rect x="${l(a.elapsed_start_seconds)}" y="18" width="${l(a.elapsed_end_seconds)-l(a.elapsed_start_seconds)}" height="318" fill="#b98cff" fill-opacity="0.18" />`).join(""):"",q=c?M("core_temp"):"",P=S.map(([a,m])=>`<rect x="${l(a)}" y="18" width="${l(m)-l(a)}" height="318" fill="#f5a623" fill-opacity="0.10" />`).join(""),I=[],B=5;for(let a=0;a<=B;a++){const m=f+(g-f)*a/B;I.push(`<line x1="56" y1="${_(m)}" x2="902" y2="${_(m)}" stroke="#22303f" stroke-width="1"/>
      <text x="48" y="${_(m)+4}" fill="#93a4b5" font-size="11" text-anchor="end">${m.toFixed(1)}</text>`)}const F=[],N=6;for(let a=0;a<=N;a++){const m=T*a/N;F.push(`<line x1="${l(m)}" y1="336" x2="${l(m)}" y2="341" stroke="#93a4b5"/>
      <text x="${l(m)}" y="356" fill="#93a4b5" font-size="11" text-anchor="middle">${h(m)}</text>`)}const k=t.parameters.box_temp_limit,z=t.records_echo.map(a=>`<circle cx="${l(a.elapsed_seconds)}" cy="${_(a.box_temp)}" r="4.5" fill="#0f1720" stroke="#e6edf3" stroke-width="2">
          <title>记录 ${a.time}：箱温 ${b(a.box_temp)}℃，环境 ${b(a.ambient_temp)}℃，箱盖${a.lid_open?"开启":"关闭"}</title></circle>`).join(""),x=t.first_failure_time,A=x?`<line x1="${l(x.elapsed_seconds)}" y1="18" x2="${l(x.elapsed_seconds)}" y2="336"
        stroke="#ff5d5d" stroke-width="1.6" stroke-dasharray="6 4"/>
      <text x="${l(x.elapsed_seconds)}" y="30" fill="#ff5d5d" font-size="11" text-anchor="middle">最早失效 ${x.time}</text>`:"",H=c?`<line x1="56" y1="${_(c.core_temp_limit)}" x2="902" y2="${_(c.core_temp_limit)}"
        stroke="#b98cff" stroke-width="1.4" stroke-dasharray="2 5"/>
      <text x="902" y="${_(c.core_temp_limit)+14}" fill="#b98cff" font-size="11" text-anchor="end">核心上限 ${c.core_temp_limit}℃</text>`:"",y=c==null?void 0:c.first_risk_time,D=y?`<line x1="${l(y.elapsed_seconds)}" y1="18" x2="${l(y.elapsed_seconds)}" y2="336"
        stroke="#b98cff" stroke-width="1.6" stroke-dasharray="6 4"/>
      <text x="${l(y.elapsed_seconds)}" y="354" fill="#b98cff" font-size="11" text-anchor="middle">最早核心风险 ${y.time}</text>`:"";return`<svg viewBox="0 0 920 380" role="img" aria-label="箱温连续曲线${c?"与核心温度曲线":""}">
    ${P}${O}${W}
    ${I.join("")}${F.join("")}
    <line x1="56" y1="${_(k)}" x2="902" y2="${_(k)}" stroke="#f5a623" stroke-width="1.6" stroke-dasharray="8 4"/>
    <text x="902" y="${_(k)-5}" fill="#f5a623" font-size="11" text-anchor="end">允许箱温 ${k}℃</text>
    ${H}
    <path d="${M("ambient_temp")}" fill="none" stroke="#7d8fa1" stroke-width="1.6" stroke-dasharray="3 3"/>
    <path d="${M("box_temp")}" fill="none" stroke="#4da3ff" stroke-width="2.4"/>
    ${c?`<path d="${q}" fill="none" stroke="#b98cff" stroke-width="2.4"/>`:""}
    ${z}${A}${D}
    <line x1="56" y1="336" x2="902" y2="336" stroke="#93a4b5"/>
    <line x1="56" y1="18" x2="56" y2="336" stroke="#93a4b5"/>
    <text x="56" y="374" fill="#93a4b5" font-size="11">经过时间（时:分:秒） →</text>
  </svg>
  <div class="legend">
    <span class="swatch"><i style="background:#4da3ff"></i>箱温连续曲线（闭式解析解）</span>
    ${c?`<span class="swatch"><i style="background:#b98cff"></i>核心温度曲线（连续驱动、跨记录传递）</span>
    <span class="swatch"><i style="background:#b98cff"></i>核心温度上限 / 超限区间</span>`:""}
    <span class="swatch"><i style="background:#7d8fa1"></i>环境温（段间线性）</span>
    <span class="swatch"><i style="background:#f5a623"></i>允许箱温</span>
    <span class="swatch"><i style="background:var(--hot);border:1px solid #ff5d5d"></i>连续超温区间</span>
    <span class="swatch"><i style="background:var(--lid);border:1px solid #f5a623"></i>箱盖开启时段</span>
    <span class="swatch">◦ 空心圆点为录入的箱温读数</span>
  </div>`}function Z(t){return t.exceedance_intervals.length?`<table class="data">
    <thead><tr><th>#</th><th>起始时刻</th><th>结束时刻</th><th class="num">持续时长(秒)</th><th>是否达到暴露限额</th></tr></thead>
    <tbody>${t.exceedance_intervals.map(e=>`<tr>
        <td>${e.index+1}</td><td>${e.start_time}</td><td>${e.end_time}</td>
        <td class="num">${u(e.duration_seconds)}（${e.duration_seconds.toFixed(1)}s）</td>
        <td><span class="tag ${e.reaches_limit?"yes":"no"}">${e.reaches_limit?"达到 → 拒收":"未达到"}</span></td>
      </tr>`).join("")}</tbody></table>`:'<div class="hint">无任何箱温超过允许值的连续区间。</div>'}function ee(t){return`<table class="data">
    <thead><tr>
      <th>#</th><th>段起→止(s)</th><th>箱盖</th><th class="num">τ(秒)</th>
      <th class="num">段内最高℃</th><th>最高位置</th>
      <th class="num">段内最低℃</th><th>穿越(相对秒)</th>
    </tr></thead>
    <tbody>${t.segments.map(e=>{const s=e.crossings.map(n=>`<span class="${n.direction}">${n.direction==="up"?"↑上穿":"↓下穿"}@${n.elapsed_seconds.toFixed(1)}</span>`).join("，");return`<tr>
        <td>${e.index+1}</td>
        <td>${e.elapsed_start_seconds} → ${e.elapsed_end_seconds}<br/><span class="hint" style="margin:0">${e.duration_seconds.toFixed(0)}s</span></td>
        <td><span class="tag ${e.lid_open?"open":"closed"}">${e.lid_open?"开启":"关闭"}</span></td>
        <td class="num">${e.tau_seconds}</td>
        <td class="num">${b(e.max_temp.value)}</td>
        <td>${e.max_temp.kind==="interior"?"段内 "+e.max_temp.elapsed_seconds.toFixed(1)+"s":e.max_temp.kind==="start"?"段起点":"段终点"}</td>
        <td class="num">${b(e.min_temp.value)}</td>
        <td>${s||"—"}</td>
      </tr>`}).join("")}</tbody></table>`}function te(t){const e=t.core_review;return e?`<div class="section-title">核心温度各段起止状态 / 极值 / 阈值穿越（跨记录连续传递）</div>
  <table class="data">
    <thead><tr>
      <th>#</th><th>段起→止(s)</th><th class="num">段初核心℃</th><th class="num">段末核心℃</th>
      <th class="num">段内最高℃</th><th class="num">段内最低℃</th><th>穿越(相对秒)</th>
    </tr></thead>
    <tbody>${e.segments.map(s=>{const n=s.crossings.map(i=>`<span class="${i.direction}">${i.direction==="up"?"↑上穿":"↓下穿"}@${i.elapsed_seconds.toFixed(1)}</span>`).join("，");return`<tr>
        <td>${s.index+1}${s.tau_equal?' <span class="tag closed" title="样品与箱体热惯性相等（退化分支）">τ相等</span>':""}</td>
        <td>${s.elapsed_start_seconds} → ${s.elapsed_end_seconds}</td>
        <td class="num">${b(s.core_temp_start)}</td>
        <td class="num">${b(s.core_temp_end)}</td>
        <td class="num">${b(s.max_temp.value)}<br/><span class="hint" style="margin:0">${s.max_temp.kind==="interior"?"段内 "+s.max_temp.elapsed_seconds.toFixed(1)+"s":s.max_temp.kind==="start"?"段起点":"段终点"}</span></td>
        <td class="num">${b(s.min_temp.value)}</td>
        <td>${n||"—"}</td>
      </tr>`}).join("")}</tbody></table>
  <div class="hint">核心温度仅在首条记录处以样品温度锚定一次；相邻段段末/段初核心温严格相接（连续驱动，不重新锚定）。</div>`:""}function se(t){const e=t.core_review;return e?e.exceedance_intervals.length?`<table class="data">
    <thead><tr><th>#</th><th>起始时刻</th><th>结束时刻</th><th class="num">持续时长(秒)</th></tr></thead>
    <tbody>${e.exceedance_intervals.map(s=>`<tr>
        <td>${s.index+1}</td><td>${s.start_time}</td><td>${s.end_time}</td>
        <td class="num">${u(s.duration_seconds)}（${s.duration_seconds.toFixed(1)}s）</td>
      </tr>`).join("")}</tbody></table>`:`<div class="hint">核心温度全程未越过 ${e.core_temp_limit}℃ 上限。</div>`:""}function ae(t){return t?`
  <div class="model-note">
    求解方式：<code>${t.model.equation}</code>；${t.model.ambient_assumption}；${t.model.solver}。<br/>
    每段以记录时刻实测箱温为初值锚定（段末模型值与下一读数偏差见审计数据），
    ${t.model.tau_switching}。${t.model.exceedance_rule}。
  </div>
  ${G(t)}
  ${Y(t)}
  <div class="chart-wrap">${Q(t)}</div>

  <div class="section-title">累计连续超温区间（跨记录取并集）</div>
  ${Z(t)}

  ${t.core_review?`<div class="section-title">核心温度连续超限区间</div>${se(t)}`:""}

  <div class="section-title">各段解析极值与阈值穿越（箱体）</div>
  ${ee(t)}
  ${te(t)}`:""}function $(){J.innerHTML=`
  <header>
    <h1>海上平台油样运输箱 · 温控审计</h1>
    <p>一阶热响应模型逐段闭式解析 · 阈值穿越精确定位 · 跨记录连续暴露累计 —— 拒绝"只看离散读数"的误放行</p>
  </header>
  <div class="layout">
    ${K()}
    <div>
      ${X(d.result)}
      ${d.result?ae(d.result):'<div class="chart-wrap"><div class="hint">提交后在此展示箱温连续曲线、各段解析极值、累计暴露区间与最早失效时刻。</div></div>'}
    </div>
  </div>`,ie()}function ie(){var t,e,s;(t=document.getElementById("submit"))==null||t.addEventListener("click",U),(e=document.getElementById("addRow"))==null||e.addEventListener("click",()=>{const{recs:n,params:i,coreReview:o}=w();if(n.length>=30)return;const r=n[n.length-1];n.push({time:typeof r.time=="number"?r.time+600:r.time,box_temp:r.box_temp,ambient_temp:r.ambient_temp,lid_open:!1}),d.records=n,d.parameters=i,d.coreReview=o,$()}),document.querySelectorAll("[data-del]").forEach(n=>n.addEventListener("click",()=>{const{recs:i,params:o,coreReview:r}=w();i.splice(Number(n.dataset.del),1),d.records=i,d.parameters=o,d.coreReview=r,$()})),document.querySelectorAll("[data-preset]").forEach(n=>{n.addEventListener("click",()=>{const i=R[n.dataset.preset];d.records=structuredClone(i.records),d.parameters={...i.parameters},d.coreReview=i.coreReview?structuredClone(i.coreReview):{...C},d.result=null,d.error=null,$()})}),(s=document.getElementById("core_enabled"))==null||s.addEventListener("change",n=>{const{coreReview:i}=w();d.coreReview={...i,enabled:n.target.checked},$()})}$();
