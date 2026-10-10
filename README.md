# AR Dome — artwork augment

Point your phone camera at the painting and a low-poly gazebo in the same blue
as the artwork's linework anchors to it in AR — with a low-poly cat chasing a
mouse inside.

**Live:** https://edwin607.github.io/ar-dome/

## How it works
- [MindAR](https://github.com/hiukim/mind-ar) image tracking (three.js build, pinned to three@0.150.1) anchors the scene to the artwork.
- `artwork.mind.gz.*` — the compiled image target, gzipped and chunked; the page reassembles and decompresses it in-browser (`DecompressionStream`, pako fallback).
- Gazebo struts are tubes matching the painting's stroke weight, in the sampled linework blue (`#2a3670`).
- Camera + HTTPS required — open on a phone for AR. Camera denied (or desktop) → orbit-controls preview against the artwork.
- `?debug=1` draws the tracked target frame and the anchor axes, so a misalignment can be diagnosed on-device.

## Anchored coordinate space

MindAR's anchor is `poseMatrix * translate(w/2, h/2, 0) * scale(w)`, so in
anchor-local space, origin at the target image centre, one unit = target image
**width**:

```
+x = right     +y = up the image     +z = out of the painting
```

The artwork therefore lies in the anchor's **XY** plane, not XZ. The scene is
authored y-up (footprint in XZ, height on +Y) so the orbit preview is natural,
and `toAnchorSpace()` rotates it by +90° about X for AR. Building the footprint
in XZ and the height on +y — as an earlier revision did — makes the whole
structure *lie flat on the painting* while tracking still looks perfect. That was
the "not aligning" bug. See SKILL.md for the full write-up.

## Scene proportions (from the rendered mockup)

| parameter | value | note |
|---|---|---|
| `R` (base/eave ring radius) | `0.34` | Ø 0.68 of the painting width; fits inside 1.0 × 0.7222 |
| `WALL_H` | `0.24` | post height |
| `ROOF_H` | `0.19` | roof rise above the eave |
| `APEX_R` | `0.15` | small ring at the top |
| `STROKE` | `0.0045` | tube radius — matches the painting's line weight |
| `ROOT_OFFSET` | `(0, 0, 0)` | centred on the artwork, as in the mockup |

The reference render is an AI-generated image: it is a good guide to look and
proportion, but its eight post feet do not agree on a single ground ring
(their implied ring centres differ by more than the ring radius), so it cannot be
used as an exact dimensional target. The values above match its silhouette and
footprint without copying that inconsistency. Tune `R`/`WALL_H`/`ROOF_H` at the
top of `index.html`.

## Repository layout
- `index.html` — the whole AR experience (single file, CDN dependencies)
- `artwork.mind.gz.aa–ad` + `artwork.mind.manifest.json` — chunked image target
- `artwork-target.jpg.aa–ac` — chunked artwork photo (preview fallback ground plane)
- `tools/` — the pipeline: compile a new target, chunk binaries, smoke-test the page, alignment regression test
- `SKILL.md` — full pipeline documentation (ar-image-augment agent skill)

## Retargeting to a new image
1. Crop the new artwork photo tight to its edges, ≤ ~900px long side → `artwork-target.jpg`
2. `uv run --with playwright python tools/compile_target.py artwork-target.jpg --out artwork.mind`
3. `gzip -9 -c artwork.mind > artwork.mind.gz && python tools/chunk.py artwork.mind.gz artwork.mind.gz --manifest artwork.mind.manifest.json`
4. Re-chunk the jpg: `python tools/chunk.py artwork-target.jpg artwork-target.jpg`
5. Resize the scene to the new aspect: the painting spans `1.0 x (h/w)`, and the scene root stays at the anchor origin
6. `uv run --with playwright python tools/smoke_test.py <url> --deny-camera` — require `errors: none`
7. `uv run --with playwright --with pillow --with numpy --with opencv-python-headless python tools/align_test.py <url>` — require `RESULT: PASS`
