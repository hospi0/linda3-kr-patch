# -*- coding: utf-8 -*-
r"""«クリア条件» 그림 → «클리어조건» (2026-09-28)
  자원 = LINDA.MIC 0x1635E0 (머리 [풀린 0xE34][압축 0x2E2][44 44 0C 0C] + tools/linlz 스트림), 한 벌뿐
  풀린 데이터: +0x14 색표1(16색, 0=투명·5‥15 회색) · +0x34 색표2(1‥4 흰색) · +0x54 1층 136×24 4bpp(회색 그림자)
             · +0x6B4 2층 136×24 4bpp(흰 획) · 끝에 그림 설명(136×24 @0x54, 32×8 @0xD14)
  원본 글자: 5칸(가운데 x≈12·38·67·95·122), 4‥18행, 흰 획 + 왼쪽·아래 회색 그림자(두 층은 안 겹침)
  한글: 갈무리14(12×14) 흰 획(2층, 위→아래 4‥2) + 왼쪽 아래 1px 그림자(1층, 회색 9‥12)
  python tools/joken.py [--write]  → 시안 my files/그래픽/클리어조건_시안.png · --write: work/kr/LINDA.MIC 에 반영
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, r'C:\claude\project\anearth-kr-patch\tools')
import bdf, linlz
from PIL import Image
RES, W, H = 0x1635E0, 136, 24
L1, L2 = 0x54, 0x6B4
CENTERS = [12, 39, 67, 95, 122]
TEXT = '클리어조건'
FONT = 'C:/claude/utils/font/Galmuri-v2.40.3/Galmuri14.bdf'


def px(buf, base, x, y):
    b = buf[base + y * 68 + x // 2]
    return (b >> 4) if x % 2 == 0 else b & 15


def setpx(buf, base, x, y, v):
    o = base + y * 68 + x // 2
    buf[o] = (buf[o] & 0x0F) | (v << 4) if x % 2 == 0 else (buf[o] & 0xF0) | v


def build(out):
    F = bdf.Font(FONT)
    g = [[0] * W for _ in range(H)]
    for ch, cx in zip(TEXT, CENTERS):
        pts, _ = F.draw(ch, 0, 0)
        x0 = min(p[0] for p in pts); x1 = max(p[0] for p in pts); y0 = min(p[1] for p in pts)
        dx = cx - (x1 - x0 + 1) // 2 - x0; dy = 4 - y0
        for x, y in pts:
            g[y + dy][x + dx] = 1
    d = bytearray(out)
    for base in (L1, L2):
        for y in range(H):
            for x in range(W):
                setpx(d, base, x, y, 0)
    for y in range(H):
        for x in range(W):
            if g[y][x]:
                setpx(d, L2, x, y, 4 if y < 9 else 3 if y < 14 else 2)
            elif (x + 1 < W and y - 1 >= 0 and g[y - 1][x + 1]) or (y - 1 >= 0 and g[y - 1][x]) or (x + 1 < W and g[y][x + 1]):
                setpx(d, L1, x, y, (9, 11, 10, 12)[(x + 2 * y) % 4])
    return bytes(d)


def render(buf, scale=5):
    import struct
    def pal(o):
        return [((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3) for c in struct.unpack_from('>16H', buf, o)]
    P1, P2 = pal(0x14), pal(0x34)
    im = Image.new('RGB', (W, H), (12, 12, 20))
    for x in range(W):                      # 화면의 빨간 선
        for y in (12, 13, 14):
            im.putpixel((x, y), (200, 0, 0) if y != 12 else (120, 0, 0))
    for y in range(H):
        for x in range(W):
            a, b = px(buf, L1, x, y), px(buf, L2, x, y)
            if a:
                im.putpixel((x, y), P1[a])
            if b:
                im.putpixel((x, y), P2[b])
    return im.resize((W * scale, H * scale), Image.NEAREST)


def apply(m):
    """m(LINDA.MIC bytearray) 에 한글 그림을 제자리로 넣는다(머리 그대로, 남는 자리 0)"""
    out, _ = linlz.decode(m, RES)
    enc = linlz.encode(build(out))
    room = int.from_bytes(m[RES + 4:RES + 8], 'little')
    assert len(enc) <= room, (len(enc), room)
    m[RES + 12:RES + 12 + room] = enc + bytes(room - len(enc))
    print('  MIC «クリア条件» 그림 → «%s» %d/%d B' % (TEXT, len(enc), room))


def main():
    m = bytearray(open(os.path.join(ROOT, 'work', 'disc', 'LINDA_LINDA.MIC'), 'rb').read())
    out, j = linlz.decode(m, RES)
    new = build(out)
    enc = linlz.encode(new)
    room = int.from_bytes(m[RES + 4:RES + 8], 'little')
    print('압축 %d B / 자리 %d B' % (len(enc), room))
    assert len(enc) <= room
    a, b = render(out), render(new)
    sheet = Image.new('RGB', (a.width, a.height * 2 + 10), (40, 40, 40))
    sheet.paste(a, (0, 0)); sheet.paste(b, (0, a.height + 10))
    dst = os.path.join(ROOT, 'my files', '그래픽'); os.makedirs(dst, exist_ok=True)
    sheet.save(os.path.join(dst, '클리어조건_시안.png'))
    print('시안 →', os.path.join(dst, '클리어조건_시안.png'))
    if '--write' in sys.argv:
        k = os.path.join(ROOT, 'work', 'kr', 'LINDA.MIC')
        km = bytearray(open(k, 'rb').read())
        km[RES + 12:RES + 12 + room] = enc + bytes(room - len(enc))
        open(k, 'wb').write(km)
        print('→', k)


if __name__ == '__main__':
    main()
