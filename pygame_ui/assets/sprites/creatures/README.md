# Sprite Templates for Creatures (Client layer)

These are starting templates generated for the ant colony game rendering.

## Files
- `red_ant.png` - Static / idle version (32x32)
- `red_ant_walk.png` - Walk animation sprite sheet (192x32 = 6 frames × 32x32)
- `red_ant_carry.png` - Carrying version (static 32x32)

## How to use / edit
1. Open the PNGs in a pixel art editor:
   - Aseprite (recommended, best for animation)
   - Piskel (free web)
   - LibreSprite, GIMP, etc.

2. For `red_ant_walk.png`:
   - It's a horizontal strip: 6 frames side-by-side.
   - Each frame is 32×32 pixels.
   - The ant is drawn facing right (the code will rotate it based on movement direction).
   - Edit each frame to improve the art (better legs, body details, antennae, etc.).
   - Keep the overall silhouette similar so rotation and scaling look good.
   - Leg animation cycle is already there (3-phase alternate).

3. For static ones:
   - Simple single frame. You can make them more detailed.

4. Adding for other species:
   - Name them after the species: `spider.png`, `springtail_walk.png`, `rival_ant_soldier_walk.png`, etc.
   - The code auto-detects `_walk`, `_carry` etc. suffixes for states.
   - Put in this `creatures/` folder.

## Technical specs used by the game
- Frame size: 32x32 works well (code scales to creature's `base_size` * 2, e.g. ~28px for worker ant).
- Recommended frames for walk: 4–8 (6 is a good balance).
- Animation speed: ~12 fps for walk (can be tweaked in code if needed).
- The sprite will be tinted with the species color from JSON.
- Rotation is applied on top for direction.

## Tips for better results
- Center the ant in each 32x32 cell.
- Make sure there's some transparent padding.
- For walk cycle: typical is contact, lift, swing, plant for legs.
- Test in-game: moving ants should cycle the walk frames + face the direction they're going.
- Carrying ants should switch to the carry sprite/sheet when they pick something up.

## If you want different frame count or size
- You can make e.g. 48x48 frames (bigger art).
- Then use manual load in code or adjust the SpriteManager.load_sprite_sheet call (pass frame_width).
- Current auto assumes frame size from image height for simplicity.

These are just starting points — replace with your own art!

If you make sheets for more species or states (attack, etc.), the system will pick them up for moving/carrying creatures.
