# AR Dome — artwork augment

Point your phone camera at the painting and a low-poly wireframe dome in the
same blue as the artwork's linework anchors to it in AR — with a low-poly cat
chasing a mouse inside.

**Live:** https://edwin607.github.io/ar-dome/

## How it works
- [MindAR](https://github.com/hiukim/mind-ar) image tracking (three.js build) anchors the scene to the artwork.
- `artwork.mind.gz.*` — the compiled image target, gzipped and chunked; the page reassembles and decompresses it in-browser (`DecompressionStream`).
- Dome edges are rendered as thick tubes matching the painting's stroke weight, colored from the sampled linework blue (`#2a3670`).
- Camera + HTTPS required — open on a phone for the AR experience.
