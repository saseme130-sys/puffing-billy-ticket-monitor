# Puffing Billy 余票监控 Bot 🚂

监控 Puffing Billy Railway 指定日期/车次的余票，**出票立刻微信通知**你去抢。

当前配置目标：**2026-08-29（8/29）· Belgrave → Lakeside（BEL-LAK）· 2 成人 + 1 儿童**
> 该日期目前是 **Sold out**，bot 会一直盯着，一旦有人退票/放票变为可订，马上通知。

---

## ⭐ 当前生效方案：云端 24/7（GitHub Actions + Server酱）

**不用一直开着电脑**，已部署到云端每小时自动查一次：

- 仓库：`saseme130-sys/puffing-billy-ticket-monitor`（个人号，Actions 免费）
- 定时：`.github/workflows/ticket_monitor.yml`，cron `0 * * * *`（每小时整点）
- 通知：**Server酱微信推送**
- 逻辑：`check_ticket.py` 无状态查询，**只有目标车次变为可订才推送微信**，售罄则静默

### 日常操作（在个人号仓库上）

命令统一加 `env -u GH_TOKEN` 前缀（本机默认 gh 账号是企业号，需绕过）：

```bash
# 手动立即查一次（无票时静默）
env -u GH_TOKEN gh workflow run ticket_monitor.yml
# 只测试微信通知，不查询余票
env -u GH_TOKEN gh workflow run ticket_monitor.yml -f test_notification=true
# 看最近运行
env -u GH_TOKEN gh run list --workflow=ticket_monitor.yml --limit 5

# 改监控日期 / 车次（改完下次运行即生效，无需改代码）
env -u GH_TOKEN gh variable set TARGET_DATES --body "29/08/2026"   # 多个用逗号分隔
env -u GH_TOKEN gh variable set ROUTE_CODE   --body "BEL-LAK"
# 更新 Server酱 SendKey（通过交互输入，避免出现在命令历史）
env -u GH_TOKEN gh secret set SERVERCHAN_KEY
```

- **改频率**：编辑 workflow 里的 `cron`（如 `0 */2 * * *`=每 2 小时）后 push。
- **暂停 / 恢复**：仓库 Actions 页面 Disable/Enable，或删掉 workflow 文件。
- ⚠️ GitHub 会在仓库 **60 天无活动**后自动停用定时任务；长期不动的话偶尔 push 一下即可。

> 下面的「本地运行」部分是备用方式（关电脑就停），云端方案已覆盖 24/7 需求，一般无需再本地跑，**避免两边同时跑导致重复通知**。

---

## 一、工作原理

网站的余票其实来自一个后台 JSON 接口。bot 直接、轻量地查这个接口（不用一直开浏览器）：

1. 打开订票页，自动提取会话 token（`oidToken`）
2. 在同一订票会话中设置 **2 成人 + 1 儿童**
3. 调用 `updateAvailability`，获取该乘客组合实际可订的日期和线路
4. 找目标日期的 **BEL-LAK** 车次状态
5. 只有完整 3 人组合变为 **Available** 才通知（微信 + Mac 弹窗 + 终端响铃）
6. 只在状态**跳变**时通知，不刷屏；可订时按设定间隔重复提醒防错过

> 不能直接使用未选择乘客时的概览状态：它可能显示 `Available`，但实际
> 选择 2 成人 + 1 儿童后仍是 `Sold out`。

状态含义：`Available`(可订) / `Sold out`(售罄) / `Not available`(不发车) / `Departed`(已发车)。

---

## 二、配置微信通知（Server酱）

云端使用仓库 Actions Secret `SERVERCHAN_KEY`，SendKey 不会进入公开代码。
本地运行时，把 SendKey 放在已被 `.gitignore` 忽略的 `secrets.local.json`：

```json
{
  "serverchan_key": "SCT_xxxxx"
}
```

本地测试：

```bash
python3 monitor.py --test-push
```

> 不配 SendKey 也能本地运行——仍会有 **macOS 弹窗 + 终端响铃**，只是没有微信推送。

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
| `passengers` | 精确校验的乘客数量；当前为 2 成人 + 1 儿童 |
| `poll_interval_seconds` | 轮询间隔（秒），默认 240=4分钟 |
| `jitter_seconds` | 随机抖动，避免规律请求（礼貌+防封） |
| `serverchan_key` | Server酱 SendKey；生产环境使用 GitHub Secret |
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
