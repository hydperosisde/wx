"""Offline reader for WeType's MARISA-derived sensitive dictionary.

Serialization and traversal were checked against the upstream MARISA source:
https://github.com/s-yata/marisa-trie/tree/master/lib/marisa/grimoire
No WeType executable or library is loaded or run.
"""
from pathlib import Path
from functools import lru_cache
import argparse
import hashlib
import json
import struct
from cityhash64 import check_hash


class Reader:
    def __init__(self, data, offset=0):
        self.data, self.pos = data, offset

    def num(self, fmt):
        size = struct.calcsize('<' + fmt)
        if self.pos + size > len(self.data):
            raise ValueError('Truncated number')
        result = struct.unpack_from('<' + fmt, self.data, self.pos)
        self.pos += size
        return result[0] if len(result) == 1 else result

    def vector(self):
        size = self.num('Q')
        if size > len(self.data) - self.pos:
            raise ValueError('Truncated vector')
        result = self.data[self.pos:self.pos + size]
        self.pos += (size + 7) // 8 * 8
        return result

    def bitvector(self):
        data = self.vector()
        nbits, ones = self.num('II')
        if nbits > len(data) * 8:
            raise ValueError('Invalid bitvector length')
        value = int.from_bytes(data, 'little') & ((1 << nbits) - 1)
        if value.bit_count() != ones:
            raise ValueError('Bitvector popcount mismatch')
        for _ in range(3):
            self.vector()  # rank and select acceleration tables
        return BitVector(data, nbits, ones)


class BitVector:
    def __init__(self, data, size, ones):
        self.data, self.size, self.ones = data, size, ones
        self.prefix = [0]
        for byte in data:
            self.prefix.append(self.prefix[-1] + byte.bit_count())
        self.select = [i for i in range(size) if self[i]]

    def __getitem__(self, i):
        if not 0 <= i < self.size:
            raise IndexError(i)
        return (self.data[i // 8] >> (i % 8)) & 1

    def rank(self, i):
        """Number of set bits before position i."""
        return self.prefix[i // 8] + (self.data[i // 8] & ((1 << (i % 8)) - 1)).bit_count()


class Trie:
    def __init__(self, reader, depth=0):
        if depth > 10:
            raise ValueError('Unexpected trie nesting')
        self.start = reader.pos
        self.louds = reader.bitvector()
        self.terminal = reader.bitvector()
        self.link = reader.bitvector()
        self.labels = reader.vector()
        self.extras = int.from_bytes(reader.vector(), 'little')
        self.width, self.mask, self.nextras = reader.num('IIQ')
        if self.width > 32 or self.nextras != self.link.ones:
            raise ValueError('Invalid extras vector')
        self.tail = reader.vector()
        self.tail_end = reader.bitvector()
        self.next = Trie(reader, depth + 1) if self.link.ones and not self.tail else None
        self.cache = reader.vector()
        self.l1, self.config = reader.num('II')
        self.end = reader.pos
        self.parents = [None] + [self.louds.select[i] - i - 1 for i in range(1, len(self.labels))]
        if len(self.labels) != self.louds.ones:
            raise ValueError('Node count mismatch')

    def handle(self, node):
        rank = self.link.rank(node)
        return self.labels[node] | (((self.extras >> (rank * self.width)) & self.mask) << 8)

    @lru_cache(maxsize=None)
    def restore(self, node):
        """Restore compressed reverse-trie path, from node to root."""
        out = bytearray()
        while node:
            if self.link[node]:
                handle = self.handle(node)
                if self.next is not None:
                    out.extend(self.next.restore(handle))
                elif self.tail_end.size:
                    while True:
                        out.append(self.tail[handle])
                        if self.tail_end[handle]:
                            break
                        handle += 1
                else:
                    end = self.tail.index(0, handle)
                    out.extend(self.tail[handle:end])
            else:
                out.append(self.labels[node])
            if node <= self.l1:
                break
            parent = self.parents[node]
            if not 0 <= parent < node:
                raise ValueError('Invalid parent')
            node = parent
        return bytes(out)

    def metadata(self):
        return dict(start=self.start, end=self.end, nodes=len(self.labels),
                    terminal_count=self.terminal.ones, link_count=self.link.ones,
                    l1=self.l1, extras_width=self.width, tail_bytes=len(self.tail),
                    next=self.next.metadata() if self.next else None)

    def key(self, node):
        """Top-level reverse_lookup reverses each compressed segment."""
        out = bytearray()
        while node:
            if self.link[node]:
                handle = self.handle(node)
                if self.next:
                    segment = self.next.restore(handle)
                else:
                    segment = self.tail[handle:self.tail.index(0, handle)]
                out.extend(segment[::-1])
            else:
                out.append(self.labels[node])
            if node <= self.l1:
                break
            node = self.parents[node]
        return bytes(out[::-1])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', type=Path, required=True)
    parser.add_argument('-o', '--output', type=Path, required=True)
    parser.add_argument('--kind440-output', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    data = args.file.read_bytes()
    if data[9:25] != b'Ime trie header\0' or struct.unpack_from('<H', data, 5)[0] != 443:
        raise ValueError('Unrecognized WeType kind=443 dictionary header')
    reader = Reader(data, 25)
    trie = Trie(reader)
    print(json.dumps(trie.metadata(), indent=2))
    words = []
    for node in trie.terminal.select:
        path = trie.key(node)
        words.append(bytes((x - 1) & 255 for x in path).decode('utf-8')[::-1])
    if len(words) != len(set(words)):
        raise ValueError('Duplicate decoded words')
    if any(not w or any(c in w for c in '\r\n\x00') for w in words):
        raise ValueError('Empty word or unexpected text delimiter')
    args.output.write_text('\n'.join(sorted(words)) + '\n', encoding='utf-8-sig')
    report = dict(words=len(words), file_md5=hashlib.md5(data).hexdigest(),
                  file_sha256=hashlib.sha256(data).hexdigest(), trie=trie.metadata())
    sections = []
    pos = 1
    for _ in range(data[0]):
        length, kind = struct.unpack_from('<II', data, pos)
        start, end = pos + 8, pos + 8 + length
        if end > len(data):
            raise ValueError('Truncated dictionary section')
        sections.append(dict(kind=kind, start=start, end=end, length=length))
        pos = end
    report['sections'] = sections
    if args.kind440_output:
        section = next(s for s in sections if s['kind'] == 440)
        base = section['start'] + 1
        header, buckets = struct.unpack_from('<II', data, base)
        if header != 0x80000001:
            raise ValueError('Unrecognized kind=440 hash table')
        checks, entries = set(), 0
        for i in range(buckets):
            offset = struct.unpack_from('<I', data, base + 8 + i * 4)[0]
            p = base + offset
            n = struct.unpack_from('<I', data, p)[0]
            if p + 4 + n * 7 > section['end']:
                raise ValueError('Truncated hash bucket')
            checks.update(struct.unpack_from('<' + 'I' * n, data, p + 4))
            entries += n
        matches = sorted(w for w in words if check_hash(w.encode('utf-8')) in checks)
        matched_checks = {check_hash(w.encode('utf-8')) for w in matches}
        args.kind440_output.write_text('\n'.join(matches) + '\n', encoding='utf-8-sig')
        report['kind440'] = dict(buckets=buckets, entries=entries,
                                 unique_hashes=len(checks), matched_words=len(matches),
                                 matched_hashes=len(matched_checks),
                                 unmatched_hash_count=len(checks - matched_checks),
                                 unmatched_hashes=[f'{h:08x}' for h in sorted(checks-matched_checks)])
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                               encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('trie','sections')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
