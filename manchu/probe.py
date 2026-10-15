# -*- coding: utf-8 -*-
"""满族音乐曲库 · 候选检索（小批量异步，避免一次性大量请求触发网络防护）
每批 2 个关键词，批间停顿；已产出 raw/NN.json 的关键词会跳过（可断点续跑）。
用法: python3 probe.py
"""
import json, os, sys, time, urllib.request

BASE = 'http://127.0.0.1:8767'
OUT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(OUT, 'raw')
os.makedirs(RAW, exist_ok=True)

# (索引, 关键词) —— 00 已完成
KEYWORDS = [
    '满语歌曲', '八音赫赫', '满族萨满', '满族古谣',
    '八角鼓 满族', '满族 庆隆舞', '满族 祭天', '满族 海东青',
    '满族 山神调', '满族 喜歌', '满族 民间小调', '满族 摇篮曲',
]
SOURCES = ['Netease', 'Kugou', 'Kuwo', 'Migu', 'QQ']
BATCH = 2


def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode('utf-8'))


def get(path):
    return json.loads(urllib.request.urlopen(BASE + path, timeout=30).read().decode('utf-8'))


def run_one(idx, kw, outdir):
    r = post('/api/probe/start', {'keywords': [kw], 'sources': SOURCES, 'outdir': outdir})
    jid = r['job_id']
    for _ in range(90):
        s = get('/api/probe/status?job=' + jid)
        if s['state'] in ('done', 'error'):
            break
        time.sleep(2)
    src = os.path.join(outdir, '00.json')
    dst = os.path.join(RAW, '%02d.json' % idx)
    if os.path.exists(src):
        os.replace(src, dst)
        j = json.load(open(dst, encoding='utf-8'))
        print('  [%02d] %-14s %d 条' % (idx, kw, len(j.get('items', []))), file=sys.stderr)
        return True
    print('  [%02d] %-14s 失败' % (idx, kw), file=sys.stderr)
    return False


stage = os.path.join(OUT, '.stage')
os.makedirs(stage, exist_ok=True)
for i, kw in enumerate(KEYWORDS, start=1):
    dst = os.path.join(RAW, '%02d.json' % i)
    if os.path.exists(dst):
        print('  [%02d] %-14s 已存在，跳过' % (i, kw), file=sys.stderr)
        continue
    run_one(i, kw, stage)
    time.sleep(3)

all_items = []
for fn in sorted(os.listdir(RAW)):
    if fn.endswith('.json'):
        all_items.extend(json.load(open(os.path.join(RAW, fn), encoding='utf-8')).get('items', []))
json.dump(all_items, open(os.path.join(OUT, 'candidates.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('候选项合计: %d' % len(all_items))
