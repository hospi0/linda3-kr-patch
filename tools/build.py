# -*- coding: utf-8 -*-
r"""린다 큐브 한글 빌더 (2026-09-28) — TSV 번역 → 글꼴(전각·반각) + LINDA.MIC PROG.BIN 글 구역 + 실행 파일 → 트랙 1
  입력: my files/tsv/linda3_*.tsv (tools/extract.py, «번역» 칸) — 시험용은 환경변수 LINDA_TSV=<폴더>
        (⛔my files 에 가짜 번역 쓰지 말 것)
  ① 번역 정리(쓰는 순간 규칙 — 막음): 제어 코드·인수 순서가 원문과 같을 것(0C·0D 는 자유) · 표에 없는 글자 금지
     · ! ? , . → 전각 · 띄어쓰기 = 반각 공백(그 밖 영숫자는 원문처럼 반각 그대로) · 부호 뒤 공백 삭제 · 대사 줄 폭 ≤ 18칸(전각 1, 반각 0.5) · 쪽당 ≤ 4줄
       (원문이 이미 더 길면 원문 한도까지)
  ② 전각 글꼴(00SL.BIN 0x54634, 1,907칸): 한글 음절 → 가나·한자 칸(기호·숫자·영문 칸은 보호, 원문에서 덜 쓰인 칸부터),
     그 칸을 가리키는 SJIS 코드로 적음. 갈무리11.
  ③ 반각 글꼴(0x5D65C, 320칸): {06}…{04} 안 한글 → 반각 가나 칸(콘덴스드) + 반각 u16 변환표 다시 가리킴 (tools/poc.py 와 같음)
  ④ MIC: 글 구역마다 조각을 번역으로 바꿔 이어 붙임(메시지는 구역 안 번호로 불림 — 실기 확정).
     새 구역 ≤ 원래 길이면 제자리 + 뒤를 00 으로(다른 구역 불변). 넘치면 같은 PROG.BIN 안 뒤 구역을 밀고 위치표 갱신,
     PROG.BIN 원래 길이도 넘치면 묶음 안 뒤 파일을 8B 단위로 밀고 묶음 목록 갱신(묶음 섹터 여유 안에서만, 모자라면 오류).
  ⑤ 실행 파일 글 = my files/tsv/linda3_exe_*.tsv (tools/extract_exe.py): 제자리·바이트 칸 이하·짧으면 반각 공백,
     계절·이름·동물 묶음은 묶음 안 길이 자유(종류 «반각» = 반각 칸). «クリア条件» 그림 = tools/joken.py.
  ⑥ --write: 트랙 1 에 00SL·MIC(커지면 SS_ASCII 밀고 LOGO 줄인 판) + 동영상 자막 work/kr/cpk/SC_*.CPK(제자리) 까지.
  python tools/build.py [--write] [--check]   (--check: 번역 없이 되돌림 검사만 — 결과 MIC 가 원본과 같아야 함)
"""
import glob, os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import extract as X                     # ★다른 프로젝트 tools 에도 extract.py 가 있다 — 경로 넣기 전에 먼저
sys.path.append(r'C:\claude\project\anearth-kr-patch\tools')
import bdf, poc
LINE_W, PAGE_LINES = 18, 4
DIGIT_PARAM = {0x01, 0x02, 0x03, 0x08, 0x09, 0x0F, 0x10, 0x11, 0x17, 0x19, 0x1A, 0x1E}
LETTER_PARAM = {0x15, 0x1C}
FREE_CTL = {0x0C, 0x0D}
PUNCT = ',.!?:;)]\'"~、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥'
# ★«}» 는 뺌 — 토큰 {XX} 의 끝이라 «{06} %s» 의 공백을 지워 버림(원문 글자 } 는 {7D})
HALF_ON, HALF_OFF = 0x06, 0x04


class RuleError(Exception):
    pass


# ── 번역 읽기 ──────────────────────────────────────────────
def load_tsv():
    folder = os.environ.get('LINDA_TSV') or os.path.join(ROOT, 'my files', 'tsv')
    tr = {}
    for f in sorted(glob.glob(os.path.join(folder, 'linda3_[0-9]*.tsv'))):
        for ln in open(f, encoding='utf-8'):
            c = ln.rstrip('\n').split('\t')
            if c[0] == 'ID' or len(c) < 6 or not c[5].strip():
                continue
            tr[X.from_text(c[4])] = (c[0], c[1], c[5])
    return tr


# ── 토큰: (kind, value) — 'ctl'(바이트, 인수 bytes) / 'ch'(글자, 반각?) ─────────
def tokens_raw(raw):
    out = []; i = 0; half = False
    while i < len(raw):
        c = raw[i]
        if c in X.LEADS:
            out.append(('ch', raw[i:i + 2], half)); i += 2; continue
        if c < 0x20:
            j = i + 1
            if c in DIGIT_PARAM:
                while j < len(raw) and 0x30 <= raw[j] <= 0x39:
                    j += 1
            elif c in LETTER_PARAM and j < len(raw) and 0x20 < raw[j] < 0x7F:
                j += 1
            out.append(('ctl', c, raw[i + 1:j]))
            if c == HALF_ON:
                half = True
            elif c == HALF_OFF:
                half = False
            i = j; continue
        out.append(('ch', bytes([c]), half)); i += 1
    return out


def tokens_tr(t):
    """번역 글 → 토큰(글자는 유니코드 한 글자)"""
    out = []; i = 0; half = False
    while i < len(t):
        if t.startswith('\\n', i):
            out.append(('ctl', 0x0D, b'')); i += 2; continue
        if t[i] == '{':
            j = t.index('}', i); h = t[i + 1:j]; i = j + 1
            if len(h) == 4:
                out.append(('ch', bytes.fromhex(h), half)); continue
            c = int(h, 16); p = ''
            if c in DIGIT_PARAM:
                while i < len(t) and t[i].isdigit() and ord(t[i]) < 0x80:
                    p += t[i]; i += 1
            elif c in LETTER_PARAM and i < len(t) and 0x20 < ord(t[i]) < 0x7F and t[i] not in '{\\':
                p = t[i]; i += 1
            if c >= 0x20:                       # {7B} {5C} 등 글자
                out.append(('ch', bytes([c]), half)); continue
            out.append(('ctl', c, p.encode()))
            if c == HALF_ON:
                half = True
            elif c == HALF_OFF:
                half = False
            continue
        out.append(('ch', t[i], half)); i += 1
    return out


def normalize(t):
    """쓰는 순간 정리: 부호 뒤 공백 1칸 삭제(2칸 이상은 둠)"""
    # ★조사 괄호 «을(를) 이어받을» 의 공백은 낱말 띄어쓰기 — 지우면 «을(를)이어받을»(걸리버에서 겪음)
    return re.sub(r'(\([가-힣]{1,2}\))|([%s]) (?! )' % re.escape(PUNCT),
                  lambda m: m.group(1) or m.group(2), t)


FULLW = {'!': '！', '?': '？', ',': '，', '.': '．'}   # 띄어쓰기 = 반각 공백(1B, 원문도 씀) — ＿(2B)면 MIC 가 넘침   # 원문도 전각 모드에서 반각 영숫자를 그대로 씀 → 이것만 바꿈


def full_char(ch):
    return FULLW.get(ch, ch)


# ── 검사 ──────────────────────────────────────────────────
def ctl_seq(toks):
    return [(c, p) for k, c, p in toks if k == 'ctl' and c not in FREE_CTL]


def measure(toks):
    """쪽마다 [줄 폭…](칸 = 14px) — ★2026-09-28 실기 화면 실측: 전각 모드는 1바이트 글자(공백 0x20 포함)도 1칸,
    반각 모드({06}…{04})만 반 칸. 보통 창 19칸(꽉 채우면 저절로 줄바꿈 → 18칸까지), 얼굴 창 15칸, 창 글 3줄"""
    pages = [[0.0]]
    for k, v, x in toks:
        if k == 'ctl':
            if v == 0x0C:
                pages.append([0.0])
            elif v == 0x0D:
                pages[-1].append(0.0)
            continue
        if not x and v in ('＿', bytes.fromhex('8151')):  #Q'):
            pages[-1][-1] += 0.5            # ★＿ = 반 칸(2026-09-28 실기: 物理＿火炎… 열 간격 2.5칸) — 띄어쓰기는 ＿ 로
        else:
            pages[-1][-1] += 0.5 if x else 1
    return [p for p in pages if any(p) or len(p) > 1]


def text_lines(p):
    """쪽 끝 «{12}\n» 뒤 빈 줄은 안 셈"""
    n = len(p)
    while n > 1 and p[n - 1] == 0:
        n -= 1
    return n


FACE_W, SMALL_W, TEXT_LINES = 15, 13, 3   # 얼굴 창({17}) 15칸 · 원문 줄이 모두 13칸 미만이면 작은 창(원문 폭까지) · 창은 글 3줄(넘으면 저절로 다음 쪽)


def limits(kind, to):
    """(줄 폭 한도, 쪽 글 줄 수 한도) — 검사 안 하는 줄이면 None"""
    positioned = any(k == 'ctl' and c in (0x02, 0x09) for k, c, _ in to)     # 위치 지정 메뉴는 폭 검사 안 함(손으로)
    if kind not in ('대사', '화면글') or positioned:
        return None
    po = measure(to)
    ow = max([w for p in po for w in p] or [0])
    if any(k == 'ctl' and c == 0x17 for k, c, _ in to):
        wmax = max(FACE_W, ow)
    elif ow < SMALL_W and not any(k == 'ctl' and (c in (0x1C, 0x19) or (c == 0x15 and a == b'Y')) for k, c, a in to) and (
            any(k == 'ctl' and c == 0x01 for k, c, _ in to) or not any(k == 'ctl' and c == 0x0C for k, c, _ in to)
            or (len(to) > 1 and to[0][:2] == ('ctl', 0x0C) and to[1] == ('ctl', 0x10, b'0'))):   # {0C}{10}0 = 즉시 표시 시스템 창(선택지는 실행 파일에서 따로 붙음)
        wmax = ow                       # 작은 창·칸: 선택지 확인 창({01})·쪽 넘김 없는 이름표 — 원문 폭까지 (도움말 줄 {0C}{15}·{19} 설명 창은 보통 창)
    else:
        wmax = max(LINE_W, ow)
    return wmax, max([TEXT_LINES] + [text_lines(p) for p in po])


def page_split_ok(to, tt):
    """번역이 쪽을 더 나눈 것만 다르면 허용: 원문에 없는 {12} 는 «{12}(\n){0C}» 꼴 쪽 끝이어야 하고,
    {12} 를 빼면 제어 순서가 원문과 같아야 함. 얼굴({17})·선택지({01}) 줄은 안 됨"""
    if any(k == 'ctl' and c in (0x17, 0x01) for k, c, _ in to):
        return False
    so = [x for x in ctl_seq(to) if x[0] != 0x12]; st = [x for x in ctl_seq(tt) if x[0] != 0x12]
    if so != st or sum(1 for x in ctl_seq(tt) if x[0] == 0x12) <= sum(1 for x in ctl_seq(to) if x[0] == 0x12):
        return False
    for i, (k, c, _) in enumerate(tt):
        if k == 'ctl' and c == 0x12:
            j = i + 1
            while j < len(tt) and tt[j][0] == 'ctl' and tt[j][1] == 0x0D:
                j += 1
            if j < len(tt) and not (tt[j][0] == 'ctl' and tt[j][1] == 0x0C):
                return False
    return True


def _ids(*rs):
    return {'%05d' % i for a, b in rs for i in range(a, b + 1)}


DEBUG_IDS = _ids((5277, 5277), (598, 603), (629, 631), (686, 714), (723, 739), (741, 743), (798, 798), (808, 813))   # 디버그 메뉴 — 폭 검사 안 함


def check(rid, kind, orig_raw, t):
    to = tokens_raw(orig_raw); tt = tokens_tr(t)
    if ctl_seq(to) != ctl_seq(tt) and not page_split_ok(to, tt):
        raise RuleError('%s 제어 코드·인수가 원문과 다름\n  원문 %s\n  번역 %s' % (rid, ctl_seq(to), ctl_seq(tt)))
    lim = None if rid in DEBUG_IDS else limits(kind, to)
    if rid not in DEBUG_IDS and any(k == 'ctl' and c in (0x02, 0x09) for k, c, _ in to):
        # 위치 지정 줄({02}/{09}): 줄마다 원문 같은 줄 폭 이하(줄 구성이 다르면 원문 최대 폭 이하) — 2026-09-28 타이틀 메뉴 넘침
        po = [w for p in measure(to) for w in p]; pt = [w for p in measure(tt) for w in p]
        for n, w in enumerate(pt):
            cap = po[n] if len(po) == len(pt) else max(po or [0])
            if w > cap + 1e-6:
                raise RuleError('%s 위치 지정 %d번째 줄 폭 %.1f칸 > 원문 %g' % (rid, n + 1, w, cap))
    if lim:
        wmax, lmax = lim
        for p in measure(tt):
            if text_lines(p) > lmax:
                raise RuleError('%s 쪽당 %d줄 > %d' % (rid, text_lines(p), lmax))
            for w in p:
                if w > wmax + 1e-6:
                    raise RuleError('%s 줄 폭 %.1f칸 > %g' % (rid, w, wmax))
    return tt


# ── 글꼴 ──────────────────────────────────────────────────
def is_hangul(ch):
    return isinstance(ch, str) and '가' <= ch <= '힣'


def slot_table(x):
    """SJIS 코드 → 전각 칸, 칸 → 코드들"""
    code2slot = {}
    for hi in list(range(0x81, 0xA0)) + list(range(0xE0, 0xEB)):
        for lo in range(0x40, 0xFD):
            if lo == 0x7F:
                continue
            try:
                s = poc.code_index(x, hi << 8 | lo)
            except IndexError:
                continue
            if 0 <= s < poc.NGLYPH:
                code2slot[hi << 8 | lo] = s
    return code2slot


def is_carrier(code):
    return 0x829F <= code <= 0x82F1 or 0x8340 <= code <= 0x8396 or 0x889F <= code <= 0x9FFC or 0xE040 <= code <= 0xEAA4


# 이름 입력판·가나 이름(세이브에 가나 코드로 저장됨 — 사냥개 별명·재료 이름 «チバベ»·세이브 목록 지명 등)용: 가타카나 72자 = 고정 한글(거센소리 규칙)
# (2026-09-28: 입력판 표 = MIC 묶음 562D·5790 구역 5 «アイウエオガギ…ロ». 이 칸은 번역문 한글도 같은 코드를 씀)
NAME_KANA = dict(zip('アイウエオガギグゲゴカキクケコザジズゼゾサシスセソダヂヅデドタチツテトバビブベボナニヌネノパピプペポハヒフヘホヤユヨワンマミムメモラリルレロ',
                     '아이우에오가기구게고카키쿠케코자지즈제조사시스세소다디두데도타치츠테토바비부베보나니누네노파피푸페포하히후헤호야유요와응마미무메모라리루레로'))


def alloc_full(x, syl, usage, extra=None):
    code2slot = slot_table(x)
    prot = {s for c, s in code2slot.items() if not is_carrier(c)} | {0}
    tail = {s for s in code2slot.values() if s >= HALF_TAIL}
    bad = [hex(c) for c, sl in code2slot.items() if sl >= HALF_TAIL and not is_carrier(c)]
    assert not bad, ('반각 글꼴 옮길 자리에 기호 칸', bad[:5])
    prot |= tail
    F = bdf.Font(poc.GALMURI)
    kmap = {}
    for c, h in (extra or {}).items():                # 반각 운반 코드의 전각 칸에도 같은 한글(동물 이름이 전각 {01} 자리에서도 찍힘)
        sl = code2slot[c]; poc.put_glyph(x, sl, poc.hangul_rows(F, h)); prot.add(sl)
    for kana, h in NAME_KANA.items():                  # 고정 칸 먼저
        c = int.from_bytes(kana.encode('cp932'), 'big'); sl = code2slot[c]
        poc.put_glyph(x, sl, poc.hangul_rows(F, h)); kmap[h] = bytes([c >> 8, c & 0xFF]); prot.add(sl)
    syl = [h for h in syl if h not in kmap]
    slots = {}
    for c, s in code2slot.items():
        if s not in prot:
            slots.setdefault(s, []).append(c)
    order = sorted(slots, key=lambda s: (sum(usage.get(c, 0) for c in slots[s]), -s))
    if len(syl) > len(order):
        raise RuleError('전각 한글 %d음절 > 쓸 수 있는 칸 %d' % (len(syl), len(order)))
    for ch, s in zip(syl, order):
        poc.put_glyph(x, s, poc.hangul_rows(F, ch))
        c = min(slots[s]); kmap[ch] = bytes([c >> 8, c & 0xFF])
    return kmap, len(order)


# 능력치 이름표 조각 글리프(2026-09-28): 원문 «攻げき すび゛ すばやさ» = 그리스 소문자 칸 γδε·ζηθ·ικλ 에 그린 그림
# (실행 파일 E0005 «{15}Sγδε…ικλ»). 전투 상태 줄은 γ·ζ·κ 한 칸만 약자로 씀 → 공·수·민 이 한 칸에 오게
LABEL_GLYPHS = {'γ': '공', 'δ': '격', 'ε': '', 'ζ': '수', 'η': '비', 'θ': '', 'ι': '', 'κ': '민', 'λ': '첩'}


SMALL_FONT = 0x5CC5C       # {05}·{15}S 작은 글꼴 8x8(4글자 32B 묶음, 줄마다 u32) — 2026-09-28 스테이트: RAM 0x060CBD80 = 0x06060C5C
SMALL_LABELS = ['공', '격', '', '수', '비', '', '', '민', '첩']   # 칸 3‥11 = 원문 «攻 げ き 守 び ゛ す 早 さ»
GALMURI7 = 'C:/claude/utils/font/Galmuri-v2.40.3/Galmuri7.bdf'


def draw_small_labels(x):
    F7 = bdf.Font(GALMURI7)
    for n, h in enumerate(SMALL_LABELS):
        rows = [[0] * 8 for _ in range(8)]
        if h:
            pts, _ = F7.draw(h, 0, 0)
            ys = [y for _, y in pts]; xs = [a for a, _ in pts]
            dy = (8 - (max(ys) - min(ys) + 1)) // 2 - min(ys); dx = (8 - (max(xs) - min(xs) + 1)) // 2 - min(xs)
            for a, y in pts:
                if 0 <= a + dx < 8 and 0 <= y + dy < 8:
                    rows[y + dy][a + dx] = 1
        i = 3 + n; g = SMALL_FONT + (i >> 2) * 32; k = i & 3
        for r in range(8):
            v = struct.unpack_from('>I', x, g + r * 4)[0]
            for q in range(8):
                bit = 4 * (7 - q) + k
                v = (v | (1 << bit)) if rows[r][q] else (v & ~(1 << bit))
            struct.pack_into('>I', x, g + r * 4, v)


def draw_label_glyphs(x):
    c2s = slot_table(x)
    F = bdf.Font(poc.GALMURI)
    for g, h in LABEL_GLYPHS.items():
        c = int.from_bytes(g.encode('cp932'), 'big')
        rows = poc.hangul_rows(F, h) if h else [[0] * 12 for _ in range(12)]
        poc.put_glyph(x, c2s[c], rows)


PLACE_EXTRA = {0x19C28}           # ハコブネ(E0014) — 지도 화면 목적지 목록 첫 항목, 지명처럼 반각으로 찍힘(2026-09-30 실기 깨짐)
PLACE_LIST = (0x62F98, 0x63288)   # 지명 목록(E1093‥) — 세이브 목록에서 반각(06…04)으로 찍힘(2026-09-28 «하치아»). 원문 전각 가나라 전각으로도 찍힐 수 있어 양쪽 한글


def free_codes(x, lit):
    """반각 표(8140‥81AB·824F‥82F1·8340‥8396)가 있고 전각 칸을 혼자 쓰는(같은 칸 공유 코드도 전부 안 쓰임) 코드 — 전각 칸 하나당 하나.
    (2026-09-28: ヽヾゝゞ〃仝々 7개가 한 칸, ´｀¨ 가 한 칸, ヮヰ·ヰヱヲ 도 한 칸 → 동물 이름 음절끼리 덮어쓰던 것 수정)"""
    rev = {int.from_bytes(k.encode('cp932'), 'big') for k in NAME_KANA}
    c2s = slot_table(x); sl = {}
    for c, s in c2s.items():
        sl.setdefault(s, []).append(c)
    dual, half, seen = [], [], set()
    for c in list(range(0x8340, 0x8397)) + list(range(0x829F, 0x82F2)) + list(range(0x8140, 0x81AC)) + list(range(0x824F, 0x829F)):
        if c in rev or c in lit or c & 0xFF == 0x7F or c not in c2s:
            continue
        half.append(c)
        s = c2s[c]
        if s and s not in seen and not any(d in lit or d in rev for d in sl[s]):
            seen.add(s); dual.append(c)
    return dual, [c for c in half if c not in dual]


def plan_half(hsyl, dual, want, dcodes, hcodes, kcodes=()):
    """반각 한글 → 운반 코드. dual(전각 모드에서도 반드시 찍히는 음절 = 동물 이름)·want(되면 좋은 것 = 지명)는
    전각 칸에도 같은 한글을 그리는 코드(dcodes, 가나 72자 고정 음절이면 그 코드), 나머지는 반각 전용 코드"""
    rev = {h: int.from_bytes(k.encode('cp932'), 'big') for k, h in NAME_KANA.items()}
    dcodes = list(dcodes); hcodes = list(hcodes); kcodes = list(kcodes)
    plan = {}; extra = {}; lost = []
    for h in sorted(hsyl, key=lambda h: (h not in dual, h not in want, h)):
        if h in rev:
            plan[h] = rev[h]; continue
        if (h in dual or h in want) and (dcodes or kcodes):
            c = (dcodes or kcodes).pop(0); plan[h] = c; extra[c] = h; continue      # kcodes = 한자 줄(반각 변환 훅 표)
        if h in dual:
            raise RuleError('전각에서도 찍히는 반각 한글 %d음절 > 코드' % len([h for h in hsyl if h in dual and h not in rev]))
        if h in want:
            lost.append(h)
        pool = hcodes or dcodes
        if not pool:
            raise RuleError('반각 한글 운반 코드 모자람')
        plan[h] = pool.pop(0)
    if lost:
        print('  지명 음절 %d개는 반각 전용(전각 칸 모자람): %s' % (len(lost), ''.join(lost)))
    return plan, extra


# ★반각 글꼴 옮김(2026-09-29): 12×12 글꼴 끝 칸 1652‥1906(한자, 번역 뒤 안 씀) 자리 0x5BA5C 로 반각 글꼴 320칸을 복사하고
# 384칸으로 늘림. 초기화 코드 0x06006C58 의 글꼴 주소 상수만 바꿈(반각 글꼴 변수 0x060CB9BC 를 쓰는 곳은 그리기 0x0600702C 하나).
# 작은 글꼴(0x5CC5C, 8×8)은 반각과 칸 번호를 같이 쓰며, 뒤의 옛 반각 자리로 늘어남(320→384칸).
HALF_TAIL = 1652
HFONT_NEW = poc.FONT + HALF_TAIL // 4 * 0x48          # 0x5BA5C
HALF_N = 384
HFONT_LIT = 0x06006C58 - 0x06004000


def relocate_half(x):
    assert HFONT_NEW + HALF_N // 4 * 48 == poc.FONT + (poc.NGLYPH + 3) // 4 * 0x48 == SMALL_FONT
    assert struct.unpack_from('>I', x, HFONT_LIT)[0] == 0x06004000 + poc.HFONT
    old = bytes(x[poc.HFONT:poc.HFONT + 320 // 4 * 48])
    x[HFONT_NEW:HFONT_NEW + len(old)] = old
    x[HFONT_NEW + len(old):HFONT_NEW + HALF_N // 4 * 48] = bytes(HALF_N // 4 * 48 - len(old))
    struct.pack_into('>I', x, HFONT_LIT, 0x06004000 + HFONT_NEW)
    x[SMALL_FONT + 320 // 4 * 32:SMALL_FONT + HALF_N // 4 * 32] = bytes((HALF_N - 320) // 4 * 32)
    poc.HFONT_OLD = poc.HFONT
    poc.HFONT = HFONT_NEW


# ★반각 변환 훅(2026-09-29): 원래 0x06006DAC 는 기호·영숫자·가나만 반각 칸으로 바꾸고 한자는 0(안 그림).
# 한자 한 줄 0x889F‥0x88FC(94자)를 전각·반각 겸용 운반 코드로 쓰려고, 앞에 표 하나 보는 함수를 붙인다.
# 자리 = 옛 반각 글꼴 자리(0x5D860, 작은 글꼴 확장 0x5D65C‥0x5D85C 뒤). 부르는 곳 = 리터럴 3곳(0x060070C8·0x06007184·0x06019B94).
KHOOK_BASE, KHOOK_N = 0x889F, 94
KHOOK_CODE = 0x5D860
KHOOK_TAB = KHOOK_CODE + 0x30
KHOOK_LITS = (0x060070C8, 0x06007184, 0x06019B94)
KHOOK_ORIG = 0x06006DAC


def install_khook(x):
    a = 0x06004000 + KHOOK_CODE
    code = [0x6043, 0x600D, 0xD106, 0x3018, 0xE25D, 0x3026, 0x8904, 0x300C,      # mov r4,r0 · extu.w · mov.l base,r1 · sub r1,r0 · mov #93,r2 · cmp/hi r2,r0 · bt orig · add r0,r0
            0xD104, 0x001D, 0x000B, 0x600D,                                      # mov.l tab,r1 · mov.w @(r0,r1),r0 · rts · extu.w r0,r0
            0xD103, 0x412B, 0x0009, 0x0009]                                      # orig: mov.l origfn,r1 · jmp @r1 · nop
    blob = struct.pack('>16H', *code) + struct.pack('>III', KHOOK_BASE, 0x06004000 + KHOOK_TAB, KHOOK_ORIG)
    assert len(blob) == 0x2C and KHOOK_CODE % 4 == 0 and KHOOK_CODE >= SMALL_FONT + HALF_N // 4 * 32
    assert KHOOK_TAB + 2 * KHOOK_N <= poc.HFONT_OLD + 320 // 4 * 48      # 옛 반각 글꼴 자리 안
    x[KHOOK_CODE:KHOOK_TAB + 2 * KHOOK_N] = blob + bytes(KHOOK_TAB - KHOOK_CODE - len(blob)) + bytes(2 * KHOOK_N)
    for lit in KHOOK_LITS:
        o = lit - 0x06004000
        assert struct.unpack_from('>I', x, o)[0] == KHOOK_ORIG, hex(lit)
        struct.pack_into('>I', x, o, a)


def khook_codes(x, lit):
    """훅 표로 반각 칸을 얻는 한자 코드 중 전각 칸을 혼자 쓰고 글자 그대로 안 찍히는 것"""
    c2s = slot_table(x); sl = {}
    for c, s_ in c2s.items():
        sl.setdefault(s_, []).append(c)
    out = []
    for c in range(KHOOK_BASE, KHOOK_BASE + KHOOK_N):
        if c & 0xFF == 0x7F or c not in c2s or c in lit:
            continue
        s_ = c2s[c]
        if s_ and s_ < HALF_TAIL and len(sl[s_]) == 1:
            out.append(c)
    return out


def alloc_half(x, hsyl, plan, hkeep):
    """반각 칸 배정 = 0x80‥0x13F 중 기호(바이트 표가 가리키는 칸 — 전각 모드 「」 등도 이 칸으로 그려짐)·글자 그대로 찍히는 칸(hkeep) 뺀 것.
    ⛔1‥0x7F 쓰지 말 것(2026-09-28 실기: ♂♀·화살표 등 런타임 기호 칸이라 «♂사키»·「→다 로 깨짐).
    작은 글꼴({05}, 8×8)은 반각과 같은 칸 번호를 씀 → 같은 칸에 8×8 한글도 그림(전투 상태 줄 이름)."""
    sym = {x[poc.HMAP_B + i] for i in range(0x6C)} | {0xB0}
    pool = [i for i in range(0x80, HALF_N) if i not in sym and i not in hkeep]
    need = set(hsyl) | set(NAME_KANA.values())
    if len(need) > len(pool):
        raise RuleError('반각 한글 %d음절 > 칸 %d' % (len(need), len(pool)))
    FC = bdf.Font(poc.GALMURI_C); F7 = bdf.Font(GALMURI7)
    hmap = {}; slot = {}
    order = sorted(need, key=lambda ch: (ch not in plan or plan[ch] >= 0x8200, ch))     # 81xx(바이트 표) 코드에 256 미만 칸부터
    for ch, h in zip(order, pool):
        poc.put_half(x, h, poc.half_rows(FC, ch)); put_small(x, h, F7, ch); slot[ch] = h
        if ch not in plan:
            continue
        code = plan[ch]
        hmap[ch] = bytes([code >> 8, code & 0xFF])
        if KHOOK_BASE <= code < KHOOK_BASE + KHOOK_N:
            struct.pack_into('>H', x, KHOOK_TAB + 2 * (code - KHOOK_BASE), h)
        elif code < 0x8200:
            assert h < 256; x[poc.HMAP_B + code - 0x8140] = h
        else:
            o = poc.HMAP_K + 2 * (code - 0x8340) if code >= 0x8340 else poc.HMAP_H + 2 * (code - 0x824F)
            struct.pack_into('>H', x, o, h)
    n = 0
    for kana, ch in NAME_KANA.items():       # 가나 이름(사냥개 등)이 반각·작은 글꼴에서 찍힐 때 — 그 한글이 반각 칸에 있으면 그 칸으로
        if ch in slot:
            code = int.from_bytes(kana.encode('cp932'), 'big')
            struct.pack_into('>H', x, poc.HMAP_K + 2 * (code - 0x8340), slot[ch]); n += 1
    print('반각 칸 %d / %d · 가나 이름 %d/72자 반각 한글' % (len(need), len(pool), n))
    return hmap


def put_small(x, i, F7, ch):
    rows = [[0] * 8 for _ in range(8)]
    pts, _ = F7.draw(ch, 0, 0)
    if pts:
        ys = [y for _, y in pts]; xs = [a for a, _ in pts]
        dy = (8 - (max(ys) - min(ys) + 1)) // 2 - min(ys); dx = (8 - (max(xs) - min(xs) + 1)) // 2 - min(xs)
        for a, y in pts:
            if 0 <= a + dx < 8 and 0 <= y + dy < 8:
                rows[y + dy][a + dx] = 1
    g = SMALL_FONT + (i >> 2) * 32; k = i & 3
    for r in range(8):
        v = struct.unpack_from('>I', x, g + r * 4)[0]
        for q in range(8):
            bit = 4 * (7 - q) + k
            v = (v | (1 << bit)) if rows[r][q] else (v & ~(1 << bit))
        struct.pack_into('>I', x, g + r * 4, v)


def small_space(tt):
    """{05}(작은 글꼴 모드, {04}·{06}·{0C} 까지) 안의 ＿ → 반각 공백. 작은 글꼴엔 ＿ 가 밑줄 글자로 찍힘
    (2026-09-28 실기: 전투 «공격 _수비 _ 민첩 / 100_091_076» — 원문은 반각 공백)"""
    out = []; small = False
    for k, v, p in tt:
        if k == 'ctl':
            if v == 0x05:
                small = True
            elif v in (0x04, 0x06, 0x0C):
                small = False
        elif k == 'ch' and v == '＿' and small:
            v = ' '
        out.append((k, v, p))
    return out


def encode(tt, kmap, hmap):
    out = bytearray()
    for k, v, p in tt:
        if k == 'ctl':
            out.append(v); out += p; continue
        if isinstance(v, bytes):
            out += v; continue
        half = p
        if is_hangul(v):
            out += (hmap if half else kmap)[v]; continue
        if not half:
            v = full_char(v)
        try:
            b = v.encode('cp932')
        except UnicodeEncodeError:
            raise RuleError('표에 없는 글자 %r' % v)
        out += b
    return bytes(out)


# ── MIC 되넣기 ─────────────────────────────────────────────
def pack_table(m):
    """첫머리 해시 목록에서 실제 묶음(PROG.BIN 으로 시작) 항목 → {섹터: (목록 위치, 섹터 수)}"""
    real = {s for s, _, _ in X.progs(bytes(m))}
    top = {}
    for o in range(0, 0x11800, 16):
        a, n = struct.unpack_from('<II', m, o)
        if a in real and n:
            top[a] = (o, n)
    assert len(top) == len(real)
    return top


def data_end(m, lo, hi):
    while hi > lo and m[hi - 1] == 0:
        hi -= 1
    return hi


def rebuild_prog(m, s, p, ln, tr_bytes, stat, force, compact=False):
    """PROG.BIN 하나 → (새 PROG 바이트) 또는 None(바뀐 것 없음). 구역 넘치면 위치표 갱신."""
    d = bytearray(m[p:p + ln])
    bounds = X.sections(d)
    head = bounds[0]
    changed = False; grew = False
    new_secs = []
    for a, b in zip(bounds, bounds[1:]):
        sec = bytes(d[a:b])
        parts = X.classify(sec) if sec else None
        if parts is None:
            new_secs.append(sec); continue
        tail = sec.endswith(X.NUL)
        np = [tr_bytes.get(q, q) for q in parts]
        if np != parts:
            changed = True; stat['조각'] += sum(1 for u, v in zip(parts, np) if u != v)
        body = X.NUL.join(np) + (X.NUL if tail else b'')
        if len(body) > len(sec):
            stat['넘친 구역'] += 1
        new_secs.append(body)
    if not changed and not force:
        return None
    # ★배치 = «원래 자리보다 앞으로 당기지 않는다»(2026-09-29: 당겨 붙였더니 필드 음성 대사 02940 에서 멈춤).
    # 구역 시작 = max(원래 시작, 앞 구역 끝) — 넘칠 때만 뒤로 밀리고, 뒤 구역의 남는 자리가 밀림을 흡수
    newpos = {}; pos = head; blob = bytearray(d[:head])
    for old, sec in zip(bounds, new_secs):
        at = max(old, pos)
        blob += bytes(at - len(blob)) + sec
        newpos[old] = at; pos = at + len(sec)
    blob += bytes(max(0, len(d) - len(blob)))
    newpos[len(d)] = len(blob)
    grew = any(newpos[o] != o for o in bounds[:-1])
    if grew:
        tbl = X.table(d); a0 = X.table_start(d)        # 정렬 안 된 표(7C6 등)도 값 대응으로 갱신
        first_moved = min((o for o in bounds[:-1] if newpos[o] != o), default=None)
        if first_moved is not None:
            other = [struct.unpack_from('<H', d, 2 * i)[0] for i in range(2, a0 // 2)]
            if any(first_moved <= v < 0xFFFF for v in other):
                raise RuleError('묶음 %X: 앞쪽 표가 밀리는 구역(%X~)을 가리킴' % (s, first_moved))
        for i, v in enumerate(tbl):
            if v in newpos:
                struct.pack_into('<H', blob, a0 + 2 * i, newpos[v] & 0xFFFF)
        stat['민 PROG'] += 1
    return bytes(blob)


OVER = {}
# ★메뉴·시스템 묶음(D1·F6·11B = 시나리오 A/B/C)도 고정: RAM 0x222900 에 올라가 원본이 0x234D80(전투 묶음 데이터 자리)
#   바로 앞에서 끝남(여유 0). 416 B 늘었더니 끝의 FACE2·POKEBELL 이 덮여 부재중 전화 창이 빈칸 + 받고 나면 지도 깨짐·이동 불가(2026-09-30 실기)
FIXED_LEN_PROGS = {0x13A, 0x19C, 0x201, 0xD1, 0xF6, 0x11B}
MAX_PACK_SECTORS = 127        # 원본 최대 묶음(254KB) — 묶음 RAM 버퍼(256KB 추정)를 넘지 않게
# MIC 뒤 배치(트랙 1): MIC(9488) → SS_ASCII.CPK(43114, 350섹터, FILM 1.06 — 그대로 뒤로) → LOGO.CPK(43464, 679섹터) → SC_01(44143)
# LOGO 영상을 줄여(tools/logoshrink.py → work/kr/LOGO_small.CPK) 생긴 섹터만큼 MIC 가 커질 수 있다.
LOGO_SMALL = os.path.join(ROOT, 'work', 'kr', 'LOGO_small.CPK')
LOGO_LBA, LOGO_SECTORS = 43464, 679
MIC_EXTRA = LOGO_SECTORS - (os.path.getsize(LOGO_SMALL) + 2047) // 2048 if os.path.exists(LOGO_SMALL) else 0


def rebuild_mic(m, tr_bytes, stat, force=False, narrow=None):
    """묶음마다 PROG.BIN 을 새로 만들고, 길어지면 묶음 안 뒤 파일을 8B 단위로 민다(묶음 목록 갱신).
       모든 묶음이 원래 섹터 수 안이면 제자리. 하나라도 넘치면 MIC 전체 묶음을 원래 순서대로
       «필요한 섹터 수»만큼 빈틈없이 다시 깔고 해시 목록의 섹터·섹터 수 갱신(MIC 크기는 원본 이하)."""
    top = pack_table(m)
    orig = bytes(m)
    packs = {}                      # 섹터 → 새 묶음 바이트(데이터 끝까지)
    for s, p, ln in X.progs(orig):
        new = rebuild_prog(m, s, p, ln, tr_bytes, stat, force)
        if new is None:
            continue
        if len(new) > ln and narrow and s in FIXED_LEN_PROGS:
            new2 = rebuild_prog(m, s, p, ln, {**tr_bytes, **narrow}, stat, force)     # 넘치면 좁은 판(＿→' ', 폭 되는 줄만)
            if len(new2) < len(new):
                new = new2
        if len(new) > ln and s in FIXED_LEN_PROGS:
            # ★전투 묶음(13A·19C·201): 뒤 OBJ 가 밀리면 끝의 SIGNAL.OBJ 가 RAM 의 다른 용도 영역에 들어가 보석·효과 깨짐(2026-09-29)
            OVER[s] = len(new) - ln
            if not os.environ.get('LINDA_OVER_OK'):
                raise RuleError('묶음 %X: 길이 고정 PROG %d B > 원래 %d B — 번역을 %d B 줄여야 함' % (s, len(new), ln, len(new) - ln))
        if narrow and (p - s * 2048 + len(new) + (data_end(orig, p + ln, s * 2048 + top[s][1] * 2048) - p - ln) + 2047) // 2048 > MAX_PACK_SECTORS:
            new = rebuild_prog(m, s, p, ln, {**tr_bytes, **narrow}, stat, force)     # 넘치는 묶음만 좁은 판
            stat['좁힌 묶음'] = stat.get('좁힌 묶음', 0) + 1
        b = s * 2048; end = b + top[s][1] * 2048
        body = bytearray(orig[b:data_end(orig, p + ln, end)])
        rel = p - b
        if len(new) <= ln:
            body[rel:rel + ln] = new + bytes(ln - len(new))
        else:
            delta = (len(new) - ln + 7) // 8 * 8
            body[rel + ln:rel + ln] = bytes(delta)
            body[rel:rel + ln + delta] = new + bytes(ln + delta - len(new))
            o = 0
            while body[o] >= 0x30 and body[o] != 0xFF:
                v = struct.unpack_from('<I', body, o + 12)[0]
                if (v >> 8) > rel:
                    struct.pack_into('<I', body, o + 12, (((v >> 8) + delta) << 8) | (v & 0xFF))
                o += 16
            stat['늘린 묶음'] += 1
        packs[s] = bytes(body)
        stat['PROG'] += 1
    need = {}
    for s, (o, n) in top.items():
        size = len(packs[s]) if s in packs else data_end(orig, s * 2048, (s + n) * 2048) - s * 2048
        need[s] = (size + 2047) // 2048
        if need[s] > MAX_PACK_SECTORS:
            raise RuleError('묶음 %X: %d섹터 > %d(RAM 버퍼) — 번역을 줄여야 함' % (s, need[s], MAX_PACK_SECTORS))
    if all(need[s] <= top[s][1] for s in top):
        for s, body in packs.items():
            m[s * 2048:s * 2048 + len(body)] = body
        return
    # 다시 깔기
    order = sorted(top)
    cur = order[0]
    lay = {}
    for s in order:
        lay[s] = cur; cur += need[s]
    orig_total = len(orig) // 2048
    limit = orig_total + MIC_EXTRA
    if cur > limit:
        raise RuleError('MIC 다시 깔기: %d섹터 > 한도 %d(원래 %d + 로고 줄여 만든 %d) — 번역을 줄여야 함'
                        % (cur, limit, orig_total, MIC_EXTRA))
    total = max(orig_total, cur)
    del m[total * 2048:]
    m.extend(bytes(total * 2048 - len(m)))
    area = bytearray((total - order[0]) * 2048)
    for s in order:
        n = top[s][1]
        body = packs[s] if s in packs else orig[s * 2048:data_end(orig, s * 2048, (s + n) * 2048)]
        q = (lay[s] - order[0]) * 2048
        area[q:q + len(body)] = body
        o = top[s][0]
        struct.pack_into('<II', m, o, lay[s], need[s])
    m[order[0] * 2048:] = area
    stat['다시 깐 MIC'] = '%d→%d섹터' % (orig_total, cur)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print('규칙: 제어·인수 순서 보존 · 띄어쓰기=반각 공백 · 부호 뒤 공백 삭제 · 대사 줄 %d칸 · 쪽 %d줄 · 표에 없는 글자 금지' % (LINE_W, PAGE_LINES))
    x = bytearray(open(os.path.join(ROOT, 'work', 'disc', '00SL.BIN'), 'rb').read())
    m = bytearray(open(X.MIC, 'rb').read())
    orig_m = bytes(m)
    tr = {} if '--check' in sys.argv else load_tsv()
    # ① 검사·토큰
    toks = {}; errors = []
    for raw, (rid, kind, t) in tr.items():
        try:
            toks[raw] = small_space(check(rid, kind, raw, normalize(t)))
        except RuleError as e:
            errors.append(str(e))
    if errors:
        print('\n'.join(errors[:50])); print('✗ 규칙 위반 %d줄 — 빌드 중단' % len(errors)); sys.exit(1)
    # ①' 실행 파일 TSV(linda3_exe_*) 검사
    exe = [] if '--check' in sys.argv else load_exe()
    for r in exe:
        try:
            r['toks'] = small_space(check(r['id'], r['kind'], r['raw'], normalize(r['tr'])))
            if r['kind'] == '반각' or PLACE_LIST[0] <= r['off'] < PLACE_LIST[1] or r['off'] in PLACE_EXTRA:        # 화면에서 06…04 안에 찍힘 → 한글은 반각 칸
                r['toks'] = [(k, v, True) if k == 'ch' else (k, v, p) for k, v, p in r['toks']]
        except RuleError as e:
            errors.append(str(e))
    if errors:
        print('\n'.join(errors[:50])); print('✗ 규칙 위반 %d줄 — 빌드 중단' % len(errors)); sys.exit(1)
    # ② 음절 모으기
    full, half = set(), set()
    for tt in list(toks.values()) + [r['toks'] for r in exe]:
        for k, v, p in tt:
            if k == 'ch' and is_hangul(v):
                (half if p else full).add(v)
    # 원문 글자 쓰임(덜 쓰인 칸부터 빌림)
    usage = {}
    for raw in set(orig_parts_iter(orig_m)):
        for k, v, p in tokens_raw(raw):
            if k == 'ch' and len(v) == 2:
                c = v[0] << 8 | v[1]; usage[c] = usage.get(c, 0) + 1
    dual = {v for r in exe if r['kind'] == '반각' for k, v, p in r['toks'] if k == 'ch' and is_hangul(v)}
    want = {v for r in exe if PLACE_LIST[0] <= r['off'] < PLACE_LIST[1] or r['off'] in PLACE_EXTRA for k, v, p in r['toks'] if k == 'ch' and is_hangul(v)}
    # 글자 그대로 찍히는 2바이트 코드(번역문·안 옮긴 원문·실행 파일) — 운반 코드로 못 씀. 디버그 화면은 뺌
    lit = set()
    for raw, tt in toks.items():
        if tr[raw][0] in DEBUG_IDS:
            continue
        for k, v, p in tt:
            if k == 'ch' and not is_hangul(v):
                b = v if isinstance(v, bytes) else (v if p else full_char(v)).encode('cp932')
                if len(b) == 2:
                    lit.add(b[0] << 8 | b[1])
    for raw in set(orig_parts_iter(orig_m)):
        if raw not in tr:
            for k, v, p in tokens_raw(raw):
                if k == 'ch' and len(v) == 2:
                    lit.add(v[0] << 8 | v[1])
    for r in exe:
        for k, v, p in r['toks']:
            if k == 'ch' and not is_hangul(v):
                b = v if isinstance(v, bytes) else (v if p else full_char(v)).encode('cp932')
                if len(b) == 2:
                    lit.add(b[0] << 8 | b[1])
    dcodes, hcodes = free_codes(x, lit)
    # 반각 글꼴에서 글자 그대로 찍히는 칸(1바이트 글자는 전각 모드에서도 반각 글꼴) — 한글로 못 덮음
    hkeep = {0, 0xB0}
    def keep(tt):
        for k, v, p in tt:
            if k != 'ch' or (not isinstance(v, bytes) and is_hangul(v)):
                continue
            b = v if isinstance(v, bytes) else (v if p else full_char(v)).encode('cp932')
            if len(b) == 1:
                hkeep.add(b[0])
            elif p:
                hkeep.add(poc.half_index(x, b[0] << 8 | b[1]))
    for raw, tt in toks.items():
        if tr[raw][0] not in DEBUG_IDS:
            keep(tt)
    for raw in set(orig_parts_iter(orig_m)):
        if raw not in tr:
            keep(tokens_raw(raw))
    for r in exe:
        keep(r['toks'])
    for r in load_exe_all(x):
        keep(tokens_raw(r))
    plan, extra = plan_half(half, dual, want, dcodes, hcodes, khook_codes(x, lit))
    relocate_half(x)
    install_khook(x)
    kmap, cap = alloc_full(x, sorted(full), usage, extra)
    draw_label_glyphs(x)
    draw_small_labels(x)
    hmap = alloc_half(x, half, plan, hkeep)
    print('전각 한글 %d음절 / 칸 %d · 반각 %d음절' % (len(full), cap, len(half)))
    # ③ 실행 파일(동물 이름 목록 바이트가 정해져야 대사 {1B} 이름을 같은 바이트로 쓸 수 있음) → MIC
    x_orig = bytes(x)
    apply_exe(x, exe, kmap, hmap)
    names = animal_names(x_orig, bytes(x), exe)
    _, tab_o = animal_table(x_orig); _, tab_n = animal_table(bytes(x))
    tr_bytes = {raw: encode(tag_animals(tt, names), kmap, hmap) for raw, tt in toks.items()}
    bad = []
    for raw, b in tr_bytes.items():
        if 0x1B in raw:
            a, z = animal_ids(raw, tab_o), animal_ids(b, tab_n)
            if a != z:
                bad.append('%s {1B} 동물 번호 원문 %s ≠ 번역 %s «%s»' % (tr[raw][0], a, z, tr[raw][2][:60]))
    if bad:
        print('\n'.join(bad[:60])); print('✗ {1B} 동물 이름이 목록과 안 맞는 줄 %d — 빌드 중단' % len(bad)); sys.exit(1)
    # 묶음이 RAM 버퍼(127섹터)를 넘을 때만 쓰는 좁은 판: 띄어쓰기 ＿(2B) → ' '(1B, 1칸) — 폭 한도를 그대로 지키는 줄만
    tr_narrow = {}
    for raw, tt in toks.items():
        t2 = [('ch', ' ', False) if (k == 'ch' and v == '＿' and not p) else (k, v, p) for k, v, p in tt]
        if t2 == tt:
            continue
        rid, kind, _ = tr[raw]
        lim = None if rid in DEBUG_IDS else limits(kind, tokens_raw(raw))
        ms = measure(t2)
        if lim and all(w <= lim[0] + 1e-6 for pg in ms for w in pg):
            tr_narrow[raw] = encode(tag_animals(t2, names), kmap, hmap)
    stat = {'조각': 0, 'PROG': 0, '넘친 구역': 0, '민 PROG': 0, '늘린 묶음': 0, '다시 깐 MIC': '-'}
    if '--check' not in sys.argv:
        import joken
        joken.apply(m)                  # 고정 위치(0x1635E0) — 묶음을 다시 깔기 «전에»
    rebuild_mic(m, tr_bytes, stat, narrow=tr_narrow)
    print('MIC: 바뀐 조각 %d · PROG.BIN %d · 넘쳐서 민 구역 %d · 늘린 묶음 %d · 다시 깐 MIC %s' % (stat['조각'], stat['PROG'], stat['넘친 구역'], stat['늘린 묶음'], stat['다시 깐 MIC']))
    if '--check' in sys.argv:
        print('되돌림 검사:', '✅ 원본과 같음' if bytes(m) == orig_m else '✗ 다름')
        return
    # ④ 쓰기(실행 파일은 ③ 앞에서 이미 반영)
    os.makedirs(os.path.join(ROOT, 'work', 'kr'), exist_ok=True)
    open(os.path.join(ROOT, 'work', 'kr', '00SL.BIN'), 'wb').write(x)
    open(os.path.join(ROOT, 'work', 'kr', 'LINDA.MIC'), 'wb').write(m)
    if '--write' in sys.argv:
        import inplace, disc
        out = os.path.join(ROOT, 'work', 'out'); os.makedirs(out, exist_ok=True)
        dst = os.path.join(out, os.path.basename(disc.ROM))
        D = disc.Disc(); ent = {p: (l, s) for p, l, s in D.files()}
        mic_l, mic_s = ent['/LINDA/LINDA.MIC']
        grow = (len(m) + 2047) // 2048 - (mic_s + 2047) // 2048
        if grow <= 0:
            inplace.patch(disc.ROM, dst, {'/00SL.BIN': bytes(x), '/LINDA/LINDA.MIC': bytes(m)})
        else:                           # MIC 가 커짐 → SS_ASCII 를 밀고 LOGO 는 줄인 판으로
            ss_l, ss_s = ent['/LINDA/SS_ASCII.CPK']
            logo = open(LOGO_SMALL, 'rb').read()
            assert ss_l == mic_l + (mic_s + 2047) // 2048 and ent['/LINDA/LOGO.CPK'][0] == LOGO_LBA
            new_ss = ss_l + grow; new_logo = new_ss + (ss_s + 2047) // 2048
            assert new_logo + (len(logo) + 2047) // 2048 <= LOGO_LBA + LOGO_SECTORS, 'LOGO 자리 부족'
            inplace.patch(disc.ROM, dst, {'/00SL.BIN': bytes(x)})
            inplace.patch_layout(dst, dst + '.tmp', {'/LINDA/LINDA.MIC': (mic_l, bytes(m)),
                                                     '/LINDA/SS_ASCII.CPK': (new_ss, D.read('/LINDA/SS_ASCII.CPK')),
                                                     '/LINDA/LOGO.CPK': (new_logo, logo)})
            os.replace(dst + '.tmp', dst)
            print('  배치: MIC +%d섹터 · SS_ASCII %d→%d · LOGO(줄인 판) %d→%d' % (grow, ss_l, new_ss, LOGO_LBA, new_logo))
        # 동영상 한글 자막(tools/moviekr.py 로 구워 둔 work/kr/cpk/SC_*.CPK, 원본과 같은 크기) — 매 빌드 제자리로
        movies = {'/LINDA/' + os.path.basename(f): open(f, 'rb').read()
                  for f in sorted(glob.glob(os.path.join(ROOT, 'work', 'kr', 'cpk', 'SC_*.CPK')))}
        if movies:
            inplace.patch(dst, dst, movies)
            print('  동영상 자막 %d개: %s' % (len(movies), ' '.join(sorted(os.path.basename(p)[:-4] for p in movies))))
        print('→', dst)


def orig_parts_iter(m):
    for s, p, ln in X.progs(m):
        d = m[p:p + ln]; offs = X.sections(d)
        for a, b in zip(offs, offs[1:]):
            parts = X.classify(d[a:b]) if b > a else None
            if parts:
                yield from (q for q in parts if q)


# NUL 로 세는 목록 — 묶음 안 길이 자유. 경계 = 00SL 목록 시작 표(0x633CC‥)의 시작 주소들
# (2026-09-28: 안쪽을 가리키는 포인터 없음 확인 · 0x63368 목록만 0x63378 을 가리키는 포인터가 있어 둘로 나눔 · MIC 의 PROG 안에 항목 주소 없음)
_EXE_STARTS = [0x60C24, 0x60C30, 0x60C5C, 0x60F9C, 0x61368, 0x61768, 0x61B54, 0x61F30, 0x622E8, 0x627E0, 0x627FC, 0x62818,
               0x62D70, 0x62D88, 0x62D90, 0x62D98, 0x62DE4, 0x62E10, 0x62E20, 0x62E44, 0x62E54, 0x62E78, 0x62E9C, 0x62F80,
               0x62F90, 0x62F98, 0x63288, 0x632C0, 0x632CC, 0x632DC, 0x63304, 0x63328, 0x63358, 0x63368, 0x63378, 0x633C0]
EXE_BLOCKS = list(zip(_EXE_STARTS, _EXE_STARTS[1:]))


def load_exe():
    folder = os.environ.get('LINDA_TSV') or os.path.join(ROOT, 'my files', 'tsv')
    rows = []
    x = open(os.path.join(ROOT, 'work', 'disc', '00SL.BIN'), 'rb').read()
    for f in sorted(glob.glob(os.path.join(folder, 'linda3_exe_*.tsv'))):
        for ln in open(f, encoding='utf-8'):
            c = ln.rstrip('\n').split('\t')
            if c[0] == 'ID' or len(c) < 6 or not c[5].strip():
                continue
            o = int(c[2], 16); raw = X.from_text(c[4])
            assert x[o:o + len(raw)] == raw and x[o + len(raw)] == 0, ('실행 파일 원문 불일치', c[0])
            rows.append({'id': c[0], 'kind': c[1], 'off': o, 'budget': int(c[3]), 'raw': raw, 'tr': c[5]})
    return rows


def load_exe_all(x=None):
    """번역 안 된 실행 파일 문자열(원문 바이트) — 원문 그대로 찍히므로 그 글자 칸은 보존"""
    folder = os.environ.get('LINDA_TSV') or os.path.join(ROOT, 'my files', 'tsv')
    for f in sorted(glob.glob(os.path.join(folder, 'linda3_exe_*.tsv'))):
        for ln in open(f, encoding='utf-8'):
            c = ln.rstrip('\n').split('\t')
            if c[0] != 'ID' and len(c) >= 5 and (len(c) < 6 or not c[5].strip()):
                yield X.from_text(c[4])


# ★{1B} 동물 이름(2026-09-30 실기 «다람쥐 → 돼지쥐»): 글 전처리 0x06014C12 가 {1B} 뒤(숫자 아님)를 0x06017134 로 넘김 →
#   0x060170B8 이 목록 0x17(00SL 목록 시작 표 0x633CC 의 0x17번, NUL 로 센 항목 1‥120, 0 = 人間)에서 «글 앞머리와 바이트가 같은
#   가장 긴 항목»(숫자로 시작하는 항목 제외)을 찾아 번호로 바꾸고 그 길이만큼 건너뜀. 못 찾으면 1번(ブタ)·4바이트.
#   ⇒ 대사의 {1B} 뒤 이름은 목록 항목과 «같은 바이트»(반각 운반 코드 — 전각 칸에도 같은 한글이 그려짐)여야 한다.
ANIMAL_LIST = 0x17


def animal_table(x):
    p = struct.unpack_from('>I', x, 0x633CC + ANIMAL_LIST * 4)[0] - 0x06004000
    out = []; o = p
    for _ in range(121):
        e = x.index(X.NUL, o); out.append(bytes(x[o:e])); o = e + 1
    return p, out


def animal_id(text, table):
    best = bid = 0
    for i in range(1, 121):
        e = table[i]
        if e and e[0] > 0x39 and text.startswith(e) and len(e) > best:
            best, bid = len(e), i
    return bid


def animal_ids(raw, table):
    """글 바이트의 {1B}(뒤가 숫자 아닌 것)마다 게임이 고르는 동물 번호"""
    out = []; i = 0
    for k, v, p in tokens_raw(raw):
        n = 1 + len(p) if k == 'ctl' else len(v)
        if k == 'ctl' and v == 0x1B and i + 1 < len(raw) and raw[i + 1] > 0x39:
            out.append(animal_id(raw[i + 1:], table))
        i += n
    return out


def animal_names(x_orig, x_new, rows):
    """번역 이름(한글 글) → 새 목록 항목 바이트"""
    p, _ = animal_table(x_orig)
    idx = {}; o = p
    for i in range(121):
        idx[o] = i; o = x_orig.index(X.NUL, o) + 1
    _, new = animal_table(x_new)
    names = {}
    for r in rows:
        if r['off'] in idx and idx[r['off']] and all(k == 'ch' and is_hangul(v) for k, v, _ in r['toks']):
            names[''.join(v for _, v, _ in r['toks'])] = new[idx[r['off']]]
    return names


def tag_animals(tt, names):
    """{1B} 뒤 한글 중 가장 긴 동물 이름을 목록 항목 바이트로 바꿈"""
    out = list(tt); i = 0
    while i < len(out):
        if out[i][0] == 'ctl' and out[i][1] == 0x1B:
            s = ''
            for k, v, p in out[i + 1:]:
                if k != 'ch' or not isinstance(v, str):
                    break
                s += v
            best = max((n for n in names if s.startswith(n)), key=len, default=None)
            if best:
                out[i + 1:i + 1 + len(best)] = [('ch', names[best], False)]
        i += 1
    return out


def apply_exe(x, rows, kmap, hmap):
    """묶음(EXE_BLOCKS) 안 = 항목 순서대로 다시 이어 붙임(묶음 길이 이하, 끝 00) · 그 밖 = 제자리, 바이트 칸 이하, 짧으면 반각 공백"""
    by = {r['off']: r for r in rows}
    done = set(); n = 0
    for lo, hi in EXE_BLOCKS:
        items = []; o = lo
        while o < hi:
            e = x.index(X.NUL, o)
            items.append((o, bytes(x[o:e]))); o = e + 1
        if not any(o in by for o, _ in items):
            continue
        blob = b''
        for o, raw in items:
            blob += (encode(by[o]['toks'], kmap, hmap) if o in by else raw) + X.NUL
            done.add(o)
        if len(blob) > hi - lo:
            raise RuleError('실행 파일 묶음 %X‥%X: %d B > %d B' % (lo, hi, len(blob), hi - lo))
        x[lo:hi] = blob + bytes(hi - lo - len(blob)); n += 1
    for r in rows:
        if r['off'] in done:
            continue
        b = encode(r['toks'], kmap, hmap)
        if len(b) > r['budget']:
            raise RuleError('%s 실행 파일 %X: %d B > 원문 %d B' % (r['id'], r['off'], len(b), r['budget']))
        x[r['off']:r['off'] + r['budget']] = b + b' ' * (r['budget'] - len(b))
    print('실행 파일: %d줄 (묶음 %d개 다시 이음)' % (len(rows), n))


if __name__ == '__main__':
    try:
        main()
    except RuleError as e:
        print('✗', e); sys.exit(1)
