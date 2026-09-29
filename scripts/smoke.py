"""温控审计 API 冒烟脚本（verify 服务内运行）。

校验：健康检查、参数约定接口、拒收裁决（含连续超温区间证据与最早失效时刻）、
放行裁决、数据不合法 (422)，以及【核心温度复核】启用 / 未启用两类审计：
未启用响应保持原样；启用后区分箱体放行但核心拒收，并对非法/无穷参数给出
字段级错误。任何断言失败即以非零退出码结束容器。
"""
from __future__ import annotations

import os
import sys

import httpx

BASE = os.environ.get("AUDIT_BASE_URL", "http://app:8000").rstrip("/")

REJECT_PAYLOAD = {
    "records": [
        {"time": 0, "box_temp": 4.0, "ambient_temp": 25.0, "lid_open": False},
        {"time": 60, "box_temp": 7.806654, "ambient_temp": 25.0, "lid_open": False},
        {"time": 1560, "box_temp": 7.254505, "ambient_temp": 3.0, "lid_open": False},
        {"time": 2460, "box_temp": 3.211819, "ambient_temp": 3.0, "lid_open": False},
        {"time": 3360, "box_temp": 3.010546, "ambient_temp": 3.0, "lid_open": False},
    ],
    "parameters": {
        "tau_closed": 300,
        "tau_open": 90,
        "box_temp_limit": 8.0,
        "exposure_limit_seconds": 600,
    },
}

PASS_PAYLOAD = {
    "records": [
        {"time": 0, "box_temp": 4.0, "ambient_temp": 3.0, "lid_open": False},
        {"time": 300, "box_temp": 3.551819, "ambient_temp": 3.5, "lid_open": False},
        {"time": 600, "box_temp": 3.703003, "ambient_temp": 4.0, "lid_open": False},
        {"time": 900, "box_temp": 3.817165, "ambient_temp": 3.8, "lid_open": False},
    ],
    "parameters": {
        "tau_closed": 300,
        "tau_open": 90,
        "box_temp_limit": 8.0,
        "exposure_limit_seconds": 600,
    },
}

# 箱体探头全程合格（箱温 < 8℃，箱体裁决放行），但样品核心温度滞后冲高、
# 核心上限设为 6℃ → 启用复核后必须判“箱体放行但核心拒收”。
CORE_REJECT_RECORDS = [
    {"time": t, "box_temp": 7.5 - 3.5 * (2.718281828459045 ** (-t / 300.0)),
     "ambient_temp": 7.5, "lid_open": False}
    for t in (0, 600, 1200, 1800, 2400)
]
CORE_REJECT_PAYLOAD = {
    "records": CORE_REJECT_RECORDS,
    "parameters": {
        "tau_closed": 300,
        "tau_open": 90,
        "box_temp_limit": 8.0,
        "exposure_limit_seconds": 600,
    },
    "core_temperature_review": {
        "enabled": True,
        "sample_initial_temp": 4.0,
        "tau_sample_seconds": 900.0,
        "core_temp_limit": 6.0,
    },
}
# 未启用复核：显式 enabled=false，响应须与不含该字段完全一致
CORE_DISABLED_PAYLOAD = {
    "records": CORE_REJECT_RECORDS,
    "parameters": CORE_REJECT_PAYLOAD["parameters"],
    "core_temperature_review": {"enabled": False},
}


def check(cond: bool, msg: str) -> None:
    if not cond:
        print(f"SMOKE FAIL: {msg}", file=sys.stderr)
        sys.exit(1)
    print(f"  ✓ {msg}")


def main() -> None:
    print(f"目标审计服务：{BASE}")
    with httpx.Client(base_url=BASE, timeout=10) as c:
        r = c.get("/healthz")
        check(r.status_code == 200 and r.json().get("status") == "ok", "GET /healthz 返回 200/ok")

        r = c.get("/api/audit/schema")
        check(r.status_code == 200 and "tau_closed" in r.json()["parameters"], "GET /api/audit/schema 含模型参数约定")

        r = c.post("/api/audit", json=REJECT_PAYLOAD)
        check(r.status_code == 200, f"拒收场景 HTTP 200（实际 {r.status_code}）")
        body = r.json()
        check(body["status"] == "reject", "拒收场景裁决为 reject/拒收")
        intervals = body["exceedance_intervals"]
        check(len(intervals) >= 1, "至少报告 1 个连续超温区间")
        iv = intervals[0]
        check(iv["start_time"] < iv["end_time"], "超温区间起点早于终点")
        check(iv["duration_seconds"] >= 600, "超温区间持续时长达到允许连续暴露时长")
        ff = body.get("first_failure_time")
        check(ff is not None, "给出最早失效时刻")
        check(
            abs(ff["elapsed_seconds"] - (iv["elapsed_start_seconds"] + 600)) < 1e-6,
            "最早失效时刻 = 区间起点 + 允许暴露时长",
        )
        check(len(body["curve"]) > len(REJECT_PAYLOAD["records"]), "返回稠密箱温连续曲线（非仅离散读数）")
        check(any(s["max_temp"]["kind"] == "interior" for s in body["segments"]), "存在段内解析极值证据")

        r = c.post("/api/audit", json=PASS_PAYLOAD)
        body = r.json()
        check(r.status_code == 200 and body["status"] == "pass", "放行场景裁决为 pass/放行")
        check(body["first_failure_time"] is None, "放行场景无失效时刻")

        # ---- 核心温度复核：未启用 ----
        plain = c.post(
            "/api/audit",
            json={"records": CORE_REJECT_RECORDS, "parameters": CORE_REJECT_PAYLOAD["parameters"]},
        ).json()
        check("core_temperature_review" not in plain, "未启用复核时响应不含 core_temperature_review")
        r = c.post("/api/audit", json=CORE_DISABLED_PAYLOAD)
        check(r.status_code == 200 and r.json() == plain, "显式 enabled=false 与未启用响应完全一致")

        # ---- 核心温度复核：启用（箱体放行但核心拒收）----
        r = c.post("/api/audit", json=CORE_REJECT_PAYLOAD)
        check(r.status_code == 200, f"启用复核 HTTP 200（实际 {r.status_code}）")
        body = r.json()
        check(body["box_status"] == "pass", "箱体探头裁决为放行")
        check(body["status"] == "reject", "启用复核后总体裁决为拒收")
        cb = body.get("core_temperature_review")
        check(isinstance(cb, dict) and cb.get("enabled") is True, "返回核心温度复核证据块")
        check(cb["status"] == "reject", "核心温度裁决为 reject（核心超限）")
        risk = cb.get("first_risk_time")
        check(isinstance(risk, dict) and risk.get("elapsed_seconds") is not None, "给出最早风险时刻")
        check(cb["exceedance_intervals"] and cb["exceedance_intervals"][0]["duration_seconds"] > 0,
              "给出核心温度连续超限区间")
        check(len(cb["segments"]) == len(CORE_REJECT_RECORDS) - 1, "逐段返回核心复核证据")
        seg = cb["segments"][0]
        check(
            abs(seg["core_temp_end"] - cb["segments"][1]["core_temp_start"]) < 1e-9,
            "样品核心温度跨记录连续传递（段末=下段起点，不重新锚定）",
        )
        check({"core_temp", "box_temp"} <= set(cb["curve"][0]), "核心曲线采样同时含核心温度与驱动箱温")

        # ---- 核心温度复核：非法/无穷参数字段级错误 ----
        raw = (
            '{"records": ' + __import__("json").dumps(CORE_REJECT_RECORDS)
            + ', "parameters": ' + __import__("json").dumps(CORE_REJECT_PAYLOAD["parameters"])
            + ', "core_temperature_review": {"enabled": true, "sample_initial_temp": 4.0,'
            ' "tau_sample_seconds": Infinity, "core_temp_limit": 6.0}}'
        )
        r = c.post("/api/audit", content=raw, headers={"content-type": "application/json"})
        check(r.status_code == 422, "无穷复核参数判为 422")
        err = r.json()["errors"][0]
        check(
            err["code"] == "bad_core_review"
            and err["field"] == "core_temperature_review.tau_sample_seconds",
            "无穷参数给出字段级错误（tau_sample_seconds）",
        )

        r = c.post("/api/audit", json={"records": [], "parameters": {}})
        check(r.status_code == 422 and r.json()["status"] == "invalid", "空记录判为数据不合法 (422)")

        bad = {
            "records": [
                {"time": 0, "box_temp": 4, "ambient_temp": 5, "lid_open": False},
                {"time": 0, "box_temp": 4, "ambient_temp": 5, "lid_open": False},
                {"time": 1, "box_temp": 4, "ambient_temp": 5, "lid_open": False},
                {"time": 2, "box_temp": 4, "ambient_temp": 5, "lid_open": False},
            ],
            "parameters": {
                "tau_closed": 300,
                "tau_open": 90,
                "box_temp_limit": 8,
                "exposure_limit_seconds": 600,
            },
        }
        r = c.post("/api/audit", json=bad)
        check(
            r.status_code == 422 and r.json()["errors"][0]["code"] == "time_not_strict",
            "时间非严格递增判为 time_not_strict",
        )

    print("冒烟全部通过。")


if __name__ == "__main__":
    main()
