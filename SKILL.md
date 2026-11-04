---
name: robloxmaxxing
description: >-
  Make 3D models for Roblox in Blender and get them into Roblox Studio: props, furniture, buildings and level kits, low-poly
  stylised objects, accessories and NPC bodies, built by Blender Python (rbx_kit: stud-native boxes, wedges, cylinders, pivots on
  hinges, flat colour + Roblox Material per part), checked against Roblox's rules (20k triangles per mesh, one material, one UV set,
  the June 2026 metre/stud change, avatar and UGC budgets), exported as FBX, then previewed live in Studio in seconds (EditableMesh,
  no upload), uploaded through Open Cloud and placed with colours, materials, collision, size and facing checked. Works with MCP for
  Blender and the Roblox Studio MCP (or headless Blender + StudioMCP over stdio). Use for any request to model, build, generate,
  export, import, upload or fix a 3D asset for a Roblox game or experience, a Roblox prop/building/map piece/accessory/NPC, "make
  this in Blender for Roblox", Blender-to-Roblox Studio pipelines, or Roblox mesh import problems (scale, facing, triangles, colours).
---

# robloxmaxxing

Blender is the source of truth for geometry; Studio is where an asset gets its colour, collision and final look. A build script
(bpy) makes named, low-poly parts in studs; **GATE A** checks Roblox's rules; `export` writes the FBX plus two sidecars; `rbx.py`
moves it into Studio and checks it there (**GATE S**). Every number comes from `references/specs.md` (Roblox's rules as of
4 Nov 2026, sourced in `~/Ngonten/Maxxing/reports/Roblox 3D models with Blender.md`).

`SKILL` = this folder. `B` = `/Applications/Blender.app/Contents/MacOS/Blender` (5.1). Run Python helpers with `python3 -I`.
Read `references/art-direction.md` before modelling anything that should look good (the brief, the three-distance check, the
techniques that turned the v1 scorpion into v2) and `references/modeling.md` once per session (build recipe, stud scale, lessons).

**Looks are a gate, not a hope.** Every asset starts with an ART BRIEF docstring in its build script (role + camera, hero
shape, value bands, palette roles, edges, exclusions), builds organic parts with `loft`/`smooth`/`taper`, exaggerates its hero
shape, ends with `K.bake_shading()`, and passes the three-distance check (`snapshot(bw=True, thumb=True)` + a Studio capture)
before upload. Boxes-and-cylinders with flat colour is a blockout, not a deliverable.

## The pipeline
| stage | where | do | gate |
|---|---|---|---|
| 0. setup | Blender | `K.setup()` (stud-native), `K.asset("Name")` | - |
| 1. blockout (optional) | Studio MCP | `generate_procedural_model` / `generate_scene` for layout ideas, `screen_capture`; throwaway | the user agrees on silhouette + footprint in studs |
| 1b. brief | build script | ART BRIEF docstring (`references/art-direction.md`) | every axis answered with observable properties |
| 2. model | Blender | `K.box(taper=, bevel=, seg=2)`, `K.loft` (organic tubes, round caps), `K.blob` (exact ellipsoids to attach to), `K.smooth` (bulbous), `K.wedge/cyl/sphere/build`, pivots on joints, `K.mat(hex, Material)`, `K.collider` for collision | `K.snapshot` / `look`: describe it in one sentence |
| 3. game-ready | Blender | `K.merge_by_material(keep=...)`, `K.bake_shading()`, `K.export(out, kind=...)`, `K.snapshot(..., bw=True, thumb=True)` | **GATE A** (in `export`, incl. value-structure warning) + the three-distance check |
| 4. preview | Studio | `rbx.py preview out/Name.mesh.json [--at x,y,z]`, then `rbx.py capture Name` | look at the capture; iterate 2-4 until right |
| 5. keep it | Studio | `rbx.py upload out/Name.fbx` -> `rbx.py place out/Name.manifest.json --asset-id N` (or 3D Importer + `rbx.py apply`) | **GATE S**: size ratio 1.00, "facing ok", every part matched, capture described |

### 2-3. Build (headless is the default; the script is the source of truth)
```bash
"$B" -b --factory-startup -P path/to/build.py -- --out path/to/out      # see examples/chest/build.py
```
```python
import sys; sys.path.insert(0, SKILL + "/blender"); import rbx_kit as K
K.setup(); K.asset("TreasureChest")
K.box("Body", (4, 2.6, 1.8), (0, 0, 0.9), "#8A5A33", material="WoodPlanks", bevel=0.06)
K.cyl("Lid", 1.3, 4, (0, 0, 1.8), "#8A5A33", material="WoodPlanks", verts=10, rot=(0, 90, 0), origin=(0, 1.3, 1.8))  # hinge pivot
...
K.merge_by_material(keep=("Lid",)); K.export(OUT, kind="prop"); K.snapshot(OUT + "/TreasureChest.png")
```
Live, with MCP for Blender: in `execute_blender_code`, `import sys, importlib; sys.path.insert(0, SKILL + "/blender"); import rbx_kit as K;
importlib.reload(K)` and call the same functions; use `look` to see each step. Keep edits in the build script and re-run it rather than
hand-patching the scene. `kind`: prop (5k budget, warn), hero (15k), building (20k), accessory / clothing (4k, ONE mesh, fail), body (10,742).

GATE A (`K.check`) FAILs on: a mesh over 20,000 triangles, more than one material per mesh, not exactly one UV set (auto-fixed with box
projection), negative scale, a part over 2048 studs, duplicate part names, textures over 4096, an accessory/clothing that is not one
mesh or over 4,000. WARNs on: floating parts (not sunk into or touching any other part), a flat value structure, open or non-manifold edges, zero-area faces, near-zero thickness, UVs outside 0-1, procedural materials
that will not export, pivots far from the mesh, total over the kind budget. A FAIL is fixed, never argued.

`export` writes `Name.fbx` (Roblox's documented settings: FBX Unit Scale, up Y, forward -Z, Path Mode Copy + embedded textures, no leaf
bones, no baked animation, custom props on), `Name.mesh.json` (triangles in Roblox axes, for the preview) and `Name.manifest.json`
(per part: colour, Material, collision, anchored, pivot, size, triangles; overall size; the GATE A findings; the FBX hash).

### 4. Preview in Studio (no key, no upload, seconds)
```bash
python3 -I "$SKILL/scripts/rbx.py" preview out/TreasureChest.mesh.json --at 0,0.5,-12
python3 -I "$SKILL/scripts/rbx.py" capture TreasureChest --out out/studio.png      # then Read the PNG and describe it
```
`rbx.py` runs its own StudioMCP client over stdio (alongside the `Roblox_Studio` MCP), so mesh data never passes through the
conversation. The preview builds each part as an EditableMesh MeshPart with the manifest's colour, Material, collision and pivot,
inside a Model tagged `RbxPreview`. **It is not saved with the place** (in-memory mesh): it is for judging the asset in Roblox
lighting next to the baseplate and a character. Re-running `preview` replaces it.

### 5. Keep it: Open Cloud (scripted) or the 3D Importer (by hand)
`CreateAssetAsync` (upload as the Studio user) is blocked from `execute_luau`, and no Studio MCP tool takes a local mesh file, so a
permanent mesh needs one of:
- **Open Cloud** (`rbx.py upload`): needs an API key with Assets Read+Write from https://create.roblox.com/dashboard/credentials. The
  user creates it, copies it, and stores it themselves from the clipboard:
  `security add-generic-password -U -s roblox-open-cloud -a "$USER" -w "$(pbpaste)" && pbcopy </dev/null`, or sets
  `ROBLOX_API_KEY` in their shell. **Not** the typed `-w` prompt: it silently cuts input at 128 characters and Roblox keys are
  longer (HTTP 401 "Invalid API Key"; `upload` warns when the stored key is exactly 128). Never ask for the key in chat, never pass it as an argument, never print it. The creator defaults to
  the logged-in Studio user (`rbx.py user`); `--group-id N` for a group. `--dry-run` prints the request without sending.
  The registry `rbx_assets.json` (next to the FBX) remembers asset IDs: an unchanged FBX is skipped, a changed one is uploaded as a
  new version of the same asset (FBX only). Models upload as Packages and pass moderation first.
- **3D Importer** (no key): File > Import 3D, pick `Name.fbx`; Scale Unit **Studs**, Merge Meshes off, keep Use Imported Pivot,
  Anchored as needed; then `rbx.py apply out/Name.manifest.json [--path Workspace.Name]` sets colours/materials/collision and runs
  the size and facing checks.
```bash
python3 -I "$SKILL/scripts/rbx.py" upload out/TreasureChest.fbx                       # -> asset id (and rbx_assets.json)
python3 -I "$SKILL/scripts/rbx.py" place out/TreasureChest.manifest.json --asset-id 123 --at 0,0.5,-12 [--fix-scale]
python3 -I "$SKILL/scripts/rbx.py" capture TreasureChest --out out/studio_final.png
```
GATE S (printed by `place` / `apply`): `size ... ratio 1.000 ok` (a mismatch means a unit problem; `--fix-scale` rescales the Model),
`facing ok` (else `FACING FLIPPED on Z`: re-export with `K.export(..., forward="Z")`), no "unmatched" or "missing" parts, and the
capture described in one sentence. `place` removes the preview of the same name (`--keep-preview` keeps it).

**Verified on a real upload (4 Nov 2026, TreasureChest, asset 76030643818252, Open Cloud, moderation Approved in seconds):**
- `K.export` defaults (FBX Unit Scale, up Y, forward -Z) arrive at **ratio 1.000** and **facing correct**: every part's position,
  rotation and size matched the preview exactly, so the preview is a faithful stand-in for the upload.
- Open Cloud gives `Model > MeshPart` per Blender object, **named exactly like the Blender objects**, plus a `PackageLink`.
- Pivots survive: the lid's hinge `PivotOffset` matched the preview to 0.0001 stud.
- **The raw upload is grey `Plastic`, `Anchored = false`, CollisionFidelity Default, no SurfaceAppearance**: FBX material colours do
  NOT come through. Always run `place` (or `apply`): it sets colour, Material, anchoring and collision from the manifest
  (CollisionFidelity is settable from `execute_luau`). Unanchored props fall through the world in Play.
- **Baked vertex shading survives the FBX upload** (ScorpionV2, asset 105844756834808): Roblox multiplies vertex colours with
  `MeshPart.Color` (tested with EditableMesh and with the upload), so `bake_shading` greys + the manifest tint = shaded colour.
- Collision proxies survive: the `Hitbox` arrives and `place` sets it Transparency 1 / CanCollide; render parts CanCollide off.
- **Updating works:** re-running `upload` on a changed FBX PATCHes the same asset (ScorpionV2 -> revision 2, approved).
  Swap it in a place by destroying the old instance, then `place` again (insert_asset loads the latest revision).
- `preview` only ever writes into the `RbxPreview` model (a name-only lookup once wrote preview parts into the uploaded
  model of the same name; fixed 4 Nov 2026).
- Still unverified: textured FBX -> SurfaceAppearance (flat-colour assets do not need it), and the 3D Importer route.

## Levels, characters, wearables
- **Levels:** model each kit piece once as its own asset, place it once, then clone it in Studio with `execute_luau` in chunks with
  `task.wait()` (same MeshId = batched draw calls). Never import a whole level as one FBX.
- **NPCs / bodies:** one contiguous, watertight, textured humanoid in A-pose with separate eyes, teeth and tongue -> import ->
  `auto_setup_avatar` (Development for NPCs, Platform for the Marketplace). Check the -Z / +Z facing on the first one.
- **Accessories / layered clothing:** `kind="accessory"` / `"clothing"`; cages and attachment from Roblox's templates and the Accessory
  Fitting Tool (`references/specs.md`). Selling needs ID verification, 2FA, Plus/Premium and fees: say so before anyone plans on it.
- **Neural fallbacks** (organic one-offs only): Studio's `generate_mesh`, MCP for Blender's `generate_3d` (may cost credits: ask),
  Meshy. Every neural mesh still goes through stage 3. Roblox's open Cube weights are research-only: not for a game you ship.

## Never ship
A mesh over 20k triangles or a part you never looked at; a level imported as one FBX; procedural shader detail you expect to survive;
an importer set to Meter without checking the ratio; brand characters (Claude, Gemini, Upwork, Meshy mascots from reelmaxxing) as
Roblox UGC or game characters; an asset you upload without the user knowing it goes to their Roblox account and through moderation;
"it works" without the GATE S lines and a described capture.

## Files
| file | use |
|---|---|
| `blender/rbx_kit.py` | setup, asset, mat, box (taper), wedge, cyl, sphere, blob (exact ellipsoid), loft + spline (organic tubes, round/flat caps), smooth (subdivision), collider (proxy), instance, build (kit as data), apply, merge_by_material, bake_shading (AO + ground gradient -> vertex colours), ensure_uv, set_origin, check (GATE A + value structure), export, snapshot (eevee/workbench, bw, thumb) |
| `references/art-direction.md` | the brief, the three-distance check, what made v1 weak and v2 better, Roblox collision/rig/hygiene rules (from awesome-gamedev-agent-skills) |
| `references/scorpion_v1_v2_studio.jpg` | v1 Blender / v2 art-directed / Studio Parts-only, side by side in Studio |
| `scripts/rbx.py` | studios, user, preview, upload, place, apply, capture, luau, tools (StudioMCP over stdio + Open Cloud, stdlib only) |
| `references/specs.md` | Roblox's import, texture, avatar/UGC and Studio rules with dates |
| `references/modeling.md` | the bpy recipe, stud scale cheat sheet, kits, textures, characters, lessons from reelmaxxing |
| `examples/chest/` | `build.py` (the treasure chest: hinge-pivot lid, merged bands) and its `out/` (FBX, sidecars, snapshots, Studio capture) |
