# -*- coding: utf-8 -*-
"""满族音乐曲库 · 新增曲目入库
从 raw/*.json 候选中按「人工核定清单」挑歌, 去重后写入 t03_满族音乐.json。
清单里的每一项都是人工确认过的满族/满语音乐; 现代同名乐队(如"萨满(Saman)")已剔除。

用法:
  python3 add_tracks.py --dry-run    # 只预览, 不写入
  python3 add_tracks.py              # 写入
"""
import json, os, sys, shutil, time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = '/Applications/满族音乐.app/Contents/Resources/app/webui/ethnos_cache/t03_满族音乐.json'
BACKUP_DIR = os.path.join(os.path.dirname(HERE), '曲库备份')

# 人工核定清单: (曲名关键字, 歌手关键字, 音源)
# 说明: 只收满族民歌/满语歌曲/满族萨满神调; 主旋律歌曲与同名流行乐队不收。
SELECTED = [
    # 满语民歌 / 满族传统曲目
    ('满语版《八音波罗》', '八音赫赫',           'Netease'),
    ('悠车调',            '八音赫赫',           'Netease'),
    ('庆隆舞',            '八音赫赫',           'Netease'),
    ('摇篮曲 (满语)',      '儿童歌曲',           'Kugou'),
    ('摇篮曲 (满族)',      '来自大山的声音',      'Kugou'),
    ('满族口弦',          '东北亚民族文化史',     'Kugou'),
    # 满族萨满祭祀音乐
    ('东北萨满神调',       '占彬',              'Kuwo'),
    ('萨满神曲',          '白老仙',             'Kuwo'),
    ('萨满帮兵调',         '占彬',              'Kuwo'),
    ('萨满鼓',            '道童张张',           'Kuwo'),
    # 满族器乐 / 古歌
    ('满族摇篮曲',         '褚楚',              'Migu'),
    ('祭天神歌',          '石忠多',             'Migu'),
    ('满族茉莉花',         '周德泽',             'Migu'),
]

SRC_CN = {'Netease': '网易云', 'Kugou': '酷狗', 'Kuwo': '酷我', 'Migu': '咪咕', 'QQ': 'QQ音乐'}


def norm(s):
    return ''.join(str(s or '').split()).lower()


def load_candidates():
    items = []
    raw = os.path.join(HERE, 'raw')
    for fn in sorted(os.listdir(raw)):
        if fn.endswith('.json'):
            items += json.load(open(os.path.join(raw, fn), encoding='utf-8')).get('items', [])
    return items


def pick(cands, name_kw, singer_kw, source):
    """在候选里找 (曲名包含关键字 且 歌手包含关键字 且 音源匹配) 的第一条"""
    for it in cands:
        if it.get('source_cn') != source:
            continue
        if name_kw not in str(it.get('song_name') or ''):
            continue
        if singer_kw and singer_kw not in str(it.get('singers') or ''):
            continue
        if not it.get('download_url'):
            continue
        return it
    return None


def make_track(it, source_cn):
    name = it.get('song_name') or '未知曲目'
    singer = it.get('singers') or '未知歌手'
    dur = it.get('duration_s') or 0
    try:
        dur = float(dur)
    except Exception:
        dur = 0.0
    song = {
        'source': source_cn + 'MusicClient',
        'root_source': None,
        'song_name': name,
        'singers': singer,
        'album': it.get('album'),
        'ext': (it.get('ext') or 'mp3'),
        'file_size_bytes': it.get('file_size_bytes'),
        'file_size': None,
        'duration_s': dur,
        'duration': None,
        'bitrate': None,
        'codec': None,
        'samplerate': None,
        'channels': None,
        'lyric': None,
        'cover_url': it.get('cover_url'),
        'episodes': None,
        'download_url': it.get('download_url'),
        'protocol': it.get('protocol') or 'HTTP',
        'identifier': it.get('identifier'),
    }
    return {
        'id': 'Ethnos#0',
        'song_name': name,
        'singers': singer,
        'album': it.get('album') or '',
        'ext': (str(it.get('ext') or 'mp3')).upper(),
        'file_size': '',
        'duration': '',
        'duration_s': dur,
        'bitrate': None,
        'cover_url': it.get('cover_url') or '',
        'lyric': False,
        'source': source_cn,
        'source_cn': SRC_CN.get(source_cn, source_cn),
        'previewable': True,
        'downloadable': True,
        'album_url': None,
        '_song': song,
    }


def main():
    dry = '--dry-run' in sys.argv
    lib = json.load(open(LIB, encoding='utf-8'))
    exist = {(norm(t.get('song_name')), norm(t.get('singers'))) for t in lib['tracks']}
    cands = load_candidates()
    print('候选项: %d    现有曲目: %d' % (len(cands), len(lib['tracks'])))

    added, skipped = [], []
    for name_kw, singer_kw, source in SELECTED:
        it = pick(cands, name_kw, singer_kw, source)
        if not it:
            skipped.append((name_kw, singer_kw, source, '候选里没找到'))
            continue
        key = (norm(it.get('song_name')), norm(it.get('singers')))
        if key in exist:
            skipped.append((name_kw, singer_kw, source, '曲库已有'))
            continue
        added.append(make_track(it, source))
        exist.add(key)

    print('\n将新增 %d 首:' % len(added))
    for t in added:
        print('  + [%s] %s — %s  (%.0fs)' % (t['source_cn'], t['song_name'], t['singers'], t['duration_s']))
    if skipped:
        print('\n跳过 %d 首:' % len(skipped))
        for n, s, src, why in skipped:
            print('  - %s / %s [%s] : %s' % (n, s, src, why))

    if dry or not added:
        print('\n(dry-run 或无新增, 未写入)')
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    bak = os.path.join(BACKUP_DIR, 't03_入库前_%s.json' % datetime.now().strftime('%Y%m%d_%H%M%S'))
    shutil.copy2(LIB, bak)
    print('\n已备份: %s' % bak)

    lib['tracks'] += added
    lib['count'] = len(lib['tracks'])
    lib['built_at'] = time.time()
    srcs = {t['source'] for t in lib['tracks']}
    lib['sources'] = sorted(srcs)
    json.dump(lib, open(LIB, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('写入完成: 曲库共 %d 首' % lib['count'])


if __name__ == '__main__':
    main()
