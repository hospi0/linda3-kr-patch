# -*- coding: utf-8 -*-
r"""동영상 대사 자막 — 미리보기 (2026-09-27, 루나 tools/moviesub.py 방식)
  work/text/movie_gNN.tsv (G 영상 안 시각 · 원문 · 번역 «\n» = 다음 자막)
  + my files/movie script/gNN.txt 의 시각 전부(«[音楽]» 포함 — 대사 끝 경계로만), 스크립트 시각 − OFFSET = 영상 시각
  행마다 «\n» 조각을 차례로 한 자막씩(글자 수 비례). 행 끝 = 다음 경계 와 «시작 + 글자×0.2초 + 조각×1.5초» 중 이른 쪽.
  글씨: 나눔고딕 Bold 14px, 흰색 + 검은 1px 테두리, 320×160 화면 아래 가운데, 넘치면 어절 두 줄.
  → work/movie/sub/gNN/s###.png(자막 판) + work/movie/sub/GNN_kr.mp4(원 화소 ×3 확대 미리보기)
  python tools/moviesub.py 01 [--encode]
  --encode: work/movie/frames/gNN/f####.png(원본 프레임, ffmpeg -fps_mode passthrough) 에 자막 판을 얹어 kr/ 에 →
            그 프레임이 든 키 구간만 cinepak 재굽기(tools/opening_enc.py, 구간 바이트 ≤ 원본) → work/kr/GNN.CPK(원본 크기로 0 채움)
"""
import os, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
FFBIN = r'C:\claude\utils\ffmpeg-9.0.1-essentials_build\bin'
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf'
PX, W, H, FPS = 14, 320, 160, 15
OFFSET = {1: 2 * 60 + 44}                         # 스크립트 시각 − 이 값 = 영상 시각 (사용자: G01 은 2:44 부터)
PUNCT_SP = re.compile(r'([,.!?…~])\s+')


def secs(t):
    m, s = t.split(':')
    return int(m) * 60 + int(s)


def duration(p):
    r = subprocess.run([os.path.join(FFBIN, 'ffprobe.exe'), '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'csv=p=0', p], capture_output=True, text=True)
    return float(r.stdout.strip())


def events(n):
    rows = []
    for ln in open(os.path.join(ROOT, 'work', 'text', 'movie_g%02d.tsv' % n), encoding='utf-8'):
        if ln.startswith('#') or not ln.strip():
            continue
        c = ln.rstrip('\n').split('\t')
        rows.append((secs(c[0]), [PUNCT_SP.sub(r'\1', p.strip()) for p in c[2].split('\\n')]))
    bd = sorted({secs(m.group(1)) - OFFSET[n] for m in
                 (re.match(r'(\d+:\d\d)', l) for l in open(os.path.join(ROOT, 'my files', 'movie script', 'g%02d.txt' % n), encoding='utf-8')) if m})
    end_all = duration(os.path.join(ROOT, 'work', 'movie', 'cpk', 'G%02d.CPK' % n))
    starts = {t for t, _ in rows}
    ev = []
    for t, parts in rows:
        total = sum(len(p) for p in parts)
        need = total * 0.2 + 1.5 * len(parts)
        nxt = min([x for x in bd if x > t and (x in starts or x - t >= need * 0.6)] + [end_all])
        end = min(nxt - 0.2, t + need, end_all - 0.1)
        a = float(t)
        for p in parts:
            d = (end - t) * len(p) / total
            ev.append((a, a + d, p)); a += d
    return ev


def wrap(text, F):
    d = ImageDraw.Draw(Image.new('L', (1, 1)))
    if d.textlength(text, font=F) <= W - 12:
        return [text]
    words = text.split(' ')
    best = min((max(d.textlength(' '.join(words[:i]), font=F), d.textlength(' '.join(words[i:]), font=F)),
                [' '.join(words[:i]), ' '.join(words[i:])]) for i in range(1, len(words)))
    assert best[0] <= W - 12, ('두 줄로도 넘침', text)
    return best[1]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    n = int(sys.argv[1])
    out = os.path.join(ROOT, 'work', 'movie', 'sub', 'g%02d' % n)
    os.makedirs(out, exist_ok=True)
    F = ImageFont.truetype(FONT, PX)
    ev = events(n)
    inputs, chain = [], '[0:v]scale=%d:%d:flags=neighbor[v0]' % (W, H)
    for k, (a, b, text) in enumerate(ev):
        print('%6.2f‥%6.2f  %s' % (a, b, text))
        im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        lines = wrap(text, F)
        y = H - 12 - (len(lines) - 1) * 17
        for ln in lines:
            d.text((W / 2, y), ln, font=F, anchor='mm', fill=(255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0)); y += 17
        # 실제 화면처럼 이진화(반투명 가장자리 없음 — cinepak 에 구울 때와 같게)
        px = im.load()
        for yy in range(H):
            for xx in range(W):
                r, g, bb, al = px[xx, yy]
                px[xx, yy] = (r, g, bb, 255) if al >= 128 else (0, 0, 0, 0)
        p = os.path.join(out, 's%03d.png' % k); im.save(p)
        inputs += ['-i', p]
        chain += ";[v%d][%d:v]overlay=enable='between(t,%.3f,%.3f)'[v%d]" % (k, k + 1, a, b, k + 1)
    chain += ';[v%d]scale=%d:%d:flags=neighbor[vo]' % (len(ev), W * 3, H * 3)
    dst = os.path.join(ROOT, 'work', 'movie', 'sub', 'G%02d_kr.mp4' % n)
    subprocess.run([os.path.join(FFBIN, 'ffmpeg.exe'), '-hide_banner', '-loglevel', 'error', '-y',
                    '-i', os.path.join(ROOT, 'work', 'movie', 'cpk', 'G%02d.CPK' % n)] + inputs +
                   ['-filter_complex', chain, '-map', '[vo]', '-map', '0:a', '-c:v', 'libx264', '-crf', '16',
                    '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', dst], check=True)
    print('자막 %d개 →' % len(ev), dst)
    if '--encode' in sys.argv:
        encode(n, ev, out)


def encode(n, ev, plates):
    import glob, opening_enc
    fr = os.path.join(ROOT, 'work', 'movie', 'frames', 'g%02d' % n)
    kr = os.path.join(fr, 'kr'); os.makedirs(kr, exist_ok=True)
    for f in glob.glob(os.path.join(kr, 'f*.png')):
        os.remove(f)
    nf = len(glob.glob(os.path.join(fr, 'f*.png')))
    k_done = 0
    for k, (a, b, _) in enumerate(ev):
        plate = Image.open(os.path.join(plates, 's%03d.png' % k))
        for f in range(nf):                          # 프레임 f(0부터) 시각 = f / 15
            if a <= f / FPS < b:
                im = Image.open(os.path.join(fr, 'f%04d.png' % (f + 1))).convert('RGBA')
                im.alpha_composite(plate)
                im.convert('RGB').save(os.path.join(kr, 'f%04d.png' % (f + 1))); k_done += 1
    src = os.path.join(ROOT, 'work', 'movie', 'cpk', 'G%02d.CPK' % n)
    dst = os.path.join(ROOT, 'work', 'kr', 'G%02d.CPK' % n)
    size = os.path.getsize(src)
    opening_enc.reencode(src, fr, kr, dst, size)
    d = open(dst, 'rb').read()
    open(dst, 'wb').write(d + bytes(size - len(d)))  # 디렉터리 크기 그대로
    print('덮은 프레임 %d → %s (%d B, 실제 %d)' % (k_done, dst, size, len(d)))


if __name__ == '__main__':
    main()
