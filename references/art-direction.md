# Art direction: from "programmer boxes" to game art

Why the first models looked weak, and what fixed them. Distilled from the `create-game-assets`, `roblox-studio-workflow`,
`roblox-characters` and `roblox-physics` skills in github.com/gamedev-skills/awesome-gamedev-agent-skills (Apache-2.0,
read 4 Nov 2026), adapted to Roblox and tested on the scorpion (`~/Ngonten/Maxxing/Roblox/scorpion`: v1 `build.py`,
v2 `build_v2.py`; `scorpion_v1_v2_studio.jpg` here shows v1 Blender, v2, and the Studio-only Parts build side by side).

## What was wrong with v1 (diagnose with the axes, not "make it prettier")
| axis | v1 | v2 fix |
|---|---|---|
| shape language | boxes + straight cylinders + cones everywhere: reads as a diagram | lofted organic tubes for legs/tail/fingers, tapered plates, subdivided bulbous palms (`loft`, `box(taper=)`, `smooth`) |
| silhouette priority | claws as small as the legs; nothing leads | claws ~2x bigger = the hero shape; tail + red barb second; legs thin secondaries |
| value | 4 browns within a narrow lightness band = mud | 3 bands (dark underside/legs, mid shell, light ridge/tips) + one danger accent; gate warns on a flat band |
| edge | sharp blocks, 1-segment chamfers | soft bevels (seg 2-3) and smooth-shaded tubes, one consistent edge treatment |
| light | flat colour: parts look pasted on | baked AO + ground gradient in vertex colours (`bake_shading`); Roblox multiplies them with `MeshPart.Color` |
| collision | the render mesh collided | an invisible box proxy (`collider`); visible parts CanCollide/CanQuery off |

## Write a brief before modelling (the docstring at the top of the build script)
Settle each axis in one line, with observable properties (never "beautiful", "cinematic", "high quality", or an artist's name):
- **Role + camera:** what the player does with it, from how far (third-person 10-40 studs is typical), its size in studs.
- **Shape language:** rounded/angular/chunky/slender; which shape signals danger, reward, interactable.
- **Silhouette priority:** the ONE hero shape, the second read, and which parts must never merge into the body mass.
- **Value:** 3 bands (dark, mid, light) + 1-2 accents with roles (danger red, reward gold, interact cyan). It must read in greyscale.
- **Palette:** exact hexes with roles; 3-6 colours per asset; reuse the family palette across assets.
- **Edges:** bevel width and segments, smooth vs faceted: the same for the whole family.
- **Material:** which Roblox Material per role (chitin SmoothPlastic, metal Metal, glow Neon) - few, deliberate.
- **Detail density:** where detail goes (head, claws, stinger), where it does not (plates stay simple).
- **Motion/rig:** which parts move, where their pivots are.
- **Exclusions:** what this asset must not look like (e.g. "not a spider": short legs, big claws).

## Build the hero first, then the family
Approve ONE representative asset (the hero enemy, the main building piece) at game scale in Studio before making the set.
Then build the family from the same brief, palette, edge treatment and texel/vertex density, changing one thing at a time.
Drift signals: proportions/limb thickness changing between assets, near-duplicate colours creeping in, different bevel
widths, highlights implying different light, detail density growing on later assets. When drift shows, go back to the hero.

## The three-distance check (every asset, before upload)
`K.snapshot(path, views=..., bw=True, thumb=True)` writes all three:
1. **Thumbnail / gameplay distance** (`*_thumb.png`, 128 px): can you name it and see its hero shape instantly?
2. **Working scale** (`*_1.png` ...): edges, shading, proportions, joins, nothing floating or intersecting badly.
3. **Context** (`rbx.py preview` + `capture` in Studio, next to a 5-stud avatar and the baseplate): scale, lighting, neighbours.
Plus **greyscale** (`*_bw.png`): the value structure must survive without hue. Describe each image in one sentence.
An asset that only works zoomed in is not game art.

## Techniques that move the needle most (cheapest first)
1. **Bake shading** (`K.bake_shading(ao=0.6, ground=0.3)` after merging): AO in crevices + darker towards the ground. Free at
   runtime (vertex colours), keeps the Studio tint editable. Needs vertices: lofts, subdivided or bevelled parts shade
   beautifully, a 12-triangle box only shades at its corners.
2. **Organic forms by lofting**, not cylinders: `K.loft(name, control_points, radii, sides=6-10, per=3-4, flatten=...)`. Radius 0
   at the end = a sharp tip (claws, barbs, horns, teeth). `flatten<1` for blades, tails, pincers.
3. **Exaggerate the hero shape** 1.5-2x past realism; shrink secondaries. Stylised Roblox art lives on proportion.
4. **Soft bevels** (seg 2-3) on every hard-surface part; smooth shading only with bevels or on lofts.
5. **Subdivide a cage** for bulbous forms (`K.smooth(ob, 2)`), each level x4 triangles; stay under the budget.
6. **Value bands + one accent**; the gate warns when the palette lightness spread is under 0.25.
7. **Taper** (`box(taper=(0.85, 0.8))`) turns slabs into plates, armour, rocks, roof edges.

## Attachment: every part grows OUT of something (the v2 -> v2.1 fix)
The user's close-up of v2 showed fingers stuck onto the palm with flat discs, a seam at every elbow, a straight ridge floating
over arched plates and past the face, and mandibles hanging under the head. Rules that fixed it:
1. **Sink, don't touch.** A part starts 0.2-0.5 studs INSIDE its parent (shoulder inside the head, hip inside the belly,
   finger base inside the palm, tail base inside the last plate). Touching surfaces show a seam; overlap hides it.
2. **Round caps at joints.** `loft` ends are hemispheres by default (`caps="round"`); two tubes that share a joint centre
   with similar radii make one smooth ball joint (arm + forearm at the elbow). Flat caps only for cut ends (`caps="flat"`).
3. **Attach to exact surfaces.** `smooth()` shrinks its cage ~25%, so anything placed against the cage's faces floats.
   Use `blob()` (an ellipsoid of exact size) for palms, heads, bulbs, then put children inside its surface by arithmetic.
4. **Follow the form.** Trim and ridges are lofts through points ON the parent's surface (half-sunk), not straight boxes
   above a curved body; stop them before they collide with another feature (the eyes).
5. **Let the gate find gaps.** GATE A warns "floating: X studs from the nearest part" for any visible part whose surface
   neither enters nor comes within 0.03 studs of another part. Close-ups in Studio find the seams; look at the joints, not only
   the whole silhouette.

## Roblox-side rules taken from the same skills
- **Collision proxies:** never collide on the detailed render mesh. One or a few boxes (`K.collider`), Transparency 1,
  CanCollide + CanQuery on; render parts CanCollide/CanQuery off. CanCollide, CanTouch and CanQuery are separate flags: set each.
- **Creatures/NPCs without a Humanoid:** rig with an `AnimationController` + `Animator` (not a Humanoid), joints as Motor6D
  between parts. The kit's separate pivot-on-joint parts (Tail1..5, StingerBulb, FingerMove) are what you join.
- **Moving enemies:** anchor only the intentional root; an anchored part freezes the whole welded assembly. Server-own
  gameplay-critical assemblies (`SetNetworkOwner(nil)`) so clients cannot drive them.
- **Studio hygiene:** inventory before adding; real named Instances, not everything spawned by one script; remove experiments
  (previews, test cubes, debug folders) when done; report what was actually verified (static / single session / Server &
  Clients), never "looks plausible" as "tested".
- **Provenance:** keep the source of every shipped piece (build script, CC0 kit and licence, generator and version) next to the
  manifest. Uploaded assets go to the user's account and through moderation: say so.
