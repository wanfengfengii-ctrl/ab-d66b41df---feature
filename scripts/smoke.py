"""温控审计 API 冒烟脚本（verify 服务内运行）。

校验：健康检查、参数约定接口、拒收裁决（含连续超温区间证据与最早失效时刻）、
数据不合法 (422)，以及**未启用 / 启用核心温度复核**两类审计 API。
任何断言失败即以非零退出码结束容器。
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

# 短时冲高：箱温连续暴露不足 3600s（箱体放行）；核心上限 7℃ 时样品越限（核心拒收）
CORE_BOX_PASS_CORE_REJECT_PAYLOAD = {
    "records": [
        {"time": 0, "box_temp": 4.0, "ambient_temp": 4.0, "lid_open": False},
        {"time": 600, "box_temp": 12.642411, "ambient_temp": 25.0, "lid_open": False},
        {"time": 1200, "box_temp": 20.0694, "ambient_temp": 25.0, "lid_open": False},
        {"time": 1800, "box_temp": 10.921607, "ambient_temp": 4.0, "lid_open": False},
    ],
    "parameters": {
        "tau_closed": 300,
        "tau_open": 90,
        "box_temp_limit": 8.0,
        "exposure_limit_seconds": 3600,
    },
    "core_review": {
        "enabled": True,
        "sample_initial_temp": 4.0,
        "tau_sample_seconds": 300,
        "core_temp_limit": 7.0,
    },
}

# 与拒收演示同一批记录：样品热惯性大、核心上限 8℃，核心同样越限
CORE_REJECT_PAYLOAD = {
    "records": REJECT_PAYLOAD["records"],
    "parameters": REJECT_PAYLOAD["parameters"],
    "core_review": {
        "enabled": True,
        "sample_initial_temp": 4.0,
        "tau_sample_seconds": 900,
        "core_temp_limit": 8.0,
    },
}

# 含 NaN 的 JSON 必须被字段级拒绝（Python json 允许 NaN，需原样发送）
CORE_BAD_JSON = """{
  "records": [
    {"time": 0, "box_temp": 4.0, "ambient_temp": 5.0, "lid_open": false},
    {"time": 1, "box_temp": 4.0, "ambient_temp": 5.0, "lid_open": false},
    {"time": 2, "box_temp": 4.0, "ambient_temp": 5.0, "lid_open": false},
    {"time": 3, "box_temp": 4.0, "ambient_temp": 5.0, "lid_open": false}
  ],
  "parameters": {"tau_closed": 300, "tau_open": 90, "box_temp_limit": 8, "exposure_limit_seconds": 600},
  "core_review": {"enabled": true, "sample_initial_temp": NaN, "tau_sample_seconds": 300, "core_temp_limit": 8}
}"""


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
        check("core_review" in r.json(), "schema 含核心温度复核 core_review 约定")

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

        # ---------- 核心温度复核：未启用（原请求、结论与证据保持不变） ----------
        print("[核心复核 · 未启用]")
        r = c.post("/api/audit", json=REJECT_PAYLOAD)
        body = r.json()
        check("core_review" not in body and "final_status" not in body, "未启用时响应不含 core_review/final_status")
        check("core_temp" not in body["curve"][0], "未启用时曲线不含 core_temp")

        # ---------- 核心温度复核：启用 ----------
        print("[核心复核 · 启用]")
        r = c.post("/api/audit", json=CORE_REJECT_PAYLOAD)
        check(r.status_code == 200, f"启用复核 HTTP 200（实际 {r.status_code}）")
        body = r.json()
        cr = body.get("core_review")
        check(isinstance(cr, dict), "返回 core_review 证据块")
        check(cr.get("enabled") is True, "core_review.enabled 回显为 true")
        check(cr.get("status") == "reject" and cr.get("verdict") == "核心拒收", "核心越限判为 reject/核心拒收")
        check(cr.get("first_risk_time") is not None, "给出最早核心风险时刻")
        check(len(cr.get("segments", [])) == len(REJECT_PAYLOAD["records"]) - 1, "逐段返回核心温度起止状态")
        # 跨记录连续传递：相邻段段末/段初核心温一致，不重新锚定
        segs = cr["segments"]
        check(
            all(abs(a["core_temp_end"] - b["core_temp_start"]) < 1e-9 for a, b in zip(segs, segs[1:])),
            "核心温度跨记录连续传递（无逐记录重新锚定）",
        )
        check(all("core_temp" in p for p in body["curve"]), "曲线上可叠加核心温度采样")
        first_up = min(
            x["elapsed_seconds"]
            for s in segs
            for x in s["crossings"]
            if x["direction"] == "up"
        )
        check(
            abs(cr["first_risk_time"]["elapsed_seconds"] - first_up) < 1e-6,
            "最早风险时刻等于首个核心上穿阈值时刻",
        )
        check(body.get("final_status") in {"pass", "reject"}, "给出最终结论 final_status")

        # 箱体放行但核心拒收：两类结论必须区分
        r = c.post("/api/audit", json=CORE_BOX_PASS_CORE_REJECT_PAYLOAD)
        body = r.json()
        check(r.status_code == 200, "箱体放行/核心拒收场景 HTTP 200")
        check(body.get("box_status") == "pass", "箱体裁决为放行")
        check(body["core_review"]["status"] == "reject", "核心裁决为拒收")
        check(body.get("final_status") == "reject", "最终结论为拒收")
        check("箱体放行但核心拒收" in body.get("final_verdict", ""), "最终结论文案区分箱体放行但核心拒收")

        # 字段级错误：非法/无穷参数
        r = c.post(
            "/api/audit",
            content=CORE_BAD_JSON,
            headers={"content-type": "application/json"},
        )
        check(r.status_code == 422, "样品温度为 NaN 判为 422")
        err = r.json()["errors"][0]
        check(err.get("field") == "core_review.sample_initial_temp", "NaN 给出字段级错误 core_review.sample_initial_temp")

        bad_tau = dict(CORE_REJECT_PAYLOAD)
        bad_tau["core_review"] = {
            "enabled": True,
            "sample_initial_temp": 4.0,
            "tau_sample_seconds": 0,
            "core_temp_limit": 8.0,
        }
        r = c.post("/api/audit", json=bad_tau)
        check(r.status_code == 422, "样品热惯性为 0 判为 422")
        check(
            r.json()["errors"][0]["field"] == "core_review.tau_sample_seconds",
            "热惯性非法给出字段级错误 core_review.tau_sample_seconds",
        )

    print("冒烟全部通过。")


if __name__ == "__main__":
    main()
