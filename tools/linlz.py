# -*- coding: utf-8 -*-
r"""린다 큐브 압축 (00SL.BIN 0x06022E78 역해석, 2026-09-28 사용자 쓰기 중단점으로 찾음)
  자원 머리(MIC): [u32 LE 풀린 크기][u32 LE 압축 크기][매개변수 4B] 다음이 스트림(끝 표시까지 한 번에 풂)
  깃발 바이트 LSB부터(필요할 때 그 자리에서 새 바이트) · 1 = 글자 1바이트
  0,1 = 짧은 참조 1바이트 b: 길이 (b>>6)+2, 거리 64-(b&63)   (off = (b&0x3F)-0x40)
  0,0 = 긴 참조 2바이트 w(BE): n=w>>12, 거리 0x1000-(w&0xFFF); n==0 이면 n=다음 바이트(0 이면 끝); 길이 n+2
"""


def dec_block(src, i, limit=0x100):
    out = bytearray(); bits = 0; fl = 0

    def bit():
        nonlocal bits, fl, i
        if bits == 0:
            fl = src[i]; i += 1; bits = 8
        b = fl & 1; fl >>= 1; bits -= 1
        return b
    while len(out) < limit:
        if bit():
            out.append(src[i]); i += 1; continue
        if bit():
            b = src[i]; i += 1
            n = (b >> 6) + 2; off = (b & 0x3F) - 0x40
        else:
            w = src[i] << 8 | src[i + 1]; i += 2
            n = w >> 12; off = (w & 0xFFF) - 0x1000
            if n == 0:
                n = src[i]; i += 1
                if n == 0:
                    break
            n += 2
        n = min(n, limit - len(out))
        for _ in range(n):
            out.append(out[len(out) + off])
    return bytes(out), i


def decode(src, i):
    """머리 붙은 자원 → (풀린 데이터, 스트림 끝 위치)"""
    u = int.from_bytes(src[i:i + 4], 'little')
    return dec_block(src, i + 12, limit=u)


def encode(data):
    """끝 표시까지 포함한 스트림(최적 파싱, 비트 단위 비용)"""
    n = len(data)
    # 매치 후보: 위치마다 (길이, 거리) — 3바이트 해시로 앞 4096 안
    heads = {}
    cand = [[] for _ in range(n)]
    for p in range(n):
        if p + 2 <= n:
            # 짧은 참조(거리 1‥64, 길이 2‥5)
            for dist in range(1, min(64, p) + 1):
                l = 0
                while l < 5 and p + l < n and data[p + l] == data[p + l - dist]:
                    l += 1
                if l >= 2:
                    cand[p].append((l, dist, 's'))
        if p + 3 <= n:
            key = data[p:p + 3]
            best = {}
            for q in reversed(heads.get(key, [])):
                dist = p - q
                if dist > 0x1000:
                    break
                l = 0
                while l < 257 and p + l < n and data[p + l] == data[q + l]:
                    l += 1
                if l >= 3 and l > best.get('l', 0):
                    best = {'l': l, 'd': dist}
                    cand[p].append((l, dist, 'l'))
                    if l == 257:
                        break
            heads.setdefault(key, []).append(p)
    INF = 1 << 60
    cost = [INF] * (n + 1); how = [None] * (n + 1); cost[n] = 0
    for p in range(n - 1, -1, -1):
        c = 9 + cost[p + 1]; h = ('c',)
        for l, dist, kind in cand[p]:
            if kind == 's':
                for ll in range(2, l + 1):
                    v = 10 + cost[p + ll]
                    if v < c:
                        c, h = v, ('s', ll, dist)
            else:
                for ll in range(3, l + 1):
                    v = (18 if ll <= 17 else 26) + cost[p + ll]
                    if v < c:
                        c, h = v, ('l', ll, dist)
        cost[p] = c; how[p] = h
    out = bytearray(); st = {'pos': None, 'nb': 8}

    def put_bit(b):
        if st['nb'] == 8:
            st['pos'] = len(out); out.append(0); st['nb'] = 0
        if b:
            out[st['pos']] |= 1 << st['nb']
        st['nb'] += 1
    p = 0
    while p < n:
        h = how[p]
        if h[0] == 'c':
            put_bit(1); out.append(data[p]); p += 1
        elif h[0] == 's':
            _, ll, dist = h
            put_bit(0); put_bit(1); out.append(((ll - 2) << 6) | (0x40 - dist)); p += ll
        else:
            _, ll, dist = h
            put_bit(0); put_bit(0)
            w = (0x1000 - dist) & 0xFFF
            if ll <= 17:
                w |= (ll - 2) << 12; out += bytes([w >> 8, w & 0xFF])
            else:
                out += bytes([w >> 8, w & 0xFF, ll - 2])
            p += ll
    put_bit(0); put_bit(0); out += b'\x00\x00\x00'       # 끝
    assert dec_block(bytes(out), 0, limit=n + 1)[0] == bytes(data)
    return bytes(out)
