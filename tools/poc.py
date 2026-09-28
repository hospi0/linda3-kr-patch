# -*- coding: utf-8 -*-
r"""린다 큐브 완전판 PoC (2026-09-28) — 타이틀 메뉴·첫 대사·메뉴 화면 일부를 한글로
  글꼴: 00SL.BIN 0x54634, 12×12 1비트, 4글자 섞은 72B 묶음(글자 k 의 픽셀 p = 비트 4×(3−p)+k), 1,907칸
  SJIS → 칸 번호: 표1 0x53320(u16 줄 위치) · 표2 0x53374(바이트 + 줄 끝 u16 기준)
  PoC 는 필요한 한글 음절만 «드문 한자 칸»(번호 끝쪽)에 덮어 그리고, 그 칸의 SJIS 코드로 글을 제자리(같은 바이트 수) 교체
  글자 = 갈무리11(12×12 칸)
  python tools/poc.py [--write]  → work/kr/00SL.BIN · work/kr/LINDA.MIC (· --write: 트랙 1 → work/out, F: 는 따로 복사)
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, r'C:\claude\project\anearth-kr-patch\tools')
import bdf
GALMURI = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.bdf'
T1, T2, FONT, NGLYPH = 0x53320, 0x53374, 0x54634, 1907


def sj(s):
    return s.encode('cp932')


def code_index(x, code):
    hi, lo = code >> 8, code & 0xFF
    r = (hi - 0x81) if hi <= 0x9F else (hi - 0xC1)
    rb = struct.unpack_from('>H', x, T1 + 2 * r)[0]
    return x[T2 + rb + lo - 0x40] + struct.unpack_from('>H', x, T2 + rb + 0xBE)[0]


def put_glyph(x, i, rows):
    """rows = 12줄 × 12칸(0/1) → 글꼴 칸 i 에 쓴다(같은 묶음의 다른 3글자 비트는 그대로)"""
    g = FONT + (i >> 2) * 0x48; k = i & 3
    for r in range(12):
        for w in range(3):
            o = g + r * 6 + w * 2
            v = struct.unpack_from('>H', x, o)[0]
            for p in range(4):
                bit = 4 * (3 - p) + k
                v = (v | (1 << bit)) if rows[r][w * 4 + p] else (v & ~(1 << bit))
            struct.pack_into('>H', x, o, v)


def hangul_rows(F, ch):
    pts, _ = F.draw(ch, 0, 0)
    ys = [y for _, y in pts]; dy = (12 - (max(ys) - min(ys) + 1)) // 2 - min(ys)
    xs = [x for x, _ in pts]; dx = (12 - (max(xs) - min(xs) + 1)) // 2 - min(xs)
    rows = [[0] * 12 for _ in range(12)]
    for x, y in pts:
        if 0 <= x + dx < 12 and 0 <= y + dy < 12:
            rows[y + dy][x + dx] = 1
    return rows


# (원문, 한글) — 글자 수 같게(＿ = 화면 빈칸, 원문 그대로 쓰는 부호는 한글 쪽에도 그대로)
MIC_REPL = [
    ('メニュー選択', '메뉴＿선택＿'),
    ('難易度調整', '난이도조정'),
    ('国分名人と競争', '코쿠분과＿대결'),
    ('ボタンで情報を切り換えます', '버튼으로＿정보를＿바꿉니다'),
]
# 메뉴 탭 줄(여러 벌) 안에서만 바꿀 낱말
TAB_LINE = bytes.fromhex('0104'.replace(' ', '')) if False else None
TABS = [('道具', '도구'), ('装備', '장비'), ('能力', '능력'), ('猟犬', '엽견'), ('情報', '정보')]
HTABS = [('ナビＳ', '나비Ｓ')]          # 탭 줄 안 반각(06) 구간

# ── 반각(제어 06) 글꼴: 00SL.BIN 0x5D65C, 8×12 1비트, 4글자 섞은 48B 묶음(줄마다 u32, 글자 k 의 픽셀 p = 비트 4×(7−p)+k), 320칸
#    SJIS → 반각 번호(0x06006DAC): 815B→0xB0 · 8140‥81AB 바이트표 0x5EABC · 824F‥82F1 u16표 0x5E8C8 · 8340‥8396 u16표 0x5EA0E · 그 밖(한자) 0 = 안 그림
#    그래서 반각 글의 한글은 «반각 가나 칸»에 콘덴스드 7×11 로 그리고, 그 칸을 가리키는 가나 코드로 쓴다
HFONT, HMAP_B, HMAP_H, HMAP_K = 0x5D65C, 0x5EABC, 0x5E8C8, 0x5EA0E
GALMURI_C = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11-Condensed.bdf'
# 이름 묶음(NUL 로 이어 붙인 목록, 표 0x633CC 는 묶음 시작만 가리킴 → 묶음 길이만 지키면 이름 길이는 자유)
SEASON_BLK = (0x60C24, ['춘', '하', '추', '동'])                                  # 전각
NAME_BLK = (0x60C30, ['켄', '린다', ('흄',), '사치코', '스미레', '자신', '', ''])  # ('…',) = 06…04 반각
ANIMAL_BLK_END = 0x60F9C
ANIMALS = ('인간 돼지 코뿔소 사자 코알라 호랑이 양 멧돼지 성게 사마귀 개미 코끼리 바이슨 트리케라 드래곤 기린 원숭이 쥐 개 늑대 '
           '고릴라 하이에나 뱀 히드라 청개구리 구더기 도마뱀 잠자리 흰나비 0 박쥐 독수리 무당벌레 벌 까마귀 고양이 프테라노 호랑나비 '
           '장어 쑤기미 메기 내장 해파리 상어 가오리 바다사자 가물치 새우 1 잉어 해삼 백곰 게 오징어 악어 돌고래 개구리 하마 거머리 '
           '2 3 아귀 여우 순록 염소 펭귄 곰 족제비 물범 문어 수달 벼룩 아르마딜 전갈 낙타 펠리컨 캥거루 거미 지네 토끼 얼룩말 메뚜기 '
           '닭 매미 버펄로 영양 물벼룩 두더지 4 너구리 개미핥기 표범 바퀴벌레 카멜레오 5 오리 공작 거북 갯민숭이 달팽이 대합 타조 제비 '
           '다람쥐 아이아이 6 코브라 말 고래 7 판다 지렁이 사슴벌레 소라 복어 임팔라 방울벌레 개복치 소금쟁이 소라게 부엉이 괴물').split()
SEASON2 = 0x60524                   # 春··夏··秋··冬 (4바이트 간격) — 전각
HFMT = (' %sなみ', ' %s급')         # 실행 파일 0xE31C «06 ' ' %s なみ»(동물 이름 비교)
# MIC 반각 글 «06 원문 [04|0E|00|0D|0C]» — 한글이 짧으면 끝 제어 앞을 반각 빈칸으로(シナリオ 는 뒤에 A‥D 가 붙어 같은 길이로 앞만)
HALF_MIC = [('トランクルームメニュー', '트렁크룸메뉴'), ('トランスカーゴ', '트랜스카고'), ('トランクルーム', '트렁크룸'),
            ('サービス', '서비스'), ('シュート', '슈트'), ('バードライン', '버드라인'), ('ナレーション', '내레이션'),
            ('チャレンジャー', '챌린저'), ('サマー・ビート', '서머・비트'), ('リンダ', '린다'), ('テーマ', '테마'),
            ('オータム・ティア', '어텀・티어'), ('スプリング・ブレス', '스프링・브레스'), ('ジングルヘル ', '징글헬 '),
            ('ジングルベル ', '징글벨 '), ('ウィンター・ペイン', '윈터・페인'), ('ビシビシ', '척척'), ('シナリオ', '시나리오')]
HALF_END = b'\x04\x0e\x00\x0d\x0c'


def half_index(x, code):
    if code <= 0x140:
        return code
    if code == 0x815B:
        return 0xB0
    if 0x8140 <= code <= 0x81AB:
        return x[HMAP_B + code - 0x8140]
    if 0x824F <= code <= 0x82F1:
        return struct.unpack_from('>H', x, HMAP_H + 2 * (code - 0x824F))[0]
    if 0x8340 <= code <= 0x8396:
        return struct.unpack_from('>H', x, HMAP_K + 2 * (code - 0x8340))[0]
    return 0


def put_half(x, i, rows):
    """rows = 12줄 × 8칸 → 반각 칸 i"""
    g = HFONT + (i >> 2) * 48; k = i & 3
    for r in range(12):
        v = struct.unpack_from('>I', x, g + r * 4)[0]
        for p in range(8):
            bit = 4 * (7 - p) + k
            v = (v | (1 << bit)) if rows[r][p] else (v & ~(1 << bit))
        struct.pack_into('>I', x, g + r * 4, v)


def half_rows(F, ch):
    pts, _ = F.draw(ch, 0, 0)
    y0 = min(y for _, y in pts); x0 = min(x for x, _ in pts)
    rows = [[0] * 8 for _ in range(12)]
    for x, y in pts:
        if 0 <= x - x0 < 8 and 0 <= y - y0 < 12:
            rows[y - y0][x - x0] = 1
    return rows
EXE_REPL = [('攻撃', '공격'), ('守備', '수비'), ('素早', '민첩'), ('所持金', '소지금'), ('年　%s', '년　%s')]
# 첫 대사: 제어 코드 사이 글 조각을 차례로(조각마다 글자 수 같게)
DLG_SEGS = [('ケン', '켄！'), ('！＿', '＿언'), ('いつまで食べてんだい', '제까지＿먹고＿있을래'), ('！', '！'),
            ('また', '또＿'), ('＿', '지'), ('遅刻しちまうよ', '각하겠어！＿＿')]


def lentest(m, anchor):
    """메시지 번호 방식 시험(2026-09-28): 첫 대사가 든 방 구역에서 0번 메시지 앞 3글자(6B)를 지우고
       첫 대사 끝에 «！！！»(6B)를 붙인다 — 구역 길이 그대로, 첫 대사 시작만 6B 앞당겨짐.
       번호로 부르면 첫 대사가 «…！！！» 로 정상, 위치로 부르면 어긋나 깨짐."""
    i = m.find(anchor); n = 0
    while i >= 0:
        s = i // 2048
        while m[s * 2048:s * 2048 + 9] != b'PROG.BIN\x00':
            s -= 1
        prog = s * 2048 + (struct.unpack_from('<I', m, s * 2048 + 12)[0] >> 8)
        cnt = struct.unpack_from('<H', m, prog + 2)[0] - 8
        offs = [prog + struct.unpack_from('<H', m, prog + 8 + 2 * k)[0] for k in range(cnt)]
        a = max(o for o in offs if o <= i); b = min(o for o in offs if o > i)
        name_end = m.find(b'\x00', a)
        m0 = name_end + 1                                   # 0번 메시지
        assert m[m0] == 0x0C
        q = m0 + 1
        while m[q] < 0x81:                                  # 제어 코드 건너뛰기
            q += 1
        cut = bytes(m[q:q + 6]); assert all(c >= 0x81 for c in cut[::2]), cut.hex()
        end = m.find(b'\x00', i)
        new = m[a:q] + m[q + 6:end] + sj('！！！') + m[end:b]
        assert len(new) == b - a
        m[a:b] = new
        print('  길이 시험: 구역 %X‥%X 0번 메시지 «%s» 지움 · 첫 대사 끝 «！！！»' % (a, b, cut.decode('cp932')))
        n += 1
        i = m.find(anchor, b)
    print('  길이 시험 %d벌' % n)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    F = bdf.Font(GALMURI)
    x = bytearray(open(os.path.join(ROOT, 'work', 'disc', '00SL.BIN'), 'rb').read())
    m = bytearray(open(os.path.join(ROOT, 'work', 'disc', 'LINDA_LINDA.MIC'), 'rb').read())
    # 필요한 음절
    texts = [k for _, k in MIC_REPL + TABS + EXE_REPL + DLG_SEGS] + SEASON_BLK[1] + [n for n in NAME_BLK[1] if isinstance(n, str)]
    syl = sorted({c for t in texts for c in t if '가' <= c <= '힣'})
    # 칸 → 대표 SJIS 코드(2단계 한자 0x98‥0xEA 줄, 번호 큰 것부터)
    # PoC: 빈도 조사 없이 아무 칸이나(최종은 어차피 전 칸 한글) — PoC 문구에 남는 원문 글자(／ ！ Ｌ Ｒ ＿ 등) 칸만 피한다
    used_jp = {c for t in [a for a, _ in MIC_REPL + TABS + EXE_REPL + DLG_SEGS] + [b for _, b in MIC_REPL + TABS + EXE_REPL + DLG_SEGS]
               for c in t if not '가' <= c <= '힣'}
    used_slots = {code_index(x, int.from_bytes(sj(c), 'big')) for c in used_jp if len(sj(c)) == 2}
    slots = []
    for i in range(1000, NGLYPH):
        if i in used_slots:
            continue
        # 그 칸을 가리키는 한자 코드 하나(글을 쓸 때 쓸 코드)
        for hi in list(range(0x88, 0xA0)) + list(range(0xE0, 0xEB)):
            hit = None
            for lo in range(0x40, 0xFD):
                if lo == 0x7F:
                    continue
                if code_index(x, hi << 8 | lo) == i:
                    hit = hi << 8 | lo; break
            if hit:
                slots.append((i, hit)); break
        if len(slots) >= len(syl):
            break
    assert len(slots) >= len(syl)
    kmap = {}
    for ch, (i, c) in zip(syl, slots):
        put_glyph(x, i, hangul_rows(F, ch)); kmap[ch] = bytes([c >> 8, c & 0xFF])
    print('한글 %d음절 → 빌린 한자 칸 %s' % (len(syl), ''.join(bytes([c >> 8, c & 0xFF]).decode('cp932') for _, c in slots[:len(syl)])))

    def enc(t):
        return b''.join(kmap[c] if c in kmap else sj(c) for c in t)

    # 반각 한글: 반각 글은 전부 한글로 바꾸므로 가나 칸(0x80‥0x13F 중 기호 아닌 칸)을 모두 쓴다.
    #   운반 코드 = 가나 SJIS 코드, 반각 u16 변환표에서 그 코드 → 새 칸 번호로 다시 가리킨다
    FC = bdf.Font(GALMURI_C)
    htexts = [b for _, b in HTABS + HALF_MIC] + [HFMT[1]] + ANIMALS + [n[0] for n in NAME_BLK[1] if isinstance(n, tuple)]
    hsyl = sorted({c for t in htexts for c in t if '가' <= c <= '힣'})
    sym = {x[HMAP_B + i] for i in range(0x6C)} | {0xB0}
    pool = [i for i in range(0x80, 320) if i not in sym]
    carriers = list(range(0x8340, 0x8397)) + list(range(0x829F, 0x82F2)) + list(range(0x8281, 0x829B))   # + 전각 ａ‥ｚ(반각 글에 안 나옴)
    print('반각 한글 %d음절 / 칸 %d / 운반 코드 %d' % (len(hsyl), len(pool), len(carriers)))
    assert len(pool) >= len(hsyl) and len(carriers) >= len(hsyl)
    hmap = {}
    for ch, h, code in zip(hsyl, pool, carriers):
        put_half(x, h, half_rows(FC, ch)); hmap[ch] = bytes([code >> 8, code & 0xFF])
        o = HMAP_K + 2 * (code - 0x8340) if code >= 0x8340 else HMAP_H + 2 * (code - 0x824F)
        struct.pack_into('>H', x, o, h)
        assert half_index(x, code) == h

    def henc(t):
        return b''.join(hmap[c] if c in hmap else sj(c) for c in t)

    # 이름 묶음(전각 춘하추동 · 이름 · 반각 동물) — 묶음 길이는 원본과 같게, 남는 자리는 끝에 NUL
    def put_block(start, end, items):
        blob = b''
        for it in items:
            blob += (b'\x06' + henc(it[0]) + b'\x04' if isinstance(it, tuple) else enc(it)) + b'\x00'
        assert len(blob) <= end - start, (hex(start), len(blob), end - start)
        x[start:end] = blob + b'\x00' * (end - start - len(blob))
        print('  EXE 이름 묶음 %X: %d/%d B' % (start, len(blob), end - start))
    old = [p for p in bytes(x[0x60C5C:ANIMAL_BLK_END]).split(b'\x00')][:-1]
    assert len(old) == len(ANIMALS), (len(old), len(ANIMALS))
    put_block(SEASON_BLK[0], NAME_BLK[0], SEASON_BLK[1])
    put_block(NAME_BLK[0], 0x60C5C, NAME_BLK[1])
    blob = b''.join(henc(a) + b'\x00' for a in ANIMALS)
    assert len(blob) <= ANIMAL_BLK_END - 0x60C5C, len(blob)
    x[0x60C5C:ANIMAL_BLK_END] = blob + b'\x00' * (ANIMAL_BLK_END - 0x60C5C - len(blob))
    print('  EXE 동물 이름 %d개 %d/%d B' % (len(ANIMALS), len(blob), ANIMAL_BLK_END - 0x60C5C))
    for n, ch in enumerate(SEASON_BLK[1]):
        o = SEASON2 + 4 * n; assert x[o:o + 2] == sj('春夏秋冬'[n]); x[o:o + 2] = enc(ch)
    a, b = sj(HFMT[0]), henc(HFMT[1]); i = x.find(a); assert i > 0 and x.find(a, i + 1) < 0
    x[i:i + len(a)] = b + b'\x00' * (len(a) - len(b))

    def repl_all(buf, a, b, where):
        A, Bb = sj(a), enc(b)
        assert len(A) == len(Bb), (a, b)
        n = 0; i = buf.find(A)
        while i >= 0:
            buf[i:i + len(A)] = Bb; n += 1; i = buf.find(A, i + len(Bb))
        print('  %s «%s» → «%s» %d곳' % (where, a, b, n))
        return n
    for a, b in MIC_REPL:
        repl_all(m, a, b, 'MIC')
    for a, b in HALF_MIC:
        A, Bb = b'\x06' + sj(a), b'\x06' + henc(b)
        assert len(Bb) <= len(A), (a, b)
        Bb += b' ' * (len(A) - len(Bb)); n = 0; i = m.find(A)
        while i >= 0:
            if a == 'シナリオ' or m[i + len(A)] in HALF_END:
                m[i:i + len(A)] = Bb; n += 1
            i = m.find(A, i + len(A))
        print('  MIC 반각 «%s» → «%s» %d곳' % (a, b, n))
    # 메뉴 탭 줄: «道具　装備　…ナビＳ» 가 든 줄만
    tabs_jp = sj('道具') + b'\x0e\x81\x40\x01' + sj('装備')
    i = m.find(tabs_jp); nline = 0
    while i >= 0:
        j = m.find(b'\x12\x00', i)
        seg = bytearray(m[i:j])
        for a, b in TABS:
            A, Bb = sj(a), enc(b); seg = seg.replace(A, Bb)
        for a, b in HTABS:
            A, Bb = b'\x06' + sj(a), b'\x06' + henc(b); assert len(A) == len(Bb); seg = seg.replace(A, Bb)
        m[i:j] = seg; nline += 1
        i = m.find(tabs_jp, j)
    print('  MIC 메뉴 탭 줄 %d벌' % nline)
    # 첫 대사(세 벌)
    anchor = sj('ケン') + b'\x10\x30' + sj('！＿') + b'\x17\x39\x10\x31\x38' + sj('いつまで')   # «ケン！＿» 만으로는 다른 대사도 걸린다
    if '--lentest' in sys.argv:
        lentest(m, anchor)
    i = m.find(anchor); nd = 0
    while i >= 0:
        end = m.find(b'\x00', i)
        seg = bytearray(m[i:end]); p = 0
        for a, b in DLG_SEGS:
            A, Bb = sj(a), enc(b)
            q = seg.find(A, p); assert q >= 0 and len(A) == len(Bb), (a, b)
            seg[q:q + len(A)] = Bb; p = q + len(Bb)
        m[i:end] = seg; nd += 1
        i = m.find(anchor, end)
    print('  MIC 첫 대사 %d벌' % nd)
    for a, b in EXE_REPL:
        repl_all(x, a, b, 'EXE')
    import joken
    joken.apply(m)
    os.makedirs(os.path.join(ROOT, 'work', 'kr'), exist_ok=True)
    open(os.path.join(ROOT, 'work', 'kr', '00SL.BIN'), 'wb').write(x)
    open(os.path.join(ROOT, 'work', 'kr', 'LINDA.MIC'), 'wb').write(m)
    if '--write' in sys.argv:
        import inplace, disc
        out = os.path.join(ROOT, 'work', 'out'); os.makedirs(out, exist_ok=True)
        dst = os.path.join(out, os.path.basename(disc.ROM))
        inplace.patch(disc.ROM, dst, {'/00SL.BIN': bytes(x), '/LINDA/LINDA.MIC': bytes(m)})
        print('→', dst)


if __name__ == '__main__':
    main()
