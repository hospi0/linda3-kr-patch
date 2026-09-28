# -*- coding: utf-8 -*-
r"""LINDA.MIC 안 압축 자원 찾기(2026-09-28): 머리 [u32 LE 풀린 크기][u32 LE 압축 크기][매개변수 4B] + tools/linlz 스트림
  조건: 풀면 끝 표시에서 정확히 «풀린 크기»가 나오고, 쓴 바이트 ≤ 압축 크기 → work/micres.tsv (위치·풀린·압축·매개변수)
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import linlz


def scan(d):
    res = []
    for o in range(0, len(d) - 12, 2):
        u, p = struct.unpack_from('<II', d, o)
        if not (0x20 <= u <= 0x100000 and 8 <= p < u + 0x100 and p <= 0x80000):
            continue
        try:
            out, j = linlz.dec_block(d, o + 12, limit=u + 1)
        except IndexError:
            continue
        if len(out) == u and j - (o + 12) <= p:
            res.append((o, u, p, d[o + 8:o + 12].hex()))
    return res


if __name__ == '__main__':
    d = open(os.path.join(ROOT, 'work', 'disc', 'LINDA_LINDA.MIC'), 'rb').read()
    r = scan(d)
    with open(os.path.join(ROOT, 'work', 'micres.tsv'), 'w', encoding='utf-8') as f:
        for o, u, p, par in r:
            f.write('%X\t%X\t%X\t%s\n' % (o, u, p, par))
    print(len(r))
