#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Puffing Billy Railway 余票监控 Bot
监控指定日期 / 车次的余票，出票即通过 Server酱(微信) + macOS 弹窗 + 终端响铃通知。

用法:
    python3 monitor.py            # 按 config.json 持续监控
    python3 monitor.py --once     # 只查一次(测试用)
    python3 monitor.py --test-push  # 发一条测试通知，验证远程通知是否配好

配置见 config.json。纯标准库，无需 pip install。
"""

import json
import os
import re
import sys
import time
import random
import ssl
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime

BASE = "https://book.puffingbillyrailway.org.au/BookingProduct/AvailabilityBook/?"
BOOKING_URL = "https://book.puffingbillyrailway.org.au/BookingProduct/AvailabilityBook/?"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PASSENGER_FARES = {
    "adult": "2867_2810",
    "child": "2867_2812",
}

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
STATE_PATH = os.path.join(HERE, "state.json")
LOG_PATH = os.path.join(HERE, "monitor.log")

_SSL_CTX = ssl.create_default_context()


# ----------------------------- 工具 -----------------------------
def log(msg):
    line = "[{}] {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    # 后台运行时 stdout 已被重定向到 monitor.log，若同时再写文件会导致每行重复。
    # 因此：交互式(tty)时打印到终端；文件始终只由本函数写一次（后台时不再 print）。
    if sys.stdout.isatty():
        print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception as e:
        log("读取 {} 失败: {}".format(path, e))
        return default


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log("写入 {} 失败: {}".format(path, e))


# ----------------------------- 抓取 -----------------------------
def http(url, data=None, headers=None, timeout=30):
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    if headers:
        h.update(headers)
    body = data.encode("utf-8") if isinstance(data, str) else data
    req = urllib.request.Request(url, data=body, headers=h)
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as r:
        return r.read().decode("utf-8", "ignore")


def fetch_oid_token():
    """GET 首页，从 HTML 里提取 oidToken。"""
    html = http(BASE)
    m = re.search(r'setCookie\(\s*"oidToken"\s*,\s*"([^"]+)"', html)
    if not m:
        raise RuntimeError("页面里找不到 oidToken（网站结构可能变了）")
    return m.group(1)


def _booking_post(token, action, data):
    """在同一个订票会话中调用指定 AJAX action。"""
    now = datetime.now().strftime("%Y-%m-%d, %H:%M:%S:000")
    url = BASE + "&{}&localtime=".format(action) + urllib.parse.quote(now)
    cookie = ("currentbrandWAFApplicationBookingProduct=PUFFING%20BILLY; "
              "oidToken=" + token)
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://book.puffingbillyrailway.org.au",
        "Referer": BASE,
        "Cookie": cookie,
    }
    return http(url, data=data, headers=headers)


def fetch_availability(token, passengers):
    """先设置乘客数量，再返回该组合实际可订的 availability 列表。"""
    unknown_types = set(passengers) - set(PASSENGER_FARES)
    if unknown_types:
        raise RuntimeError(
            "不支持的乘客类型: {}".format(", ".join(sorted(unknown_types))))

    updates = []
    for passenger_type, fare_id in PASSENGER_FARES.items():
        count = passengers.get(passenger_type, 0)
        if isinstance(count, bool) or not isinstance(count, int):
            raise RuntimeError("乘客数量无效: {}".format(passenger_type))
        if count < 0:
            raise RuntimeError("乘客数量无效: {}".format(passenger_type))
        updates.extend((passenger_type, fare_id) for _ in range(count))

    if not updates:
        raise RuntimeError("未配置有效乘客，拒绝使用空会话查询")

    for passenger_type, fare_id in updates:
        body = "&fare={}&roomtype=&increment=1".format(fare_id)
        raw = _booking_post(token, "updateBookingFareQty", body)
        try:
            response = json.loads(raw)
        except ValueError as e:
            raise RuntimeError(
                "设置乘客数量失败({}): {}".format(passenger_type, e))
        if response.get("result") != "OK":
            raise RuntimeError(
                "设置乘客数量失败({}): {}".format(
                    passenger_type,
                    response.get("message") or response.get("result"),
                ))

    raw = _booking_post(token, "updateAvailability", "BookingCategory=1")
    if not raw or raw.strip() in ("", "[]"):
        raise RuntimeError("接口返回空（session 失效？将重取 token）")
    obj = json.loads(raw)
    if obj.get("result") not in (None, "OK"):
        raise RuntimeError("接口 result={}".format(obj.get("result")))
    availability = obj.get("availability")
    if not isinstance(availability, list):
        raise RuntimeError("接口缺少有效 availability 列表")
    return availability


def evaluate_date(av_list, target_date, route_code):
    """
    返回目标日期的状态判定 dict:
      { in_window, date_status, route_status, bookable, raw }
    route_status/bookable 针对指定车次(route_code)。
    """
    entry = next((x for x in av_list if x.get("date") == target_date), None)
    if entry is None:
        return {"in_window": False, "date_status": "未上架",
                "route_status": "未上架", "bookable": False, "raw": None}

    date_status = entry.get("status", "?")
    details = entry.get("detailedAvailability") or []
    route = next((d for d in details
                  if str(d.get("code", "")).upper() == route_code.upper()), None)

    if route is not None:
        avail = str(route.get("available", "")).strip()
        bookable = avail.lower() == "available"
        route_status = avail or date_status
    else:
        # 该车次没出现在可订列表里 -> 该线路当天不可订。
        # 注意: 当日整体可能是 "Available"(因为别的线路有票, 如 BEL-GEM)，
        # 但我们的目标线路无票，必须明确区分，避免误报。
        bookable = False
        if date_status.lower() == "available":
            route_status = "该线路无票(仅其他线路可订)"
        else:
            route_status = date_status

    return {"in_window": True, "date_status": date_status,
            "route_status": route_status, "bookable": bookable, "raw": entry}


# ----------------------------- 通知 -----------------------------
def notify_serverchan(cfg, title, content_md):
    key = (cfg.get("notify", {}).get("serverchan_key") or "").strip()
    if not key:
        return None
    payload = urllib.parse.urlencode({
        "title": title[:100],
        "desp": content_md,
    })
    try:
        raw = http(
            "https://sctapi.ftqq.com/{}.send".format(key),
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
            timeout=20,
        )
        resp = json.loads(raw)
        ok = resp.get("code") == 0
        info = resp.get("message") or resp.get("msg") or raw[:200]
        return ok, info
    except Exception as e:
        return False, str(e)


def notify_wxpusher(cfg, title, content_md, summary):
    spt = (cfg.get("notify", {}).get("wxpusher_spt") or "").strip()
    if not spt:
        return None  # 未配置，跳过
    payload = {
        "content": "## {}\n\n{}".format(title, content_md),
        "summary": summary[:100],
        "contentType": 3,  # 3 = markdown
        "spt": spt,
    }
    try:
        raw = http("https://wxpusher.zjiecode.com/api/send/message/simple-push",
                   data=json.dumps(payload),
                   headers={"Content-Type": "application/json"}, timeout=20)
        resp = json.loads(raw)
        ok = resp.get("code") == 1000
        return ok, resp.get("msg", raw[:200])
    except Exception as e:
        return False, str(e)


def notify_pushplus(cfg, title, content_md):
    token = (cfg.get("notify", {}).get("pushplus_token") or "").strip()
    if not token:
        return False, "未配置 pushplus_token"
    payload = {
        "token": token,
        "title": title,
        "content": content_md,
        "template": "markdown",
    }
    topic = (cfg.get("notify", {}).get("pushplus_topic") or "").strip()
    if topic:
        payload["topic"] = topic
    try:
        raw = http("https://www.pushplus.plus/send",
                   data=json.dumps(payload),
                   headers={"Content-Type": "application/json"}, timeout=20)
        resp = json.loads(raw)
        ok = resp.get("code") == 200
        return ok, resp.get("msg", raw[:200])
    except Exception as e:
        return False, str(e)


def notify_macos(cfg, title, subtitle, text):
    if not cfg.get("notify", {}).get("macos_notification", True):
        return
    try:
        safe = lambda s: str(s).replace('"', "'")
        script = ('display notification "{}" with title "{}" subtitle "{}" sound name "Glass"'
                  .format(safe(text), safe(title), safe(subtitle)))
        subprocess.run(["osascript", "-e", script], timeout=10)
    except Exception as e:
        log("macOS 通知失败: {}".format(e))


def terminal_bell(cfg, times=5):
    if not cfg.get("notify", {}).get("terminal_bell", True):
        return
    try:
        sys.stdout.write("\a" * times)
        sys.stdout.flush()
    except Exception:
        pass


def send_all(cfg, title, subtitle, lines):
    content_md = "\n\n".join(lines)
    terminal_bell(cfg)
    notify_macos(cfg, title, subtitle, subtitle)

    serverchan = notify_serverchan(cfg, title, content_md)
    if serverchan is not None:
        ok, info = serverchan
        if ok:
            log("✅ Server酱微信推送成功")
            return True
        log("⚠️ Server酱推送失败: {}".format(info))

    wx = notify_wxpusher(cfg, title, content_md, subtitle)
    if wx is not None:
        ok, info = wx
        if ok:
            log("✅ WxPusher 微信推送成功")
            return True
        log("⚠️ WxPusher 未发送: {}".format(info))

    if (cfg.get("notify", {}).get("pushplus_token") or "").strip():
        ok, info = notify_pushplus(cfg, title, content_md)
        if ok:
            log("✅ PushPlus 微信推送成功")
            return True
        log("⚠️ PushPlus 未发送: {}".format(info))

    return False


# ----------------------------- 主循环 -----------------------------
def build_notice(target_date, ev, cfg, kind):
    p = cfg.get("passengers", {})
    pax = "{}成人 + {}儿童".format(p.get("adult", 0), p.get("child", 0))
    if kind == "bookable":
        title = "🎉 有票了! {} {}".format(cfg.get("route_name_hint", ""), target_date)
        sub = "{} 现在可订 ({})，快抢!".format(target_date, ev["route_status"])
    else:
        title = "ℹ️ 状态变化 {} {}".format(cfg.get("route_name_hint", ""), target_date)
        sub = "{} 状态: {}".format(target_date, ev["route_status"])
    lines = [
        "## {}".format(title),
        "- 日期: **{}**".format(target_date),
        "- 车次: **{} ({})**".format(cfg.get("route_name_hint", ""), cfg.get("route_code", "")),
        "- 车次状态: **{}**".format(ev["route_status"]),
        "- 当日整体: {}".format(ev["date_status"]),
        "- 乘客: {}".format(pax),
        "- 立即订票: [{}]({})".format(BOOKING_URL, BOOKING_URL),
        "",
        "_由 Puffing Billy 监控 bot 于 {} 发出_".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ]
    return title, sub, lines


def check_once(cfg, state, do_notify=True):
    token = fetch_oid_token()
    av = fetch_availability(token, cfg.get("passengers", {}))
    ncfg = cfg.get("notify", {})
    renotify_s = int(ncfg.get("renotify_available_every_minutes", 30)) * 60
    now_ts = time.time()

    for target in cfg.get("target_dates", []):
        ev = evaluate_date(av, target, cfg.get("route_code", "BEL-LAK"))
        key = target
        prev = state.get(key, {})
        prev_status = prev.get("route_status")
        prev_bookable = prev.get("bookable", False)
        last_notified = prev.get("last_notified_ts", 0)

        status_str = "{} | 车次:{} | 整体:{} | 可订:{}".format(
            target, ev["route_status"], ev["date_status"], ev["bookable"])
        log(status_str)

        should_notify = False
        kind = "status"
        if do_notify:
            if ev["bookable"]:
                # 新变可订，或距上次提醒超过间隔 -> 再提醒(防错过)
                if not prev_bookable or (now_ts - last_notified) >= renotify_s:
                    should_notify = True
                    kind = "bookable"
            elif ev["route_status"] != prev_status:
                # 状态跳变(如 未上架->Sold out，Sold out->Not available 等)
                first_seen = ev["in_window"] and not prev.get("in_window", False)
                if ev["route_status"] != prev_status and (
                        ncfg.get("notify_on_first_seen", True) or not first_seen):
                    should_notify = True
                    kind = "status"

        if should_notify:
            title, sub, lines = build_notice(target, ev, cfg, kind)
            send_all(cfg, title, sub, lines)
            prev["last_notified_ts"] = now_ts

        prev.update({
            "route_status": ev["route_status"],
            "date_status": ev["date_status"],
            "bookable": ev["bookable"],
            "in_window": ev["in_window"],
            "checked_ts": now_ts,
        })
        state[key] = prev

    save_json(STATE_PATH, state)
    return state


def apply_secret_overrides(cfg):
    """把密钥从环境变量 / 本地 secrets.local.json 覆盖进 cfg（这些都不进 git）。"""
    cfg.setdefault("notify", {})
    # 1) 本地 gitignore 的密钥文件（方便本地常驻运行）
    local = load_json(os.path.join(HERE, "secrets.local.json"), {})
    for k in ("serverchan_key", "wxpusher_spt",
              "pushplus_token", "pushplus_topic"):
        if local.get(k):
            cfg["notify"][k] = local[k]
    # 2) 环境变量优先级最高（云端/CI 用）
    if os.getenv("WXPUSHER_SPT", "").strip():
        cfg["notify"]["wxpusher_spt"] = os.getenv("WXPUSHER_SPT").strip()
    if os.getenv("PUSHPLUS_TOKEN", "").strip():
        cfg["notify"]["pushplus_token"] = os.getenv("PUSHPLUS_TOKEN").strip()
    if os.getenv("SERVERCHAN_KEY", "").strip():
        cfg["notify"]["serverchan_key"] = os.getenv("SERVERCHAN_KEY").strip()
    return cfg


def main():
    args = set(sys.argv[1:])
    cfg = load_json(CONFIG_PATH, None)
    if cfg is None:
        log("找不到 config.json，退出")
        sys.exit(1)
    cfg = apply_secret_overrides(cfg)

    if "--test-push" in args:
        log("发送测试通知...")
        send_all(cfg, "✅ 测试通知", "远程通知通道已配置",
                 ["## 这是一条来自 Puffing Billy 监控 bot 的测试消息",
                  "如果你在微信里看到它，说明通知配置成功。"])
        return

    state = load_json(STATE_PATH, {})

    if "--once" in args:
        try:
            check_once(cfg, state, do_notify="--no-notify" not in args)
        except Exception as e:
            log("查询失败: {}".format(e))
        return

    interval = int(cfg.get("poll_interval_seconds", 240))
    jitter = int(cfg.get("jitter_seconds", 90))
    log("=== Puffing Billy 监控启动 ===")
    log("目标: {} | 车次: {} | 间隔: {}s(±{}s)".format(
        cfg.get("target_dates"), cfg.get("route_code"), interval, jitter))
    remote_keys = ("serverchan_key", "wxpusher_spt", "pushplus_token")
    if not any((cfg.get("notify", {}).get(k) or "").strip()
               for k in remote_keys):
        log("⚠️ 尚未配置远程通知，微信不会推送（仍有 Mac 弹窗+响铃）。")

    fails = 0
    while True:
        try:
            check_once(cfg, state, do_notify=True)
            fails = 0
        except Exception as e:
            fails += 1
            log("第 {} 次查询出错: {}".format(fails, e))
        sleep_s = interval + random.randint(-jitter, jitter)
        # 连续失败时退避
        if fails:
            sleep_s = min(sleep_s * (1 + fails), 1800)
        sleep_s = max(30, int(sleep_s))
        time.sleep(sleep_s)


if __name__ == "__main__":
    main()
