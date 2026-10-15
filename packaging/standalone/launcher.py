#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""满族音乐 · 独立应用启动器

职责:
  1. 把可写数据重定向到 ~/Library/Application Support/满族音乐 (App 包内资源只读)
  2. 首次运行把随包携带的满族专题曲库播种到数据目录
  3. 选一个空闲端口, 把后端服务跑在本进程内 (进程即应用本身)
  4. 服务就绪后自动打开浏览器, 直接落在满族音乐歌单页

目录布局 (打包后):
  ＜App＞/Contents/Resources/
      app/         项目源码根 (webui/ + musicdl/)
      runtime/     便携 Python 运行时
      bin/         额外可执行文件 (yt-dlp)
  本文件位于 ＜App＞/Contents/Resources/app/packaging/standalone/launcher.py
"""
import os
import sys
import json
import socket
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

APP_NAME = '满族音乐'
TOPIC_KEY = 't03'
TOPIC_FILE = 't03_满族音乐.json'
PREFERRED_PORT = 8767          # 刻意避开山河回响的 8766, 两个应用可同时跑

RES_DIR = Path(__file__).resolve().parents[3]                 # -> Contents/Resources
APP_DIR = RES_DIR / 'app'                                     # 项目源码根
DATA_DIR = Path.home() / 'Library' / 'Application Support' / APP_NAME

PORT_FILE = DATA_DIR / 'server.port'
PID_FILE = DATA_DIR / 'server.pid'


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def seed_topic():
    """把随包的满族曲库复制到数据目录; 内容有变化时覆盖, 保证升级后数据是新的"""
    src = APP_DIR / 'webui' / 'ethnos_cache' / TOPIC_FILE
    if not src.exists():
        log(f'警告: 随包曲库缺失 {src}')
        return
    dst_dir = DATA_DIR / 'webui' / 'ethnos_cache'
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / TOPIC_FILE
    data = src.read_bytes()
    if not dst.exists() or dst.read_bytes() != data:
        dst.write_bytes(data)
        log(f'已播种曲库 {TOPIC_FILE} -> {dst} ({len(data)} 字节)')
    else:
        log(f'曲库已是最新 {dst}')


def pick_port():
    """优先用固定端口; 被占用时退回系统分配的空闲端口"""
    for candidate in (PREFERRED_PORT, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(('127.0.0.1', candidate))
            except OSError:
                continue
            return s.getsockname()[1]
    return 0


def _no_proxy_opener():
    """绕过系统/环境里的代理: 本地回环绝不该走代理(否则健康的服务会被误判)"""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def already_running():
    """已有实例在跑就返回它的端口, 否则 None。

    shell 入口(run.sh)里已有一次同样的判断, 这里再判一次是兜底:
    万一两次双击几乎同时到达, 两边都过了 shell 检查, 也不会起出第二个服务。
    """
    try:
        port = int(PORT_FILE.read_text(encoding='utf-8').strip())
        pid = int(PID_FILE.read_text(encoding='utf-8').strip())
    except Exception:
        return None
    try:
        os.kill(pid, 0)                      # 只探测存活, 不发信号
    except OSError:
        return None
    try:
        with _no_proxy_opener().open(f'http://127.0.0.1:{port}/api/topics', timeout=2) as resp:
            if resp.status == 200 and TOPIC_KEY.encode() in resp.read():
                return port
    except Exception:
        return None
    return None


def playlist_url(port):
    return f'http://127.0.0.1:{port}/#playlist?id={TOPIC_KEY}&platform=ethnos'


def wait_ready_and_open(port, url, timeout=90.0):
    opener = _no_proxy_opener()
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with opener.open(f'http://127.0.0.1:{port}/api/topics', timeout=2) as resp:
                if resp.status == 200:
                    log(f'服务就绪, 打开 {url}')
                    webbrowser.open(url)
                    return
        except Exception:
            pass
        time.sleep(0.5)
    log('警告: 等待服务就绪超时, 未自动打开浏览器')


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 单实例守卫: 已经在跑就只把页面调出来, 不再起第二个服务
    existing = already_running()
    if existing:
        log(f'已有实例在运行(端口 {existing}), 直接打开页面')
        webbrowser.open(playlist_url(existing))
        return

    seed_topic()

    # 必须在导入后端模块之前设好: 模块在导入期就会创建目录 / 读取这些常量
    os.environ['MRE_DATA_DIR'] = str(DATA_DIR)
    os.environ['MRE_ONLY_ETHNIC'] = ''            # 独立包只要满族专题, 不展示 56 个民族空壳
    port = pick_port()
    os.environ['MRE_HOST'] = '127.0.0.1'
    os.environ['MRE_PORT'] = str(port)

    # 让 yt-dlp 等外部二进制能被找到(B站音源解析用)
    bin_dir = RES_DIR / 'bin'
    if bin_dir.is_dir():
        os.environ['PATH'] = f'{bin_dir}{os.pathsep}{os.environ.get("PATH", "")}'

    sys.path.insert(0, str(APP_DIR))
    import webui.mountainriverechoes as mre

    PORT_FILE.write_text(str(port), encoding='utf-8')
    PID_FILE.write_text(str(os.getpid()), encoding='utf-8')
    log(f'{APP_NAME} 启动中: http://127.0.0.1:{port}  (数据目录 {DATA_DIR})')

    # 预热歌名索引(后台), 让首次搜歌不用等建索引 —— 与 __main__ 的行为一致
    threading.Timer(
        5.0, lambda: threading.Thread(target=mre._build_song_index, daemon=True).start()
    ).start()

    url = playlist_url(port)
    threading.Thread(target=wait_ready_and_open, args=(port, url), daemon=True).start()

    mre.app.run(host='127.0.0.1', port=port, threaded=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
