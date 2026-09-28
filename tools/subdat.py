# -*- coding: utf-8 -*-
r"""PS1 영문패치 SUBTITLE.DAT → 동영상별 영문 자막 TSV (2026-09-27)
  적재 0x801D3800 · 문장(문단째 이어 저장, 00 끝, 4B 맞춤)
  시각 표 20B [u32 줄 주소][u16 0xFF00|줄 글자 수][u16 시작][u16 끝(프레임, 15=1초)][u16 x y x y][u16 0]
  동영상 색인(0x56F4‥) 12B [u32 id][u32 기록 수][u32 첫 기록 주소] × 20 = PS1 _RI02‥_RI21 순서(끝 시각이 영상 길이에 하나씩 맞음)
  한 줄 = 기록 하나 = 문단 안 [주소, 글자 수] 조각. 한 자막 여러 줄 = 시각 같은 기록 여럿(y 순)
  글자: 대문자 +0x41 · 소문자 +0x47 · 숫자 0x40+n · . , ! ? " ( ) : ' - = 34 35 36 37 38 39 3A 3B 3E 3F · 띄어쓰기 4C
  새턴 대응: SC_n ↔ _RIn, 단 _RI03 = SC_03(0‥38.9초) + SC_23(38.9초‥, 새턴 시각 = −38.9초)
  python tools/subdat.py → my files/tsv/linda3_동영상자막_영문.tsv
"""
import collections, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, 'work', 'movie', 'psx', 'SUBTITLE.DAT')
OUT = os.path.join(ROOT, 'my files', 'tsv', 'linda3_동영상자막_영문.tsv')
BASE = 0x801D3800
INDEX = 0x56F4
FPS = 15
SPLIT03 = 578 / 15                   # _RI03 안 SC_23 시작(초) — tools/align.py 프레임 대조(578프레임)
PUNCT = {0x34: '.', 0x35: ',', 0x36: '!', 0x37: '?', 0x38: '"', 0x39: '(', 0x3A: ')',
         0x3B: ':', 0x3E: "'", 0x3F: '-', 0x4C: ' ', 0xFF: '~'}


def char(c):
    if c <= 0x19:
        return chr(c + 0x41)
    if c <= 0x33:
        return chr(c + 0x47)
    if 0x40 <= c <= 0x49:
        return chr(c - 0x40 + 0x30)
    return PUNCT.get(c)


def text(d, a, n):
    out = []; unk = []
    for c in d[a:a + n]:
        ch = char(c)
        if ch is None:
            ch = '{%02X}' % c; unk.append(c)
        out.append(ch)
    return ''.join(out).strip(' '), unk


def load():
    d = open(SRC, 'rb').read()
    idx = []; o = INDEX
    while True:
        i, n, p = struct.unpack_from('<III', d, o)
        if not 0x80100000 <= p < 0x80300000:
            break
        idx.append((i, n, p)); o += 12
    assert len(idx) == 20
    rows = []; unk = collections.Counter()
    for m, (mid, n, p) in enumerate(idx):
        ri = m + 2                                          # _RI02‥_RI21
        recs = [struct.unpack_from('<IHHHHHHHH', d, p - BASE + 20 * k) for k in range(n)]
        groups = collections.OrderedDict()
        for r in recs:
            groups.setdefault((r[2], r[3]), []).append(r)
        for (a, b), rs in groups.items():
            rs = sorted(rs, key=lambda r: (r[5], r[0]))     # y 순
            lines = []
            for r in rs:
                t, u = text(d, r[0] - BASE, r[1] & 0xFF); lines.append(t); unk.update(u)
            s0, s1 = a / FPS, b / FPS
            sat = 'SC_%02d' % ri; ofs = 0.0
            if ri == 3 and s0 >= SPLIT03 - 0.05:
                sat = 'SC_23'; ofs = SPLIT03
            rows.append((sat, '_RI%02d' % ri, round(s0 - ofs, 2), round(s1 - ofs, 2), lines))
    order = {('SC_%02d' % k): k for k in range(1, 25)}
    rows.sort(key=lambda r: (order[r[0]], r[2]))
    return rows, unk


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rows, unk = load()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('ID\t새턴\tPS1\t시작초\t끝초\t영문\t한글\n')
        for k, (sat, ri, a, b, lines) in enumerate(rows):
            f.write('M%03d\t%s\t%s\t%.2f\t%.2f\t%s\t\n' % (k + 1, sat, ri, a, b, chr(92).join([''] * 0) or (chr(92) + 'n').join(lines)))
    per = collections.Counter(r[0] for r in rows)
    print('자막 %d개 → %s' % (len(rows), OUT))
    print(' '.join('%s:%d' % (k, per[k]) for k in sorted(per, key=lambda x: int(x[3:]))))
    print('모르는 글자 코드', dict(unk))


if __name__ == '__main__':
    main()
