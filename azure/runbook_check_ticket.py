#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Azure Automation 定时 Runbook —— 自包含单文件版（纯标准库）。
每小时由 Automation 计划触发，检查 Puffing Billy 指定日期/车次余票，
可订即通过 WxPusher 微信推送。

密钥/参数来源（优先级从高到低）：
  1. Azure Automation 变量: WXPUSHER_SPT / TARGET_DATES / ROUTE_CODE
  2. 环境变量（本地测试用）
  3. 文件内默认值
"""

import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime

# -------- 默认参数（也可用 Automation 变量覆盖）--------
DEFAULT_TARGET_DATES = "29/08/2026"
DEFAULT_ROUTE_CODE = "BEL-LAK"
DEFAULT_ROUTE_NAME = "Belgrave to Lakeside"

BASE = "https://book.puffingbillyrailway.org.au/BookingProduct/AvailabilityBook/?"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def get_setting(name, default=""):
    """依次尝试 Automation 变量 -> 环境变量 -> 默认值。"""
    try:
        import automationassets  # 仅在 Azure Automation 沙箱内可用
        val = automationassets.get_automation_variable(name)
        if val:
            return str(val)
    except Exception:
        pass
    return os.getenv(name, default)


def http(url, data=None, headers=None, timeout=30):
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    if headers:
        h.update(headers)
    body = data.encode("utf-8") if isinstance(data, str) else data
    req = urllib.request.Request(url, data=body, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def fetch_oid_token():
    html = http(BASE)
    m = re.search(r'setCookie\(\s*"oidToken"\s*,\s*"([^"]+)"', html)
    if not m:
        raise RuntimeError("页面里找不到 oidToken（网站结构可能变了）")
    return m.group(1)


def fetch_availability(token):
    now = datetime.now().strftime("%Y-%m-%d, %H:%M:%S:000")
    url = BASE + "&updateAvailability&localtime=" + urllib.parse.quote(now)
    cookie = ("currentbrandWAFApplicationBookingProduct=PUFFING%20BILLY; "
              "oidToken=" + token)
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://book.puffingbillyrailway.org.au",
        "Referer": BASE, "Cookie": cookie,
    }
    raw = http(url, data="BookingCategory=1", headers=headers)
    if not raw or raw.strip() in ("", "[]"):
        raise RuntimeError("接口返回空（session 失效？）")
    return json.loads(raw).get("availability", [])


def evaluate_date(av_list, target_date, route_code):
    entry = next((x for x in av_list if x.get("date") == target_date), None)
    if entry is None:
        return {"date_status": "未上架", "route_status": "未上架", "bookable": False}
    date_status = entry.get("status", "?")
    details = entry.get("detailedAvailability") or []
    route = next((d for d in details
                  if str(d.get("code", "")).upper() == route_code.upper()), None)
    if route is not None:
        avail = str(route.get("available", "")).strip()
        return {"date_status": date_status, "route_status": avail or date_status,
                "bookable": avail.lower() == "available"}
    rs = "该线路无票(仅其他线路可订)" if date_status.lower() == "available" else date_status
    return {"date_status": date_status, "route_status": rs, "bookable": False}


def notify_wxpusher(spt, title, content_md, summary):
    payload = {"content": "## {}\n\n{}".format(title, content_md),
               "summary": summary[:100], "contentType": 3, "spt": spt}
    raw = http("https://wxpusher.zjiecode.com/api/send/message/simple-push",
               data=json.dumps(payload),
               headers={"Content-Type": "application/json"}, timeout=20)
    resp = json.loads(raw)
    return resp.get("code") == 1000, resp.get("msg", raw[:200])


def main():
    spt = get_setting("WXPUSHER_SPT", "").strip()
    targets = [d.strip() for d in
               get_setting("TARGET_DATES", DEFAULT_TARGET_DATES).split(",") if d.strip()]
    route = get_setting("ROUTE_CODE", DEFAULT_ROUTE_CODE).strip() or DEFAULT_ROUTE_CODE

    token = fetch_oid_token()
    av = fetch_availability(token)

    for target in targets:
        ev = evaluate_date(av, target, route)
        print("{} | route:{} | overall:{} | bookable:{}".format(
            target, ev["route_status"], ev["date_status"], ev["bookable"]))
        if ev["bookable"]:
            title = "🎉 有票了! {} {}".format(DEFAULT_ROUTE_NAME, target)
            sub = "{} 现在可订，快去抢!".format(target)
            lines = [
                "- 日期: **{}**".format(target),
                "- 车次: **{} ({})**".format(DEFAULT_ROUTE_NAME, route),
                "- 状态: **{}**".format(ev["route_status"]),
                "- 订票: [{}]({})".format(BASE, BASE),
                "",
                "_Azure 监控于 {} UTC 发出_".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M")),
            ]
            if spt:
                ok, info = notify_wxpusher(spt, title, "\n\n".join(lines), sub)
                print("WxPusher push:", "ok" if ok else "fail " + str(info))
            else:
                print("WARN: 未配置 WXPUSHER_SPT，跳过微信推送")
    print("done.")


if __name__ == "__main__":
    main()
