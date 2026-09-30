# -*- coding: utf-8 -*-
"""메뉴·시스템 묶음(D1·F6·11B) 길이 고정용 문장 다듬기 (2026-09-30).
   세 묶음이 RAM 0x222900 에 올라가고 원본이 0x234D80(전투 묶음 데이터) 바로 앞에서 끝남 → PROG 가 늘면
   끝의 FACE2·POKEBELL 이 덮여 부재중 전화 창이 빈칸 + 지도 깨짐·이동 불가. 좁은 판으로도 8 B 넘쳐 구역 26‥31 에서 줄임.
   백업 work/trcheck/tsv_before_systrim/ · 대조 sys_trim_diff.tsv
   python sys_trim.py [--write]"""
import glob, os, shutil, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
R = [
    ('00228', '별것＿없음', '없음'),                                   # 特になし
    ('00243', '덫을＿스스로＿만드는', '덫을＿직접＿만드는'),            # 00236·00237 과 같은 말
    ('00218', '현재＿달성＿수', '현재＿달성수'),
    ('00219', '현재＿달성＿수', '현재＿달성수'),
    ('00206', '아이템＿팩에는', '아이템팩에는'),
    ('00070', '자동응답＿전화＿수신＿', '자동응답＿수신＿'),           # 留守番コール入電 — {15}K 창은 좁히지 않아 ＿ 유지분만큼(2026-09-30)
]
w = '--write' in sys.argv
tdir = os.path.join(ROOT, 'my files', 'tsv')
bak = os.path.join(ROOT, 'work', 'trcheck', 'tsv_before_systrim')
if w and not os.path.exists(bak):
    shutil.copytree(tdir, bak)
hit = {}; diff = ['ID\t전\t후']
for f in sorted(glob.glob(os.path.join(tdir, 'linda3_0*.tsv'))):
    lines = open(f, encoding='utf-8').read().split('\n')
    ch = False
    for i, ln in enumerate(lines):
        c = ln.split('\t')
        if len(c) < 6:
            continue
        for k, (rid, a, b) in enumerate(R):
            if c[0] == rid and a in c[5]:
                before = c[5]
                c[5] = c[5].replace(a, b, 1); hit[k] = hit.get(k, 0) + 1; ch = True
                diff.append('%s\t%s\t%s' % (rid, before, c[5]))
        lines[i] = '\t'.join(c)
    if ch and w:
        open(f, 'w', encoding='utf-8').write('\n'.join(lines))
if w:
    open(os.path.join(ROOT, 'work', 'trcheck', 'sys_trim_diff.tsv'), 'w', encoding='utf-8').write('\n'.join(diff) + '\n')
print('적용 %d / %d' % (len(hit), len(R)))
for k in range(len(R)):
    if k not in hit:
        print('못 찾음', R[k])
