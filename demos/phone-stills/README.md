# Phone stills for the landing page samples

On phones, the landing page shows Saltbox Plumbing and Forno Lume as stills of their pages (`demos/<name>/phone/`),
moved with transform, because scrolling a live page inside a frame stutters on phones. Redo them after changing either demo:

1. `node capture.mjs http://localhost:3300/yegsites/demos/saltbox-plumbing/ shots/saltbox-plumbing` (any local server
   that serves the demo). It shoots the page one 390 x 750 screen at a time at 2x, with the sticky header shot once.
2. `py stitch.py shots/saltbox-plumbing ../saltbox-plumbing/phone` stitches them, cuts 800 px strips and prints the strip
   heights and the header box.
3. Put those numbers in `PHONE` in `/index.html` (the samples part of the script). Same for `forno-lume`.

`shots/` is scratch: don't commit it.
