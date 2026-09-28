# -*- coding: utf-8 -*-
r"""린다 큐브 — 받은 번역 자동 손질 (2026-09-28)
  python tools/trfix.py   (work/trcheck/norm → work/trcheck/fixed, 손질 기록 work/trcheck/fixlog.tsv, 남은 위반 work/trcheck/남은위반.tsv)
  ① 부호 뒤 공백 1칸 삭제(build.normalize — 2칸 이상은 둠)
  ② 숫자 인수 토큰 바로 뒤 ASCII 숫자가 인수에 붙어 버린 것(«{02}29192» ← 원문 {02}29 + «１９２») → 붙은 숫자를 전각으로
  ③ 번역의 제어 순서가 원문 순서의 «부분열»이면(번역가가 {10}·{17} 을 빠뜨림) 빠진 토큰을 되살림:
     앞뒤 살아 있는 토큰 사이에서 원문 글자 위치 비율로 자리를 잡고, 가까운 낱말 경계(공백·＿·부호 뒤·줄 끝)로 붙임.
     원문에서 끝 토큰(뒤에 글자 없음)이면 번역 끝에.
  ④ 대사 쪽이 줄 폭을 넘으면 그 쪽만 다시 접음: 줄을 공백으로 이어(부호 뒤면 공백 없이) 18칸(원문이 더 길면 원문 한도)에
     낱말 경계로 탐욕 접기. 쪽 줄 수가 한도를 넘으면 접지 않고 남은위반에(손으로 줄임). ⛔글자 단위로 자르지 않음.
  ⑤ 그 밖(순서 뒤바뀜·원문에 없는 토큰)은 손대지 않고 남은위반에.
"""
import csv, glob, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build as B
X = B.X
SRC = os.path.join(ROOT, 'work', 'trcheck', 'norm')
OUT = os.path.join(ROOT, 'work', 'trcheck', 'fixed')
BS = chr(92)
FW = str.maketrans('0123456789', '０１２３４５６７８９')
BREAK_AFTER = set(B.PUNCT) | {' ', '＿'}
SPACE = '--space' in sys.argv                # ＿(전각 빈칸)으로 쓴 띄어쓰기 → 반각 공백
# 용어 통일(2026-09-28, tools/termscan.py 로 찾아 다수·원음 쪽으로) — (틀린 꼴 정규식, 바른 꼴, 원문 조건)
TERMS = [
    (r'비스찬|비스챤|비스챈', '비스천', None), (r'네오케니아', '네오케냐', None), (r'판하임', '팬하임', None),
    (r'갈렉스', '가렉스', None), (r'스퍼름리나|스파무리나', '스퍼머리나', None), (r'오즈삿', '오즈샛', None),
    (r'핫슬', '허슬', None), (r'포메랑', '포메란', None), (r'데미지', '대미지', None), (r'더그폰드', '다그폰드', None),
    (r'트리클로스', '트리크로스', None), (r'우르마', '우루마', None), (r'코랄코라나', '코랄콜라나', None),
    (r'네부르', '네뷸', None), (r'루리나 타워', '루리나스 타워', None), (r'마블 폴리스', '마블폴리스', None),
    (r'리나밸리', '리나 밸리', None), (r'네블', '네뷸', 'ネブール'), (r'촌장|시장', '읍장', '町長'),
]
CHARS = {'·': '・', '―': '－', '—': 'ー'}    # 글꼴에 없는(또는 딴 글자로 가는) 부호 → 원문에 쓰인 부호
AUTO_RESTORE = {0x10, 0x17}          # 말 속도·입 모양(?) — 빠뜨려도 뜻은 안 바뀌는 것만 자동 복원


def ser(toks):
    s = []
    for k, v, x in toks:
        if k == 'ctl':
            s.append('\\n' if v == 0x0D else '{%02X}%s' % (v, x.decode()))
        elif isinstance(v, str):
            s.append(v)
        else:
            s.append('{%s}' % v.hex().upper())
    return ''.join(s)


def seq_idx(toks):
    return [i for i, (k, v, _) in enumerate(toks) if k == 'ctl' and v not in B.FREE_CTL]


def fix_digits(to, tt):
    """숫자 인수에 붙은 숫자 → 전각 글자로 떼어 냄"""
    so = B.ctl_seq(to); it = seq_idx(tt); changed = False
    if len(it) != len(so):
        return tt, False
    out = list(tt)
    for n, i in reversed(list(enumerate(it))):
        c, p = out[i][1], out[i][2]
        oc, op = so[n]
        if c == oc and p != op and c in B.DIGIT_PARAM and p.startswith(op):
            extra = p[len(op):].decode().translate(FW)
            out[i:i + 1] = [('ctl', c, op)] + [('ch', ch, False) for ch in extra]
            changed = True
    return out, changed


def wrap_half(o, t):
    """원문 {06}숫자{04}(반각 숫자 묶음)를 번역가가 벗겨 버린 것 → 번역의 같은 숫자에 다시 씌움(NFKC 로 비교)"""
    import unicodedata
    segs = re.findall(r'\{06\}([^{}]*?)\{04\}', o)
    have = len(re.findall(r'\{06\}', t))
    if not segs or have >= len(re.findall(r'\{06\}', o)):
        return t
    cur = 0; out = t
    for sg in segs:
        key = unicodedata.normalize('NFKC', sg).strip()
        if not key or re.search(r'[^0-9\-+/.:%, ]', key):
            continue
        pat = re.compile(r'(?<![0-9０-９{])' + ''.join('[%s%s]' % (re.escape(c), re.escape(chr(ord(c) + 0xFEE0)) if 0x21 <= ord(c) < 0x7F else re.escape(c)) for c in key) + r'(?![0-9０-９])')
        mm = pat.search(out, cur)
        if not mm:
            continue
        if out[max(0, mm.start() - 4):mm.start()] == '{06}':
            cur = mm.end(); continue
        rep = '{06}' + sg + '{04}'                   # 원문 묶음 그대로
        out = out[:mm.start()] + rep + out[mm.end():]
        cur = mm.start() + len(rep)
    return out


def restore_waits(o, t):
    """원문 쪽 끝 {12}(키 대기)를 번역가가 뺀 것 → 같은 번째 쪽 끝에"""
    op = o.split('{0C}'); tp = t.split('{0C}')
    if len(op) != len(tp) or o.count('{12}') == t.count('{12}'):
        return t
    NL = BS + 'n'
    def core_of(x):
        while x.endswith(NL):
            x = x[:-2]
        return x
    for i, (a, b) in enumerate(zip(op, tp)):
        if core_of(a).endswith('{12}') and '{12}' not in b:
            core = core_of(b); trail = b[len(core):]
            if a.endswith(NL) and not trail:
                trail = NL
            tp[i] = core + '{12}' + trail
    return '{0C}'.join(tp)


def restore_missing(to, tt):
    so = B.ctl_seq(to); st = B.ctl_seq(tt)
    import collections
    miss = collections.Counter(so) - collections.Counter(st)
    if collections.Counter(st) - collections.Counter(so) or any(c not in AUTO_RESTORE for c, _ in miss):
        return None                                   # {10}·{17} 말고 빠진 토큰(변수 {1E} 등)이나 더 들어간 토큰은 손으로
    # 부분열 짝짓기(앞에서부터 탐욕)
    match = []; j = 0
    for n, s in enumerate(st):
        while j < len(so) and so[j] != s:
            j += 1
        if j == len(so):
            return None
        match.append(j); j += 1
    oi = seq_idx(to); ti = seq_idx(tt)
    # 원문 토큰의 «글자 위치»
    def charpos(toks):
        pos = []; n = 0
        for k, v, x in toks:
            pos.append(n)
            if k == 'ch':
                n += 1
        return pos, n
    opos, olen = charpos(to); tpos, tlen = charpos(tt)
    ins = []                                          # (번역 토큰 자리, 토큰)
    matched = dict(zip(match, ti))
    for k in range(len(so)):
        if k in matched:
            continue
        prev = max([m for m in matched if m < k], default=None)
        nxt = min([m for m in matched if m > k], default=None)
        o_lo = opos[oi[prev]] if prev is not None else 0
        o_hi = opos[oi[nxt]] if nxt is not None else olen
        t_lo = matched[prev] + 1 if prev is not None else 0
        t_hi = matched[nxt] if nxt is not None else len(tt)
        o_here = opos[oi[k]]
        if nxt is None and o_here >= olen:            # 원문 끝 토큰 → 번역 끝(끝 줄바꿈·쪽 앞)
            ins.append((t_hi, ('ctl', so[k][0], so[k][1]), k)); continue
        if prev is None and o_here == 0:
            ins.append((t_lo, ('ctl', so[k][0], so[k][1]), k)); continue
        r = (o_here - o_lo) / (o_hi - o_lo) if o_hi > o_lo else 0.5
        c_lo = tpos[t_lo] if t_lo < len(tt) else tlen
        c_hi = tpos[t_hi] if t_hi < len(tt) else tlen
        want = c_lo + r * (c_hi - c_lo)
        # 후보: t_lo‥t_hi 사이 토큰 자리 중 낱말 경계
        cands = []
        for p in range(t_lo, t_hi + 1):
            prevtok = tt[p - 1] if p > 0 else None
            b = (p == t_lo or p == t_hi or prevtok is None or
                 (prevtok[0] == 'ch' and isinstance(prevtok[1], str) and prevtok[1] in BREAK_AFTER) or
                 (prevtok[0] == 'ctl' and prevtok[1] in B.FREE_CTL) or
                 (p < len(tt) and tt[p][0] == 'ctl' and tt[p][1] in B.FREE_CTL))
            if b:
                cp = tpos[p] if p < len(tt) else tlen
                cands.append((abs(cp - want), p))
        p = min(cands)[1]
        ins.append((p, ('ctl', so[k][0], so[k][1]), k))
    out = list(tt)
    for p, tok, k in sorted(ins, key=lambda z: (z[0], z[2]), reverse=True):
        out.insert(p, tok)
    # 같은 자리에 여럿 넣었을 때 원문 순서 보장
    if B.ctl_seq(out) != so:
        return None
    return guard_digits(out)


def guard_digits(tt):
    """숫자 인수 토큰 바로 뒤 ASCII 숫자 → 전각(안 그러면 인수에 붙어 읽힘)"""
    out = list(tt)
    for i in range(1, len(out)):
        k, v, x = out[i]
        if k == 'ch' and isinstance(v, str) and v.isdigit() and ord(v) < 0x80:
            j = i - 1
            while j >= 0 and out[j][0] == 'ch' and isinstance(out[j][1], str) and out[j][1] in '０１２３４５６７８９':
                j -= 1
            if j >= 0 and out[j][0] == 'ctl' and out[j][1] in B.DIGIT_PARAM:
                out[i] = ('ch', v.translate(FW), x)
    return out


def rewrap(to, tt, wmax, lmax):
    """넘치는 쪽만 다시 접기. 실패하면 None"""
    pages = [[]]
    for t in tt:
        if t[0] == 'ctl' and t[1] == 0x0C:
            pages.append([t]); continue
        pages[-1].append(t)
    out = []
    for pg in pages:
        ms = B.measure(pg)
        if not ms or (max(max(p) for p in ms) <= wmax and max(B.text_lines(p) for p in ms) <= lmax):
            out += pg; continue
        if any(t[0] == 'ctl' and t[1] in (0x15, 0x02, 0x09) for t in pg):
            return None                               # 위치 지정 쪽은 손으로
        # 선택지 줄({01} 이 든 첫 줄부터 끝까지)은 그대로 두고 그 앞 글만 다시 접음
        choice = []
        if any(t[0] == 'ctl' and t[1] == 0x01 for t in pg):
            i = next(n for n, t in enumerate(pg) if t[0] == 'ctl' and t[1] == 0x01)
            j = max([n for n in range(i) if pg[n][0] == 'ctl' and pg[n][1] == 0x0D] or [-1])
            if j < 0:
                return None
            choice = pg[j:]; pg = pg[:j]
            if B.measure(choice) and max(B.measure(choice)[0]) > wmax:
                return None
        head = []
        body = list(pg)
        if body and body[0][0] == 'ctl' and body[0][1] == 0x0C:
            head = [body.pop(0)]
        tail = []
        while body and body[-1][0] == 'ctl' and body[-1][1] == 0x0D:     # 쪽 끝 «{12}\n» 의 줄바꿈은 그대로
            tail.insert(0, body.pop())
        # 줄 이음: 0D → 공백(앞 글자가 부호/공백이면 없앰)
        flat = []
        for t in body:
            if t[0] == 'ctl' and t[1] == 0x0D:
                last = next((u for u in reversed(flat) if u[0] == 'ch'), None)
                if last is not None and not (isinstance(last[1], str) and last[1] in BREAK_AFTER):
                    flat.append(('ch', '＿', False))
                continue
            flat.append(t)
        flat = B.tokens_tr(B.normalize(ser(flat)))
        # 낱말 단위(끝이 BREAK_AFTER 인 글자까지)로 묶기
        words = []; cur = []
        for t in flat:
            cur.append(t)
            if t[0] == 'ch' and isinstance(t[1], str) and t[1] in BREAK_AFTER:
                words.append(cur); cur = []
        if cur:
            words.append(cur)
        def w_of(ts):
            m = B.measure(ts); return m[0][0] if m else 0

        def wrap(ws):
            lines = [[]]
            for wd in ws:
                trial = lines[-1] + wd
                core = list(trial)
                while core and core[-1][0] == 'ch' and core[-1][1] in (' ', '＿'):
                    core.pop()
                if lines[-1] and w_of(core) > wmax:
                    lines.append(list(wd))
                else:
                    lines[-1] = trial
            res = []
            for n, ln in enumerate(lines):
                while ln and ln[-1][0] == 'ch' and ln[-1][1] in (' ', '＿'):
                    ln.pop()
                if n:
                    res.append(('ctl', 0x0D, b''))
                res += ln
            return res, len(lines)

        def last_ch(wd):
            for t in reversed(wd):
                if t[0] == 'ch' and isinstance(t[1], str) and t[1] not in (' ', '＿'):
                    return t[1]
            return ''

        def paginate(ws):
            """[쪽 토큰…] — 문장 끝(. ! ? … ∥) > 쉼표 > 고르게 순으로 나눔"""
            res, n = wrap(ws)
            if n <= lmax:
                return [res]
            best = None
            for k in range(1, len(ws)):
                c = last_ch(ws[k - 1])
                if c in '．！？…∥.!?♪■':
                    pr = 0
                elif c in '다요야죠네까군라걸':
                    pr = 1
                elif c in '，、,고서면데며니만':
                    pr = 2
                else:
                    pr = 5
                r1, n1 = wrap(ws[:k])
                if n1 > lmax:
                    continue
                rest = paginate(ws[k:])
                if rest is None:
                    continue
                n2 = B.text_lines(B.measure(rest[0])[0])
                short = 3 if min(w_of(r1), B.measure(rest[0])[0][0]) < 8 and min(n1, n2) == 1 else 0
                score = (len(rest), pr + abs(n1 - n2) + short - w_of(r1) / 100)
                if best is None or score < best[0]:
                    best = (score, [r1] + rest)
            return best[1] if best else None

        if B.text_lines(B.measure(wrap(words)[0])[0]) > lmax and (choice or any(t[0] == 'ctl' and t[1] in (0x17, 0x01) for t in to)):
            return None
        pages_ = paginate(words)
        if pages_ is None:
            return None
        res = []
        for i, pt in enumerate(pages_):
            if i:
                res += [('ctl', 0x12, b''), ('ctl', 0x0D, b''), ('ctl', 0x0C, b'')]
            res += pt
        ms = B.measure(head + res + tail + choice)
        if max(w for p_ in ms for w in p_) > wmax or max(B.text_lines(p_) for p_ in ms) > lmax:
            return None
        out += head + res + tail + choice
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    os.makedirs(OUT, exist_ok=True)
    log = []; left = []
    manual = {}
    mp = os.path.join(ROOT, 'work', 'trcheck', 'manual.tsv')
    if os.path.exists(mp):
        for ln in open(mp, encoding='utf-8').read().splitlines()[1:]:
            if '\t' in ln:
                k, v = ln.split('\t', 1); manual[k] = v
    subs = {}                                          # 줄 안 일부만 바꿈: ID·바꿀 것·바꿀 말
    sp = os.path.join(ROOT, 'work', 'trcheck', 'manual_sub.tsv')
    if os.path.exists(sp):
        for ln in open(sp, encoding='utf-8').read().splitlines()[1:]:
            if ln.count('\t') == 2:
                k, a, b = ln.split('\t'); subs.setdefault(k, []).append((a.replace(' ', '＿'), b.replace(' ', '＿')))
    for p in sorted(glob.glob(os.path.join(SRC, 'linda3_*.tsv'))):
        rows = list(csv.reader(open(p, encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))
        for r in rows[1:]:
            rid, kind, o, t0 = r[0], r[1], r[4], r[5]
            raw = X.from_text(o)
            to = B.tokens_raw(raw)
            t = B.normalize(''.join(CHARS.get(ch, ch) for ch in t0)); terms_hit = []
            for a, b, cond in TERMS:
                if cond is None or cond in o:
                    t2 = re.sub(a, b, t)
                    if t2 != t:
                        t = t2; terms_hit.append(b)
            if SPACE:
                t = B.normalize(re.sub(r'(?<=[가-힣!?,.…」』)~∥！？，．～])＿(?=[가-힣「『(0-9０-９A-Za-zＡ-Ｚ…{])', ' ', t))
            t = ser([('ch', '＿', False) if (k == 'ch' and v == ' ' and not x) else (k, v, x) for k, v, x in B.tokens_tr(t)])
            t1 = restore_waits(o, wrap_half(o, t))
            if t1 != t:
                t = t1; pre = ['반각·대기복원']
            else:
                pre = []
            tt = B.tokens_tr(t)
            assert ser(tt) == t, (rid, t)
            what = list(pre) + (['용어'] if terms_hit else [])
            if B.normalize(t0) != t0:
                what.append('부호뒤공백')
            if B.ctl_seq(to) != B.ctl_seq(tt):
                tt2, ch = fix_digits(to, tt)
                if ch:
                    tt = tt2; what.append('숫자인수')
                if B.ctl_seq(to) != B.ctl_seq(tt):
                    tt2 = restore_missing(to, tt)
                    if tt2 is not None:
                        tt = tt2; what.append('토큰복원')
            tt = guard_digits(tt)
            try:
                B.check(rid, kind, raw, ser(tt))
            except B.RuleError as e:
                msg = str(e)
                if ('줄 폭' in msg or '쪽당' in msg) and '위치 지정' not in msg and B.limits(kind, to):
                    wmax, lmax = B.limits(kind, to)
                    tt2 = rewrap(to, tt, wmax, lmax)
                    if tt2 is not None:
                        tt = tt2; what.append('다시접기')
            t = ser(tt)
            for a, b in subs.get(rid, []):
                if a not in t:
                    sys.exit('⛔manual_sub %s: «%s» 없음' % (rid, a))
                t = t.replace(a, b); what.append('부분손질')
            if rid in manual:
                t = B.normalize(manual[rid]); what.append('손질')
            # ★띄어쓰기 = ＿(반 칸, 2B) — 반각 공백 ' ' 는 전각 모드에서 1칸이라 넓다(2026-09-28 실기). 반각 구간 {06}…{04} 안은 그대로
            t = ser([('ch', '＿', False) if (k == 'ch' and v == ' ' and not x) else (k, v, x) for k, v, x in B.tokens_tr(t)])
            try:
                B.check(rid, kind, raw, t)
            except B.RuleError as e:
                left.append((os.path.basename(p)[:10], rid, kind, str(e).split('\n')[0], o, t))
            if what:
                log.append((os.path.basename(p)[:10], rid, '+'.join(what), t0, t))
            r[5] = t
        with open(os.path.join(OUT, os.path.basename(p)), 'w', encoding='utf-8', newline='\n') as f:
            f.write(''.join('\t'.join(x) + '\n' for x in rows))
    d = os.path.join(ROOT, 'work', 'trcheck')
    with open(os.path.join(d, 'fixlog.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('파일\tID\t손질\t받은 것\t고친 것\n' + ''.join('\t'.join(x) + '\n' for x in log))
    with open(os.path.join(d, '남은위반.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('파일\tID\t종류\t위반\t원문\t번역\n' + ''.join('\t'.join(x) + '\n' for x in left))
    import collections
    c = collections.Counter(w for x in log for w in x[2].split('+'))
    lc = collections.Counter(x[3].split(' ')[1] for x in left)
    print('손질 %d줄 %s · 남은 위반 %d %s' % (len(log), dict(c), len(left), dict(lc)))


if __name__ == '__main__':
    main()
