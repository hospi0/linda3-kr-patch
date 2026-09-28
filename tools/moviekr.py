# -*- coding: utf-8 -*-
r"""새턴 동영상(SC_xx.CPK)에 한글 자막 입히기 (2026-09-27)
  자막 = PS1 영문패치 SUBTITLE.DAT 시각(tools/subdat.py) + 번역(work/trans/movie_ko.tsv)
  시각: 새턴 프레임 = PS1 프레임 − d (work/movie/align.tsv, tools/align.py), SC_23 은 _RI03 − 578
  글씨: 나눔고딕 Bold 14px, 흰색 + 검은 1px 테두리, 화면 아래 가운데, 어절 단위로 줄 나눔(폭 304px)
  재굽기: 걸리버 tools/opening_enc.py(자막 든 키 구간만 cinepak 다시 — 띠 2개, 구간 바이트 ≤ 원본, 빚은 뒤 구간에서 갚음)
  → work/kr/cpk/SC_xx.CPK (원본과 같은 크기로 0 채움)
  python tools/moviekr.py [SC_02 …] [--preview]
"""
import glob, os, re, shutil, subprocess, sys
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import subdat
FF = r'C:\claude\utils\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe'
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf'
PX, LINE_H, MAXW, BOTTOM = 14, 17, 304, 6
FPS = 15
PUNCT = (",.!?:;)]}'\"~" "、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥")
MOV = os.path.join(ROOT, 'work', 'movie')


def squeeze(t):
    return re.sub('([' + re.escape(PUNCT) + '])[ 　](?![ 　])', r'\1', t)


def wrap(font, text):
    """«\n» 은 그대로 줄바꿈, 넘치면 어절 단위로 더 나눈다(글자 단위 분할 금지)"""
    out = []
    for para in text.split(chr(92) + 'n'):
        words = para.split(' '); cur = ''
        for w in words:
            t = (cur + ' ' + w) if cur else w
            if font.getlength(t) <= MAXW or not cur:
                cur = t
            else:
                out.append(cur); cur = w
        out.append(cur)
    for ln in out:
        assert font.getlength(ln) <= MAXW, ('한 어절이 너무 김', ln)
    return out


def plate(font, lines, w, h):
    """투명 판(RGBA) 에 자막"""
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    y0 = h - BOTTOM - LINE_H * len(lines)
    for k, ln in enumerate(lines):
        x = (w - font.getlength(ln)) / 2; y = y0 + LINE_H * k
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    dr.text((x + dx, y + dy), ln, font=font, fill=(0, 0, 0, 255))
        dr.text((x, y), ln, font=font, fill=(255, 255, 255, 255))
    return im


def load_subs():
    rows, _ = subdat.load()
    ko = {}
    for l in open(os.path.join(ROOT, 'work', 'trans', 'movie_ko.tsv'), encoding='utf-8').read().split('\n')[1:]:
        if l.strip():
            i, t = l.split('\t', 1); ko[i] = t
    al = {}
    for l in open(os.path.join(MOV, 'align.tsv'), encoding='utf-8').read().split('\n')[1:]:
        if l.strip():
            c = l.split('\t'); al[c[0]] = int(c[2])
    subs = {}
    for k, (sat, ri, a, b, lines) in enumerate(rows):
        mid = 'M%03d' % (k + 1)
        d = al[sat] - (578 if sat == 'SC_23' else 0)      # SC_23 시각은 subdat 이 이미 −578/15 해 둠
        f0 = round(a * FPS) - d; f1 = round(b * FPS) - d
        subs.setdefault(sat, []).append((f0, f1, squeeze(ko[mid]), mid))
    return subs


def frames(name):
    fr = os.path.join(MOV, 'frames', name)
    if not glob.glob(os.path.join(fr, 'f*.png')):
        os.makedirs(fr, exist_ok=True)
        subprocess.run([FF, '-v', 'error', '-i', os.path.join(MOV, 'cpk', name + '.CPK'), '-fps_mode', 'passthrough',
                        os.path.join(fr, 'f%04d.png')], check=True)
    return fr, sorted(glob.glob(os.path.join(fr, 'f*.png')))


def burn(name, subs, font):
    fr, fl = frames(name)
    kr = os.path.join(MOV, 'krframes', name)
    if os.path.isdir(kr):
        shutil.rmtree(kr)
    os.makedirs(kr)
    w, h = Image.open(fl[0]).size
    n = 0
    for f0, f1, text, mid in subs:
        pl = plate(font, wrap(font, text), w, h)
        for f in range(max(0, f0), min(len(fl), f1)):
            src = os.path.join(kr, 'f%04d.png' % (f + 1))
            base = Image.open(src if os.path.exists(src) else fl[f]).convert('RGBA')
            Image.alpha_composite(base, pl).convert('RGB').save(src); n += 1
    return fr, kr, len(fl), n


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import filmcpk, opening_enc
    opening_enc.STRIPS = 2                          # 린다 새턴 CPK = 프레임마다 띠 2개
    opening_enc.TMP = os.path.join(MOV, '_gop')
    font = ImageFont.truetype(FONT, PX)
    subs = load_subs()
    names = [a for a in sys.argv[1:] if a.startswith('SC_')] or sorted(subs, key=lambda s: int(s[3:]))
    os.makedirs(os.path.join(ROOT, 'work', 'kr', 'cpk'), exist_ok=True)
    for name in names:
        fr, kr, nf, nd = burn(name, subs[name], font)
        # 영상 조각 수 = 프레임 수 확인
        film = filmcpk.read(open(os.path.join(MOV, 'cpk', name + '.CPK'), 'rb').read())
        nv = sum(1 for e in film['stab'] if e[2] != 0xFFFFFFFF)
        assert nv == nf, (name, nv, nf)
        print('%s 자막 %d개 · 덮은 프레임 %d / %d' % (name, len(subs[name]), nd, nf))
        if '--preview' in sys.argv:
            continue
        src = os.path.join(MOV, 'cpk', name + '.CPK'); size = os.path.getsize(src)
        out = os.path.join(ROOT, 'work', 'kr', 'cpk', name + '.CPK')
        try:
            ln = opening_enc.reencode(src, fr, kr, out, size, log=lambda *a: None)
        except AssertionError as e:                  # 자리 초과(긴 키 구간 하나를 다시 굽는 SC_19 등) → 원본 그대로 두고 다음으로
            print('   ⚠%s 자리 초과로 건너뜀(원본 유지): %s' % (name, e))
            if os.path.exists(out):
                os.remove(out)
            continue
        data = open(out, 'rb').read(); open(out, 'wb').write(data + bytes(size - len(data)))
        print('   → %s %d B (원본 %d)' % (out, ln, size))


if __name__ == '__main__':
    main()
