#!/bin/bash
# 后台启动监控 bot，日志写入 monitor.log
cd "$(dirname "$0")"
if pgrep -f "monitor.py" >/dev/null 2>&1; then
  echo "监控似乎已在运行。用 ./stop.sh 停止，或查看 monitor.log。"
  echo "当前进程：$(pgrep -fl monitor.py)"
  exit 0
fi
nohup python3 monitor.py >> monitor.log 2>&1 &
echo "已在后台启动，PID=$!"
echo "实时看日志：tail -f monitor.log"
