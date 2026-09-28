# -*- coding: utf-8 -*-
r"""실행 파일(00SL.BIN) 글 추출 (2026-09-28) → my files/tsv/linda3_exe_001‥.tsv (29KB씩)
  대상: 0x60000‥0x64000 문자열 구역(장비·아이템·능력·지명·메뉴 등) + 서식 문자열(능력치 창·소지금·なみ) + 흩어진 확인분.
  ★되넣기 규칙(빌더): 제자리 · «바이트» 칸 이하 · 짧으면 반각 공백으로 채움(NUL 로 채우면 NUL 을 세는 목록이 어긋남)
    단, 종류 «묶음»(계절·이름 0x60C24‥0x60C5C, 동물 0x60C5C‥0x60F9C — NUL 로 세는 목록, 구조 확인됨)은 묶음 전체 길이 안에서 자유.
    종류 «반각»(동물 이름: 화면에서 06…04 반각 모드로 찍힘) — 한글은 반각 칸(음절 수 한도 184)에.
  거르기: 한 글자+{06} 4바이트 기록(데이터 표)·반각 잡음이 일본어보다 많은 조각은 뺌.
  번역 칸: PoC 에서 정한 계절(춘하추동)·이름·동물·능력치 서식은 미리 채움(tools/poc.py).
  python tools/extract_exe.py
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import extract as X
sys.path.append(r'C:\claude\project\anearth-kr-patch\tools')
import poc
EXE = os.path.join(ROOT, 'work', 'disc', '00SL.BIN')
REGION = (0x60000, 0x64000)
FORMATS = [0xE314, 0xE678, 0xE688, 0xE698, 0xE6A8, 0xEB8C]
SCATTER = [0x10B9C, 0x10BA4, 0x10BB0, 0x10BBC, 0x12858, 0x12860, 0x12868, 0x19C28, 0x19ECD]
SEASON = (0x60C24, 0x60C30); NAMES = (0x60C30, 0x60C5C); ANIMAL = (0x60C5C, 0x60F9C)


def noise(b):
    t = re.sub(r'\{[0-9A-F]{2,4}\}\d*', '', X.to_text(b))
    return sum(1 for c in t if ord(c) < 0x80 and not c.isdigit() and c not in ' %-/.:')


def strings(d):
    out = []
    lo, hi = REGION; o = lo
    for piece in d[lo:hi].split(X.NUL):
        if piece:
            ok, jp = X.parse(piece)
            if ok and jp >= 1 and noise(piece) <= jp and not re.fullmatch(rb'..\x06', piece):
                out.append((o, piece))
        o += len(piece) + 1
    out = [(o, p) for o, p in out if not (o < SEASON[0] < o + len(p))]     # «{02}{03}{03}春» 처럼 앞 데이터에 붙은 것 → 묶음 시작부터
    for o in FORMATS + SCATTER + [SEASON[0]]:
        out.append((o, d[o:d.index(X.NUL, o)]))
    return sorted(set(out))


def kind(o):
    if SEASON[0] <= o < NAMES[1]:
        return '묶음'
    if ANIMAL[0] <= o < ANIMAL[1]:
        return '반각'
    return '실행파일'


def prefill(d):
    """PoC 에서 정한 번역 → {위치: 번역}"""
    pre = {}
    for o, ch in zip(range(SEASON[0], SEASON[1], 3), poc.SEASON_BLK[1]):
        pre[o] = ch
    o = NAMES[0]
    for it in poc.NAME_BLK[1]:
        raw = d[o:d.index(X.NUL, o)]
        if raw:
            pre[o] = ('{06}%s{04}' % it[0]) if isinstance(it, tuple) else it
        o += len(raw) + 1
    o = ANIMAL[0]
    for a in poc.ANIMALS:
        raw = d[o:d.index(X.NUL, o)]
        pre[o] = a; o += len(raw) + 1
    pre[0x60522] = '{01}{01}춘'; pre[0x60528] = '하'; pre[0x6052C] = '추'; pre[0x60530] = '동'
    pre[0xEB8C] = '{0C}{06}ＡＭＤ%d{04}년　%s　소지금{06} %s{04}{15}{85}￥'
    pre[0xE678] = '{04}{09}10Σ공격{09}-4'
    pre[0xE688] = '\\n{04}{09}10Τ수비{09}-4'
    pre[0xE698] = '\\n{04}{09}10Υ민첩{09}-4'
    pre[0xE314] = '{06}{06}84{06} %s급'
    return pre


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    d = open(EXE, 'rb').read()
    rows = strings(d); pre = prefill(d)
    dst = os.path.join(ROOT, 'my files', 'tsv')
    head = 'ID\t종류\t위치\t바이트\t원문\t번역\n'
    files = []; buf = head; size = len(head.encode('utf-8')); cnt = {}
    for n, (o, raw) in enumerate(rows, 1):
        t = X.to_text(raw); assert X.from_text(t) == raw
        k = kind(o); cnt[k] = cnt.get(k, 0) + 1
        line = 'E%04d\t%s\t%X\t%d\t%s\t%s\n' % (n, k, o, len(raw), t, pre.get(o, ''))
        if size + len(line.encode('utf-8')) > X.CHUNK and buf != head:
            files.append(buf); buf = head; size = len(head.encode('utf-8'))
        buf += line; size += len(line.encode('utf-8'))
    files.append(buf)
    for k, body in enumerate(files, 1):
        with open(os.path.join(dst, 'linda3_exe_%03d.tsv' % k), 'w', encoding='utf-8', newline='\n') as f:
            f.write(body)
    print('실행 파일 글 %d줄 %s · 미리 채운 번역 %d → my files/tsv/linda3_exe_001‥%03d.tsv' % (len(rows), cnt, len(pre), len(files)))


if __name__ == '__main__':
    main()
