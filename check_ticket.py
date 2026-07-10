#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云端一次性检查脚本（供 GitHub Actions / Azure Functions 等定时环境调用）。

与常驻版 monitor.py 的区别：
  - 无状态：不读写 state.json（云端每次是全新容器）
  - 只在"目标车次可订"时推送微信；售罄/未上架时静默（打印日志即可）
  - 配置从环境变量读取，回落 config.json

环境变量：
  WXPUSHER_SPT     WxPusher 极简推送 token（必填才会推微信）
  PUSHPLUS_TOKEN   （可选）PushPlus token，作为备用
  TARGET_DATES     （可选）逗号分隔，如 "29/08/2026,30/08/2026"，覆盖 config.json
  ROUTE_CODE       （可选）如 "BEL-LAK"

退出码：0=正常(无论是否有票)；非0=查询/网络异常(便于 Actions 标红重试)
"""

import os
import sys

import monitor  # 复用抓取/解析/通知逻辑


def main():
    cfg = monitor.load_json(monitor.CONFIG_PATH, {}) or {}
    cfg.setdefault("notify", {})
    cfg = monitor.apply_secret_overrides(cfg)

    dates_env = os.getenv("TARGET_DATES", "").strip()
    if dates_env:
        cfg["target_dates"] = [d.strip() for d in dates_env.split(",") if d.strip()]
    route_env = os.getenv("ROUTE_CODE", "").strip()
    if route_env:
        cfg["route_code"] = route_env

    # 云端不弹 Mac 通知
    cfg["notify"]["macos_notification"] = False
    cfg["notify"]["terminal_bell"] = False

    if os.getenv("TEST_NOTIFICATION", "").strip().lower() == "true":
        delivered = monitor.send_all(
            cfg,
            "✅ 小火车监控测试",
            "Server酱微信通知通道",
            [
                "这是一条来自 Puffing Billy 余票监控的测试消息。",
                "收到此消息说明 Server酱通知通道工作正常。",
            ],
        )
        if delivered:
            print("测试通知发送成功。")
            return 0
        print("测试通知发送失败。")
        return 3

    targets = cfg.get("target_dates", [])
    route = cfg.get("route_code", "BEL-LAK")
    if not targets:
        print("未配置 target_dates，退出")
        return 1

    try:
        token = monitor.fetch_oid_token()
        av = monitor.fetch_availability(token)
    except Exception as e:
        print("查询失败: {}".format(e))
        return 2  # 让 Actions 标记失败，便于发现网站变动

    any_bookable = False
    delivery_failed = False
    for target in targets:
        ev = monitor.evaluate_date(av, target, route)
        print("{} | 车次:{} | 整体:{} | 可订:{}".format(
            target, ev["route_status"], ev["date_status"], ev["bookable"]))
        if ev["bookable"]:
            any_bookable = True
            title, sub, lines = monitor.build_notice(target, ev, cfg, "bookable")
            if not monitor.send_all(cfg, title, sub, lines):
                delivery_failed = True

    if not any_bookable:
        print("目标日期暂无可订票，本次静默。")
    if delivery_failed:
        print("目标车次可订，但所有通知渠道均发送失败。")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
