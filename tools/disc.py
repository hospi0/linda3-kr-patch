# -*- coding: utf-8 -*-
r"""린다 큐브 완전판 디스크(트랙 1 MODE1 / 트랙 2 MODE2, 2352) 읽기 — ISO9660, 디렉터리 포함
  python tools/disc.py ls              → 파일 목록(경로 LBA 크기)
  python tools/disc.py get [접두…]     → work/disc/ 에 뽑기(접두 없으면 CPK·SND·CDDA 뺀 전부)
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
ROM = r'C:\claude\roms\ss\완료\Linda^3 Kanzenban (Japan)\Linda^3 Kanzenban (Japan) (Track 1).bin'
SKIP = ('/CPK/', '/ENDCPK/', '/SND/', '/CDDA')


class Disc:
    def __init__(self, path=ROM):
        self.f = open(path, 'rb')

    def sec(self, l, n=1):
        out = bytearray()
        for i in range(n):
            self.f.seek((l + i) * 2352 + 16); out += self.f.read(2048)
        return bytes(out)

    def files(self):
        root = self.sec(16)[156:190]
        out = []

        def walk(l, s, base):
            d = self.sec(l, (s + 2047) // 2048); i = 0
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
                        out.append((base + '/' + name, ll, ss))
                i += n
        walk(struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0], '')
        return out

    def read(self, path):
        for nm, l, s in self.files():
            if nm == path:
                return self.sec(l, (s + 2047) // 2048)[:s]
        raise KeyError(path)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    D = Disc()
    if sys.argv[1] == 'ls':
        for nm, l, s in D.files():
            print('%-28s %7d %10d' % (nm, l, s))
    elif sys.argv[1] == 'get':
        pre = tuple(sys.argv[2:])
        out = os.path.join(ROOT, 'work', 'disc'); k = 0
        for nm, l, s in D.files():
            if (pre and nm.startswith(pre)) or (not pre and not nm.startswith(SKIP)):
                p = os.path.join(out, nm.strip('/').replace('/', os.sep))
                os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, 'wb').write(D.sec(l, (s + 2047) // 2048)[:s]); k += 1
        print(k, '개 →', out)
