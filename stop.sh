#!/bin/bash
# 停止后台监控 bot
pid=$(pgrep -f "monitor.py")
if [ -z "$pid" ]; then
  echo "没有在运行的监控进程。"
  exit 0
fi
kill $pid && echo "已停止 (PID=$pid)"
