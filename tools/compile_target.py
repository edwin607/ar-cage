#!/usr/bin/env python3
"""Compile a MindAR image target (.mind) from an image, headless via Playwright.

Usage:
  python compile_target.py <image> [--out target.mind] [--port 8000] [--dir .]

Requires: playwright (chromium). Serve the directory containing compile.html
over HTTP; this script starts its own server on --port rooted at --dir.
"""
import argparse, base64, http.server, functools, os, socketserver, sys, threading
from playwright.sync_api import sync_playwright

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('image', help='target image (jpg/png), relative to --dir')
    ap.add_argument('--out', default='target.mind')
    ap.add_argument('--port', type=int, default=8123)
    ap.add_argument('--dir', default='.', help='directory to serve (compile.html must be in it; default: cwd)')
    args = ap.parse_args()

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=args.dir)
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(('127.0.0.1', args.port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
            '--ignore-gpu-blocklist', '--enable-webgl'])
        page = browser.new_page()
        page.on('pageerror', lambda e: print('pageerror:', str(e)[:300]))
        page.goto(f'http://127.0.0.1:{args.port}/compile.html?src=./{args.image}')
        page.wait_for_function('window.done === true', timeout=300000)
        err = page.evaluate('window.err')
        if err:
            print('COMPILE ERROR:', err); sys.exit(1)
        data = base64.b64decode(page.evaluate('window.b64'))
        open(args.out, 'wb').write(data)
        print(f'wrote {args.out} ({len(data)} bytes)')
        browser.close()
    server.shutdown()

if __name__ == '__main__':
    main()
