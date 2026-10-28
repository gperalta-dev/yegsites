# Mirrorline wash: how it is made

1. Start photo: Pexels 6873008 by Tima Miroshnichenko (free licence), the wall sign painted out, cropped to 16:9.
2. Google Gemini edited a copy of it so the car is dusty and muddy (same framing).
3. Google Veo animated the rinse from the start photo (10 s clip, first 6.8 s used).
4. `py detail_frames.py dirty.jpg rinse.mp4 ../frames 6.8 10 46` writes frames 0 (dirty), 1 to 14 (dissolve into the foam)
   and 15 to 82 (the rinse) as 1440x810 desktop and 456x810 phone WebP.

Mirrorline Detail Co. is a made-up business. The source clips stay outside the repo.
