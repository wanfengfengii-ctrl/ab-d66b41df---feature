"""一阶热响应模型解析求解引擎。

模型（每段记录区间内）：

    dT/dt = (T_env(t) - T(t)) / τ

* T 为箱温，T_env(t) 在相邻两条记录之间按约定做线性插值；
* τ 为箱体热惯性（时间常数），箱盖开启/关闭取不同常数，
  在箱盖状态对应的整段区间内保持该常数，跨记录点无缝延续；
* 不使用欧拉/龙格-库塔等数值步进，也不按离散采样点裁决：
  每段均给出闭式解，阈值穿越点在由解析驻点切分出的单调区间上
  以二分求根（收敛容差 1e-12 s）精确定位。

区间 [t_i, t_{i+1}]，令 s = t - t_i，Δ = t_{i+1} - t_i，
T_env(s) = a + b·s（a 为起点环境温，b 为线性斜率），则：

    T(s) = a + b·(s - τ) + (T_i - a + b·τ)·exp(-s/τ)

    T'(s) = b - (T_i - a + b·τ)/τ · exp(-s/τ)

裁决口径：严格超限 T > T_limit；相邻超温子区间在全局取并集后，
任一连续超温区间持续达到允许连续暴露时长即判拒收，首个失效时刻
为该区间起点 + 允许暴露时长。

核心温度复核（启用 core_review 时额外求解）：

箱体闭式曲线 T_box(t) 作为油样一阶响应的**连续驱动**，样品核心温度

    dT_core/dt = (T_box(t) - T_core(t)) / τ_sample

在**首条记录处唯一锚定**（取录入的样品温度），此后跨所有记录连续
传递，绝不在每条记录处用探头读数重新锚定样品状态。线性驱动下仍为
闭式解。令本段箱温常数为 τ_b、样品热惯性为 τ_s，
K = C0 - a + b·τ_s，H = F0 - a + b·τ_b（C0 为段初核心温，F0 为
段初箱温闭式值），则：

    C(s) = F(s) + b·(τ_b - τ_s) + K·exp(-s/τ_s) - H·exp(-s/τ_b)
    C'(s) = b - K/τ_s·exp(-s/τ_s) + H/τ_b·exp(-s/τ_b)

退化情形 τ_s == τ_b 时：

    C(s) = F(s) + (C0 - F0)·exp(-s/τ)，C'(s) = b - K/τ·exp(-s/τ)

C' 为两个指数项之差，至多有一个解析转折点（C''=0 的点可闭式定位），
故段内驻点不超过两个；据此切分单调子区间后二分定位阈值穿越与极值。
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Optional

# 时间求根容差（秒）与连续区间合并容差
ROOT_TOL = 1e-12
MERGE_TOL = 1e-9
BISECT_ITER = 200
# 仅用于画图的每段采样密度（不参与任何裁决）
DISPLAY_SAMPLES_PER_SEGMENT = 48


class ThermalValidationError(ValueError):
    """输入数据不合法。"""

    def __init__(self, code: str, message: str, field: Optional[str] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "field": self.field}


def _is_finite_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def parse_time(value: Any) -> tuple[float, bool]:
    """返回 (epoch 秒, 是否 ISO 文本)。ISO 与数值两种格式各自必须统一。"""
    if isinstance(value, str):
        text = value.strip()
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ThermalValidationError(
                "bad_time", f"时间 {value!r} 不是合法的 ISO 8601 日期时间", "time"
            ) from exc
        if dt.tzinfo is not None:
            return dt.timestamp(), True
        # 朴素时间按 UTC 解释，保证可计算
        return dt.replace(tzinfo=timezone.utc).timestamp(), True
    if _is_finite_number(value):
        return float(value), False
    raise ThermalValidationError(
        "bad_time", f"时间 {value!r} 必须是 ISO 8601 字符串或数值型纪元秒", "time"
    )


def _box_temperature(s: float, t_i: float, a: float, b: float, tau: float) -> float:
    """段内闭式箱温，s 为距段起点的秒数。"""
    return a + b * (s - tau) + (t_i - a + b * tau) * math.exp(-s / tau)


def _stationary_point(t_i: float, a: float, b: float, tau: float, duration: float) -> Optional[float]:
    """解析驻点 s*（段内局部极值），不存在则返回 None。b == 0 时箱温单调。"""
    if b == 0.0:
        return None
    ratio = (t_i - a + b * tau) / (b * tau)
    if ratio <= 0.0:
        return None
    s_star = tau * math.log(ratio)
    if 0.0 < s_star < duration:
        return s_star
    return None


def _bisect_root(f, lo: float, hi: float, f_lo: float) -> float:
    """在已知单调且端点异号的区间上二分求 f(s)=0。"""
    for _ in range(BISECT_ITER):
        mid = 0.5 * (lo + hi)
        f_mid = f(mid)
        if hi - lo <= ROOT_TOL:
            return mid
        if (f_lo > 0.0) == (f_mid > 0.0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _exceedance_on_piece(f, lo: float, hi: float, limit: float) -> Optional[tuple[float, float]]:
    """在单调子区间上求严格超限 {s : f(s) > limit} 的起止。

    单调函数仅需比较端点；端点异号时二分求根。
    """
    v_lo = f(lo) - limit
    v_hi = f(hi) - limit
    above_lo = v_lo > 0.0
    above_hi = v_hi > 0.0
    if above_lo and above_hi:
        return (lo, hi)
    if not above_lo and not above_hi:
        return None
    root = _bisect_root(lambda s: f(s) - limit, lo, hi, v_lo)
    return (lo, root) if above_lo else (root, hi)


def _merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not intervals:
        return []
    intervals = sorted(intervals)
    merged: list[list[float]] = [[intervals[0][0], intervals[0][1]]]
    for start, end in intervals[1:]:
        if start <= merged[-1][1] + MERGE_TOL:
            if end > merged[-1][1]:
                merged[-1][1] = end
        else:
            merged.append([start, end])
    return [(s, e) for s, e in merged]


# 样品热惯性与箱体热惯性视为相等的相对容差（退化分支）
CORE_TAU_EQUAL_REL = 1e-9


def _core_funcs(
    c0: float, box_start: float, a: float, b: float, tau_b: float, tau_s: float
):
    """返回 (C, C')：以箱温闭式曲线为连续驱动的样品核心温度闭式解。

    C 仅在首条记录处锚定一次，段末状态交由下一段作为初值继续传递。
    一般情形 (tau_s != tau_b)：

        gamma = tau_b*H/(tau_b-tau_s)，H = F0-a+b*tau_b，K = C0-a+b*(tau_b+tau_s)
        C(s) = a + b*(s-tau_b-tau_s) + K*exp(-s/tau_s) + gamma*(exp(-s/tau_b)-exp(-s/tau_s))

    差指数项以 expm1 稳定计算，tau_s≈tau_b 时不发生大数相消。
    退化情形 tau_s == tau_b = tau：

        C(s) = a + b*(s-2*tau) + (C0-a+2*b*tau + H*s/tau)*exp(-s/tau)
    """
    H = box_start - a + b * tau_b
    if abs(tau_b - tau_s) <= CORE_TAU_EQUAL_REL * max(1.0, tau_b, tau_s):
        tau = 0.5 * (tau_b + tau_s)

        def C(s: float) -> float:
            return a + b * (s - 2.0 * tau) + (
                c0 - a + 2.0 * b * tau + H * s / tau
            ) * math.exp(-s / tau)

        def Cp(s: float) -> float:
            e = math.exp(-s / tau)
            return b + e / tau * (H - c0 + a - 2.0 * b * tau - H * s / tau)

        return C, Cp, True

    gamma = tau_b * H / (tau_b - tau_s)
    K = c0 - a + b * (tau_b + tau_s)
    delta = 1.0 / tau_s - 1.0 / tau_b  # exp(-s/tau_b)/exp(-s/tau_s) = exp(s*delta)

    def C(s: float) -> float:
        e_s = math.exp(-s / tau_s)
        # gamma*(e_b - e_s) = gamma*e_s*expm1(s*delta)
        return a + b * (s - tau_b - tau_s) + e_s * (K + gamma * math.expm1(s * delta))

    def Cp(s: float) -> float:
        e_s = math.exp(-s / tau_s)
        # C' = b - K/tau_s*e_s - gamma*(e_b/tau_b - e_s/tau_s)
        #    = b - K/tau_s*e_s + gamma*e_s*((1/tau_s-1/tau_b) - expm1(s*delta)/tau_b)
        return b - K / tau_s * e_s + gamma * e_s * (
            delta - math.expm1(s * delta) / tau_b
        )

    return C, Cp, False


def _core_monotonic_cuts(
    Cp, a: float, b: float, box_start: float, tau_b: float, tau_s: float,
    duration: float, equal_tau: bool,
) -> tuple[list[float], list[float]]:
    """解析定位核心温度 C 的全部段内驻点。

    返回 (monotonic_cuts, stationary)：monotonic_cuts 含 0/duration 与全部驻点
    （切分后每段单调，供端点比较与二分穿越），stationary 为段内驻点（供极值）。

    C' 至多有两个零点：C' 中的指数和（记 A(s)）的导数 C'' 至多一个零点，
    该转折点可闭式定位，把区间切成 A 的两个单调子区间后各自至多一个根，
    再以二分精确定位；不依赖展示采样密度。
    """
    H = box_start - a + b * tau_b
    pivot: Optional[float] = None

    if equal_tau:
        tau = 0.5 * (tau_b + tau_s)
        # C' = b + e^{-s/tau}/tau * (Q - H*s/tau)，Q = H - C0 + a - 2b*tau。
        # g(s)=e^{-s/tau}(Q-Hs/tau) 的唯一转折点 s_g = tau*(Q+H)/H （H != 0）。
        # 从 Cp(0) 反解 Q（Cp(0)=b+Q/tau），无需再传入 C0：
        Q = (Cp(0.0) - b) * tau
        if H != 0.0:
            s_g = tau * (Q + H) / H
            if 0.0 < s_g < duration:
                pivot = s_g
    else:
        # C''=0 ⇒ exp(s*delta) = -D*tau_b^2/(gamma*tau_s^2)，需 RHS>0
        gamma = tau_b * H / (tau_b - tau_s)
        # Cp(0) = b - gamma/tau_b - D/tau_s ⇒ D = (b - gamma/tau_b - Cp(0))*tau_s
        D = (b - gamma / tau_b - Cp(0.0)) * tau_s
        delta = 1.0 / tau_s - 1.0 / tau_b
        if gamma != 0.0 and D != 0.0 and delta != 0.0:
            rhs = -(D * tau_b * tau_b) / (gamma * tau_s * tau_s)
            if rhs > 0.0:
                s_a = math.log(rhs) / delta
                if 0.0 < s_a < duration:
                    pivot = s_a

    base_cuts = [0.0, duration] if pivot is None else [0.0, pivot, duration]

    roots: list[float] = []
    for lo, hi in zip(base_cuts, base_cuts[1:]):
        v_lo, v_hi = Cp(lo), Cp(hi)
        if (v_lo > 0.0) != (v_hi > 0.0) and v_lo != 0.0 and v_hi != 0.0:
            roots.append(_bisect_root(Cp, lo, hi, v_lo))

    # 驻点=符号改变的内部根；转折点 pivot 处若 C' 恰为 0（峰/谷恰落在 C''=0
    # 的退化相切情形），它本身也是驻点。
    stationary = list(roots)
    if pivot is not None:
        scale = max(1.0, abs(b), abs(Cp(0.0)), abs(Cp(duration)))
        if abs(Cp(pivot)) <= 1e-10 * scale:
            stationary.append(pivot)
    stationary = sorted(set(stationary))
    # 切分点恒含 pivot：C' 在 pivot 两侧各自单调，保证每段至多一个驻点，
    # 且把峰/谷恰在 pivot 的驼峰正确切成两个单调子区间（端点比较才不漏判）。
    all_cuts = sorted({0.0, duration, *roots, *( [pivot] if pivot is not None else [] )})
    return all_cuts, stationary


def audit(payload: dict[str, Any]) -> dict[str, Any]:
    """执行完整温控审计，返回可直接序列化的结果字典。"""
    records = payload.get("records")
    if not isinstance(records, list):
        raise ThermalValidationError("bad_records", "records 必须是数组", "records")
    if not 4 <= len(records) <= 30:
        raise ThermalValidationError(
            "bad_records", f"记录数必须在 4 至 30 条之间，当前为 {len(records)} 条", "records"
        )

    params = payload.get("parameters")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ThermalValidationError(
            "bad_params", "parameters 必须是对象", "parameters"
        )

    def _require_positive(name: str, label: str) -> float:
        value = params.get(name)
        if not _is_finite_number(value):
            raise ThermalValidationError("bad_param", f"{label}必须是有限数值", name)
        if float(value) <= 0:
            raise ThermalValidationError("bad_param", f"{label}必须大于 0", name)
        return float(value)

    tau_closed = _require_positive("tau_closed", "箱盖关闭热惯性")
    tau_open = _require_positive("tau_open", "箱盖开启热惯性")
    exposure_limit = _require_positive("exposure_limit_seconds", "允许连续暴露时长（秒）")

    limit_raw = params.get("box_temp_limit")
    if not _is_finite_number(limit_raw):
        raise ThermalValidationError(
            "bad_param", "允许箱温必须是有限数值", "box_temp_limit"
        )
    box_temp_limit = float(limit_raw)

    # ---------- 可选：核心温度复核 ----------
    # 未启用（缺省 / enabled=false）时请求、结论与证据与原审计完全一致；
    # 启用后额外以逐段箱温闭式曲线为连续驱动求解样品核心温度（跨记录连续传递）。
    cr_raw = payload.get("core_review")
    core_enabled = False
    sample_initial_temp = tau_sample = core_temp_limit = None
    if cr_raw is not None:
        if not isinstance(cr_raw, dict):
            raise ThermalValidationError(
                "bad_core_review", "core_review 必须是对象", "core_review"
            )
        enabled = cr_raw.get("enabled", False)
        if not isinstance(enabled, bool):
            raise ThermalValidationError(
                "bad_core_review",
                "core_review.enabled 必须是布尔值 true/false",
                "core_review.enabled",
            )
        core_enabled = enabled
        if core_enabled:
            def _core_field(name: str, label: str, positive: bool = False) -> float:
                value = cr_raw.get(name)
                if not _is_finite_number(value):
                    raise ThermalValidationError(
                        "bad_core_param",
                        f"{label}必须是有限数值（不得为 NaN/Infinity）",
                        f"core_review.{name}",
                    )
                num = float(value)
                if positive and num <= 0.0:
                    raise ThermalValidationError(
                        "bad_core_param",
                        f"{label}必须大于 0",
                        f"core_review.{name}",
                    )
                return num

            sample_initial_temp = _core_field("sample_initial_temp", "首条记录时的样品温度")
            tau_sample = _core_field("tau_sample_seconds", "样品对箱温的热惯性", positive=True)
            core_temp_limit = _core_field("core_temp_limit", "核心温度上限")

    # 解析并逐条校验记录
    parsed: list[dict[str, Any]] = []
    iso_mode: Optional[bool] = None
    prev_t: Optional[float] = None
    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            raise ThermalValidationError(
                "bad_record", f"第 {idx + 1} 条记录必须是对象", f"records[{idx}]"
            )
        try:
            t, is_iso = parse_time(rec.get("time"))
        except ThermalValidationError as exc:
            exc.field = f"records[{idx}].time"
            raise
        if iso_mode is None:
            iso_mode = is_iso
        elif is_iso != iso_mode:
            raise ThermalValidationError(
                "mixed_time",
                "所有时间必须统一使用 ISO 8601 字符串或统一使用数值纪元秒，不得混用",
                f"records[{idx}].time",
            )
        if prev_t is not None and not t > prev_t:
            raise ThermalValidationError(
                "time_not_strict",
                f"第 {idx + 1} 条记录时间必须严格晚于上一条",
                f"records[{idx}].time",
            )

        box_t = rec.get("box_temp")
        amb_t = rec.get("ambient_temp")
        if not _is_finite_number(box_t):
            raise ThermalValidationError(
                "bad_temp", f"第 {idx + 1} 条箱温必须是有限数值", f"records[{idx}].box_temp"
            )
        if not _is_finite_number(amb_t):
            raise ThermalValidationError(
                "bad_temp", f"第 {idx + 1} 条环境温必须是有限数值", f"records[{idx}].ambient_temp"
            )
        lid_open = rec.get("lid_open")
        if not isinstance(lid_open, bool):
            raise ThermalValidationError(
                "bad_lid",
                f"第 {idx + 1} 条箱盖状态必须是布尔值 true/false",
                f"records[{idx}].lid_open",
            )
        parsed.append(
            {"t": t, "box": float(box_t), "amb": float(amb_t), "lid_open": lid_open}
        )
        prev_t = t

    t0 = parsed[0]["t"]

    def fmt(t_abs: float) -> Any:
        if iso_mode:
            # 输入（含朴素时间按 UTC 解释）统一以 UTC 回显，避免容器时区造成错位
            return datetime.fromtimestamp(t_abs, tz=timezone.utc).isoformat()
        return round(t_abs, 3)

    segments: list[dict[str, Any]] = []
    raw_intervals: list[tuple[float, float]] = []
    core_raw_intervals: list[tuple[float, float]] = []
    core_segments: list[dict[str, Any]] = []
    curve: list[dict[str, Any]] = []

    # 核心温度：仅在首条记录处锚定一次，随后跨记录连续传递，绝不重新锚定
    core_state = sample_initial_temp if core_enabled else None

    for i in range(len(parsed) - 1):
        r0, r1 = parsed[i], parsed[i + 1]
        duration = r1["t"] - r0["t"]
        a = r0["amb"]
        b = (r1["amb"] - r0["amb"]) / duration
        tau = tau_open if r0["lid_open"] else tau_closed
        t_start_box = r0["box"]

        def f(s: float, _ti=t_start_box, _a=a, _b=b, _tau=tau) -> float:
            return _box_temperature(s, _ti, _a, _b, _tau)

        # 端点解析值（末端闭式值应与该模型连续求解一致）
        t_end_model = f(duration)

        # 解析驻点 → 切分单调子区间
        s_star = _stationary_point(t_start_box, a, b, tau, duration)
        cuts = [0.0] + ([s_star] if s_star is not None else []) + [duration]

        # 段内超温子区间先收集，循环后在驻点相接处合并
        seg_intervals: list[tuple[float, float]] = []
        crossings: list[dict[str, Any]] = []
        for lo, hi in zip(cuts, cuts[1:]):
            piece = _exceedance_on_piece(f, lo, hi, box_temp_limit)
            if piece is not None:
                seg_intervals.append(piece)
            # 记录阈值穿越方向（内部穿越根）
            if (f(lo) - box_temp_limit) * (f(hi) - box_temp_limit) < 0:
                root = _bisect_root(lambda s: f(s) - box_temp_limit, lo, hi, f(lo) - box_temp_limit)
                direction = "up" if f(hi) > box_temp_limit else "down"
                crossings.append(
                    {
                        "elapsed_seconds": round(r0["t"] - t0 + root, 6),
                        "time": fmt(r0["t"] + root),
                        "box_temp": box_temp_limit,
                        "direction": direction,
                    }
                )

        # 驻点处相接的两个超温子区间属于同一连续区间，段内先合并
        seg_intervals = _merge_intervals(seg_intervals)

        # 段内极值（解析）
        candidates = [(0.0, t_start_box), (duration, t_end_model)]
        if s_star is not None:
            candidates.append((s_star, f(s_star)))
        s_max, val_max = max(candidates, key=lambda p: p[1])
        s_min, val_min = min(candidates, key=lambda p: p[1])

        u0 = r0["t"] - t0
        seg = {
            "index": i,
            "start_time": fmt(r0["t"]),
            "end_time": fmt(r1["t"]),
            "elapsed_start_seconds": round(u0, 6),
            "elapsed_end_seconds": round(u0 + duration, 6),
            "duration_seconds": round(duration, 6),
            "lid_open": r0["lid_open"],
            "tau_seconds": tau,
            "ambient_start": a,
            "ambient_end": r1["amb"],
            "ambient_slope_per_second": b,
            "box_temp_start": t_start_box,
            "box_temp_end_model": t_end_model,
            "box_temp_end_recorded": r1["box"],
            "model_record_gap": r1["box"] - t_end_model,
            "max_temp": {
                "time": fmt(r0["t"] + s_max),
                "elapsed_seconds": round(u0 + s_max, 6),
                "value": val_max,
                "kind": "interior" if 0.0 < s_max < duration else ("start" if s_max == 0 else "end"),
            },
            "min_temp": {
                "time": fmt(r0["t"] + s_min),
                "elapsed_seconds": round(u0 + s_min, 6),
                "value": val_min,
                "kind": "interior" if 0.0 < s_min < duration else ("start" if s_min == 0 else "end"),
            },
            "crossings": sorted(crossings, key=lambda c: c["elapsed_seconds"]),
            "exceedance_intervals": [
                {
                    "start_time": fmt(r0["t"] + s_lo),
                    "end_time": fmt(r0["t"] + s_hi),
                    "elapsed_start_seconds": round(u0 + s_lo, 6),
                    "elapsed_end_seconds": round(u0 + s_hi, 6),
                    "duration_seconds": round(s_hi - s_lo, 6),
                }
                for s_lo, s_hi in seg_intervals
            ],
        }
        segments.append(seg)
        raw_intervals.extend((u0 + s_lo, u0 + s_hi) for s_lo, s_hi in seg_intervals)

        # ---------- 核心温度复核（启用时）：以本段箱温闭式曲线连续驱动 ----------
        core_ev = None
        if core_enabled:
            C, Cp, equal_tau = _core_funcs(core_state, t_start_box, a, b, tau, tau_sample)
            core_cuts, core_stationary = _core_monotonic_cuts(
                Cp, a, b, t_start_box, tau, tau_sample, duration, equal_tau
            )

            core_seg_intervals: list[tuple[float, float]] = []
            core_crossings: list[dict[str, Any]] = []
            for lo, hi in zip(core_cuts, core_cuts[1:]):
                piece = _exceedance_on_piece(C, lo, hi, core_temp_limit)
                if piece is not None:
                    core_seg_intervals.append(piece)
                if (C(lo) - core_temp_limit) * (C(hi) - core_temp_limit) < 0:
                    root = _bisect_root(
                        lambda s: C(s) - core_temp_limit, lo, hi, C(lo) - core_temp_limit
                    )
                    core_crossings.append(
                        {
                            "elapsed_seconds": round(u0 + root, 6),
                            "time": fmt(r0["t"] + root),
                            "core_temp": core_temp_limit,
                            "direction": "up" if C(hi) > core_temp_limit else "down",
                        }
                    )
            core_seg_intervals = _merge_intervals(core_seg_intervals)

            core_candidates = [(0.0, core_state), (duration, C(duration))]
            core_candidates.extend((s_star_c, C(s_star_c)) for s_star_c in core_stationary)
            cs_max, cval_max = max(core_candidates, key=lambda p: p[1])
            cs_min, cval_min = min(core_candidates, key=lambda p: p[1])

            core_ev = {
                "index": i,
                "tau_sample_seconds": tau_sample,
                "tau_box_seconds": tau,
                "tau_equal": equal_tau,
                "start_time": fmt(r0["t"]),
                "end_time": fmt(r1["t"]),
                "elapsed_start_seconds": round(u0, 6),
                "elapsed_end_seconds": round(u0 + duration, 6),
                "core_temp_start": core_state,
                "core_temp_end": C(duration),
                "max_temp": {
                    "time": fmt(r0["t"] + cs_max),
                    "elapsed_seconds": round(u0 + cs_max, 6),
                    "value": cval_max,
                    "kind": "interior"
                    if 0.0 < cs_max < duration
                    else ("start" if cs_max == 0.0 else "end"),
                },
                "min_temp": {
                    "time": fmt(r0["t"] + cs_min),
                    "elapsed_seconds": round(u0 + cs_min, 6),
                    "value": cval_min,
                    "kind": "interior"
                    if 0.0 < cs_min < duration
                    else ("start" if cs_min == 0.0 else "end"),
                },
                "crossings": sorted(core_crossings, key=lambda c: c["elapsed_seconds"]),
                "exceedance_intervals": [
                    {
                        "start_time": fmt(r0["t"] + s_lo),
                        "end_time": fmt(r0["t"] + s_hi),
                        "elapsed_start_seconds": round(u0 + s_lo, 6),
                        "elapsed_end_seconds": round(u0 + s_hi, 6),
                        "duration_seconds": round(s_hi - s_lo, 6),
                    }
                    for s_lo, s_hi in core_seg_intervals
                ],
            }
            core_segments.append(core_ev)
            core_raw_intervals.extend(
                (u0 + s_lo, u0 + s_hi) for s_lo, s_hi in core_seg_intervals
            )
            # 段末核心温作为下一段初值——跨记录连续传递，不重新锚定
            core_state = C(duration)

        # 画图采样（展示用途；裁决全部基于上面的解析结果）
        for k in range(DISPLAY_SAMPLES_PER_SEGMENT + 1):
            s = duration * k / DISPLAY_SAMPLES_PER_SEGMENT
            point = {
                "elapsed_seconds": round(u0 + s, 6),
                "time": fmt(r0["t"] + s),
                "box_temp": f(s),
                "ambient_temp": a + b * s,
                "lid_open": r0["lid_open"],
            }
            if core_enabled:
                point["core_temp"] = C(s)
            curve.append(point)

    # 全局连续超温区间（跨记录取并集，间隙才打断连续性）
    # 丢弃零宽度项：仅在切点接触阈值（T 始终 <= limit）不构成严格超限
    merged = [
        (lo, hi)
        for lo, hi in _merge_intervals(raw_intervals)
        if hi - lo > MERGE_TOL
    ]
    exceedance_intervals: list[dict[str, Any]] = []
    first_failure: Optional[dict[str, Any]] = None
    for n, (u_lo, u_hi) in enumerate(merged):
        duration = u_hi - u_lo
        entry = {
            "index": n,
            "start_time": fmt(t0 + u_lo),
            "end_time": fmt(t0 + u_hi),
            "elapsed_start_seconds": round(u_lo, 6),
            "elapsed_end_seconds": round(u_hi, 6),
            "duration_seconds": round(duration, 6),
            "reaches_limit": duration + MERGE_TOL >= exposure_limit,
        }
        if entry["reaches_limit"] and first_failure is None:
            failure_elapsed = u_lo + exposure_limit
            first_failure = {
                "time": fmt(t0 + failure_elapsed),
                "elapsed_seconds": round(failure_elapsed, 6),
                "interval_index": n,
                "interval_start_time": entry["start_time"],
                "exposure_limit_seconds": exposure_limit,
            }
        exceedance_intervals.append(entry)

    total_exceedance = sum(e["duration_seconds"] for e in exceedance_intervals)

    verdict = "reject" if first_failure is not None else "pass"

    # ---------- 核心温度复核汇总：是否越限 + 首个超限（风险）时刻 ----------
    core_review_result: Optional[dict[str, Any]] = None
    if core_enabled:
        core_merged = [
            (lo, hi)
            for lo, hi in _merge_intervals(core_raw_intervals)
            if hi - lo > MERGE_TOL
        ]
        core_intervals: list[dict[str, Any]] = []
        first_core_risk: Optional[dict[str, Any]] = None
        for n, (u_lo, u_hi) in enumerate(core_merged):
            entry = {
                "index": n,
                "start_time": fmt(t0 + u_lo),
                "end_time": fmt(t0 + u_hi),
                "elapsed_start_seconds": round(u_lo, 6),
                "elapsed_end_seconds": round(u_hi, 6),
                "duration_seconds": round(u_hi - u_lo, 6),
            }
            if first_core_risk is None:
                first_core_risk = {
                    "time": fmt(t0 + u_lo),
                    "elapsed_seconds": round(u_lo, 6),
                    "interval_index": n,
                    "interval_start_time": entry["start_time"],
                }
            core_intervals.append(entry)

        core_status = "reject" if first_core_risk is not None else "pass"
        core_review_result = {
            "enabled": True,
            "status": core_status,
            "verdict": "核心拒收" if core_status == "reject" else "核心放行",
            "sample_initial_temp": sample_initial_temp,
            "tau_sample_seconds": tau_sample,
            "core_temp_limit": core_temp_limit,
            "anchoring": "样品核心温度仅在首条记录处以 sample_initial_temp 锚定一次，"
            "随后以逐段箱温闭式曲线为连续驱动，跨记录传递段末状态，不在任一记录处重新锚定",
            "solver": "线性驱动一阶响应闭式解（差指数项以 expm1 稳定计算）；"
            "覆盖 tau_sample==tau_box 退化分支；段内驻点解析定位、单调区间二分穿越（容差 1e-12s）",
            "exceedance_intervals": core_intervals,
            "total_exceedance_seconds": round(
                sum(e["duration_seconds"] for e in core_intervals), 6
            ),
            "first_risk_time": first_core_risk,
            "segments": core_segments,
            "core_temp_end": core_state,
        }

    result = {
        "status": verdict,
        "verdict": "拒收" if verdict == "reject" else "放行",
        "model": {
            "equation": "dT/dt = (T_env(t) - T) / tau",
            "ambient_assumption": "相邻记录间环境温度线性变化",
            "solver": "每段闭式解析解；阈值穿越为单调区间二分求根（容差 1e-12s），无离散采样裁决",
            "exceedance_rule": "严格超限 T > T_limit；连续超温区间在全局取并集",
            "segment_initial_condition": "每段以该记录时刻实测箱温为初值锚定，段内由闭式解推进；"
            "model_record_gap 给出段末模型值与下一读数的偏差作为证据",
            "tau_switching": "tau 取段起点箱盖状态（开启/关闭），状态在记录时刻切换",
        },
        "parameters": {
            "tau_closed": tau_closed,
            "tau_open": tau_open,
            "box_temp_limit": box_temp_limit,
            "exposure_limit_seconds": exposure_limit,
        },
        "record_count": len(parsed),
        "segments": segments,
        "exceedance_intervals": exceedance_intervals,
        "total_exceedance_seconds": round(total_exceedance, 6),
        "first_failure_time": first_failure,
        "curve": curve,
        "records_echo": [
            {
                "time": fmt(r["t"]),
                "elapsed_seconds": round(r["t"] - t0, 6),
                "box_temp": r["box"],
                "ambient_temp": r["amb"],
                "lid_open": r["lid_open"],
            }
            for r in parsed
        ],
    }

    if core_review_result is not None:
        box_rejected = verdict == "reject"
        core_rejected = core_status == "reject"
        final_reject = box_rejected or core_rejected
        if box_rejected and core_rejected:
            final_verdict = "拒收（箱体与核心均超限）"
        elif core_rejected:
            final_verdict = "拒收（箱体放行但核心拒收）"
        elif box_rejected:
            final_verdict = "拒收（箱体超限、核心未越限）"
        else:
            final_verdict = "放行（箱体与核心均合格）"
        result["core_review"] = core_review_result
        result["box_status"] = verdict
        result["final_status"] = "reject" if final_reject else "pass"
        result["final_verdict"] = final_verdict
        result["box_rejected"] = box_rejected
        result["core_rejected"] = core_rejected

    return result
