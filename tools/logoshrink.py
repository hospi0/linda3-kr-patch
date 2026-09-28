# -*- coding: utf-8 -*-
r"""LOGO.CPK 영상 줄이기 (2026-09-28, 사용자 결정 «로고 동영상 줄여») — MIC 가 커질 자리를 만든다
  배치: MIC(늘어남) → SS_ASCII.CPK(FILM 1.06, 내용 그대로 뒤로) → LOGO.CPK(줄임) → SC_01.CPK(위치 불변)
  LOGO = FILM 1.09 · cinepak 320×224 · 15fps · 150프레임 · 키 구간 14 · 띠 2개 · 소리 PCM(그대로)
  키 구간마다 원본 프레임(ffmpeg passthrough)을 cinepak 으로 다시 굽되 q 를 올려 «원래 구간 × RATIO» 이하로.
  → work/kr/LOGO_small.CPK · 미리보기 work/movie/LOGO_small.mp4
  python tools/logoshrink.py [RATIO=0.35]
"""
import glob, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import filmcpk, opening_enc
FF = opening_enc.FF
SRC = os.path.join(ROOT, 'work', 'movie', 'cpk', 'LOGO.CPK')
DST = os.path.join(ROOT, 'work', 'kr', 'LOGO_small.CPK')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ratio = float(sys.argv[1]) if len(sys.argv) > 1 else 0.35
    opening_enc.STRIPS = 2
    fr = os.path.join(ROOT, 'work', 'movie', 'frames', 'logo')
    if not glob.glob(os.path.join(fr, 'f*.png')):
        os.makedirs(fr, exist_ok=True)
        subprocess.run([FF, '-v', 'error', '-y', '-i', SRC, '-fps_mode', 'passthrough', os.path.join(fr, 'f%04d.png')], check=True)
    film = filmcpk.read(open(SRC, 'rb').read())
    vid = [i for i, e in enumerate(film['stab']) if e[2] != 0xFFFFFFFF]
    key = [k for k, i in enumerate(vid) if not film['stab'][i][2] & 0x80000000]
    chunks = list(film['chunks']); infos = [e[2] for e in film['stab']]
    before = sum(len(chunks[i]) for i in vid)
    for a, b in zip(key, key[1:] + [len(vid)]):
        frames = [os.path.join(fr, 'f%04d.png' % (f + 1)) for f in range(a, b)]
        budget = sum(len(film['chunks'][vid[f]]) for f in range(a, b)) * ratio
        for q in (4, 6, 8, 12, 16, 20, 24, 31):
            new = opening_enc.encode(frames, q)
            if sum(map(len, new)) <= budget:
                break
        for f, c in zip(range(a, b), new):
            chunks[vid[f]] = c
            t = film['stab'][vid[f]][2] & 0x7FFFFFFF
            infos[vid[f]] = t if f == a else t | 0x80000000
        print('구간 %3d‥%3d  q %2d  %6d / 목표 %6d B' % (a + 1, b, q, sum(map(len, new)), budget))
    assert all(len(c) % 4 == 0 for c in chunks)
    data = filmcpk.write(film, chunks, infos)
    open(DST, 'wb').write(data)
    after = sum(len(chunks[i]) for i in vid)
    orig = os.path.getsize(SRC)
    print('영상 %d → %d B · 파일 %d → %d B (%d → %d 섹터, 줄어든 %d 섹터)' % (
        before, after, orig, len(data), (orig + 2047) // 2048, (len(data) + 2047) // 2048,
        (orig + 2047) // 2048 - (len(data) + 2047) // 2048))
    subprocess.run([FF, '-v', 'error', '-y', '-i', DST, '-vf', 'scale=960:672:flags=neighbor', '-c:v', 'libx264', '-crf', '16',
                    '-pix_fmt', 'yuv420p', '-c:a', 'aac', os.path.join(ROOT, 'work', 'movie', 'LOGO_small.mp4')], check=True)


if __name__ == '__main__':
    main()
