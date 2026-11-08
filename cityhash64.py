"""CityHash64, translated from Google's reference implementation.

Copyright (c) 2011 Google, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

Reference: https://github.com/google/cityhash/blob/master/src/city.cc
"""
M = (1 << 64) - 1
K0 = 0xc3a5c85c97cb3127
K1 = 0xb492b66fbe98f273
K2 = 0x9ae16a3b2f90404f


def rotate(x, shift):
    x &= M
    return ((x >> shift) | (x << (64 - shift))) & M


def mix(x):
    x &= M
    return x ^ (x >> 47)


def hash16(u, v, mul=0x9ddfea08eb382d69):
    a = ((u ^ v) * mul) & M
    a ^= a >> 47
    b = ((v ^ a) * mul) & M
    b ^= b >> 47
    return (b * mul) & M


def swap(x):
    return int.from_bytes((x & M).to_bytes(8, 'little'), 'big')


def cityhash64(s):
    n = len(s)
    def f(i):
        return int.from_bytes(s[i:i + 8], 'little')
    mul = (K2 + n * 2) & M
    if n <= 16:
        if n >= 8:
            a = (f(0) + K2) & M
            b = f(n - 8)
            c = (rotate(b, 37) * mul + a) & M
            d = ((rotate(a, 25) + b) * mul) & M
            return hash16(c, d, mul)
        if n >= 4:
            a = int.from_bytes(s[:4], 'little')
            b = int.from_bytes(s[-4:], 'little')
            return hash16(n + (a << 3), b, mul)
        if n:
            y = s[0] + (s[n >> 1] << 8)
            z = n + (s[-1] << 2)
            return (mix((y * K2) ^ (z * K0)) * K2) & M
        return K2
    if n <= 32:
        a = (f(0) * K1) & M
        b = f(8)
        c = (f(n - 8) * mul) & M
        d = (f(n - 16) * K2) & M
        return hash16((rotate(a + b, 43) + rotate(c, 30) + d) & M,
                      (a + rotate(b + K2, 18) + c) & M, mul)
    if n <= 64:
        a = f(0) * K2 & M
        b, c, d = f(8), f(n - 24), f(n - 32)
        e, zf = f(16) * K2 & M, f(24) * 9 & M
        g, h = f(n - 8), f(n - 16) * mul & M
        u = (rotate(a + g, 43) + (rotate(b, 30) + c) * 9) & M
        v = (((a + g) & M) ^ d) + zf + 1
        v &= M
        w = (swap((u + v) * mul) + h) & M
        x = (rotate(e + zf, 42) + c) & M
        y = ((swap((v + w) * mul) + g) * mul) & M
        z = (e + zf + c) & M
        a = (swap((x + z) * mul + y) + b) & M
        b = mix((z + a) * mul + d + h) * mul & M
        return (b + x) & M
    def weak(i, a, b):
        w, x, y, z = f(i), f(i + 8), f(i + 16), f(i + 24)
        a = (a + w) & M
        b = rotate(b + a + z, 21)
        c = a
        a = (a + x + y) & M
        b = (b + rotate(a, 44)) & M
        return ((a + z) & M, (b + c) & M)
    x = f(n - 40)
    y = (f(n - 16) + f(n - 56)) & M
    z = hash16((f(n - 48) + n) & M, f(n - 24))
    v = weak(n - 64, n, z)
    w = weak(n - 32, y + K1, x)
    x = (x * K1 + f(0)) & M
    length = (n - 1) & ~63
    for i in range(0, length, 64):
        x = rotate(x + y + v[0] + f(i + 8), 37) * K1 & M
        y = rotate(y + v[1] + f(i + 48), 42) * K1 & M
        x ^= w[1]
        y = (y + v[0] + f(i + 40)) & M
        z = rotate(z + w[0], 33) * K1 & M
        v = weak(i, v[1] * K1, x + w[0])
        w = weak(i + 32, z + w[1], y + f(i + 16))
        z, x = x, z
    return hash16((hash16(v[0], w[0]) + mix(y) * K1 + z) & M,
                  (hash16(v[1], w[1]) + x) & M)


def check_hash(s):
    return hash16((cityhash64(s) - K2) & M, 0x1dbba5) & 0xffffffff
