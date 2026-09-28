# -*- coding: utf-8 -*-
r"""린다 큐브 — 용어 통일 후보 찾기 (2026-09-28)
  python tools/termscan.py [폴더=work/trcheck/fixed]
  원문 가타카나 낱말(3자 이상)·한자 낱말(2자 이상)이 3줄 이상에 나오면, 그 줄들 번역의 한글 낱말(조사 떼기 전 어절 앞부분) 중
  가장 많이 함께 나오는 것(대표)을 잡고, 대표가 없는 줄에서 대표와 닮은 낱말(앞 2자 같음·편집거리 ≤2)을 «흔들림»으로 적음.
  → work/trcheck/용어흔들림.tsv (원어 · 대표(줄 수) · 흔들린 꼴 · ID 목록)  — 자동 수정 안 함(사람이 고름)
"""
import csv, glob, os, re, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)


def ed(a, b):
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        p, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (ca != cb))
    return d[-1]


def words(t):
    t = re.sub(r'\{[0-9A-F]{2,4}\}\d*', ' ', t).replace('\\n', ' ')
    ws = set()
    for w in re.findall(r'[가-힣]+', t):
        for n in range(2, min(len(w), 6) + 1):
            ws.add(w[:n])
    return ws


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'work', 'trcheck', 'fixed')
    rows = []
    for p in sorted(glob.glob(os.path.join(src, 'linda3_*.tsv'))):
        rows += list(csv.reader(open(p, encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))[1:]
    occ = collections.defaultdict(list)
    for r in rows:
        o = re.sub(r'\{[0-9A-F]{2,4}\}\d*', '＿', r[4])
        for k in set(re.findall(r'[ァ-ヴー]{3,}', o)) | set(re.findall(r'[一-龥]{2,4}', o)):
            occ[k].append(r)
    out = []
    for k, rs in sorted(occ.items(), key=lambda z: -len(z[1])):
        if len(rs) < 3:
            continue
        ws = [words(r[5]) for r in rs]
        c = collections.Counter(w for s in ws for w in s)
        if not c:
            continue
        # 대표: 가장 긴 것 중 줄 수가 최다에 가까운 것
        top = max(c.values())
        cand = [w for w, n in c.items() if n >= top * 0.9]
        rep = max(cand, key=lambda w: (len(w), c[w]))
        if c[rep] < len(rs) * 0.5 or c[rep] == len(rs):
            continue
        var = collections.defaultdict(list)
        for r, s in zip(rs, ws):
            if rep in s:
                continue
            sim = [w for w in s if len(w) >= 2 and w[0] == rep[0] and w != rep and ed(w, rep) <= max(1, len(rep) // 3)
                   and not w.startswith(rep) and not rep.startswith(w)]
            var[max(sim, key=len) if sim else '(없음)'].append(r[0])
        if any(v != '(없음)' for v in var):
            out.append((k, '%s(%d/%d)' % (rep, c[rep], len(rs)),
                        ' · '.join('%s:%s' % (v, ','.join(ids[:8])) for v, ids in sorted(var.items(), key=lambda z: -len(z[1])))))
    with open(os.path.join(ROOT, 'work', 'trcheck', '용어흔들림.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('원어\t대표\t흔들림(꼴:ID)\n' + ''.join('\t'.join(x) + '\n' for x in out))
    print('후보 %d' % len(out))


if __name__ == '__main__':
    main()
