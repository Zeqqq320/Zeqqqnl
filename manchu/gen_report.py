# -*- coding: utf-8 -*-
"""满族音乐曲库 · 变动统计报告生成
对比「变动前基线」与「当前曲库」, 统计增删、来源分布、时长分布, 输出 markdown。
用法: python3 gen_report.py
"""
import json, os, glob, time
from collections import Counter
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = '/Applications/满族音乐.app/Contents/Resources/app/webui/ethnos_cache/t03_满族音乐.json'
BACKUP_DIR = os.path.join(os.path.dirname(HERE), '曲库备份')

# 本轮人工核定的新增曲目分类
CATEGORY = {
    '满语版《八音波罗》': '满语民歌',
    '悠车调': '满语民歌',
    'Dancing Song 庆隆舞': '满族传统歌舞',
    '摇篮曲 (满语)': '满语民歌',
    'B6 摇篮曲 (满族)': '满族民歌采集',
    '满族口弦系列#满族': '满族器乐',
    '东北萨满神调': '萨满祭祀',
    '萨满神曲 (拉马走阵没怠慢)': '萨满祭祀',
    '萨满帮兵调': '萨满祭祀',
    '萨满鼓': '萨满祭祀',
    '满族摇篮曲 竖琴弹唱曲': '满族器乐',
    '祭天神歌': '萨满祭祀',
    '满族茉莉花': '满族民歌采集',
}


def norm(s):
    return ''.join(str(s or '').split()).lower()


def dur(t):
    try:
        return float(t.get('duration_s') or 0)
    except Exception:
        return 0.0


def fmt_mmss(s):
    s = int(round(s))
    return '%d:%02d' % (s // 60, s % 60)


def load(path):
    return json.load(open(path, encoding='utf-8'))


def stats(tracks):
    return {
        'n': len(tracks),
        'minutes': sum(dur(t) for t in tracks) / 60.0,
        'sources': Counter((t.get('source_cn') or t.get('source') or '未知') for t in tracks),
        'singers': Counter((t.get('singers') or '未知歌手') for t in tracks),
    }


def main():
    cur = load(LIB)
    baks = sorted(glob.glob(os.path.join(BACKUP_DIR, 't03_基线_*.json')))
    base = load(baks[0]) if baks else {'tracks': []}

    b_tracks, c_tracks = base.get('tracks', []), cur['tracks']
    b_keys = {(norm(t.get('song_name')), norm(t.get('singers'))) for t in b_tracks}
    c_keys = {(norm(t.get('song_name')), norm(t.get('singers'))) for t in c_tracks}

    added = [t for t in c_tracks if (norm(t.get('song_name')), norm(t.get('singers'))) not in b_keys]
    removed = [t for t in b_tracks if (norm(t.get('song_name')), norm(t.get('singers'))) not in c_keys]

    sb, sc = stats(b_tracks), stats(c_tracks)
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    L = []
    L.append('# 满族音乐曲库 · 变动总结报告')
    L.append('')
    L.append('> 生成时间：%s　｜　曲库：`t03_满族音乐.json`　｜　维护目录：`.workbuddy/曲库维护`' % now)
    L.append('')

    L.append('## 一、变动概览')
    L.append('')
    L.append('| 指标 | 变动前 | 变动后 | 变化 |')
    L.append('| --- | --- | --- | --- |')
    L.append('| 曲目总数 | %d 首 | %d 首 | **+%d** |' % (sb['n'], sc['n'], sc['n'] - sb['n']))
    L.append('| 删除曲目 | — | — | %d |' % len(removed))
    L.append('| 总时长 | %.1f 分钟 | %.1f 分钟 | %+.1f 分钟 |'
             % (sb['minutes'], sc['minutes'], sc['minutes'] - sb['minutes']))
    L.append('| 涉及歌手 | %d 位 | %d 位 | %+d |'
             % (len(sb['singers']), len(sc['singers']), len(sc['singers']) - len(sb['singers'])))
    L.append('| 接入音源 | %d 个 | %d 个 | %+d |'
             % (len(sb['sources']), len(sc['sources']), len(sc['sources']) - len(sb['sources'])))
    L.append('')

    L.append('## 二、新增曲目明细（%d 首）' % len(added))
    L.append('')
    L.append('| # | 曲名 | 歌手 | 音源 | 时长 | 分类 |')
    L.append('| --- | --- | --- | --- | --- | --- |')
    for i, t in enumerate(added, 1):
        nm = t.get('song_name') or '未知曲目'
        L.append('| %d | %s | %s | %s | %s | %s |' % (
            i, nm, t.get('singers') or '未知歌手',
            t.get('source_cn') or t.get('source') or '未知',
            fmt_mmss(dur(t)), CATEGORY.get(nm, '满族音乐')))
    L.append('')

    if removed:
        L.append('## 三、删除曲目明细（%d 首）' % len(removed))
        L.append('')
        for t in removed:
            L.append('- %s — %s' % (t.get('song_name'), t.get('singers')))
        L.append('')
    else:
        L.append('## 三、删除曲目')
        L.append('')
        L.append('本轮为**纯增量维护**，未删除任何既有曲目。')
        L.append('')

    L.append('## 四、音源分布前后对比')
    L.append('')
    allsrc = sorted(set(sb['sources']) | set(sc['sources']),
                    key=lambda k: -sc['sources'].get(k, 0))
    L.append('| 音源 | 变动前 | 变动后 | 变化 |')
    L.append('| --- | --- | --- | --- |')
    for s in allsrc:
        a, b = sb['sources'].get(s, 0), sc['sources'].get(s, 0)
        L.append('| %s | %d | %d | %+d |' % (s, a, b, b - a))
    L.append('')

    L.append('## 五、新增曲目的分类构成')
    L.append('')
    cat = Counter(CATEGORY.get(t.get('song_name'), '满族音乐') for t in added)
    for k, v in cat.most_common():
        L.append('- %s：%d 首' % (k, v))
    L.append('')

    L.append('## 六、筛选原则（本轮剔除说明）')
    L.append('')
    L.append('本轮共检索候选 406 条，最终只采纳 13 条。剔除的主要原因：')
    L.append('')
    L.append('| 剔除类型 | 典型例子 | 原因 |')
    L.append('| --- | --- | --- |')
    L.append('| 同名现代乐队 | 萨满（Saman）与听潮阁合作的《剜心》《沉溺》等 | 是网络流行歌手/乐队，与满族萨满文化无关 |')
    L.append('| 通用民族风歌曲 | 《青藏高原》《卓玛》《鸿雁》《套马杆》 | 藏族/蒙古族歌曲，非满族 |')
    L.append('| 主旋律创作歌 | 《满族儿女心向党》《满族儿女爱中华》 | 八音赫赫演唱但属主旋律创作，非满族传统音乐 |')
    L.append('| 宗教咒语 | 《六字真言颂（满语）》 | 满语演唱的藏传佛教咒语，非满族音乐 |')
    L.append('| 同名异族曲艺 | 《八角鼓（白族）》 | 八角鼓条目指向白族，非满族八角鼓 |')
    L.append('| 网络翻唱/电台 | 沈利海燃·宝贝系列、浙江音乐台节目 | UGC 翻唱与电台录音，不入曲库 |')
    L.append('| 无效数据 | 雷佳《摇篮曲》咪咕条目（时长 0） | 时长缺失，无法播放 |')
    L.append('')

    L.append('## 七、歌手维度前后对比（TOP 10）')
    L.append('')
    L.append('| 歌手 | 变动前 | 变动后 |')
    L.append('| --- | --- | --- |')
    for s, v in sc['singers'].most_common(10):
        L.append('| %s | %d | %d |' % (s, sb['singers'].get(s, 0), v))
    L.append('')

    L.append('## 八、维护方式')
    L.append('')
    L.append('曲库文件：`/Applications/满族音乐.app/Contents/Resources/app/webui/ethnos_cache/t03_满族音乐.json`')
    L.append('')
    L.append('| 操作 | 命令 |')
    L.append('| --- | --- |')
    L.append('| 检索候选 | `bash 曲库维护/run_one.sh <序号> "<关键词>"` |')
    L.append('| 预览新增 | `python3 曲库维护/add_tracks.py --dry-run` |')
    L.append('| 写入新增 | `python3 曲库维护/add_tracks.py` |')
    L.append('| 生成报告 | `python3 曲库维护/gen_report.py` |')
    L.append('')
    L.append('新增曲目须先写入 `add_tracks.py` 的 `SELECTED` 清单（曲名关键字 / 歌手关键字 / 音源），')
    L.append('脚本会自动去重，已存在的曲目跳过，写入前自动备份到 `曲库备份/`。')
    L.append('')

    L.append('## 九、数据健康提示')
    L.append('')
    L.append('- 曲库条目保存的是**抓取瞬间的 CDN 直链**，酷狗/酷我/咪咕等通常数小时至数天后失效。')
    L.append('- 失效后播放器会调用 `/api/resolve` 按「曲名 + 歌手 + 时长」重新联网搜索并换源续播，用户无感。')
    L.append('- 因此曲库文件无需频繁重建，条目元数据长期有效，链接由运行时自愈。')
    L.append('')

    out = os.path.join(os.path.dirname(HERE), '曲库变动报告.md')
    open(out, 'w', encoding='utf-8').write('\n'.join(L))
    print('报告已生成: %s' % out)
    print('  变动前 %d 首 -> 变动后 %d 首 (+%d)' % (sb['n'], sc['n'], len(added)))


if __name__ == '__main__':
    main()
