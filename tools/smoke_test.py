#!/usr/bin/env python3
"""Smoke-test an AR page headless: boots it, reports JS errors and hint text.

Usage:
  python smoke_test.py <url> [--wait 15] [--fake-video file.y4m] [--shot out.png]

--fake-video feeds a looping video file as the camera (make one with:
  ffmpeg -loop 1 -i target.jpg -t 10 -r 15 -pix_fmt yuv420p fakecam.y4m)
Without it, getUserMedia fails and the page's fallback path is exercised.
"""
import argparse
from playwright.sync_api import sync_playwright

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('url')
    ap.add_argument('--wait', type=int, default=15)
    ap.add_argument('--fake-video', default=None)
    ap.add_argument('--shot', default=None)
    args = ap.parse_args()

    launch = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']
    if args.fake_video:
        launch += [f'--use-file-for-fake-video-capture={args.fake_video}',
                   '--use-fake-ui-for-media-stream']
    else:
        launch += ['--use-fake-ui-for-media-stream']

    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=launch)
        page = browser.new_page(viewport={'width': 420, 'height': 800})
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('console', lambda m: errors.append('console.' + m.type + ': ' + m.text[:200]) if m.type == 'error' else None)
        page.goto(args.url)
        page.wait_for_timeout(args.wait * 1000)
        hint_el = page.query_selector('#hint')
        print('hint:', hint_el.text_content() if hint_el else '(no #hint element)')
        print('errors:', errors if errors else 'none')
        if args.shot:
            page.screenshot(path=args.shot)
        browser.close()

if __name__ == '__main__':
    main()
