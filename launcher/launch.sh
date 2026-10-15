#!/bin/bash
# 山河回响 (mountainriverechoes) 启动器
# 幂等: 已在运行则直接打开浏览器; 否则后台拉起服务后再打开。
# 由桌面 App「山河回响.app」调用, 也可在终端直接执行。
set -u

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST='127.0.0.1'
PORT='8766'
URL="http://${HOST}:${PORT}"
# 可选: 第一个参数指定要打开的地址(如满族音乐专题深链); 缺省打开首页
OPEN_URL="${1:-${URL}}"

PY="${PROJECT_ROOT}/venv/bin/python"
ENTRY="${PROJECT_ROOT}/webui/mountainriverechoes.py"

RUNTIME_DIR="${HOME}/Library/Application Support/MountainRiverEchoes"
PID_FILE="${RUNTIME_DIR}/server.pid"
LOG_FILE="${RUNTIME_DIR}/server.log"
mkdir -p "${RUNTIME_DIR}"

# --- 工具函数 ---------------------------------------------------------------

# 健康探测: 一律绕过代理, 避免本机 7897 死代理造成误判
health() { curl --noproxy '*' -s -o /dev/null -m 2 "${URL}/" 2>/dev/null; }

pid_alive() {
  local p="${1:-}"
  [ -n "${p}" ] && kill -0 "${p}" 2>/dev/null
}

is_running() {
  if pid_alive "$(cat "${PID_FILE}" 2>/dev/null)"; then return 0; fi
  # 兜底: 端口已被监听(可能是上次未写 pid 的残留进程)也算在跑
  if lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then return 0; fi
  return 1
}

alert() {
  osascript -e "display dialog \"${1}\" buttons {\"好\"} default button 1 with icon caution with title \"山河回响\"" >/dev/null 2>&1
}

# --- 主流程 -----------------------------------------------------------------

if ! is_running; then
  if [ ! -x "${PY}" ]; then
    alert "找不到 Python 虚拟环境：\n${PY}\n\n请先在项目目录执行依赖安装。"
    exit 1
  fi

  echo "[launcher] $(date '+%F %T') starting server ..." >> "${LOG_FILE}"
  cd "${PROJECT_ROOT}" || exit 1

  # 清掉本机 7897 死代理; nohup + 重定向让服务脱离启动器独立存活
  env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u ALL_PROXY -u all_proxy \
    nohup "${PY}" "${ENTRY}" >> "${LOG_FILE}" 2>&1 &
  SERVER_PID=$!
  echo "${SERVER_PID}" > "${PID_FILE}"
  disown 2>/dev/null || true

  # 等待就绪, 最多 60 秒
  for _ in $(seq 1 120); do
    if health; then break; fi
    if ! pid_alive "${SERVER_PID}"; then
      alert "服务启动失败（进程已退出）。\n\n日志：\n${LOG_FILE}"
      exit 1
    fi
    sleep 0.5
  done
fi

if health; then
  open "${OPEN_URL}"
else
  alert "服务未能在 60 秒内就绪。\n\n请查看日志：\n${LOG_FILE}"
  exit 1
fi
