#!/usr/bin/env python3
"""生成桌面快捷方式图标 (1024x1024 PNG)。

本机没有 SVG 渲染器(rsvg/inkscape/chrome/qlmanage 都不可用), 因此用 Pillow
按 appicon.svg 的同一套几何数据重绘。做法是先按 SC 倍超采样, 最后 LANCZOS 缩回,
保证圆角与曲线边缘平滑。

用法:
    python make_icon.py                 # 默认: 山河回响 / 青蓝配色 -> appicon.png
    python make_icon.py manchu          # 满族音乐 / 绛金配色   -> appicon-manchu.png
输出:
    <对应 png>  (1024x1024, 带透明通道)
"""
import sys

from PIL import Image, ImageDraw, ImageChops

SC = 2                      # 超采样倍率
SZ = 1024                   # 逻辑画布尺寸
W = SZ * SC

BOX = (100, 100, 924, 924)  # macOS 应用图标标准内容区
RADIUS = 185                # 圆角半径

# 配色方案: (天空渐变, 远山, 中山, 近山, 江面, 日色)
PALETTES = {
    'shanhe': dict(
        SKY=[(0.00, (10, 36, 55)), (0.45, (20, 72, 92)), (1.00, (29, 110, 124))],
        RIDGE_BACK=[(0.0, (47, 129, 148)), (1.0, (35, 106, 124))],
        RIDGE_MID=[(0.0, (29, 90, 107)), (1.0, (22, 74, 89))],
        RIDGE_FRONT=[(0.0, (18, 60, 74)), (1.0, (12, 44, 56))],
        RIVER=[(0.0, (159, 224, 228)), (1.0, (62, 155, 168))],
        SUN=(247, 178, 103),
        OUT='appicon.png',
    ),
    # 满族: 绛红夜空 + 鎏金日, 与山河回响的青蓝形成区分
    'manchu': dict(
        SKY=[(0.00, (38, 14, 22)), (0.45, (78, 24, 32)), (1.00, (122, 44, 40))],
        RIDGE_BACK=[(0.0, (150, 74, 62)), (1.0, (120, 54, 50))],
        RIDGE_MID=[(0.0, (104, 44, 46)), (1.0, (84, 34, 40))],
        RIDGE_FRONT=[(0.0, (66, 24, 33)), (1.0, (44, 15, 24))],
        RIVER=[(0.0, (255, 226, 168)), (1.0, (203, 143, 76))],
        SUN=(255, 205, 112),
        OUT='appicon-manchu.png',
    ),
}

SUN_C = (700, 352)
SUN_R = 250
SUN_CORE_R = 92

RIDGE_BACK_PTS = [(100, 622), (262, 452), (372, 566), (520, 400), (648, 552),
                  (760, 470), (924, 630), (924, 800), (100, 800)]
RIDGE_MID_PTS = [(100, 700), (232, 566), (336, 660), (470, 520), (604, 664),
                 (716, 592), (924, 716), (924, 820), (100, 820)]
RIDGE_FRONT_PTS = [(100, 780), (214, 676), (330, 760), (452, 646), (586, 764),
                   (700, 700), (924, 796), (924, 860), (100, 860)]


# --- 基础工具 ---------------------------------------------------------------

def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def sample_stops(stops, t):
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        if p0 <= t <= p1:
            k = 0.0 if p1 == p0 else (t - p0) / (p1 - p0)
            return lerp(c0, c1, k)
    return stops[-1][1]


def cubic(p0, p1, p2, p3, n=72):
    pts = []
    for i in range(n + 1):
        t = i / n
        m = 1 - t
        x = m**3 * p0[0] + 3 * m * m * t * p1[0] + 3 * m * t * t * p2[0] + t**3 * p3[0]
        y = m**3 * p0[1] + 3 * m * m * t * p1[1] + 3 * m * t * t * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


def P(pts):
    return [(x * SC, y * SC) for x, y in pts]


def gradient(bbox, stops, size=(W, W)):
    """bbox 内自上而下的线性渐变 (对齐 SVG objectBoundingBox 语义)。"""
    x0, y0, x1, y1 = [v * SC for v in bbox]
    w, h = max(1, int(round(x1 - x0))), max(1, int(round(y1 - y0)))
    strip = Image.new('RGBA', (1, h), (0, 0, 0, 0))
    px = strip.load()
    for y in range(h):
        t = y / (h - 1) if h > 1 else 0.0
        px[0, y] = sample_stops(stops, t) + (255,)
    tile = strip.resize((w, h), Image.NEAREST)
    canvas = Image.new('RGBA', size, (0, 0, 0, 0))
    canvas.paste(tile, (int(round(x0)), int(round(y0))))
    return canvas


def poly(pts, stops, opacity=1.0):
    """多边形 + 自身 bbox 渐变填充, 返回整幅大小的图层。"""
    mask = Image.new('L', (W, W), 0)
    ImageDraw.Draw(mask).polygon(P(pts), fill=255)
    grad = gradient((min(p[0] for p in pts), min(p[1] for p in pts),
                     max(p[0] for p in pts), max(p[1] for p in pts)), stops)
    layer = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    layer.paste(grad, (0, 0), mask)
    if opacity < 1.0:
        a = layer.getchannel('A').point(lambda v: round(v * opacity))
        layer.putalpha(a)
    return layer


def stroke(pts, width, color, alpha, layer):
    d = ImageDraw.Draw(layer)
    wpx = max(1, int(round(width * SC)))
    d.line(P(pts), fill=color + (alpha,), width=wpx, joint='curve')
    r = wpx / 2
    for x, y in (pts[0], pts[-1]):
        cx, cy = x * SC, y * SC
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (alpha,))


# --- 绘制 -------------------------------------------------------------------

def render(pal):
    canvas = Image.new('RGBA', (W, W), (0, 0, 0, 0))

    # 天空
    canvas = Image.alpha_composite(canvas, gradient(BOX, pal['SKY']))

    # 日晕 + 太阳
    glow = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    steps = 150
    for i in range(steps, 0, -1):
        r = SUN_R * i / steps * SC
        cx, cy = SUN_C[0] * SC, SUN_C[1] * SC
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=pal['SUN'] + (round(255 * 0.0055),))
    canvas = Image.alpha_composite(canvas, glow)

    sun = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    r = SUN_CORE_R * SC
    cx, cy = SUN_C[0] * SC, SUN_C[1] * SC
    ImageDraw.Draw(sun).ellipse([cx - r, cy - r, cx + r, cy + r], fill=pal['SUN'] + (255,))
    canvas = Image.alpha_composite(canvas, sun)

    # 三层山峦
    canvas = Image.alpha_composite(canvas, poly(RIDGE_BACK_PTS, pal['RIDGE_BACK'], 0.62))
    canvas = Image.alpha_composite(canvas, poly(RIDGE_MID_PTS, pal['RIDGE_MID'], 0.88))
    canvas = Image.alpha_composite(canvas, poly(RIDGE_FRONT_PTS, pal['RIDGE_FRONT'], 1.0))

    # 江面 (顶部为三段贝塞尔)
    river_top = [(100, 812)]
    river_top += cubic((100, 812), (220, 786), (320, 838), (442, 816))[1:]
    river_top += cubic((442, 816), (566, 794), (660, 842), (786, 818))[1:]
    river_top += cubic((786, 818), (852, 806), (894, 812), (924, 818))[1:]
    river_poly = river_top + [(924, 924), (100, 924)]
    canvas = Image.alpha_composite(canvas, poly(river_poly, pal['RIVER'], 1.0))

    # 水波
    waves = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    stroke(cubic((188, 866), (262, 846), (334, 886), (408, 866)), 12, (255, 250, 236), 140, waves)
    stroke(cubic((520, 892), (594, 872), (666, 912), (740, 892)), 12, (255, 250, 236), 140, waves)
    stroke(cubic((300, 902), (356, 888), (412, 916), (468, 902)), 9, (255, 250, 236), 100, waves)
    canvas = Image.alpha_composite(canvas, waves)

    # 音符
    note = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    nd = ImageDraw.Draw(note)
    white = (255, 255, 255, 240)

    # 符头: 单独图层旋转 -20°
    rx, ry = 56 * SC, 43 * SC
    head = Image.new('RGBA', (rx * 2, ry * 2), (0, 0, 0, 0))
    ImageDraw.Draw(head).ellipse([0, 0, rx * 2 - 1, ry * 2 - 1], fill=white)
    head = head.rotate(20, resample=Image.BICUBIC, expand=True)
    note.paste(head, (int(322 * SC - head.width / 2), int(512 * SC - head.height / 2)), head)

    # 符干
    sx, sy, sw, sh = 366 * SC, 352 * SC, 17 * SC, 168 * SC
    nd.rounded_rectangle([sx, sy, sx + sw, sy + sh], radius=sw / 2, fill=white)

    # 符尾
    flag = cubic((373, 352), (424, 366), (450, 400), (448, 448))
    flag += cubic((448, 448), (436, 410), (412, 384), (373, 372))[1:]
    nd.polygon(P(flag), fill=white)

    canvas = Image.alpha_composite(canvas, note)

    # 内描边高光
    ImageDraw.Draw(canvas).rounded_rectangle(
        P([(BOX[0], BOX[1]), (BOX[2], BOX[3])]),
        radius=RADIUS * SC, outline=(255, 255, 255, 26), width=int(6 * SC),
    )

    # 圆角裁剪: 只收缩 alpha 通道, RGB 已正确
    mask = Image.new('L', (W, W), 0)
    ImageDraw.Draw(mask).rounded_rectangle(P([(BOX[0], BOX[1]), (BOX[2], BOX[3])]),
                                           radius=RADIUS * SC, fill=255)
    r_, g_, b_, a_ = canvas.split()
    canvas = Image.merge('RGBA', (r_, g_, b_, ImageChops.multiply(a_, mask)))

    return canvas.resize((SZ, SZ), Image.LANCZOS)


if __name__ == '__main__':
    name = sys.argv[1] if len(sys.argv) > 1 else 'shanhe'
    pal = PALETTES[name]
    out = render(pal)
    out.save(pal['OUT'])
    print('saved', pal['OUT'], out.size, out.mode)
