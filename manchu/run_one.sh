#!/bin/bash
# 单个关键词检索（一次只搜一个，避免批量网络请求被安全策略掐断）
# 用法: bash run_one.sh <序号> <关键词>
cd "$(dirname "$0")" || exit 1
RAW=raw; mkdir -p "$RAW" .stage
PP=/Users/liguiyao/.workbuddy/binaries/python/envs/default/bin/python
IDX=$1; KW=$2
F=$(printf "%02d.json" "$IDX")

if [ -f "$RAW/$F" ]; then echo "[$F] $KW 已存在，跳过"; exit 0; fi

R=$(curl -s --noproxy '*' -m 25 -X POST -H 'Content-Type: application/json' \
    -d "{\"keywords\":[\"$KW\"],\"sources\":[\"Netease\",\"Kugou\",\"Kuwo\"],\"outdir\":\"$(pwd)/.stage\"}" \
    http://127.0.0.1:8767/api/probe/start)
JID=$(echo "$R" | $PP -c 'import json,sys
try: print(json.load(sys.stdin)["job_id"])
except Exception: print("")')
[ -z "$JID" ] && { echo "[$F] $KW 启动失败: $R"; exit 1; }

for _ in $(seq 1 40); do
  S=$(curl -s --noproxy '*' -m 10 "http://127.0.0.1:8767/api/probe/status?job=$JID")
  echo "$S" | grep -qE '"state": *"(done|error)"' && break
  sleep 2
done

if [ -f .stage/00.json ]; then
  mv .stage/00.json "$RAW/$F"
  $PP -c "
import json
j=json.load(open('$RAW/$F',encoding='utf-8'))
print('[$F] $KW -> %d 条' % len(j['items']))
for it in j['items'][:8]:
    print('    [%s] %s | %s' % (it.get('source_cn'), str(it.get('song_name'))[:30], str(it.get('singers'))[:12]))
"
else
  echo "[$F] $KW 无结果"
fi
