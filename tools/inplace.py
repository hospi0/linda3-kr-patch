# -*- coding: utf-8 -*-
r"""트랙 1(MODE1/2352) 파일 제자리 바꿔 넣기 (2026-09-27)
  새 파일은 원래 섹터 수 안이어야 한다(동영상 재굽기는 원본과 같은 크기로 0 채움) → 디렉터리·다른 트랙은 안 건드린다.
  쓴 섹터는 헤더(동기·MSF·모드 1) + EDC/ECC 재계산(anearth tools/cdmode1).
  python tools/inplace.py → work/out/…(Track 1).bin  (work/kr/cpk/*.CPK 를 /LINDA/ 에)
"""
import glob, os, shutil, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, r'C:\claude\project\anearth-kr-patch\tools')
import cdmode1, disc

SYNC = b'\x00' + b'\xff' * 10 + b'\x00'


def bcd(n):
    return (n // 10) << 4 | n % 10


def sector(lba, data):
    f = lba + 150
    s = bytearray(2352)
    s[0:16] = SYNC + bytes([bcd(f // 4500), bcd(f // 75 % 60), bcd(f % 75), 1])
    s[16:16 + len(data)] = data
    return bytes(cdmode1.fix(s))


def patch(src, dst, files):
    ent = {p: (l, s) for p, l, s in disc.Disc(src).files()}
    if os.path.abspath(src) != os.path.abspath(dst):
        shutil.copyfile(src, dst)
    with open(dst, 'r+b') as fh:
        for p, d in files.items():
            l, s = ent[p]
            assert len(d) <= (s + 2047) // 2048 * 2048, (p, len(d), s)
            d = d + bytes(-len(d) % 2048)
            for k in range(len(d) // 2048):
                fh.seek((l + k) * 2352); fh.write(sector(l + k, d[k * 2048:(k + 1) * 2048]))
    # 되읽기 검사
    D = disc.Disc(dst)
    try:
        for p, d in files.items():
            l, s = ent[p]
            assert D.sec(l, (s + 2047) // 2048)[:len(d)] == d, p
    finally:
        D.f.close()


def dir_records(fh):
    """{경로: (디렉터리 LBA, 기록 위치(디렉터리 안), 파일 LBA, 크기)}"""
    def user(l, n=1):
        out = bytearray()
        for i in range(n):
            fh.seek((l + i) * 2352 + 16); out += fh.read(2048)
        return out
    root = user(16)[156:190]
    res = {}

    def walk(l, s, base):
        d = user(l, (s + 2047) // 2048); i = 0
        while i < len(d):
            n = d[i]
            if n == 0:
                i = (i // 2048 + 1) * 2048; continue
            rec = d[i:i + n]
            ll, ss = struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0]
            nl = rec[32]; name = rec[33:33 + nl].decode('latin1').split(';')[0]
            if name not in ('\x00', '\x01'):
                if rec[25] & 2:
                    walk(ll, ss, base + '/' + name)
                else:
                    res[base + '/' + name] = (l, i, ll, ss)
            i += n
    walk(struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0], '')
    return res, user


def patch_layout(src, dst, files):
    """files = {경로: (새 LBA, 데이터)} — 옮기거나 크기가 바뀌는 파일. 디렉터리 기록 LBA·크기(양 엔디안) 갱신.
       겹침 검사: 새 자리들이 서로·다른 파일과 겹치지 않아야 함. 트랙 길이·다른 파일 위치는 그대로."""
    shutil.copyfile(src, dst)
    with open(dst, 'r+b') as fh:
        recs, user = dir_records(fh)
        spans = {p: (l, (s + 2047) // 2048) for p, (_, _, l, s) in recs.items() if p not in files}
        spans.update({p: (l, (len(d) + 2047) // 2048) for p, (l, d) in files.items()})
        iv = sorted((l, l + n, p) for p, (l, n) in spans.items() if n)
        for (a1, b1, p1), (a2, b2, p2) in zip(iv, iv[1:]):
            assert b1 <= a2, ('겹침', p1, p2, a1, b1, a2)
        dirs = {}
        for p, (l, d) in files.items():
            dl, off, _, _ = recs[p]
            if dl not in dirs:
                dirs[dl] = user(dl, 8)
            dd = dirs[dl]
            struct.pack_into('<I', dd, off + 2, l); struct.pack_into('>I', dd, off + 6, l)
            struct.pack_into('<I', dd, off + 10, len(d)); struct.pack_into('>I', dd, off + 14, len(d))
            pad = d + bytes(-len(d) % 2048)
            for k in range(len(pad) // 2048):
                fh.seek((l + k) * 2352); fh.write(sector(l + k, pad[k * 2048:(k + 1) * 2048]))
        for dl, dd in dirs.items():
            for k in range(len(dd) // 2048):
                fh.seek((dl + k) * 2352 + 16); cur = fh.read(2048)
                if cur != bytes(dd[k * 2048:(k + 1) * 2048]):
                    fh.seek((dl + k) * 2352); fh.write(sector(dl + k, bytes(dd[k * 2048:(k + 1) * 2048])))
    D = disc.Disc(dst)
    try:
        for p, (l, d) in files.items():
            assert D.read(p) == d, ('되읽기', p)
    finally:
        D.f.close()


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    files = {'/LINDA/' + os.path.basename(f): open(f, 'rb').read() for f in sorted(glob.glob(os.path.join(ROOT, 'work', 'kr', 'cpk', '*.CPK')))}
    out = os.path.join(ROOT, 'work', 'out'); os.makedirs(out, exist_ok=True)
    dst = os.path.join(out, os.path.basename(disc.ROM))
    patch(disc.ROM, dst, files)
    print('파일 %d개 → %s' % (len(files), dst))


if __name__ == '__main__':
    main()
