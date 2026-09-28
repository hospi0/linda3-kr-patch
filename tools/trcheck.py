# -*- coding: utf-8 -*-
r"""린다 큐브 — 받은 번역 정규화·대조 (2026-09-28)
  python tools/trcheck.py "my files/린다번역/린다번역"
  · 파일 이름 앞 10자(linda3_NNN)로 원본 my files/tsv/linda3_NNN.tsv 와 짝 → 줄마다 ID·종류·공유·첫위치·원문 이 원본과 같은지
    (다르면 원본 값을 쓰고 목록에 적음 — 빌더는 원문을 열쇠로 번역을 찾으므로 원문이 틀리면 번역이 조용히 버려진다)
  · CRLF·BOM·끝 공백 정리, 번역 칸의 실개행·탭 금지, 이중 이스케이프(\\n) → \n
  → work/trcheck/norm/linda3_NNN.tsv (원본 열 + 번역) · work/trcheck/대조.tsv(어긋난 칸) · 빈 번역 목록
"""
import csv, glob, io, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, 'my files', 'tsv')
OUT = os.path.join(ROOT, 'work', 'trcheck', 'norm')
BS = chr(92)


def rows_of(p):
    t = open(p, 'rb').read().decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
    return list(csv.reader(io.StringIO(t), delimiter='\t', quoting=csv.QUOTE_NONE))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    src_dir = sys.argv[1]
    os.makedirs(OUT, exist_ok=True)
    diffs = []; empty = []; tot = done = 0; seen = set()
    for p in sorted(glob.glob(os.path.join(src_dir, '*.tsv'))):
        key = os.path.basename(p)[:10]
        orig = rows_of(os.path.join(SRC, key + '.tsv'))
        got = rows_of(p)
        if len(orig) != len(got):
            sys.exit('⛔%s: 행 수 %d ≠ 원본 %d' % (p, len(got), len(orig)))
        seen.add(key); out = [orig[0]]
        for o, g in zip(orig[1:], got[1:]):
            tot += 1
            for k in range(5):
                if k < len(g) and g[k] != o[k]:
                    diffs.append((key, o[0], ['ID', '종류', '공유', '첫위치', '원문'][k], o[k], g[k]))
            tr = g[5].strip() if len(g) > 5 else ''
            tr = tr.replace(BS + BS + 'n', BS + 'n')
            if '\t' in tr or '\n' in tr:
                sys.exit('⛔%s %s: 번역 칸에 탭·실개행' % (key, o[0]))
            if tr:
                done += 1
            else:
                empty.append((key, o[0], o[4]))
            out.append(o[:5] + [tr])
        with open(os.path.join(OUT, key + '.tsv'), 'w', encoding='utf-8', newline='\n') as f:
            f.write(''.join('\t'.join(r) + '\n' for r in out))
    missing = sorted({os.path.basename(p)[:10] for p in glob.glob(os.path.join(SRC, 'linda3_0*.tsv'))} - seen)
    with open(os.path.join(ROOT, 'work', 'trcheck', '대조.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('파일\tID\t칸\t원본\t받은 것\n' + ''.join('\t'.join(d) + '\n' for d in diffs))
    with open(os.path.join(ROOT, 'work', 'trcheck', '빈번역.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('파일\tID\t원문\n' + ''.join('\t'.join(e) + '\n' for e in empty))
    print('파일 %d · 줄 %d · 번역 %d · 빈 번역 %d · 원본과 다른 칸 %d · 안 받은 파일 %s' % (len(seen), tot, done, len(empty), len(diffs), missing))


if __name__ == '__main__':
    main()
