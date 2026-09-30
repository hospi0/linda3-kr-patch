# -*- coding: utf-8 -*-
"""{1B} 동물 이름을 도감 목록(실행 파일 목록 0x17) 번역과 같은 말로 (2026-09-30).
   게임은 {1B} 뒤 글을 목록 항목과 바이트 비교해 동물 번호를 고름(못 찾으면 1번 돼지·4바이트) → 이름이 다르면 «돼지쥐» 처럼 깨짐.
   빌더 build.py 가 원문·번역 동물 번호를 대조해 막는다. 백업 work/trcheck/tsv_before_animalfix/ · 대조 animal_fix_diff.tsv
   python animal_fix.py [--write]"""
import glob, os, shutil, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
R = [
    ('00968', '{1B}흰곰도', '{1B}백곰도'),                   # シロクマ = 도감 «백곰»
    ('00989', '{1B}흰곰을', '{1B}백곰을'),
    ('01695', '{1B}북극곰', '{1B}백곰'),
    ('01699', '{1B}북극곰', '{1B}백곰'),
    ('02440', '{1B}버팔로', '{1B}버펄로'),                   # バファロ
    ('02905', '{1B}용과', '{1B}드래곤과'),                   # ドラゴン
    ('03537', '{1B}강아지＿우리에', '어린＿{1B}개＿우리에'),   # 子{1B}イヌ
    ('04192', '{1B}쏨뱅이를', '{1B}쑤기미를'),               # オコゼ
    ('05259', '{1B}곱창코끼리쯤', '{1B}내장쯤'),             # ゾウモツ
    ('05277', '{1B}큰바다사자', '{1B}바다사자'),             # トド
    ('05933', '{1B}숲청개구리', '{1B}청개구리'),             # モリアオ
    ('01558', '{1B}자는＿척이나', '{1B}너구리처럼＿자는＿척이나'),   # {1B}タヌキ寝入り
]
w = '--write' in sys.argv
tdir = os.path.join(ROOT, 'my files', 'tsv')
bak = os.path.join(ROOT, 'work', 'trcheck', 'tsv_before_animalfix')
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
                c[5] = c[5].replace(a, b); hit[k] = hit.get(k, 0) + 1; ch = True
                diff.append('%s\t%s\t%s' % (rid, before, c[5]))
        lines[i] = '\t'.join(c)
    if ch and w:
        open(f, 'w', encoding='utf-8').write('\n'.join(lines))
if w:
    open(os.path.join(ROOT, 'work', 'trcheck', 'animal_fix_diff.tsv'), 'w', encoding='utf-8').write('\n'.join(diff) + '\n')
print('적용 %d / %d' % (len(hit), len(R)))
for k in range(len(R)):
    if k not in hit:
        print('못 찾음', R[k])
