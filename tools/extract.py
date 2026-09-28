# -*- coding: utf-8 -*-
r"""린다 큐브 대사 추출 (2026-09-28) — LINDA.MIC 묶음 434개 PROG.BIN 의 «글 구역» → my files/tsv/linda3_001‥NNN.tsv (29KB씩)
  구조(docs/01 «MIC 구조 해독»): 묶음 = 섹터 경계 [이름 12B][u32 위치<<8]… · PROG.BIN 머리 [u16 8][u16 8+n][u32][u16 구역 위치×n]
  글 구역 = 00 으로 나눈 조각 목록. 메시지는 구역 안 번호로 불림(실기 확정) → 길이 자유.
  ★쓰레기 거르기(그림·수치 구역에도 SJIS 처럼 보이는 바이트가 많다):
    조각 검사 = 끝까지 «SJIS 글자(81‥84·87‥9F·E0‥EA 리드, 사용자정의 제외 · 표에 없는 칸은 게임 전용 기호로 통과)
               / 제어 01‥1F / ASCII 20‥7E / 06…04(반각) 안의 반각 가나 A1‥DF» 로만 읽혀야 통과
    구역 = 조각 «전부» 통과 + 일본어 4자 이상 → 글 구역.  일본어가 있는데 떨어진 구역은 work/text_rejected.tsv (검토용)
  종류: 방이름(제어 없는 첫 조각 · 뒤가 0C 메시지) · 대사(0C 로 시작) · 화면글(제어 코드 든 메뉴·표 글) · 문구(그 밖)
  전용 기호 칸({XXXX})만 있는 조각(아이콘)은 안 뽑음
  표기: SJIS·ASCII 그대로 · 0D = \n · 그 밖의 01‥1F·80 이상 1바이트 = {XX} · 표에 없는 SJIS 칸 = {XXXX} · '{' = {7B} · '\' = {5C}
  같은 원문은 한 줄(«공유» = 나온 횟수, «첫위치» = 묶음섹터:구역:조각). 순서 = 디스크에 처음 나온 순서.
  python tools/extract.py
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
MIC = os.path.join(ROOT, 'work', 'disc', 'LINDA_LINDA.MIC')
LEADS = set(range(0x81, 0x85)) | set(range(0x87, 0xA0)) | set(range(0xE0, 0xEB))
NUL, PAGE = bytes(1), 0x0C
CHUNK = 29 * 1024                # 사용자: 파일당 29KB


def progs(m):
    for s in range(len(m) // 2048):
        b = s * 2048
        if m[b:b + 9] == b'PROG.BIN' + NUL:
            off = struct.unpack_from('<I', m, b + 12)[0] >> 8
            nxt = struct.unpack_from('<I', m, b + 28)[0] >> 8
            yield s, b + off, nxt - off


def table(d):
    """구역 위치표 = u16 단어 [a/2 : 첫값/2] (a = 첫 단어 — 보통 8, 메뉴·시스템 묶음 D1 등은 0x2C).
       a 앞(단어 2‥a/2−1)은 다른 표(D1 = 20개). 4개 묶음(13A·19C·201·7C6)은 순서대로가 아님."""
    a = struct.unpack_from('<H', d, 0)[0]
    first = struct.unpack_from('<H', d, a)[0]
    raw = [struct.unpack_from('<H', d, 2 * i)[0] for i in range(a // 2, first // 2)]
    return unwrap(raw, len(d))


def unwrap(raw, n):
    """★64KB 넘는 PROG(전투 13A 등 0x11FF8)는 u16 값이 0x10000 을 넘으며 한 바퀴 돈다(0x10431 → 0x431).
       차례로 읽다 앞 값보다 0x8000 넘게 작아지면 +0x10000 (2026-09-29: 이걸 코드 앞쪽으로 잘못 읽어 전투 글이 밀림)."""
    if n <= 0x10000:
        return raw
    out = []; base = 0; prev = None
    for v in raw:
        u = v + base
        if prev is not None and u + 0x8000 < prev and u + 0x10000 <= n:
            base += 0x10000; u += 0x10000
        out.append(u); prev = u
    return out


def sections(d):
    """구역 경계 = 위치표 값을 정렬한 것(겹침 제거) + [PROG 길이]"""
    return sorted({v for v in table(d) if v <= len(d)} | {len(d)})


def table_start(d):
    return struct.unpack_from('<H', d, 0)[0]


def parse(b):
    """조각 → (통과?, 일본어 글자 수)"""
    i = 0; jp = 0; half = False
    while i < len(b):
        c = b[i]
        if c in LEADS:
            if i + 1 >= len(b):
                return False, 0
            t = b[i + 1]
            if not (0x40 <= t <= 0xFC and t != 0x7F):
                return False, 0
            try:
                ch = b[i:i + 2].decode('cp932')
                if 0xE000 <= ord(ch) <= 0xF8FF:
                    return False, 0
                if c >= 0x82:
                    jp += 1                     # 일본어 글자 수(표에 없는 전용 기호 칸은 안 셈)
            except UnicodeDecodeError:
                pass                                # 게임 전용 칸 → {XXXX}
            i += 2
        elif 0x01 <= c <= 0x7E:
            if c == 0x06:
                half = True
            elif c == 0x04:
                half = False
            i += 1
        elif half and 0xA1 <= c <= 0xDF:
            i += 1
        else:
            return False, 0
    return True, jp


def classify(sec):
    """글 구역이면 조각 목록, 아니면 None"""
    if sec.endswith(NUL):
        sec = sec[:-1]
    parts = sec.split(NUL)
    ok = [parse(p) for p in parts if p]
    if not ok or not all(v for v, _ in ok):
        return None
    if sum(n for _, n in ok) < 4:
        return None
    return parts


def kind_of(k, raw, parts):
    ctl = any(c < 0x20 for c in raw)
    if k == 0 and not ctl and len(parts) > 1 and any(p[:1] == bytes([PAGE]) for p in parts[1:]):
        return '방이름'
    if raw[:1] == bytes([PAGE]):
        return '대사'
    if ctl:
        return '화면글'
    return '문구'


def to_text(b):
    out = []; i = 0
    while i < len(b):
        c = b[i]
        if c in LEADS:
            try:
                out.append(b[i:i + 2].decode('cp932'))
            except UnicodeDecodeError:
                out.append('{%04X}' % (c << 8 | b[i + 1]))
            i += 2; continue
        if c == 0x0D:
            out.append('\\n')
        elif c < 0x20 or c in (0x7B, 0x5C) or c >= 0x80:
            out.append('{%02X}' % c)
        else:
            out.append(chr(c))
        i += 1
    return ''.join(out)


def from_text(t):
    out = bytearray(); i = 0
    while i < len(t):
        if t.startswith('\\n', i):
            out.append(0x0D); i += 2
        elif t[i] == '{':
            j = t.index('}', i); h = t[i + 1:j]
            out += int(h, 16).to_bytes(len(h) // 2, 'big'); i = j + 1
        elif ord(t[i]) < 0x80:
            out.append(ord(t[i])); i += 1
        else:
            out += t[i].encode('cp932'); i += 1
    return bytes(out)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    m = open(MIC, 'rb').read()
    rows = {}; order = []; rej = {}
    nsec = 0
    for s, p, ln in progs(m):
        d = m[p:p + ln]
        offs = sections(d)
        for k, (a, b) in enumerate(zip(offs, offs[1:])):
            sec = d[a:b]
            if not sec:
                continue
            parts = classify(sec)
            if parts is None:
                jp = sum(parse(x)[1] for x in sec.split(NUL) if parse(x)[0])
                if jp >= 10:
                    key = sec[:64]
                    if key not in rej:
                        rej[key] = ['%X:%d' % (s, k), 0, jp]
                    rej[key][1] += 1
                continue
            nsec += 1
            for j, raw in enumerate(parts):
                if not raw or not parse(raw)[1]:
                    continue                    # 빈 조각·일본어 없는 조각(파일 이름·숫자)은 안 뽑음
                if raw not in rows:
                    rows[raw] = [kind_of(j, raw, parts), 0, '%X:%d:%d' % (s, k, j)]; order.append(raw)
                rows[raw][1] += 1
    dst = os.path.join(ROOT, 'my files', 'tsv'); os.makedirs(dst, exist_ok=True)
    head = 'ID\t종류\t공유\t첫위치\t원문\t번역\n'
    cnt = {}; nchar = 0; files = []; buf = head; size = len(head.encode('utf-8'))
    for n, raw in enumerate(order, 1):
        kind, c, loc = rows[raw]
        t = to_text(raw); assert from_text(t) == raw, raw
        nchar += parse(raw)[1]; cnt[kind] = cnt.get(kind, 0) + 1
        line = '%05d\t%s\t%d\t%s\t%s\t\n' % (n, kind, c, loc, t)
        if size + len(line.encode('utf-8')) > CHUNK and buf != head:
            files.append(buf); buf = head; size = len(head.encode('utf-8'))
        buf += line; size += len(line.encode('utf-8'))
    files.append(buf)
    for k, body in enumerate(files, 1):
        with open(os.path.join(dst, 'linda3_%03d.tsv' % k), 'w', encoding='utf-8', newline='\n') as f:
            f.write(body)
    path = os.path.join(dst, 'linda3_001‥%03d.tsv' % len(files))
    with open(os.path.join(ROOT, 'work', 'text_rejected.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('첫위치\t공유\t일본어\t앞 64B\n')
        for key, (loc, c, jp) in sorted(rej.items(), key=lambda kv: -kv[1][2]):
            f.write('%s\t%d\t%d\t%s\n' % (loc, c, jp, key.decode('cp932', errors='replace').replace('\n', ' ').replace('\t', ' ')))
    print('글 구역 %d · %d줄 %s · 일본어 %d자 → %s' % (nsec, len(order), cnt, nchar, path))
    print('떨어진 구역(일본어 10자 이상) %d종 → work/text_rejected.tsv' % len(rej))


if __name__ == '__main__':
    main()
