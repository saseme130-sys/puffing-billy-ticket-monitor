# Puffing Billy 余票监控 Bot 🚂

监控 Puffing Billy Railway 指定日期/车次的余票，**出票立刻微信通知**你去抢。

当前配置目标：**2026-08-29（8/29）· Belgrave → Lakeside（BEL-LAK）· 2 成人 + 1 儿童**
> 该日期目前是 **Sold out**，bot 会一直盯着，一旦有人退票/放票变为可订，马上通知。

---

## 一、工作原理

网站的余票其实来自一个后台 JSON 接口。bot 直接、轻量地查这个接口（不用一直开浏览器）：

1. 打开订票页，自动提取会话 token（`oidToken`）
2. 调用 `updateAvailability` 接口，拿到每天每条线路的状态
3. 找目标日期的 **BEL-LAK** 车次状态
4. 一旦从"无票"变为 **Available** → 发通知（微信 + Mac 弹窗 + 终端响铃）
5. 只在状态**跳变**时通知，不刷屏；可订时按设定间隔重复提醒防错过

状态含义：`Available`(可订) / `Sold out`(售罄) / `Not available`(不发车) / `Departed`(已发车)。

---

## 二、配置微信通知（PushPlus）

1. 手机微信扫码关注并登录 **PushPlus**：https://www.pushplus.plus
2. 在「一对一推送」页面复制你的 **token**
3. 打开本目录的 `config.json`，把 token 填进去：

```json
"notify": {
  "pushplus_token": "把你的token粘贴到这里",
  ...
}
```

4. 验证是否配好（会给你微信发一条测试消息）：

```bash
python3 monitor.py --test-push
```

> 不配 token 也能用——仍会有 **macOS 弹窗 + 终端响铃**，只是没有微信推送。

---

## 三、运行

```bash
# 前台运行（关掉终端就停）
python3 monitor.py

# 后台常驻运行（推荐，关终端也继续跑）
./run.sh
tail -f monitor.log     # 实时看日志
./stop.sh               # 停止

# 只查一次当前状态（测试）
python3 monitor.py --once
```

Mac 需装了 Python 3（系统自带）。**无需 pip 安装任何东西**。

---

## 四、config.json 说明

| 字段 | 含义 |
|---|---|
| `target_dates` | 要监控的日期，格式 `DD/MM/YYYY`，可填多个 |
| `route_code` | 车次代码。`BEL-LAK`=Belgrave→Lakeside；`BEL-GEM`=Belgrave→Gembrook |
| `poll_interval_seconds` | 轮询间隔（秒），默认 240=4分钟 |
| `jitter_seconds` | 随机抖动，避免规律请求（礼貌+防封） |
| `pushplus_token` | PushPlus 微信推送 token |
| `pushplus_topic` | （可选）群组推送 topic，一对一留空即可 |
| `macos_notification` | 是否弹 Mac 通知 |
| `terminal_bell` | 是否终端响铃 |
| `notify_on_first_seen` | 目标日期首次进入可售窗口时是否通知 |
| `renotify_available_every_minutes` | 有票时每隔多少分钟重复提醒一次 |

改完配置后重启 bot 生效。

---

## 五、注意事项

- **间隔别调太短**：默认 4 分钟已足够，过于频繁可能被网站限流或封 IP。抢票不差这几分钟。
- 接口只返回**今天起约 68 天**的窗口；更远的日期要等进入窗口才查得到（bot 会自动处理，标为"未上架"）。
- 收到通知后请**尽快手动去官网下单**：https://book.puffingbillyrailway.org.au/BookingProduct/AvailabilityBook/?
  （bot 只负责监控通知，不自动下单——自动占座属于另一层风险，需要你确认后再加。）
- 若网站改版导致取不到 token，日志会报错，届时告诉我我来适配。

---

## 文件清单

- `monitor.py` — 主程序
- `config.json` — 配置
- `run.sh` / `stop.sh` — 后台启动 / 停止
- `state.json` — 运行状态（自动生成，用于去重）
- `monitor.log` — 日志（自动生成）
