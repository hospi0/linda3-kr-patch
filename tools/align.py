# -*- coding: utf-8 -*-
r"""PS1(_RIn) ↔ 새턴(SC_n) 동영상 시각 맞추기 (2026-09-27)
  두 영상을 15fps 40×24 흑백으로 풀어 프레임 차이가 가장 작은 어긋남(새턴 프레임 = PS1 프레임 − d)을 찾는다.
  SC_23 은 _RI03 의 38.9초(583프레임)부터와 맞춘다.
  → work/movie/align.tsv (새턴 PS1 어긋남프레임 평균차)
"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
FF = r'C:\claude\utils\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe'
W, H = 40, 24


def frames(path, fps=15):
    r = subprocess.run([FF, '-v', 'error', '-i', path, '-vf', 'fps=%d,scale=%d:%d' % (fps, W, H),
                        '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True, check=True)
    b = r.stdout; n = len(b) // (W * H)
    return [b[i * W * H:(i + 1) * W * H] for i in range(n)]


def diff(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def best(sat, ps, base=0, rng=20):
    res = []
    for dshift in range(-rng, rng + 1):
        tot = 0; n = 0
        for i in range(0, len(sat), 7):
            j = i + base + dshift
            if 0 <= j < len(ps):
                tot += diff(sat[i], ps[j]); n += 1
        if n > 20:
            res.append((tot / n, dshift))
    return min(res)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    out = []
    for n in list(range(2, 23)) + [23]:
        sat = os.path.join(ROOT, 'work', 'movie', 'mp4', 'SC_%02d.mp4' % n)
        ri = 3 if n == 23 else n
        ps = os.path.join(ROOT, 'work', 'movie', 'psx', 'mp4', '_RI%02d.mp4' % ri)
        fs, fp = frames(sat), frames(ps)
        base = 583 if n == 23 else 0
        e, dshift = best(fs, fp, base)
        out.append((n, ri, dshift + base, e))
        print('SC_%02d ↔ _RI%02d  PS1 프레임 = 새턴 프레임 + %d  (평균차 %.1f)  새턴 %d · PS1 %d 프레임' % (n, ri, dshift + base, e, len(fs), len(fp)))
    with open(os.path.join(ROOT, 'work', 'movie', 'align.tsv'), 'w', encoding='utf-8') as f:
        f.write('새턴\tPS1\t어긋남(PS1=새턴+d)\t평균차\n')
        for n, ri, dd, e in out:
            f.write('SC_%02d\t_RI%02d\t%d\t%.1f\n' % (n, ri, dd, e))


if __name__ == '__main__':
    main()
