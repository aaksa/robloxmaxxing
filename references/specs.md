# Roblox import rules (as of 4 Nov 2026)

Sources: the research report `~/Ngonten/Maxxing/reports/Roblox 3D models with Blender.md` (every line there has its URL).
Where the docs and the live engine disagree, both are given. Re-check anything dated before you rely on it for a release.

## Any mesh
| rule | value | note |
|---|---|---|
| triangles | **20,000 per mesh (MeshPart)** | over it, the importer auto-simplifies with "funky results"; no vertex or per-file cap documented |
| geometry | watertight, no zero thickness, no n-gons, quads where possible | one-sided faces are invisible from behind; "Make Double Sided" costs performance |
| materials | **one per mesh** | a multi-material object is split into several MeshParts on import |
| UVs | **one UV set, inside 0-1**, overlaps allowed | `rbx_kit` adds box-projection UVs when missing |
| vertex colours | import from FBX and glTF (importer "Ignore Vertex Colors" off by default); **multiplied with MeshPart.Color** (tested 4 Nov 2026, EditableMesh and Open Cloud FBX) | `rbx_kit` stores grey shading (AO + ground gradient) there and the flat tint in MeshPart.Color |
| formats | .fbx, .gltf/.glb, .obj (importer); .fbx/.gltf/.glb/.rbxm (Open Cloud, **no .obj**) | only FBX and glTF keep hierarchy, PBR, cages, rigs, animation; FBX holds ONE animation track; only FBX assets can be updated in place by Open Cloud |
| hierarchy | FBX: Model > MeshPart per mesh. glTF: Model > Model per mesh > MeshPart per primitive | "Merge Meshes" collapses everything into one MeshPart |
| largest part | 2048 studs per axis | |
| upload size | 20 MB per Open Cloud call; images < 8000 x 8000 | |

## Scale and axes (the 2026 trap)
- **16 June 2026:** importer Scale Unit "Meter" changed from 20 studs/m to **25/7 ~ 3.571 studs/m** (1 stud = 0.28 m). Custom Scale Factor
  (since 19 May 2026) = 5.6 restores the old behaviour. Every older "import in metres" tutorial is now off by 5.6x.
- This skill is **stud-native**: Blender Unit System None, 1 BU = 1 stud, FBX "Apply Scalings: FBX Unit Scale", importer Scale Unit
  **Studs**. `rbx.py place/apply` compares the result with the manifest size and prints the ratio (`--fix-scale` rescales).
- Axes: Blender Z up, front -Y. Roblox Y up, front -Z (LookVector). `rbx_kit` maps Roblox = (-x, z, y) for the preview and the
  manifest. FBX export: up Y, forward `-Z` (Blender's default): **verified 4 Nov 2026** on an Open Cloud upload (ratio 1.000,
  every part's position and rotation identical to the preview). `place` still prints "facing ok (axes tested ...)" every time.

## Pivots, LOD, collision, draw calls
- Importer defaults: Set Pivot to Scene Origin ON, Use Imported Pivot ON -> the Blender object origin becomes the MeshPart pivot, the
  world origin the Model pivot. Put origins at the base or the hinge (the chest's lid pivots on its hinge line).
- No author LOD meshes. RenderFidelity Automatic switches detail at 250 and 500 studs; Model.LevelOfDetail SLIM needs streaming.
- CollisionFidelity, cheapest -> dearest: Box, Hull, Default, PreciseConvexDecomposition (+ Tunable with a precision slider).
  Box for small props, Hull for round ones, Default for walkable or concave shapes. Set per part with `ob["rbx_collision"]`.
- **Draw calls cost more than triangles.** Meshes batch only with the same MeshContent AND identical SurfaceAppearance. So: model each
  unique piece once, import it once, duplicate it in Studio (or use Packages), share one trim sheet / Color tints. Never import a
  whole assembled level as one FBX.

## Textures / PBR (SurfaceAppearance)
- Maps: Color, Normal, Roughness, Metalness, EmissiveMask. Metalness workflow only. **Normal maps OpenGL (Y+)** = Blender's native.
- Separate greyscale maps (no ORM packing). Map properties are Plugin security: no runtime swaps (only the Color tint).
- Size: spec page says 1024 for UV maps; the engine has rendered **4K since 30 Jan 2026** (8K imports are transcoded to 4K);
  the performance docs still advise 512 for most images. Avatar items: 2048 max.
- Texel guide (stud-native): 256 px for a 5x5-stud surface, 512 for 10x10, 1024 for 20x20.
- Open Cloud FBX uploads (verified 4 Nov 2026, flat-colour asset): material colours are dropped (parts arrive grey Plastic,
  unanchored, collision Default, no SurfaceAppearance); the manifest step restores them. Still unverified: whether a textured FBX
  gets a SurfaceAppearance. Test on the first textured asset before relying on it. Procedural Blender nodes never export - bake to images (PAWS: Bakery, or Cycles bake).

## Avatars and UGC (stricter, on top of the above)
| item | budget | must have |
|---|---|---|
| body | 10,742 tris total: head 4,000, torso 1,750, each limb 1,248 | 15 watertight `<Part>_Geo` meshes + `_OuterCage` each; R15 hierarchy Root > HumanoidRootNode > LowerTorso > UpperTorso; Root and LowerTorso at 0,0,0; `_Att` attachments |
| skinning | max 4 influences per vertex, none on Root | bones scale 1, rotation 0 at rest |
| dynamic head | inside the head budget | `DynamicHead` joint under Head; >= 17 FACS poses; `Head_Geo` string props `RootFaceJoint`, `Frame0..N`; FBX "Include Custom Properties" ON |
| rigid accessory | 4,000 tris, ONE mesh, textures <= 2048 | fits its per-type box (Normal Hat 1.87 x 2.5 x 1.87 studs); attachments come from the Accessory Fitting Tool, not Blender |
| layered clothing | 4,000 tris, ONE mesh, <= 8x8x8 studs, skinned to R15 (<= 4 bones/vertex) | `<Name>_InnerCage` + `<Name>_OuterCage` from Roblox's cage templates; move outer-cage verts only; never delete cage verts/UVs |
- **Avatar Setup / `auto_setup_avatar`** (Studio MCP): give it one contiguous, watertight, textured humanoid in A- or T-pose, distinct neck,
  separate eyes/teeth/tongue, no accessories; it makes the R15 rig, skinning, FACS, cages and the 15-part split. Presets: Platform
  (Marketplace) / Development (NPCs).
- Facing conflict in the docs: the body spec says +Z, Avatar Setup says front faces -Z. Check with one test import.
- Marketplace (since 14 Jul 2026): ID verification to upload; 2-step verification + Roblox Plus/Premium to publish; 80 Robux upload
  fee (500 with an emissive mask); refundable advance 600 (3D clothing) to 2,500 (body) Robux.
- Animation: FBX with animation on, NLA strips / All Actions / Force start-end keys OFF, constraints and IK baked to keys; one clip per
  file; import via Animation Editor > ... > Import > From File (or the RBXMonkey live link).

## Studio-side limits that shape the pipeline
- **No Studio MCP tool takes a local mesh file.** `store_image` takes local PNG/JPG (<= 5 MB), `upload_image` takes URLs.
- `AssetService:CreateAssetAsync` (upload as the Studio user, no key) **is blocked from execute_luau** ("not available yet",
  tested 4 Nov 2026). So permanent meshes come from Open Cloud (API key) or the 3D Importer (by hand).
- EditableMesh (what `rbx.py preview` uses): 60,000 vertices / 20,000 triangles per mesh; lives in memory, not a saved asset.
- `execute_luau` runs on Studio's main thread: chunk heavy loops with `task.wait()` (the preview yields every 1,000 triangles).
- Studio's own generators (via the Studio MCP): `generate_procedural_model` (primitives, 50 per rolling 24 h in Assistant),
  `generate_scene` (beta since 30 Oct 2026), `generate_mesh` (10k tris default), `generate_texture`, `generate_material`,
  `segment_mesh` (<= 5 parts, preview), `generate_avatar` / `auto_setup_avatar`.
- Roblox's open Cube 3D / CubePart weights are **research-only** (CUBE3D RESEARCH-ONLY RAIL-MS licence): not for a commercial game.
