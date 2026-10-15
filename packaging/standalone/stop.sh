#!/bin/bash
# 满族音乐 · 停止服务
# 优先请求应用自带 /api/shutdown 优雅退出; 失败再按 PID 补刀
set -u
DATA="$HOME/Library/Application Support/满族音乐"
PORTFILE="$DATA/server.port"
PIDFILE="$DATA/server.pid"
LOCKDIR="$DATA/server.lock"

port=""; pid=""
[ -f "$PORTFILE" ] && port="$(cat "$PORTFILE" 2>/dev/null)"
[ -f "$PIDFILE" ] && pid="$(cat "$PIDFILE" 2>/dev/null)"
# 锁里存的是后端进程 PID(与 run.sh exec 前同一个 PID), 优先采用
[ -n "$(cat "$LOCKDIR/pid" 2>/dev/null)" ] && pid="$(cat "$LOCKDIR/pid" 2>/dev/null)"

if [ -z "$pid" ]; then
  echo "满族音乐: 未在运行"
  exit 0
fi

running=0
kill -0 "$pid" 2>/dev/null && running=1
if [ "$running" = 0 ]; then
  echo "满族音乐: 已停止"
  rm -f "$PORTFILE" "$PIDFILE"
  rm -rf "$LOCKDIR"
  exit 0
fi

if [ -n "$port" ]; then
  /usr/bin/curl -s --noproxy '*' -m 3 -X POST "http://127.0.0.1:${port}/api/shutdown" >/dev/null 2>&1
fi

for _ in 1 2 3 4 5 6 7 8 9 10; do
  kill -0 "$pid" 2>/dev/null || break
  sleep 0.5
done

if kill -0 "$pid" 2>/dev/null; then
  kill "$pid" 2>/dev/null
  sleep 1
  kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null
fi

rm -f "$PORTFILE" "$PIDFILE"
rm -rf "$LOCKDIR"
echo "满族音乐: 已停止 (pid $pid)"
