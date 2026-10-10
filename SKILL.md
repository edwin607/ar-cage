---
name: ar-image-augment
description: "Build a web-AR page that anchors a low-poly 3D augment to a physical artwork or image (MindAR image tracking + three.js, deployed to GitHub Pages). Use when the user wants to augment a painting/photo/poster with 3D geometry viewable through a phone camera, retarget an existing AR page to a new image, or debug MindAR tracking/alignment issues."
labels:
  - Engineering
  - Content
---

# AR Image Augment

Pipeline for anchoring a three.js scene to a physical image via [MindAR](https://github.com/hiukim/mind-ar) image tracking, served as a static page (GitHub Pages). Reference implementation: `edwin607/ar-dome`.

## Pipeline

1. **Target image** — crop the artwork photo tight to its edges, minimal background, ≤ ~900px on the long side. Landscape/portrait matters: the tracker's coordinate space is normalized to image width = 1 unit, height = h/w.
2. **Compile the target** (headless, needs WebGL):
   `uv run --with playwright python scripts/compile_target.py artwork-target.jpg --out artwork.mind`
   Playwright chromium must be installed (`playwright install chromium` once). The SwiftShader flags inside the script are required — MindAR's compiler needs WebGL.
3. **Chunk for hosting** (GitHub MCP rejects base64 payloads above ~160 KB; raw git pushes don't need this):
   `gzip -9 -c artwork.mind > artwork.mind.gz`
   `python scripts/chunk.py artwork.mind.gz artwork.mind.gz --manifest artwork.mind.manifest.json`
   The page reassembles + decompresses in-browser (`DecompressionStream`, pako fallback for Safari < 16.4).
4. **Scene** — single `index.html`, ESM import map pinned to `three@0.150.1` (newer three drops `sRGBEncoding`, which MindAR 1.2.5 imports; r150 `BufferGeometryUtils` exports `mergeBufferGeometries`, not `mergeGeometries`). Merge static geometry into one draw call.
5. **Verify** — `uv run --with playwright python scripts/smoke_test.py http://localhost:8000/index.html` (serve the dir first). `errors: none` required. Use `--fake-video fakecam.y4m` to exercise the tracking path, `--shot out.png` for a visual check of the fallback preview.
6. **Deploy** — commit via `GITHUB_CREATE_OR_UPDATE_FILE_CONTENTS` (payloads < ~150 KB), enable Pages with `build_type=legacy, source__branch=main, source__path=/`, then poll `curl` until the new markers appear (propagation takes 1–3 min).

## Device gotchas (learned on iOS Safari)

- **Black camera feed**: MindAR injects `<video>` at `z-index:-2`, behind the page background. Fix: `#ar-container video { z-index:0 !important; object-fit:cover }`, canvas `z-index:1`, and `renderer.setClearColor(0x000000, 0)`.
- **Anchor floating/misaligned**: MindAR computes the projection in `resize()`, which can run before stream dimensions exist. Call `mindarThree.resize()` after `start()` resolves, and again on `orientationchange` (debounced ~300 ms).
- **Anchor placement**: `anchor.group` origin is target-image center; +x right, +z down the image, units = image width. Position scene content with a small offset group so the augment sits on the artwork's compositional focal point, not dead-center.
- **Camera-denied fallback**: always provide an OrbitControls preview against the target image as ground plane — desktop users and permission denials otherwise dead-end.

## Files

- `scripts/compile_target.py` — headless .mind compiler (self-contained HTTP server + Playwright)
- `scripts/compile.html` — browser-side compiler page driven by compile_target.py (`?src=` param)
- `scripts/chunk.py` — split binary into `<prefix>.aa/.ab/...` + manifest
- `scripts/smoke_test.py` — headless boot test with optional fake camera + screenshot
- `index.html` — reference page (gazebo augment, cat/mouse chase, all fixes applied)
