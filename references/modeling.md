# Modeling for Roblox with bpy (and what reelmaxxing already learned)

## Why code-built geometry
A script that places a bevelled box, a 10-sided half-cylinder and a wedge produces exactly the triangles it was written to produce,
with named parts, deliberate pivots and real UVs. Neural meshes (Meshy, `generate_mesh`, `generate_3d`, Cube) arrive dense, unnamed and
as one blob: use them only for organic one-offs, and run them through the same gate (decimate, retopo, one material, UVs).
The pattern to copy from the research systems (LL3M, MeshCoder): **ground in the API, build named parts, look after every step.**

## Scale cheat sheet (studs; rules of thumb - test in Play)
| thing | studs |
|---|---|
| R15 avatar height | ~5 (the `snapshot` blue post) |
| one stud cube | 1 x 1 x 1 (the `snapshot` yellow cube) |
| doorway | 4-5 wide x 7-8 tall (avatars jump; leave headroom) |
| ceiling / storey | 10-12 |
| table / counter | 2.5-3.5 high |
| chair seat | ~1.5-2 high |
| walk-up step | keep <= 1 high to walk up without jumping (check in Play) |
| prop you pick up | 0.5-2 |
Read size in context: the snapshot puts a stud cube and a 5-stud post next to every asset.

Before the recipe: write the ART BRIEF and know the hero shape (`references/art-direction.md`). The recipe below makes
correct geometry; the brief and the three-distance check make it look like game art.

## The build recipe (`rbx_kit`)
1. `K.setup()`, `K.asset("Name")`: one collection = one Model. Stud-native (Unit System None).
2. Block the silhouette first with `box / wedge / cyl / sphere` (sizes in studs, `loc` = centre). Read it at gameplay distance:
   one clear silhouette beats detail (Roblox drops detail beyond 250 studs).
3. Low segment counts: cylinders 8-16 sides (4 tris per side), spheres 12 x 8, bevels `seg=1` (a chamfer catches light; more
   segments rarely read in Roblox lighting). Typical props: hundreds to ~2,000 triangles; heroes up to 15,000; never a single mesh
   over 20,000.
4. Pivots where things turn or sit: `origin="bottom"` for things on the floor, the hinge line for lids/doors (`origin=(x, y, z)`),
   `K.set_origin(ob, ...)` to move one later. Parts that move or that scripts touch stay separate objects with clear names.
5. Colour: `K.mat("#hex", "Wood")` - a flat colour plus a Roblox Material (`MATERIALS` lists them). Studio applies them from the
   manifest (MeshPart.Color + Material), which looks like Roblox and batches. 2-4 colours per prop, one dominant.
6. Fewer parts: `K.merge_by_material(keep=("Lid",))` joins parts that share a material (bands + lock -> one gold part).
   Organic parts (legs, tails, horns, fingers, roots, tentacles, pipes): `K.loft(name, points, radii, sides, per, flatten)`
   through 3-4 control points; radius 0 at the end for a tip; ends are rounded caps. Bulbous parts that other parts attach to
   (palms, heads, bulbs): `K.blob(name, size, loc)` (exact ellipsoid); free-standing soft forms: a box cage + `K.smooth(ob, 2)`
   (it shrinks ~25%). Start every attached part INSIDE its parent (`art-direction.md`, "Attachment").
   Plates/armour/rocks: `K.box(..., taper=(0.85, 0.8), bevel=..., seg=2)`. Collision: `K.collider("Hitbox", size, loc)`.
6b. `K.bake_shading(ao=0.6, ground=0.3)` after merging (AO + ground gradient into grey vertex colours; ~1 s).
7. `K.export(out, kind=...)` runs GATE A, bakes modifiers/rotation/scale, writes FBX + mesh.json + manifest.json.
8. Look: `K.snapshot(out/Name.png, views=(...))` headless, or MCP for Blender's `look` live. Then `rbx.py preview` and
   `rbx.py capture` in Studio. Describe each image in one sentence before you call it done.

Custom properties a part can carry (all optional): `ob["rbx_collision"]` = "Box" | "Hull" | "Default" | "PreciseConvexDecomposition"
(default: Box under 6 studs, else Default), `ob["rbx_anchored"]` (default True), `ob["rbx_cancollide"]` (True),
`ob["rbx_castshadow"]` (True for parts >= 1 stud).

## Levels and kits
Model each unique piece once (wall, corner, door frame, window, roof edge, floor tile), export it as its own asset, preview/upload it
once, then assemble the level in Studio with `execute_luau` (clone + PivotTo in chunks with `task.wait()`). Every clone shares one
MeshId and batches. A whole level in one FBX looks the same in Studio and runs worse. Snap kit pieces to a grid you can say out loud
(4 studs is a good default; walls 1 stud thick, 12 tall).

## Textures when flat colour is not enough
Unwrap deliberately (seams or Smart UV Project, pack into 0-1), then bake to separate PNGs (Color, Normal OpenGL, Roughness,
Metalness) at the texel density in `specs.md`. PAWS: Bakery (free, Blender Extensions) batches it; Cycles bake works headless.
Keep one material per mesh. Share a trim sheet across a kit. First textured upload: check whether a SurfaceAppearance arrived; if
not, upload the PNGs (`store_image` takes local PNGs) and create the SurfaceAppearance by hand once.

## Classic blocky avatar style (from a user reference, 4 Nov 2026; example: ~/Ngonten/Maxxing/Roblox/weaver_blocky/build.py)
Take the STYLE from a reference, never its character (no franchise suits, logos, emblems or masks: design your own).
- Proportions (studs): legs 1 x 1 x 2 (thigh block + shin band + sneaker), torso 2.1 x 1.05 x 2, arms 1 x 1 x 1.6-2 hanging
  just off the torso, head ~1.5 x 1.4 x 1.3 (bigger than R6 for appeal), total ~5.3.
- Every block soft-rounded (`bevel` 0.1-0.36, `seg=3`); the head gets the biggest radius.
- Colour blocking: a centre panel sunk into a differently coloured torso, cuffs at wrists/ankles, a belt, a chest emblem.
- C-shaped claw hand: a `loft` along a ~290 degree arc (ring radius ~0.33, tube ~0.21), ring in the X-Z plane, the opening facing
  the body, top sunk into the cuff (it reads from the front; an arc opening forward reads as a ball).
- Sneakers: charcoal upper + wider cream sole + 2 accent lace bars on the toe face.
- R6 names (Head, Torso, Left Arm, Right Arm, Left Leg, Right Leg) with pivots at neck/shoulders/hips; other colours per limb
  joined as "<Limb> Gear<n>" (one material per mesh). Native Parts can do this style too (`SpecialMesh` Head), but get no
  rounded blocks, no C hands, no baked shading.

## Characters, accessories, animation
- NPC or avatar body: model one contiguous, watertight, textured humanoid in A-pose (front -Y in Blender) with separate eyes, teeth,
  tongue; import it; run `auto_setup_avatar` (Development preset for NPCs, Platform for the Marketplace). Do not hand-rig unless
  Avatar Setup fails.
- Rigid accessory: ONE mesh (`kind="accessory"`, 4,000 tris), modelled in place on a mannequin (RBX Toolbox gives R15 dummies);
  the Accessory Fitting Tool makes the attachment.
- Layered clothing: start from Roblox's cage templates; Limit Total = 4 weights; export with Include Custom Properties; finish in the
  Accessory Fitting Tool. `rbx_kit` gates the triangle budget only; Roblox's validation tool and the AFT do the rest.
- Animation: one clip per FBX (Roblox keeps one track), bake IK/constraints to keys, then Animation Editor > Import > From File.

## Lessons carried over from reelmaxxing (the blocky mascot + set kit)
These come from `~/Ngonten/Maxxing/reelmaxxing/blender/mascot_lib.py`, `set_lib.py` and `runtime/outfits.js`, where the same problems
were solved for reels. Only the parts that matter for game assets:
1. **The kit is data, the builders are dumb.** The wardrobe is boxes in body units in ONE JSON file, read by every build
   (2D, Three.js, Blender). For Roblox: describe a kit (props, accessories, a building set) as a table of parts
   `{name, size, loc, color, material, origin}` and let one loop call `K.box`. New item = new entry, not new code.
2. **Proportions as a spec.** The mascot is defined in body units (W 1, H 0.86, legs 0.34 ...). Define your game's look the same way
   in studs against the 5-stud avatar, write it at the top of the build script, and never eyeball sizes per asset.
3. **Origins at the joints, names on every part.** The mascot's arms pivot at the shoulder, legs at the hip, so acting is one rotation.
   Same for lids, doors, wheels, levers: pivot on the hinge (the chest's `Lid`).
4. **Smooth shading only where there is a bevel.** Smooth-shading a sharp box averages normals across big faces: blotchy gradients
   that shift with the camera. `rbx_kit` shades flat unless bevelled (harden normals) or explicitly `smooth=` (sharp by angle).
5. **Procedural looks do not travel.** The reel mascot's felt bump renders in Blender and vanishes in glTF. In Roblox only flat
   colour, Roblox Materials and baked images survive. Decide which one you are using before modelling detail into a shader.
6. **Colours are sRGB hex at the edges, linear inside Blender.** `K.mat` converts for the viewport; the manifest keeps the hex
   that `Color3.fromHex` expects.
7. **Never hardcode a Blender enum or node name.** Set enums through `_enum(obj, prop, (candidates))`, find shader nodes by
   `type`. Blender 5.x renamed and moved things; this kept the reel scripts alive across versions.
8. **Headless is the default.** `Blender -b --factory-startup -P build.py -- --out ...` is reproducible: no add-ons, no user prefs.
   The live MCP session is for looking and small edits; the build script is the source of truth (re-run it, do not hand-patch).
9. **One clip per track.** The reel GLBs carry NLA tracks "Idle" and "Hop" as separate glTF clips; Roblox FBX keeps one, so export
   each clip as its own FBX.
10. **Alive, not static (NPCs).** The reel rule: idle breathing, blinks, a look towards what matters, anticipation before a move,
   overshoot after. For Roblox NPCs that means an Idle clip that loops with a subtle sway, not a T-pose standing still.
11. **A FAIL is fixed, never argued; nothing is done until you looked at it.** GATE A in Blender, the size/facing check in Studio,
   and a capture you describe in one sentence. Say what is real and what you did not verify.
12. **Brand characters are not yours to ship.** The Claude, Gemini, Upwork and Meshy mascots in reelmaxxing stand for those
   companies. Fine in commentary reels; never upload them as Roblox UGC or game characters. Design the game's own characters with the
   same rules (one silhouette change per role, 2-4 colours, reads at thumbnail size).
