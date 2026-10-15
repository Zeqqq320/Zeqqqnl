#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 e09_满族 曲库里筛出真正的满族音乐, 并产出两样东西:

  1) 专题曲库  webui/ethnos_cache/t01_满族音乐.json
     供「山河回响」WebUI 的「专题」页 / #playlist 深链直接播放。
     刻意做成专题库(tNN)而不是覆盖 e09 民族库 —— 民族库有 ETHNOS_MIN_VIABLE=100
     的启动校验, 干净集仅 83 首会被判为「未构建」进而触发重建(噪声回来)。

  2) 人读清单  满族音乐/满族音乐清单.csv / .md / 剔除清单.csv

e09 库当初用关键词 ['满族民歌', '满族歌曲', '那英'] 构建, 所以混入三类噪声:
  1) 那英相关的演唱会直拍 / reaction / vlog(那英是满族, 但不是"满族音乐")
  2) 其他民族或通俗流行(科尔沁/蒙古/藏族/陕北…), 被搜索串带进来
  3) 完全非音乐(56 民族纪录片、社会话题回应、桃李杯舞蹈比赛)
判定以「满语 / 满族音乐语汇」为正面证据, 不靠"猜标题像不像民歌"。
"""
import csv
import json
import re
import time
from collections import Counter
from pathlib import Path

ROOT = Path('/Users/liguiyao/WorkBuddy/民族音乐/Zeqqqnl')
SRC = ROOT / 'webui/ethnos_cache/e09_满族.json'
CACHE_DIR = ROOT / 'webui/ethnos_cache'
OUT_DIR = ROOT.parent / '满族音乐'

TOPIC_KEY = 't03'   # t01=摩梭, t02=各民族祝酒歌 已被占用
TOPIC_NAME = '满族音乐'
TOPIC_PATH = CACHE_DIR / f'{TOPIC_KEY}_{TOPIC_NAME}.json'
TOPIC_KWS = ['满族民歌', '满语歌曲', '满洲传统音乐', '萨满音乐', '海东青', '额尔春', '庆隆舞']

# 满语 / 满族音乐专有语汇(正面证据)
KEEP_PAT = re.compile(
    r'满族|满语|满洲|满文|manju|manchu|tsing|'
    r'萨满|shaman|jaqdan|尼山|'
    r'海东青|xongkoro|额尔春|erecun|乌春|ucun|莽式|maksin|'
    r'庆隆舞|承德清音|清音燕乐|燕乐|宫廷音乐|清宫|'
    r'打猎歌|跑南海|mederi|悠车|摇篮曲|山神调|祭天|童谣|悠悠歌|喜歌|'
    r'乌布西奔|萨尔拉|鳇鱼贡|讷殷|望祭山|波布|苏克素护河|十二字头|'
    r'甩葱|那卡|赛音格格|gucu|gharghan|uksalara|juwerge|阿噶柏勒|乌日衮|'
    r'射箭之歌|祈福中华|枫叶红|乌拉街|白山黑水|旗人|女真|八旗|纽祜禄|'
    r'桃花红|发福生财|月牙五更|东北民歌|关东',
    re.I,
)

# 公认的满族音乐人 / 满族音乐合辑 / 满语演唱者
ARTIST_KEEP = {
    '阿克善', '八音赫赫', '雅鲁熙', '木东', 'ManjuKumun', '卡玛萨', 'Karmashsa',
    'Karmasisa', '滨海满族', '伊通满族艺术团', '熙敏科特', '瑞鸣音乐', '阿日图Artu',
    '叶筱希',
}

# 明确的非满族内容生产者 / 频道(硬噪声)
ARTIST_DROP = {
    'VV音乐局', '茴香醋饺子', '囤点馒头778', '梓鹿Zicky', '哈哈娱乐丫',
    '耀祖哥', '墨辰铭', 'Wukiwuki', '清北门之约', '华夏复兴社', '桂花之香',
    '小徐同学骂骂咧咧', '一颗狼星-许篮心', '元嘉东顾', '穷途末路的穷兔',
    '为什么舞蹈',
}

# 非音乐内容(视频/纪录片/社会话题), 按标题剔除
NONMUSIC_PAT = re.compile(
    r'reaction|vlog|演唱会|直拍|纪录片|探秘中华|个民族|回应|'
    r'桃李杯|群舞|舞蹈比赛|现场完整版|全程不间断',
    re.I,
)

# 通俗流行/其他民族金曲(歌手白名单之外的常见噪声歌手)
POP_ARTISTS = {
    '乌兰图雅', '乌兰图雅&云飞', '阿宝', '王二妮', '王二妮&云飞', '黄静美', '朱明瑛',
    '汤灿', '林小玥', '降央卓玛', '罗姣', '马美如', '林栖', '陈小涛', '林响', '古筝',
    '顿珠拉姆', '十二大美女', '崔京浩', '王可可', '李琼', '呼斯楞', '李娜', '亚东',
    '索朗扎西', '上官红燕', '徐千雅', '乌兰托娅', '韩红', '苏勒亚其其格', '容中尔甲',
    '次仁央宗', '徐泽（要不要买菜）', '阿鲁阿卓&泽旺多吉', '云飞', '王洛宾', '李谷一',
    '郭兰英', '刀郎', '央金兰泽', '王琪', '欣宝儿', '巴邓顿珠&自游诗', '何鹏&乌兰图雅',
    '赵真&杨雯梓', 'ANU', '扎西尼玛', '中央民族乐团', '纯音乐', '未知歌手', '宋祖英',
}


def classify(tracks):
    """返回 (kept, dropped); 元素为 (track_dict, reason)。"""
    kept, dropped = [], []
    for t in tracks:
        name = str(t.get('song_name') or '')
        singers = str(t.get('singers') or '')
        album = str(t.get('album') or '')
        blob = f'{name} {album}'
        artist_hit = [a for a in ARTIST_KEEP if a in singers]
        title_hit = KEEP_PAT.search(blob)
        hard_noise = [a for a in ARTIST_DROP if a in singers]
        nonmusic = NONMUSIC_PAT.search(name)
        is_pop = singers.strip() in POP_ARTISTS and not artist_hit

        # 判定优先级: 硬噪声 > 非音乐形态 > 满族正面证据 > 通俗流行 > 默认剔除
        # (正面证据必须压过 POP 名单: 「未知歌手 - 满族民歌 摇篮曲」是真曲目)
        if hard_noise:
            keep, reason = False, 'drop-artist'
        elif nonmusic:
            keep, reason = False, 'nonmusic'
        elif artist_hit:
            keep, reason = True, 'artist:' + artist_hit[0]
        elif title_hit:
            keep, reason = True, 'kw:' + title_hit.group(0)
        elif is_pop:
            keep, reason = False, 'pop'
        else:
            keep, reason = False, 'no-manchu-evidence'

        (kept if keep else dropped).append((t, reason))
    return kept, dropped


def build_topic(payload, kept):
    """按 _ethnos_payload 的 schema 拼一个专题库, 逐字段保留 _song(播放凭据)。"""
    tracks = []
    for t in kept:
        tracks.append({k: v for k, v in t.items() if k not in ('sid',)})
    cover = next((t.get('cover_url') for t in tracks if t.get('cover_url')), '')
    return {
        'v': 2,
        'partial': False,
        'name': TOPIC_NAME,
        'group': TOPIC_NAME,
        'key': TOPIC_KEY,
        'cover': cover,
        'count': len(tracks),
        'built_at': time.time(),
        'kws': TOPIC_KWS,
        'sources': payload.get('sources') or [],
        'tracks': tracks,
    }


def export_csv(path, rows, header):
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    if not OUT_DIR.exists():
        OUT_DIR.mkdir(parents=True)
    payload = json.loads(SRC.read_text(encoding='utf-8'))
    tracks = payload.get('tracks') or []
    kept, dropped = classify(tracks)

    print(f'原始 {len(tracks)} 首 -> 保留 {len(kept)} / 剔除 {len(dropped)}\n')
    print('=' * 96)
    print('【保留】')
    for i, (t, r) in enumerate(kept, 1):
        print(f'{i:3d} | {str(t.get("singers"))[:20]:<20} | {str(t.get("song_name"))[:62]:<62} | {r}')
    print('=' * 96)
    print('【剔除】')
    for i, (t, r) in enumerate(dropped, 1):
        print(f'{i:3d} | {str(t.get("singers"))[:20]:<20} | {str(t.get("song_name"))[:62]:<62} | {r}')

    # 1) 专题曲库
    topic = build_topic(payload, [t for t, _ in kept])
    TOPIC_PATH.write_text(json.dumps(topic, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'\n[专题曲库] {TOPIC_PATH}  ({topic["count"]} 首)')

    # 2) 人读清单
    export_csv(
        OUT_DIR / '满族音乐清单.csv',
        [[i, t.get('song_name'), t.get('singers'), t.get('album'), t.get('source_cn') or t.get('source'),
          t.get('duration'), r] for i, (t, r) in enumerate(kept, 1)],
        ['序号', '歌名', '歌手', '专辑', '音源', '时长', '入选依据'],
    )
    export_csv(
        OUT_DIR / '剔除清单.csv',
        [[i, t.get('song_name'), t.get('singers'), t.get('album'), t.get('source_cn') or t.get('source'),
          r] for i, (t, r) in enumerate(dropped, 1)],
        ['序号', '歌名', '歌手', '专辑', '音源', '剔除原因'],
    )

    by_artist = Counter(str(t.get('singers') or '未知歌手').split(',')[0].strip() for t, _ in kept)
    reason_cn = {'pop': '通俗/其他民族流行', 'drop-artist': '噪声频道', 'nonmusic': '非音乐(视频/纪录片/舞蹈)',
                 'no-manchu-evidence': '无满族语汇证据'}
    drop_stat = Counter(reason_cn.get(r, r) for _, r in dropped)

    md = ['# 满族音乐 · 筛选报告', '',
          f'- 源曲库：`webui/ethnos_cache/e09_满族.json`（{len(tracks)} 首，构建关键词 `满族民歌 / 满族歌曲 / 那英`）',
          f'- 筛选结果：**保留 {len(kept)} 首 / 剔除 {len(dropped)} 首**',
          f'- 专题曲库：`{TOPIC_PATH.name}`（山河回响 WebUI「专题」页）', '',
          '## 为什么会有这么多非满族内容', '',
          'e09 库的构建关键词里带着「那英」（她是满族），于是抓进来大量那英演唱会直拍、',
          'reaction、vlog；同时「满族民歌」这个串在各大音源上会连带召回其他民族的民歌与通俗流行。',
          '因此不能按"歌手像不像民歌"判断，只能以**满语/满族音乐专有语汇**作为正面证据。', '',
          '## 剔除原因分布', '']
    md += [f'- {k}：{v} 首' for k, v in drop_stat.most_common()]
    md += ['', '## 保留曲目', '', '| # | 歌名 | 歌手 | 专辑 | 音源 |', '| --- | --- | --- | --- | --- |']
    for i, (t, _) in enumerate(kept, 1):
        md.append(f'| {i} | {t.get("song_name") or ""} | {t.get("singers") or ""} | {t.get("album") or ""} | {t.get("source_cn") or t.get("source") or ""} |')
    md += ['', '## 主要演唱者/来源', '']
    md += [f'- {k}：{v} 首' for k, v in by_artist.most_common()]
    (OUT_DIR / '满族音乐清单.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(f'[人读清单] {OUT_DIR}/满族音乐清单.csv / .md / 剔除清单.csv')


if __name__ == '__main__':
    main()
