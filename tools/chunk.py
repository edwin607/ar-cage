#!/usr/bin/env python3
"""Chunk a binary file for size-limited hosting + write a manifest.

Usage:
  python chunk.py <file> <prefix> [--size 100000] [--manifest out.json]

Produces <prefix>.aa, <prefix>.ab, ... and a manifest the page fetches to
reassemble the file in-browser (see loadTarget() in index.html).
"""
import argparse, json, os, string, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('prefix')
    ap.add_argument('--size', type=int, default=100000)
    ap.add_argument('--manifest', default=None)
    args = ap.parse_args()

    data = open(args.file, 'rb').read()
    names = []
    for i in range(0, len(data), args.size):
        idx = i // args.size
        suffix = 'a' + string.ascii_lowercase[idx] if idx < 26 else string.ascii_lowercase[idx // 26 - 1] + string.ascii_lowercase[idx % 26]
        name = f'{args.prefix}.{suffix}'
        open(name, 'wb').write(data[i:i + args.size])
        names.append(suffix)
    manifest = {'parts': names, 'sizes': {n: os.path.getsize(f'{args.prefix}.{n}') for n in names}}
    out = args.manifest or f'{args.prefix}.manifest.json'
    json.dump(manifest, open(out, 'w'), indent=2)
    print(f'{len(names)} chunks -> {out}')

if __name__ == '__main__':
    main()
