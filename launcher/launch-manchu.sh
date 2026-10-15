#!/bin/bash
# 满族音乐 桌面启动器
# 复用山河回响的服务进程(幂等), 然后直接打开「满族音乐」专题曲库(t03)。
# 由桌面 App「满族音乐.app」调用, 也可在终端直接执行。
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/launch.sh" \
  'http://127.0.0.1:8766/#playlist?id=t03&platform=ethnos'
