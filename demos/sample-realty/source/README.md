# Sample Realty flight: how it is made

Blender 5.2, Cycles on the GPU. 240 frames, 1600x900, then `pack.py` makes the web frames.

1. `py fetch_assets.py assets/dl` downloads the CC0 Poly Haven trees, plants, textures and skies.
2. `py fetch_osm.py assets/geo` downloads central Edmonton from OpenStreetMap (Overpass) and terrain tiles (AWS open data).
3. `py prep_geo.py assets/geo assets/geo/out` projects it to local metres; `py prep_scatter.py assets/geo/out -150 -1850 520`
   paints the land cover and places the city trees.
4. `blender -b -P main.py -- --dl assets/dl --geo assets/geo/out --out frames --res 1600x900 --samples 80` renders.
   Add `--frames 0,120,172 --res 960x540 --samples 32` for quick test stills.
5. `py pack.py frames ../frames 55` writes `frames/d` (desktop) and `frames/m` (portrait phones).
6. The walk inside is a 10 second Google Veo clip made from a render of the front door. `py add_interior.py clip.mp4 frames/f239.png .. 64 40`
   pushes in on the porch while it dissolves into the clip, adds frames 240 to 317 and the sixth chapter.
7. The second clip starts on the first clip's last frame (kitchen to hallway to bedroom).
   `py add_interior_more.py clip2.mp4 .. 64 40 "Down the hall." "..."` appends frames 318 to 380 and a chapter.
8. Four more clips, each made in Gemini (Veo) from the previous clip's last frame, appended the same way. Every prompt
   names the same house (2,250 sq ft, two storeys, 4 bedrooms, 3.5 baths) and the same finishes so rooms stay in scale:
   ensuite 381 to 443, upstairs hall and second bedroom 444 to 506, kids' room 507 to 569, bonus room over the garage 570 to 632.
   The stairs down, the back door and the yard are still to do.
9. Sunset re-render (now the `main.py` defaults): Blender's physical sky (multiple scattering) drawn for a sun 2.5 degrees
   up, the sun lamp at 9 degrees from the west-south-west so it still clears the neighbours' roofs, three times as many
   lit windows. The flight drops into the river valley west of the bridges, flies east along the river over the High
   Level Bridge and past the Walterdale, then climbs over the south side to the suburb; its speed follows its height
   over the ground. `landmarks.py` builds both bridges from their published dimensions: the High Level (black steel,
   777 m, a Pratt truss with the road inside and the streetcar on top about 47 m over the river, concrete piers in the
   river, steel towers on the approaches) and the Walterdale (two white arches 54 m tall over a 206 m span, leaning
   13.5 degrees toward each other, 16 hangers each). After a re-render, `py add_interior.py <clip 1> <new f239.png> .. 64 40 --fade-only`
   redoes the dissolve into the walk inside without touching the clip frames or the page.

What is real: downtown footprints and heights, the river, bridges, roads, parks and terrain. What is made up: the
suburb on the south side, the house, the listing and the interior (made with AI). Credits: Map data (c) OpenStreetMap contributors (ODbL).
Elevation: Terrain Tiles on AWS, including Natural Resources Canada data (Open Government Licence, Canada).
Poly Haven assets are CC0.
