#!/bin/bash
# 山河回响 (mountainriverechoes) 停止器
# 优先走应用自带的 /api/shutdown, 失败则按 PID / 端口兜底清理。
set -u

PORT='8766'
URL="http://127.0.0.1:${PORT}"
RUNTIME_DIR="${HOME}/Library/Application Support/MountainRiverEchoes"
PID_FILE="${RUNTIME_DIR}/server.pid"

# 健康探测: 一律绕过代理, 避免本机 7897 死代理造成误判
up() { curl --noproxy '*' -s -o /dev/null -m 1 "${URL}/" 2>/dev/null; }

# 等服务下线, 最多 10 秒
wait_down() {
  for _ in $(seq 1 20); do
    up || return 0
    sleep 0.5
  done
  return 1
}

# 1) 应用自带的优雅退出接口 (内部 1 秒后 os._exit)
curl --noproxy '*' -s -o /dev/null -m 3 -X POST "${URL}/api/shutdown" 2>/dev/null

if ! wait_down; then
  # 2) 按 PID 强杀
  PID="$(cat "${PID_FILE}" 2>/dev/null)"
  if [ -n "${PID}" ] && kill -0 "${PID}" 2>/dev/null; then
    kill "${PID}" 2>/dev/null
    wait_down || kill -9 "${PID}" 2>/dev/null
    wait_down
  fi
fi

if up; then
  # 3) 最后兜底: 按监听端口清理
  PIDS="$(lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN -t 2>/dev/null)"
  if [ -n "${PIDS}" ]; then
    echo "${PIDS}" | xargs kill 2>/dev/null
    wait_down
  fi
fi

rm -f "${PID_FILE}"

if up; then
  echo "山河回响: 未能停止（端口 ${PORT} 仍被占用）"
  exit 1
else
  echo "山河回响: 已停止"
  exit 0
fi
