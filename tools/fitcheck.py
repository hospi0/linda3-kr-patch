# -*- coding: utf-8 -*-
r"""린다 큐브 — 손으로 고친 번역 줄 검사 (2026-09-28)
  python tools/fitcheck.py 파일.tsv   (ID \t 번역, 줄바꿈 = 글자 \n)
  원문을 my files/tsv 에서 찾아 빌더 규칙(build.check)으로 검사하고, 쪽마다 줄 폭을 찍음. 통과 못 하면 ✗.
"""
import csv, glob, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build as B


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    src = {}
    for p in glob.glob(os.path.join(ROOT, 'my files', 'tsv', 'linda3_0*.tsv')):
        for r in list(csv.reader(open(p, encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))[1:]:
            src[r[0]] = r
    bad = 0
    for ln in open(sys.argv[1], encoding='utf-8').read().splitlines()[1:]:
        if '\t' not in ln:
            continue
        i, t = ln.split('\t', 1)
        r = src[i]; raw = B.X.from_text(r[4]); t = B.normalize(t)
        try:
            tt = B.check(i, r[1], raw, t); ok = '✓'
        except B.RuleError as e:
            tt = B.tokens_tr(t); ok = '✗ ' + str(e).split('\n')[0]; bad += 1
        lim = B.limits(r[1], B.tokens_raw(raw))
        ws = ' | '.join(','.join('%g' % w for w in p) for p in B.measure(tt))
        if ok != '✓' or '-v' in sys.argv:
            print(i, ok, '한도', lim, '폭', ws)
    print('실패', bad)


if __name__ == '__main__':
    main()
