# -*- coding: utf-8 -*-
r"""PS1 판(Linda³ Again, MODE2/2352 한 트랙) ISO9660 읽기
  python tools/psxdisc.py ls [bin]
"""
import os, struct, sys
ROM_EN = r'C:\claude\roms\ps\Linda3 Again (English v0.95.9)\Linda3 Again (English v0.95.9).bin'


class Disc:
    def __init__(self, path=ROM_EN):
        self.f = open(path, 'rb')

    def sec(self, l, n=1):
        out = bytearray()
        for i in range(n):
            self.f.seek((l + i) * 2352 + 24); out += self.f.read(2048)
        return bytes(out)

    def raw(self, l, n):
        self.f.seek(l * 2352); return self.f.read(n * 2352)

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


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    D = Disc(sys.argv[2] if len(sys.argv) > 2 else ROM_EN)
    for p, l, s in D.files():
        print('%-32s %8d %10d' % (p, l, s))
