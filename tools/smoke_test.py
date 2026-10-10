#!/usr/bin/env python3
"""Smoke-test an AR page headless: boots it, reports JS errors and hint text.

Usage:
  python smoke_test.py <url> [--wait 15] [--fake-video file.y4m] [--shot out.png]
                       [--deny-camera]

--fake-video feeds a looping video file as the camera (make one with:
  ffmpeg -loop 1 -i target.jpg -t 8 -r 10 -pix_fmt yuv420p fakecam.y4m)
--deny-camera forces getUserMedia to reject, exercising the page's fallback.
Without either, getUserMedia fails and the fallback path is exercised.

Note: --fake-video now also passes --use-fake-device-for-media-stream. Without
that flag Chrome silently falls back to the *real* webcam, so the "fake" run
was never actually fake.

Set PLAYWRIGHT_BROWSERS_PATH or `playwright install chromium` first; if the
bundled Chromium is missing this falls back to the installed Google Chrome.
"""
import argparse, sys
from playwright.sync_api import sync_playwright

DENY_JS = ("navigator.mediaDevices.getUserMedia = async () => "
           "{ throw new DOMException('denied','NotAllowedError'); };")


def launch(p, args):
    """Bundled Chromium if present, else the system Chrome channel."""
    try:
        return p.chromium.launch(headless=True, args=args)
    except Exception as e:
        print(f'(bundled chromium unavailable: {str(e)[:80]} — using channel="chrome")')
        return p.chromium.launch(channel='chrome', headless=True, args=args)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('url')
    ap.add_argument('--wait', type=int, default=15)
    ap.add_argument('--fake-video', default=None)
    ap.add_argument('--shot', default=None)
    ap.add_argument('--deny-camera', action='store_true')
    ap.add_argument('--width', type=int, default=420)
    ap.add_argument('--height', type=int, default=800)
    args = ap.parse_args()

    launch_args = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']
    if args.fake_video:
        launch_args += ['--use-fake-ui-for-media-stream',
                        '--use-fake-device-for-media-stream',
                        f'--use-file-for-fake-video-capture={args.fake_video}']
    else:
        launch_args += ['--use-fake-ui-for-media-stream']

    errors = []
    with sync_playwright() as p:
        browser = launch(p, launch_args)
        page = browser.new_page(viewport={'width': args.width, 'height': args.height})
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('console', lambda m: errors.append('console.' + m.type + ': ' + m.text[:200])
                if m.type == 'error' else None)
        if args.deny_camera or not args.fake_video:
            page.add_init_script(DENY_JS)
        page.goto(args.url)
        page.wait_for_timeout(args.wait * 1000)
        hint_el = page.query_selector('#hint')
        print('hint:', hint_el.text_content() if hint_el else '(no #hint element)')
        print('mode:', page.evaluate('window.__mode || "(unknown)"'))
        probe = page.evaluate('window.__probe ? window.__probe() : null')
        if probe:
            print('probe:', probe)
        print('errors:', errors if errors else 'none')
        if args.shot:
            page.screenshot(path=args.shot)
        browser.close()
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
