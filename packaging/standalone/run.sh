#!/bin/bash
# 满族音乐 · 独立应用入口
# 位置: ＜App＞/Contents/MacOS/launcher  (app bundle 的可执行文件)
# 职责: 用原子锁保证单实例 -> 已在跑就等就绪后开页面; 否则拉起内置运行时的后端服务
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
RES="$(cd "$HERE/../Resources" && pwd)"
DATA="$HOME/Library/Application Support/满族音乐"
PORTFILE="$DATA/server.port"
PIDFILE="$DATA/server.pid"
LOCKDIR="$DATA/server.lock"
LOG="$DATA/server.log"
URL_SUFFIX="/#playlist?id=t03&platform=ethnos"

mkdir -p "$DATA"

# 锁是原子操作(mkdir 成功者得锁)。持锁进程就是后端进程本身 ——
# run.sh 最后用 exec 顶替本 shell, PID 不变, 所以锁里的 $$ 始终等于服务进程 PID。
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  OWNER="$(cat "$LOCKDIR/pid" 2>/dev/null)"
  if [ -n "$OWNER" ] && kill -0 "$OWNER" 2>/dev/null; then
    # 已有实例: 等它把端口跑起来(冷启动可能十几秒), 再打开页面
    PORT=""
    for _ in $(seq 1 240); do
      kill -0 "$OWNER" 2>/dev/null || break
      PORT="$(cat "$PORTFILE" 2>/dev/null)"
      if [ -n "$PORT" ] && /usr/bin/curl -s --noproxy '*' -m 2 \
           "http://127.0.0.1:${PORT}/api/topics" 2>/dev/null | /usr/bin/grep -q 't03'; then
        break
      fi
      PORT=""
      sleep 0.5
    done
    if [ -n "$PORT" ]; then
      /usr/bin/open "http://127.0.0.1:${PORT}${URL_SUFFIX}"
    fi
    exit 0
  fi
  # 持锁进程已死 -> 陈旧锁, 清掉后重新抢
  rm -rf "$LOCKDIR"
  mkdir "$LOCKDIR" 2>/dev/null || exit 1
fi
echo $$ > "$LOCKDIR/pid"

PY="$RES/runtime/python/bin/python3"
[ -x "$PY" ] || { echo "内置运行时缺失: $PY" >> "$LOG"; exit 1; }

# 由 LaunchServices 拉起时环境是精简的, 强制 UTF-8 以免中文日志触发编码异常
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

# 关键: 禁止往 app bundle 里写 .pyc。
# app 是 ad-hoc 签名的, 一旦包内多出任何文件, 签名封印即失效,
# Gatekeeper 会判定"应用已损坏"并拒绝启动(实测: 首次运行后生成 96 个 .pyc 就打不开了)。
# 字节码缓存统一改写到可写的数据目录。
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX="$DATA/.pycache"

{
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') 启动 ====="
} >> "$LOG"

# exec: 让后端进程直接顶替本 shell, 保持与 app bundle 的进程归属关系(锁里的 PID 因此依旧有效)
exec "$PY" "$RES/app/packaging/standalone/launcher.py" >> "$LOG" 2>&1
