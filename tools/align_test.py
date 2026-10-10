#!/usr/bin/env python3
"""Alignment regression test for the AR page.

MindAR's anchor space is  x = right, y = up the image, z = out of the painting,
with the target image lying in the XY plane and one unit = the target image
WIDTH (see README "Anchored coordinate space"). Getting that frame wrong makes
the augment lie flat on the artwork instead of standing on it, which is exactly
the class of bug this test catches.

How it works: instead of hoping a webcam or a .y4m shows the artwork, it warps
the target photo into a *known* quad — a synthetic camera view of the painting
lying on a surface — and injects that as the camera through a canvas
MediaStream. The page exposes window.__alignProbe(), which projects the four
corners of the target rectangle with the live anchor matrix and camera. If the
anchor frame is correct those corners land on the painted quad.

Usage:
  python align_test.py <url> [--target artwork-target.jpg] [--shot out.png]
                       [--tolerance 45] [--wait 16]
"""
import argparse, base64, json, sys
import numpy as np, cv2
from PIL import Image
from playwright.sync_api import sync_playwright

# a plausible phone view of a landscape painting lying on a surface
QUAD = np.float32([[214, 196], [788, 152], [832, 598], [112, 542]])   # TL TR BR BL
W, H = 900, 650

INIT = """
(() => {
  const B64 = "data:image/png;base64,%s";
  const W = %d, H = %d;
  const img = new Image();
  let ready = false;
  img.onload = () => { ready = true; };
  img.src = B64;
  const canvas = document.createElement('canvas');
  canvas.width = W; canvas.height = H;
  canvas.style.cssText = 'position:fixed;left:0;top:0;opacity:0.01;pointer-events:none;z-index:-1';
  const ctx = canvas.getContext('2d');
  function draw() {
    if (ready) ctx.drawImage(img, 0, 0, W, H);
    else { ctx.fillStyle = '#888'; ctx.fillRect(0, 0, W, H); }
    requestAnimationFrame(draw);
  }
  function boot() { document.body.appendChild(canvas); requestAnimationFrame(draw); }
  if (document.body) boot(); else document.addEventListener('DOMContentLoaded', boot);
  const real = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
  navigator.mediaDevices.getUserMedia = async (c) => {
    if (!c || !c.video) return real(c);
    return canvas.captureStream(30);
  };
})();
"""


def load_target_bytes(path):
    """Read an image, or reassemble it from the repo's <name>.aa/.ab/... chunks."""
    import glob, os
    if os.path.exists(path):
        return open(path, 'rb').read()
    parts = sorted(glob.glob(path + '.*'))
    parts = [p for p in parts if not p.endswith('.json')]
    if not parts:
        raise SystemExit(f'cannot find {path} or its chunks')
    return b''.join(open(p, 'rb').read() for p in parts)


def synthesize_view(target_path, out_png):
    """Warp the painting into QUAD over a neutral surface; returns the ground truth."""
    import io
    t = np.asarray(Image.open(io.BytesIO(load_target_bytes(target_path))).convert('RGB'))
    th, tw = t.shape[:2]
    Hm = cv2.getPerspectiveTransform(
        np.float32([[0, 0], [tw, 0], [tw, th], [0, th]]), QUAD)
    yy = np.linspace(0, 1, H)[:, None]
    bg = np.zeros((H, W, 3), np.uint8)
    for c, base in enumerate((198, 194, 190)):
        bg[..., c] = np.clip(base + 16 * yy, 0, 255).astype(np.uint8)
    frame = bg.copy()
    sh = cv2.GaussianBlur(cv2.warpPerspective(np.full((th, tw), 255, np.uint8), Hm, (W, H)),
                          (0, 0), 11).astype(np.float32) / 255.0
    for c in range(3):
        frame[..., c] = (bg[..., c] * (1 - 0.30 * sh)).astype(np.uint8)
    warped = cv2.warpPerspective(t, Hm, (W, H))
    mask = cv2.warpPerspective(np.full((th, tw), 255, np.uint8), Hm, (W, H)) > 0
    frame[mask] = warped[mask]
    Image.fromarray(frame).save(out_png)
    return QUAD.copy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('url')
    ap.add_argument('--target', default='artwork-target.jpg')
    ap.add_argument('--view', default=None, help='write the synthetic camera frame here')
    ap.add_argument('--shot', default=None, help='write the rendered AR screenshot here')
    ap.add_argument('--tolerance', type=float, default=45.0, help='max per-corner error, px')
    ap.add_argument('--wait', type=int, default=16)
    args = ap.parse_args()

    view = args.view or '/tmp/align_view.png'
    truth = synthesize_view(args.target, view)

    with sync_playwright() as p:
        b64 = base64.b64encode(open(view, 'rb').read()).decode()
        try:
            browser = p.chromium.launch(headless=True, args=[
                '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
                '--ignore-gpu-blocklist', '--enable-webgl',
                '--use-fake-ui-for-media-stream',
                '--autoplay-policy=no-user-gesture-required'])
        except Exception:
            browser = p.chromium.launch(channel='chrome', headless=True, args=[
                '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
                '--ignore-gpu-blocklist', '--enable-webgl',
                '--use-fake-ui-for-media-stream',
                '--autoplay-policy=no-user-gesture-required'])
        page = browser.new_page(viewport={'width': W, 'height': H})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.add_init_script(INIT % (b64, W, H))
        page.goto(args.url)
        page.wait_for_timeout(args.wait * 1000)
        probe = page.evaluate('window.__alignProbe ? window.__alignProbe() : null')
        if args.shot:
            page.screenshot(path=args.shot)
        browser.close()

    if not probe:
        print('FAIL: window.__alignProbe() is unavailable (AR never started?)')
        sys.exit(1)
    if errors:
        print('page errors:', errors)
    err = np.linalg.norm(np.array(probe['quad'], float) - truth, axis=1)
    print('ground truth quad :', truth.astype(int).tolist())
    print('anchor-frame quad :', probe['quad'])
    print('viewport/video    :', probe['viewport'], probe['video'])
    print('per-corner error  :', err.round(1).tolist(), ' max', round(float(err.max()), 1), 'px')
    print('scene up . normal :', probe.get('upDot'), ' (must be ~+1: augment stands on the painting)')
    print('footprint fits    :', probe.get('footprintFits'))

    checks = {
        'target found': bool(probe.get('targetFound')),
        f'corner error <= {args.tolerance}px': float(err.max()) <= args.tolerance,
        'augment stands on painting (upDot >= 0.98)': float(probe.get('upDot', 0)) >= 0.98,
        'base ring inside painting': bool(probe.get('footprintFits')),
        'no page errors': not errors,
    }
    for k, v in checks.items():
        print(f'  [{"ok" if v else "FAIL"}] {k}')
    ok = all(checks.values())
    print('RESULT:', 'PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
