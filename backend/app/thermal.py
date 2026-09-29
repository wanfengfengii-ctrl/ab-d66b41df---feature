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


# ===========================================================================
# 核心温度复核
#
# 探头合格只代表箱体测点合格，不代表油样内部已同步降温。启用复核后，
# 样品核心温度 C(t) 同样以一阶热响应对【连续箱温闭式曲线 T_box(t)】做
# 响应，样品自身热惯性为 tau_sample：
#
#     dC/dt = (T_box(t) - C(t)) / tau_sample
#
# 关键口径（与箱体裁决不同）：
#
# * 驱动 T_box 是上一步逐段闭式求解得到的【整条连续曲线】，跨记录传递，
#   绝不在每条记录处用实测箱温重新锚定样品状态；
# * 样品初值只在【首条记录时刻】锚定一次（core_initial_temp），之后由
#   闭式解逐段推进，段末状态即下一段初值；
# * 段内箱温闭式解形如 T_box(s) = c0 + c1*s + c2*exp(-s/tau_box)，代入
#   样品方程可直接积分，无需任何数值步进；
# * 不按展示采样点裁决：段内极值由解析驻点定位，阈值穿越在单调子区间
#   上二分求根（容差 1e-12s）；
# * 必须覆盖退化情形 tau_sample == tau_box（公式 0/0，取极限闭式解）。
# ===========================================================================


def _core_coeffs(t_start: float, a: float, b: float, tau_box: float) -> tuple[float, float, float]:
    """段内连续箱温闭式解写成 T_box(s) = c0 + c1*s + c2*exp(-s/tau_box)。"""
    c0 = a - b * tau_box
    c1 = b
    c2 = t_start - a + b * tau_box
    return c0, c1, c2


def _core_temperature(
    s: float,
    c_start: float,
    a: float,
    b: float,
    t_box_start: float,
    tau_box: float,
    tau_sample: float,
) -> float:
    """样品核心温度段内闭式解，s 为距段起点秒数；自动处理 tau_sample==tau_box。"""
    c0, c1, c2 = _core_coeffs(t_box_start, a, b, tau_box)
    eS = math.exp(-s / tau_sample)
    if tau_sample == tau_box:
        # 退化情形（等热惯性）：对 (c2/tau)*s*exp(-s/tau) 直接积分
        val = c0 - c1 * tau_sample + c1 * s + c2 * (s / tau_sample) * eS + (
            c_start - c0 + c1 * tau_sample
        ) * eS
    else:
        # D = c2 / (1 - tau_sample/tau_box)
        k = c2 * tau_box / (tau_box - tau_sample)
        val = c0 - c1 * tau_sample + c1 * s + k * math.exp(-s / tau_box) + (
            c_start - c0 + c1 * tau_sample - k
        ) * eS
    return val


def _core_stationary_points(
    c_start: float,
    a: float,
    b: float,
    t_box_start: float,
    tau_box: float,
    tau_sample: float,
    duration: float,
) -> list[float]:
    """样品核心温度段内全部解析驻点 s*（C'(s)=0 ⇔ T_box(s)=C(s)）。

    关键结构性论证：在 gap=T_box-C 的任一零点处 gap'=T_box'（因 C'=gap/τs），
    即穿越方向由该时刻箱温导数决定。箱温段内至多一个驻点（T_box' 单调、至多
    一次过零），因此在箱温驻点两侧 T_box' 各保号；保号区间内每次穿越方向
    相同，gap 至多穿越一次。故以箱温驻点切分后逐段二分即可找出全部驻点
    （一段内最多两个：滞后样品在箱温谷底/峰顶附近可出现先峰后谷）。
    """
    def gap(s: float) -> float:
        return _box_temperature(s, t_box_start, a, b, tau_box) - _core_temperature(
            s, c_start, a, b, t_box_start, tau_box, tau_sample
        )

    box_star = _stationary_point(t_box_start, a, b, tau_box, duration)
    cuts = [0.0] + ([box_star] if box_star is not None else []) + [duration]

    roots: list[float] = []
    for j, (lo, hi) in enumerate(zip(cuts, cuts[1:])):
        # 箱温驻点恰为 gap 零点时，它本身就是核心温度驻点（内部切点）
        if box_star is not None and j == 1 and gap(box_star) == 0.0:
            roots.append(box_star)
        g_lo, g_hi = gap(lo), gap(hi)
        if g_lo * g_hi < 0.0:
            roots.append(_bisect_root(gap, lo, hi, g_lo))
    roots = sorted(set(roots))
    return [s for s in roots if 0.0 < s < duration]


def _core_segments(
    parsed: list[dict[str, Any]],
    box_segments: list[dict[str, Any]],
    tau_closed: float,
    tau_open: float,
    tau_sample: float,
    core_initial_temp: float,
    core_limit: float,
    t0: float,
    fmt,
) -> dict[str, Any]:
    """以连续箱温闭式曲线为驱动，跨记录传递求解样品核心温度并裁决。

    返回每段起止状态、段内极值、阈值穿越、核心超温区间、核心曲线采样与
    最早风险时刻。样品状态全程只在首条记录锚定一次。
    """
    segments: list[dict[str, Any]] = []
    raw_intervals: list[tuple[float, float]] = []
    curve: list[dict[str, Any]] = []

    # 唯一一次锚定：首条记录时刻的样品温度
    c_state = float(core_initial_temp)

    for i in range(len(parsed) - 1):
        r0, r1 = parsed[i], parsed[i + 1]
        duration = r1["t"] - r0["t"]
        a = r0["amb"]
        b = (r1["amb"] - r0["amb"]) / duration
        tau_box = tau_open if r0["lid_open"] else tau_closed
        t_box_start = box_segments[i]["box_temp_start"]

        def g(s: float, _cs=c_state, _a=a, _b=b, _tb=t_box_start, _tbk=tau_box) -> float:
            return _core_temperature(s, _cs, _a, _b, _tb, _tbk, tau_sample)

        c_start = c_state
        c_end_model = g(duration)

        # 解析驻点（可能多个）→ 切分单调子区间
        s_stars = _core_stationary_points(
            c_start, a, b, t_box_start, tau_box, tau_sample, duration
        )
        cuts = [0.0] + s_stars + [duration]

        seg_intervals: list[tuple[float, float]] = []
        crossings: list[dict[str, Any]] = []
        for lo, hi in zip(cuts, cuts[1:]):
            piece = _exceedance_on_piece(g, lo, hi, core_limit)
            if piece is not None:
                seg_intervals.append(piece)
            if (g(lo) - core_limit) * (g(hi) - core_limit) < 0:
                root = _bisect_root(lambda s: g(s) - core_limit, lo, hi, g(lo) - core_limit)
                direction = "up" if g(hi) > core_limit else "down"
                crossings.append(
                    {
                        "elapsed_seconds": round(r0["t"] - t0 + root, 6),
                        "time": fmt(r0["t"] + root),
                        "core_temp": core_limit,
                        "direction": direction,
                    }
                )

        seg_intervals = _merge_intervals(seg_intervals)

        candidates = [(0.0, c_start), (duration, c_end_model)]
        for s_star in s_stars:
            candidates.append((s_star, g(s_star)))
        s_max, val_max = max(candidates, key=lambda p: p[1])
        s_min, val_min = min(candidates, key=lambda p: p[1])

        u0 = r0["t"] - t0

        def kind_of(s: float) -> str:
            return "interior" if 0.0 < s < duration else ("start" if s == 0.0 else "end")

        seg = {
            "index": i,
            "start_time": fmt(r0["t"]),
            "end_time": fmt(r1["t"]),
            "elapsed_start_seconds": round(u0, 6),
            "elapsed_end_seconds": round(u0 + duration, 6),
            "duration_seconds": round(duration, 6),
            "lid_open": r0["lid_open"],
            "tau_box_seconds": tau_box,
            "tau_sample_seconds": tau_sample,
            "degenerate_equal_tau": tau_sample == tau_box,
            "ambient_start": a,
            "ambient_end": r1["amb"],
            "ambient_slope_per_second": b,
            # 每段起止【样品】状态（连续传递，非重新锚定）
            "core_temp_start": c_start,
            "core_temp_end": c_end_model,
            # 同段驱动箱温起止（闭式连续曲线），便于复核样品跟随关系
            "box_driver_temp_start": t_box_start,
            "box_driver_temp_end": box_segments[i]["box_temp_end_model"],
            "max_temp": {
                "time": fmt(r0["t"] + s_max),
                "elapsed_seconds": round(u0 + s_max, 6),
                "value": val_max,
                "kind": kind_of(s_max),
            },
            "min_temp": {
                "time": fmt(r0["t"] + s_min),
                "elapsed_seconds": round(u0 + s_min, 6),
                "value": val_min,
                "kind": kind_of(s_min),
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

        # 展示采样（仅画图；裁决全部基于上面的解析结果）
        for k in range(DISPLAY_SAMPLES_PER_SEGMENT + 1):
            s = duration * k / DISPLAY_SAMPLES_PER_SEGMENT
            curve.append(
                {
                    "elapsed_seconds": round(u0 + s, 6),
                    "time": fmt(r0["t"] + s),
                    "core_temp": g(s),
                    "box_temp": _box_temperature(s, t_box_start, a, b, tau_box),
                    "lid_open": r0["lid_open"],
                }
            )

        # 跨记录传递：段末闭式状态即下一段初值（不在记录点重新锚定样品）
        c_state = c_end_model

    merged = [
        (lo, hi) for lo, hi in _merge_intervals(raw_intervals) if hi - lo > MERGE_TOL
    ]
    return {
        "segments": segments,
        "raw_intervals": merged,
        "curve": curve,
        "final_core_temp": c_state,
    }


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

    # -------- 核心温度复核（默认不启用；不启用时请求/结论/证据完全保持原样） --------
    review_cfg = payload.get("core_temperature_review")
    core_review_enabled = False
    sample_initial_temp: Optional[float] = None
    tau_sample: Optional[float] = None
    core_temp_limit: Optional[float] = None
    if review_cfg is not None:
        if not isinstance(review_cfg, dict):
            raise ThermalValidationError(
                "bad_core_review",
                "core_temperature_review 必须是对象",
                "core_temperature_review",
            )
        enabled = review_cfg.get("enabled", False)
        if enabled is None:
            enabled = False
        if not isinstance(enabled, bool):
            raise ThermalValidationError(
                "bad_core_review",
                "核心温度复核开关 enabled 必须是布尔值 true/false",
                "core_temperature_review.enabled",
            )
        core_review_enabled = enabled
        if enabled:
            base_field = "core_temperature_review"

            def _core_number(name: str, label: str, positive: bool = False) -> float:
                value = review_cfg.get(name)
                if not _is_finite_number(value):
                    raise ThermalValidationError(
                        "bad_core_review",
                        f"{label}必须是有限数值（不得为 NaN/Infinity）",
                        f"{base_field}.{name}",
                    )
                val = float(value)
                if positive and val <= 0.0:
                    raise ThermalValidationError(
                        "bad_core_review", f"{label}必须大于 0", f"{base_field}.{name}"
                    )
                return val

            sample_initial_temp = _core_number("sample_initial_temp", "首条记录时的样品温度")
            tau_sample = _core_number("tau_sample_seconds", "样品对箱温的热惯性（秒）", positive=True)
            core_temp_limit = _core_number("core_temp_limit", "核心温度上限")

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
    curve: list[dict[str, Any]] = []

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

        # 画图采样（展示用途；裁决全部基于上面的解析结果）
        for k in range(DISPLAY_SAMPLES_PER_SEGMENT + 1):
            s = duration * k / DISPLAY_SAMPLES_PER_SEGMENT
            curve.append(
                {
                    "elapsed_seconds": round(u0 + s, 6),
                    "time": fmt(r0["t"] + s),
                    "box_temp": f(s),
                    "ambient_temp": a + b * s,
                    "lid_open": r0["lid_open"],
                }
            )

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

    box_reject = first_failure is not None

    # -------- 核心温度复核结果 --------
    core_block: Optional[dict[str, Any]] = None
    core_reject = False
    if core_review_enabled:
        solved = _core_segments(
            parsed,
            segments,
            tau_closed,
            tau_open,
            tau_sample,
            sample_initial_temp,
            core_temp_limit,
            t0,
            fmt,
        )
        core_intervals: list[dict[str, Any]] = []
        first_risk: Optional[dict[str, Any]] = None
        for n, (u_lo, u_hi) in enumerate(solved["raw_intervals"]):
            duration = u_hi - u_lo
            core_intervals.append(
                {
                    "index": n,
                    "start_time": fmt(t0 + u_lo),
                    "end_time": fmt(t0 + u_hi),
                    "elapsed_start_seconds": round(u_lo, 6),
                    "elapsed_end_seconds": round(u_hi, 6),
                    "duration_seconds": round(duration, 6),
                }
            )
            if first_risk is None:
                first_risk = {
                    "time": fmt(t0 + u_lo),
                    "elapsed_seconds": round(u_lo, 6),
                    "interval_index": n,
                }
        core_total = sum(e["duration_seconds"] for e in core_intervals)
        core_reject = first_risk is not None
        # 全局段内极值（跨段），便于一页给出核心最高温证据
        all_max = max(s["max_temp"]["value"] for s in solved["segments"])
        all_min = min(s["min_temp"]["value"] for s in solved["segments"])
        core_block = {
            "enabled": True,
            "status": "reject" if core_reject else "pass",
            "verdict": "核心温度超限" if core_reject else "核心温度未越限",
            "sample_initial_temp": sample_initial_temp,
            "tau_sample_seconds": tau_sample,
            "core_temp_limit": core_temp_limit,
            "sample_final_temp": solved["final_core_temp"],
            "core_max_temp": all_max,
            "core_min_temp": all_min,
            "exceedance_intervals": core_intervals,
            "total_exceedance_seconds": round(core_total, 6),
            "first_risk_time": first_risk,
            "segments": solved["segments"],
            "curve": solved["curve"],
            "model": {
                "equation": "dC/dt = (T_box(t) - C(t)) / tau_sample",
                "driver": "驱动为箱体逐段闭式连续曲线 T_box(t)（含线性环境温项与指数项），非离散读数",
                "initial_condition": "样品核心温度仅在首条记录时刻以 sample_initial_temp 锚定一次，"
                "此后段末闭式状态直接作为下一段初值，跨记录连续传递，不在任何记录点重新锚定",
                "degenerate_case": "tau_sample == tau_box（样品热惯性等于箱体热惯性）采用等价极限闭式解",
                "solver": "驱动指数项在样品一阶方程下直接积分得闭式解；段内驻点解析定位、"
                "阈值穿越在单调子区间二分求根（容差 1e-12s），不按展示采样点裁决",
                "exceedance_rule": "严格超限 C > core_temp_limit；首个超限时刻为首次上穿点",
            },
        }

    reject = box_reject or core_reject
    verdict = "reject" if reject else "pass"
    if not core_review_enabled:
        verdict_text = "拒收" if box_reject else "放行"
    elif box_reject and core_reject:
        verdict_text = "拒收（箱体与核心温度均超限）"
    elif core_reject:
        verdict_text = "拒收（箱体放行但核心温度超限）"
    elif box_reject:
        verdict_text = "拒收（箱体超限，核心温度未越限）"
    else:
        verdict_text = "放行"

    return {
        "status": verdict,
        "verdict": verdict_text,
        # 箱体/核心分项结论仅在启用核心温度复核时输出；
        # 未启用时响应与原审计完全一致（不多出任何字段）。
        **(
            {
                "box_status": "reject" if box_reject else "pass",
                "box_verdict": "拒收" if box_reject else "放行",
            }
            if core_block is not None
            else {}
        ),
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
        # 未启用复核时不输出该字段（保持原响应不变）；启用时为核心温度复核证据
        **({"core_temperature_review": core_block} if core_block is not None else {}),
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
