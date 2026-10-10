---
name: ar-image-augment
description: "Build a web-AR page that anchors a low-poly 3D augment to a physical artwork or image (MindAR image tracking + three.js, deployed to GitHub Pages). Use when the user wants to augment a painting/photo/poster with 3D geometry viewable through a phone camera, retarget an existing AR page to a new image, or debug MindAR tracking/alignment issues."
labels:
  - Engineering
  - Content
---

# AR Image Augment

Pipeline for anchoring a three.js scene to a physical image via [MindAR](https://github.com/hiukim/mind-ar) image tracking, served as a static page (GitHub Pages). Reference implementation: `edwin607/ar-dome`.

## The anchor coordinate space (get this right first)

MindAR builds each anchor as `poseMatrix * postMatrix`, where `postMatrix` is
`translate(inputWidth/2, inputHeight/2, 0) * scale(inputWidth)`. So in
anchor-local space, with the origin at the target image's **centre** and one unit
equal to the target image's **width**:

```
+x = right          +y = UP the image          +z = OUT of the painting (toward the viewer)
```

**The target image lies in the anchor's XY plane, not the XZ plane.** A
`PlaneGeometry` added straight to `anchor.group` lies flat on the artwork, and a
structure whose height runs along `+y` lies flat on the artwork too — it does not
stand up. This is a silent, very convincing-looking bug: tracking is perfect and
the augment sits in the right place, but it is *lying down*.

Recommended authoring: build the scene **y-up** (footprint in XZ, height on +Y),
which is also what an `OrbitControls` preview wants, and wrap it for AR:

```js
function toAnchorSpace(o) {
  const g = new THREE.Group();
  g.rotation.x = Math.PI / 2;   // +Y (up) -> +z (out of the painting)
  g.add(o);
  return g;
}
anchor.group.add(toAnchorSpace(scene));
```

`tools/align_test.py` asserts `sceneUp · paintingNormal ≈ +1`, which fails loudly
if this frame is wrong.

## Pipeline

1. **Target image** — crop the artwork photo tight to its edges, minimal background, ≤ ~900px on the long side. Landscape/portrait matters: the tracker's unit is the image width, so the plane spans `1.0 x h/w` in anchor space and the augment must fit inside that.
2. **Compile the target** (headless, needs WebGL):
   `uv run --with playwright python tools/compile_target.py artwork-target.jpg --out artwork.mind`
   Playwright chromium must be installed (`playwright install chromium` once). The SwiftShader flags inside the script are required — MindAR's compiler needs WebGL. If the bundled Chromium cannot be installed, `tools/smoke_test.py` and `tools/align_test.py` fall back to the system Chrome via `channel="chrome"`.
3. **Chunk for hosting** (GitHub MCP rejects base64 payloads above ~160 KB; raw git pushes don't need this):
   `gzip -9 -c artwork.mind > artwork.mind.gz`
   `python tools/chunk.py artwork.mind.gz artwork.mind.gz --manifest artwork.mind.manifest.json`
   The page reassembles + decompresses in-browser (`DecompressionStream`, pako fallback for Safari < 16.4).
4. **Scene** — single `index.html`, ESM import map pinned to `three@0.150.1` (newer three drops `sRGBEncoding`, which MindAR 1.2.5 imports; r150 `BufferGeometryUtils` exports `mergeBufferGeometries`, not `mergeGeometries`). Merge static geometry into one draw call. Keep total light intensity near 1.0 — over-lighting washes a dark linework blue out to lilac.
5. **Verify** — serve the dir, then:
   - `uv run --with playwright python tools/smoke_test.py http://localhost:8000/index.html --deny-camera` → `errors: none`, `mode: preview`
   - `uv run --with playwright --with pillow --with numpy --with opencv-python-headless python tools/align_test.py http://localhost:8000/index.html` → `RESULT: PASS` (checks tracking accuracy **and** that the augment stands on the painting)
   - On a phone, append `?debug=1` to draw the tracked target frame plus the x/y/z axes: the cyan outline must sit on the artwork's edges.
   `--fake-video fakecam.y4m` exercises the tracking path with a looping clip (`ffmpeg -loop 1 -i target.jpg -t 8 -r 10 -pix_fmt yuv420p fakecam.y4m`). Note Chrome needs `--use-fake-device-for-media-stream` as well, otherwise it silently uses the real webcam.
6. **Deploy** — commit via `GITHUB_CREATE_OR_UPDATE_FILE_CONTENTS` (payloads < ~150 KB), enable Pages with `build_type=legacy, source__branch=main, source__path=/`, then poll `curl` until the new markers appear (propagation takes 1–3 min).

## Device gotchas (learned on iOS Safari)

- **Black camera feed**: MindAR injects `<video>` at `z-index:-2`, behind the page background. Fix: `#ar-container video { z-index:0 !important; object-fit:cover }`, canvas `z-index:1`, and `renderer.setClearColor(0x000000, 0)`.
- **Anchor floating/misaligned**: MindAR computes the projection in `resize()`, which can run before stream dimensions exist. Call `mindarThree.resize()` after `start()` resolves, and again on `orientationchange` (debounced ~300 ms).
- **Augment lies flat on the artwork**: the anchor frame is the XY plane, not XZ — see "The anchor coordinate space" above.
- **Stuck spinner over the fallback**: if `start()` rejects, MindAR has already injected `<video>` into your container and `.mindar-ui-overlay` elements into `document.body`. Remove both before starting an orbit preview.
- **Anchor placement**: `anchor.group` origin is the target-image centre. Place the scene root at the origin and size the footprint to sit inside `1.0 x h/w`; a scene offset in the *wrong* axis (e.g. nudging `x`/`z` when the plane is XY) reads as "the augment misses the painting".
- **Camera-denied fallback**: always provide an OrbitControls preview against the target image as ground plane — desktop users and permission denials otherwise dead-end.

## Files

- `tools/compile_target.py` — headless .mind compiler (self-contained HTTP server + Playwright)
- `tools/compile.html` — browser-side compiler page driven by compile_target.py (`?src=` param)
- `tools/chunk.py` — split binary into `<prefix>.aa/.ab/...` + manifest
- `tools/smoke_test.py` — headless boot test with optional fake camera + screenshot
- `tools/align_test.py` — alignment regression test; feeds a synthetic camera view of the painting via a canvas MediaStream and asserts the anchor frame lands on it and the augment stands on it
- `index.html` — reference page (gazebo augment, cat/mouse chase, all fixes applied)
