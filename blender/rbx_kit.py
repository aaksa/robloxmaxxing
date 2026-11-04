"""rbx_kit - build Roblox-ready assets in Blender and hand them to Studio.

Convention: 1 Blender unit = 1 stud (Unit System None), Z up, the asset's front faces -Y (Blender's front view).
One collection = one asset = one Roblox Model; one mesh object = one MeshPart (one material each).

Load it:
  headless   import sys; sys.path.insert(0, "<skill>/blender"); import rbx_kit as K
  live MCP   exec(open("<skill>/blender/rbx_kit.py").read(), globals())   (then call the functions directly)

Build:      K.setup(); K.asset("Chest"); K.box("Base", (4, 3, 2), (0, 0, 1), "#8B5A2B", material="Wood") ...
Finish:     K.merge_by_material()  (fewer MeshParts = fewer draw calls)   K.apply()   rep = K.check(kind="prop")
Export:     K.export("out/")  -> Chest.fbx, Chest.mesh.json (Studio preview), Chest.manifest.json (colours, collision, size)
Look:       K.snapshot("out/Chest.png")  (Workbench, three-quarter view; headless-safe)
"""
import bpy, bmesh, math, json, os, re, hashlib
from mathutils import Vector, Matrix

TRI_LIMIT = 20000                       # Roblox: per mesh (MeshPart), hard limit
BUDGETS = {"prop": 5000, "hero": 15000, "building": 20000, "accessory": 4000, "clothing": 4000, "body": 10742}
PART_MAX = 2048.0                       # Roblox: largest part size per axis, studs
MATERIALS = ("Plastic", "SmoothPlastic", "Wood", "WoodPlanks", "Metal", "DiamondPlate", "CorrodedMetal", "Foil", "Neon",
             "Glass", "ForceField", "Concrete", "Brick", "Cobblestone", "Granite", "Marble", "Slate", "Pebble", "Sand",
             "Sandstone", "Grass", "LeafyGrass", "Ground", "Mud", "Rock", "Basalt", "Ice", "Glacier", "Snow", "Fabric",
             "Carpet", "Leather", "Rubber", "Cardboard", "Plaster", "ClayRoofTiles", "RoofShingles", "CeramicTiles", "Asphalt",
             "Pavement", "Limestone", "CrackedLava", "Salt")

_ASSET = {"col": None}
_MATS = {}


# ---------------------------------------------------------------- scene
def setup(clear=True):
    """stud-native scene: Unit System None, unit scale 1. clear=True empties the file (factory scene)."""
    sc = bpy.context.scene
    if clear:
        for ob in list(bpy.data.objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        for c in list(bpy.data.collections):
            bpy.data.collections.remove(c)
        for m in list(bpy.data.meshes):
            bpy.data.meshes.remove(m)
        _MATS.clear()
    sc.unit_settings.system = "NONE"
    sc.unit_settings.scale_length = 1.0
    return sc


def asset(name):
    """start (or switch to) the asset collection `name`; new parts land in it"""
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    _ASSET["col"] = col
    return col


def _col(collection=None):
    if collection is None:
        collection = _ASSET["col"]
    if isinstance(collection, str):
        collection = bpy.data.collections[collection]
    if collection is None:
        raise RuntimeError("no asset collection: call K.asset('Name') first")
    return collection


def parts(collection=None):
    return [o for o in _col(collection).all_objects if o.type == "MESH"]


# ---------------------------------------------------------------- colour + material
def lin(hexcol):
    h = hexcol.lstrip("#")
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return tuple(f(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))


def mat(hexcol, material="SmoothPlastic", rough=None, metal=None):
    """flat-colour material. The colour and Roblox Material travel in the manifest (Studio sets MeshPart.Color/Material);
    the Principled colour is only what Blender shows. Procedural nodes do NOT export - bake them (references/modeling.md)."""
    if material not in MATERIALS:
        raise ValueError("unknown Roblox material %r" % material)
    hexcol = "#" + hexcol.lstrip("#").upper()
    key = (hexcol, material)
    if key in _MATS:
        return _MATS[key]
    m = bpy.data.materials.new("rbx_%s_%s" % (material, hexcol[1:]))
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*lin(hexcol), 1)
    # show baked shading (the "Shade" colour attribute, see bake_shading) in Blender renders: base x shade, and plain base
    # where a mesh has no Shade attribute (missing attribute -> alpha 0 -> mix factor 0). Roblox does the same multiply.
    att = nt.nodes.new("ShaderNodeAttribute")
    att.attribute_name = "Shade"
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    _enum(mix, "blend_type", ("MULTIPLY",))
    ins = [s for s in mix.inputs if s.type == "RGBA"]
    ins[0].default_value = (*lin(hexcol), 1)
    nt.links.new(att.outputs["Alpha"], mix.inputs[0])
    nt.links.new(att.outputs["Color"], ins[1])
    nt.links.new(next(s for s in mix.outputs if s.type == "RGBA"), bsdf.inputs["Base Color"])
    is_metal = material in ("Metal", "DiamondPlate", "CorrodedMetal", "Foil")
    bsdf.inputs["Roughness"].default_value = rough if rough is not None else (0.35 if material in ("SmoothPlastic", "Glass", "Ice") else 0.7)
    bsdf.inputs["Metallic"].default_value = metal if metal is not None else (0.8 if is_metal else 0.0)
    if material == "Neon":
        bsdf.inputs["Emission Color"].default_value = (*lin(hexcol), 1)
        bsdf.inputs["Emission Strength"].default_value = 3.0
    m.diffuse_color = (*lin(hexcol), 1)          # solid-view colour
    m["rbx_color"] = hexcol
    m["rbx_material"] = material
    _MATS[key] = m
    return m


# ---------------------------------------------------------------- builders (low-poly, named, pivot where you want it)
def _link(ob, collection=None):
    _col(collection).objects.link(ob)
    return ob


def _white_shade(me):
    """every kit mesh carries a white 'Shade' attribute (a missing attribute renders BLACK through the material's multiply)"""
    if "Shade" not in me.color_attributes:
        at = me.color_attributes.new("Shade", "BYTE_COLOR", "CORNER")
        for d in at.data:
            d.color_srgb = (1, 1, 1, 1)
        me.color_attributes.active_color = at
    return me


def _from_bm(name, bm, collection=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    _white_shade(me)
    return _link(bpy.data.objects.new(name, me), collection)


def _finish(ob, loc, color, material, origin, rot, bevel, seg, smooth, collision, size):
    """place the mesh: centre at loc, then move the pivot to `origin` ('center' | 'bottom' | 'top' | world (x, y, z))"""
    me = ob.data
    if rot != (0, 0, 0):
        me.transform(Matrix.Rotation(math.radians(rot[2]), 4, "Z") @ Matrix.Rotation(math.radians(rot[1]), 4, "Y")
                     @ Matrix.Rotation(math.radians(rot[0]), 4, "X"))
    loc = Vector(loc)
    if origin == "center":
        piv = loc.copy()
    elif origin in ("bottom", "top"):
        zs = [v.co.z for v in me.vertices]
        piv = loc + Vector((0, 0, min(zs) if origin == "bottom" else max(zs)))
    else:
        piv = Vector(origin)
    off = loc - piv
    me.transform(Matrix.Translation(off))
    ob.location = piv
    me.materials.append(mat(color, material))
    if bevel:
        md = ob.modifiers.new("bevel", "BEVEL")
        md.width = min(bevel, min(size) / 3)
        md.segments = seg
        md.limit_method = "ANGLE"
        md.harden_normals = True            # flat faces stay flat, only the chamfers shade smooth
    # reelmaxxing lesson: smooth shading on a sharp box averages corner normals across big faces (blotchy, flickers);
    # so: flat unless bevelled (harden normals) or explicitly smooth (then sharp edges by angle)
    for p in me.polygons:
        p.use_smooth = bool(bevel) or bool(smooth)
    if smooth and not bevel:
        try:
            me.set_sharp_from_angle(angle=math.radians(smooth if isinstance(smooth, (int, float)) and smooth is not True else 40))
        except Exception:
            pass
    if collision:
        ob["rbx_collision"] = collision
    return ob


def box(name, size, loc=(0, 0, 0), color="#A3A2A5", material="SmoothPlastic", origin="center", rot=(0, 0, 0), bevel=0.0,
        seg=1, collision=None, collection=None, taper=None):
    """box of `size` (x, y, z studs) centred at `loc`. bevel>0 adds a chamfer (seg=1: +12 faces, cheap; seg=2-3 reads as
    rounded plastic in Roblox light). taper=(tx, ty) scales the TOP face (a plate, a frustum, a wedgy armour piece)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        tx, ty = taper if (taper and v.co.z > 0) else (1, 1)
        v.co = Vector((v.co.x * size[0] * tx, v.co.y * size[1] * ty, v.co.z * size[2]))
    return _finish(_from_bm(name, bm, collection), loc, color, material, origin, rot, bevel, seg, False, collision, size)


def spline(pts, per=4):
    """Catmull-Rom through control points: a few points in, a smooth path out (per = samples per span)"""
    P = [Vector(p) for p in pts]
    if len(P) < 3:
        return P
    P2 = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(P2) - 2):
        p0, p1, p2, p3 = P2[i - 1], P2[i], P2[i + 1], P2[i + 2]
        for k in range(per):
            t = k / per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-1])
    return out


def _lerp_list(vals, n):
    """resample a list of numbers to n values (radii along a spline)"""
    if len(vals) == n:
        return list(vals)
    out = []
    for i in range(n):
        x = i * (len(vals) - 1) / max(n - 1, 1)
        a = int(math.floor(x))
        b = min(a + 1, len(vals) - 1)
        out.append(vals[a] + (vals[b] - vals[a]) * (x - a))
    return out


def loft(name, pts, radii, color="#A3A2A5", material="SmoothPlastic", sides=8, flatten=1.0, per=4, origin="start",
         smooth=True, collision=None, collection=None, up=(0, 0, 1), caps="round", cap_steps=3):
    """an organic tube along a smooth path: legs, tails, horns, tentacles, claws, pipes, branches.
    pts: control points (world, studs); radii: one per control point (0 at the end = a sharp tip).
    flatten<1 squashes the cross-section towards `up` (a flat tail, a blade, a pincer). Pivot: 'start' (the joint), 'center' or xyz.
    caps='round' (default) closes each open end with a hemisphere, so two tubes meeting at a joint blend like capsules
    instead of showing flat discs; 'flat' gives disc caps. Start a tube INSIDE the part it grows from (see art-direction.md).
    Triangles ~= sides x 2 x (samples - 1) + caps (sides x 2 x cap_steps each)."""
    path = spline(pts, per) if per > 1 else [Vector(p) for p in pts]
    R = _lerp_list(list(radii), len(path))
    T = [(path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized() for i in range(len(path))]
    st = []                      # stations: (centre, radius, tangent)
    if caps == "round" and R[0] > 1e-4:
        for k in range(cap_steps, 0, -1):
            a = math.pi / 2 * k / cap_steps
            st.append((path[0] - T[0] * R[0] * math.sin(a), R[0] * math.cos(a) if k < cap_steps else 0.0, T[0]))
    st += [(path[i], R[i], T[i]) for i in range(len(path))]
    if caps == "round" and R[-1] > 1e-4:
        for k in range(1, cap_steps + 1):
            a = math.pi / 2 * k / cap_steps
            st.append((path[-1] + T[-1] * R[-1] * math.sin(a), R[-1] * math.cos(a) if k < cap_steps else 0.0, T[-1]))
    bm = bmesh.new()
    rings = []
    upv = Vector(up).normalized()
    prev_n = None
    for p, r, t in st:
        n = prev_n if prev_n is not None else (upv - t * upv.dot(t))
        if n.length < 1e-4:
            n = Vector((1, 0, 0)) - t * t.x
        n = (n - t * n.dot(t)).normalized()          # parallel transport: no twisting along the path
        prev_n = n
        b = t.cross(n).normalized()
        if r <= 1e-4:
            rings.append([bm.verts.new(p)])
            continue
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides
            ring.append(bm.verts.new(p + b * math.cos(a) * r + n * math.sin(a) * r * flatten))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        if len(r0) == 1 and len(r1) == 1:
            continue
        for k in range(sides):
            if len(r1) == 1:
                bm.faces.new((r0[k], r0[(k + 1) % sides], r1[0]))
            elif len(r0) == 1:
                bm.faces.new((r0[0], r1[(k + 1) % sides], r1[k]))
            else:
                bm.faces.new((r0[k], r0[(k + 1) % sides], r1[(k + 1) % sides], r1[k]))
    if len(rings[0]) > 1:
        bm.faces.new(list(reversed(rings[0])))
    if len(rings[-1]) > 1:
        bm.faces.new(rings[-1])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = _from_bm(name, bm, collection)
    me = ob.data
    if origin == "start":
        piv = path[0].copy()
    elif origin == "center":
        piv = sum(path, Vector()) / len(path)
    else:
        piv = Vector(origin)
    me.transform(Matrix.Translation(-piv))
    ob.location = piv
    me.materials.append(mat(color, material))
    for p in me.polygons:
        p.use_smooth = bool(smooth)
    if smooth:
        try:
            me.set_sharp_from_angle(angle=math.radians(50))
        except Exception:
            pass
    if collision:
        ob["rbx_collision"] = collision
    return ob


def blob(name, size, loc=(0, 0, 0), color="#A3A2A5", material="SmoothPlastic", seg=16, rings=10, rot=(0, 0, 0), origin="center",
         collision=None, collection=None):
    """an ellipsoid of EXACT size (x, y, z studs): palms, heads, bellies, eggs, rocks, bulbs. Unlike smooth() on a box (which
    shrinks the cage ~20-40%), its surface is where you put it, so attached parts can be sunk into it reliably."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=0.5)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    return _finish(_from_bm(name, bm, collection), loc, color, material, origin, rot, 0, 1, True, collision, size)


def smooth(ob, levels=1):
    """Catmull-Clark subdivision (applied at export): turns a blocky cage into a soft, organic form. Each level x4 triangles.
    It SHRINKS the cage (a cube ends ~25% smaller per side): don't attach other parts to the cage's faces; use blob() for that."""
    md = ob.modifiers.new("subsurf", "SUBSURF")
    md.levels = md.render_levels = levels
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def collider(name, size, loc, rot=(0, 0, 0), collection=None):
    """an invisible collision proxy box (Transparency 1, CanCollide, CanQuery). When an asset has one, its visible parts
    default to CanCollide off: players and raycasts hit the simple box, not the detailed mesh."""
    ob = box(name, size, loc, "#FF00FF", rot=rot, collision="Box", collection=collection)
    ob["rbx_proxy"] = True
    return ob


def wedge(name, size, loc=(0, 0, 0), color="#A3A2A5", material="SmoothPlastic", origin="center", rot=(0, 0, 0), collision=None,
          collection=None):
    """Roblox WedgePart shape: full bottom, slope rising from the front (-y) up to a tall back (+y)"""
    x, y, z = (s / 2 for s in size)
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in ((-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z), (-x, y, z), (x, y, z))]
    for f in ((0, 3, 2, 1), (0, 1, 5, 4), (3, 4, 5, 2), (0, 4, 3), (1, 2, 5)):
        bm.faces.new([vs[i] for i in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _finish(_from_bm(name, bm, collection), loc, color, material, origin, rot, 0, 1, False, collision, size)


def cyl(name, r, h, loc=(0, 0, 0), color="#A3A2A5", material="SmoothPlastic", verts=12, r2=None, origin="center", rot=(0, 0, 0),
        smooth=True, collision=None, collection=None):
    """cylinder (or cone/frustum with r2) along Z. verts=8-16 for props; each side costs 4 triangles"""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=verts, radius1=r, radius2=r if r2 is None else r2, depth=h)
    if r2 == 0:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    return _finish(_from_bm(name, bm, collection), loc, color, material, origin, rot, 0, 1, smooth, collision, (r * 2, r * 2, h))


def sphere(name, r, loc=(0, 0, 0), color="#A3A2A5", material="SmoothPlastic", seg=12, rings=8, origin="center", smooth=True,
           collision=None, collection=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    return _finish(_from_bm(name, bm, collection), loc, color, material, origin, (0, 0, 0), 0, 1, smooth, collision, (r * 2,) * 3)


def instance(name, src, loc, rot_z=0.0, collection=None):
    """a linked duplicate (same mesh data). In Studio, duplicate the MeshPart instead of exporting copies (same MeshId batches)."""
    ob = bpy.data.objects.new(name, src.data)
    ob.location = loc
    ob.rotation_euler = (0, 0, math.radians(rot_z))
    for md in src.modifiers:                       # modifiers live on the object, not the mesh: copy them (bevels!)
        nm = ob.modifiers.new(md.name, md.type)
        for p in md.bl_rna.properties:
            if not p.is_readonly and p.identifier not in ("name", "type"):
                try:
                    setattr(nm, p.identifier, getattr(md, p.identifier))
                except (AttributeError, TypeError, ValueError):
                    pass
    for k in ("rbx_collision", "rbx_anchored", "rbx_cancollide", "rbx_castshadow"):
        if k in src:
            ob[k] = src[k]
    return _link(ob, collection)


def build(spec, collection=None):
    """a kit as data: [{"shape": "box", "name": "Seat", "size": [2, 2, 0.4], "loc": [0, 0, 1.6], "color": "#8A5A33",
    "material": "Wood", ...}, ...]. Keys are the builder's arguments; "shape" is box | wedge | cyl | sphere. Returns the objects."""
    makers = {"box": box, "wedge": wedge, "cyl": cyl, "sphere": sphere}
    out = []
    for item in spec:
        kw = dict(item)
        fn = makers[kw.pop("shape", "box")]
        name = kw.pop("name")
        for k in ("size", "loc", "rot"):
            if k in kw:
                kw[k] = tuple(kw[k])
        if isinstance(kw.get("origin"), list):
            kw["origin"] = tuple(kw["origin"])
        out.append(fn(name, collection=collection, **kw))
    return out


# ---------------------------------------------------------------- finishing
def tris(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    ev.to_mesh_clear()
    return n


def apply(collection=None):
    """bake modifiers and rotation/scale into the meshes, flatten the hierarchy; pivots (locations) are kept.
    Linked duplicates become single-user here, so model each unique piece ONCE per asset and instance in Studio."""
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in parts(collection):
        mw = ob.matrix_world.copy()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        ob.modifiers.clear()
        old = ob.data
        ob.data = me
        me.name = ob.name
        if old.users == 0:
            bpy.data.meshes.remove(old)
        loc, rot, sca = mw.decompose()
        me.transform(Matrix.LocRotScale(None, rot, sca))
        if any(s < 0 for s in sca):
            me.flip_normals()
        ob.parent = None
        ob.matrix_world = Matrix.Translation(loc)
    return parts(collection)


def join(name, objs):
    """join specific parts (same material) into one object named `name`, keeping the first one's pivot. Use it to fold the
    gear of ONE body segment together (pads + gauntlet), where merge_by_material would weld gear across limbs and break a rig."""
    objs = [bpy.data.objects[o] if isinstance(o, str) else o for o in objs]
    mats = {o.data.materials[0].name for o in objs if o.data.materials}
    if len(mats) > 1:
        raise ValueError("join(%s): parts have different materials %s (Roblox: one material per mesh)" % (name, sorted(mats)))
    dg = bpy.context.evaluated_depsgraph_get()
    base = objs[0]
    bm = bmesh.new()
    for o in objs:
        tmp = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        tmp.transform(base.matrix_world.inverted() @ o.matrix_world)
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    me = base.data.copy()
    bm.to_mesh(me)
    bm.free()
    base.modifiers.clear()
    base.data = me
    for o in objs[1:]:
        bpy.data.objects.remove(o, do_unlink=True)
    base.name = me.name = name
    return base


def merge_by_material(collection=None, keep=()):
    """join every part that shares one material into one object (named after the first). Fewer MeshParts = fewer draw calls.
    Parts in `keep` (names) stay separate: things that move, that scripts touch, or that need their own collision."""
    groups = {}
    for ob in parts(collection):
        if ob.name in keep or len(ob.data.materials) != 1:
            continue
        groups.setdefault(ob.data.materials[0].name, []).append(ob)
    apply(collection)
    out = []
    for name, obs in groups.items():
        if len(obs) < 2:
            out += obs
            continue
        base = obs[0]
        bm = bmesh.new()
        for ob in obs:
            tmp = ob.data.copy()
            tmp.transform(Matrix.Translation(ob.location - base.location))
            bm.from_mesh(tmp)
            bpy.data.meshes.remove(tmp)
        bm.to_mesh(base.data)
        bm.free()
        for ob in obs[1:]:
            bpy.data.objects.remove(ob, do_unlink=True)
        out.append(base)
    return out


def ensure_uv(ob):
    """one UV set inside 0-1 (Roblox needs exactly one). Missing -> box projection normalised to the part's size."""
    me = ob.data
    while len(me.uv_layers) > 1:
        me.uv_layers.remove(me.uv_layers[-1])
    if len(me.uv_layers) == 1:
        return False
    uv = me.uv_layers.new(name="UVMap")
    lo = Vector([min(v.co[i] for v in me.vertices) for i in range(3)])
    span = max(max(v.co[i] for v in me.vertices) - lo[i] for i in range(3)) or 1.0
    for p in me.polygons:
        ax = max(range(3), key=lambda i: abs(p.normal[i]))
        a, b = [i for i in range(3) if i != ax]
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = ((co[a] - lo[a]) / span, (co[b] - lo[b]) / span)
    return True


def set_origin(ob, where="bottom"):
    """move the pivot without moving the mesh: 'bottom' (centre of the base) | 'center' | world (x, y, z)"""
    ws = [ob.matrix_world @ v.co for v in ob.data.vertices]
    lo = Vector([min(w[i] for w in ws) for i in range(3)])
    hi = Vector([max(w[i] for w in ws) for i in range(3)])
    c = (lo + hi) / 2
    piv = Vector((c.x, c.y, lo.z)) if where == "bottom" else c if where == "center" else Vector(where)
    off = ob.matrix_world.inverted() @ piv
    ob.data.transform(Matrix.Translation(-off))
    ob.matrix_world = ob.matrix_world @ Matrix.Translation(off)


def bake_shading(collection=None, ao=0.6, ground=0.3, distance=None, samples=48, floor=True):
    """Bake soft shading into a grey 'Shade' vertex-colour attribute: ambient occlusion (crevices, under the body, where parts
    meet) x a ground gradient (darker towards the feet). Roblox MULTIPLIES vertex colours with MeshPart.Color (tested
    4 Nov 2026), so parts keep their editable tint and gain depth. The single biggest step from 'programmer boxes' to
    'game art' for flat-colour assets; it needs vertices to shade, so give big flat faces a few loops (loft/smooth/bevel).
    ao: strength 0-1; ground: gradient strength 0-1; distance: AO ray length in studs (default 1/4 of the asset height)."""
    sc = bpy.context.scene
    allp = apply(collection)
    proxies = [o for o in allp if o.get("rbx_proxy")]
    for o in proxies:                 # invisible colliders must not occlude (or be baked)
        o.hide_render = True
    obs = [o for o in allp if not o.get("rbx_proxy")]
    lo, hi = _bounds(obs)
    height = max(hi.z - lo.z, 0.5)
    tmp = []
    if floor:            # a ground plane so the underside darkens like it would standing in the world
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=max(hi - lo) * 2)
        fl = _from_bm("_bake_floor", bm, collection)
        fl.location = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z - 0.01)
        tmp.append(fl)
    old_engine = sc.render.engine
    _enum(sc.render, "engine", ("CYCLES",))
    sc.cycles.samples = samples
    try:
        sc.cycles.device = "CPU"
    except Exception:
        pass
    if sc.world is None:
        sc.world = bpy.data.worlds.new("World")
    sc.world.light_settings.distance = distance or height / 4
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for ob in obs:
        me = ob.data
        if "Shade" in me.color_attributes:
            me.color_attributes.remove(me.color_attributes["Shade"])
        at = me.color_attributes.new("Shade", "BYTE_COLOR", "CORNER")
        me.color_attributes.active_color = at
        ob.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    _enum(sc.render.bake, "target", ("VERTEX_COLORS",))
    bpy.ops.object.bake(type="AO", target="VERTEX_COLORS")
    for ob in obs:
        me = ob.data
        at = me.color_attributes["Shade"]
        mw = ob.matrix_world
        for li, lp in enumerate(me.loops):
            occ = at.data[li].color[0]
            z = (mw @ me.vertices[lp.vertex_index].co).z
            t = min(max((z - lo.z) / height, 0.0), 1.0)
            g = (1 - ground) + ground * (t * t * (3 - 2 * t))
            s = max(0.0, min(1.0, (1 - ao + ao * occ) * g))
            at.data[li].color_srgb = (s, s, s, 1.0)
        ob["rbx_shaded"] = True
    for o in tmp:
        bpy.data.objects.remove(o, do_unlink=True)
    for o in proxies:
        o.hide_render = False
    try:
        sc.render.engine = old_engine
    except TypeError:
        pass
    print("baked shading into %d parts (ao %.2f, ground %.2f, distance %.2f studs)" % (len(obs), ao, ground, sc.world.light_settings.distance))
    return obs


def _luminance(hexcol):
    r, g, b = lin(hexcol)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# ---------------------------------------------------------------- the gate
def _bounds(obs):
    ws = [ob.matrix_world @ v.co for ob in obs for v in ob.data.vertices]
    if not ws:
        return Vector((0, 0, 0)), Vector((0, 0, 0))
    return (Vector([min(w[i] for w in ws) for i in range(3)]), Vector([max(w[i] for w in ws) for i in range(3)]))


def _procedural(m):
    """True when the material's look comes from nodes that won't export (anything but plain values / image textures)"""
    if not m or not m.use_nodes:
        return False
    ok = {"BSDF_PRINCIPLED", "OUTPUT_MATERIAL", "TEX_IMAGE", "NORMAL_MAP", "UVMAP", "TEX_COORD", "MAPPING", "SEPARATE_COLOR",
          "ATTRIBUTE", "MIX"}
    return any(n.type not in ok for n in m.node_tree.nodes)


def _floating(obs, collection=None, tol=0.03):
    """parts whose surface never comes within `tol` studs of another visible part (detached fingers, hovering eyes ...).
    Joints should OVERLAP (sink a tube's rounded end into its parent), not merely touch."""
    from mathutils.bvhtree import BVHTree
    vis = [o for o in obs if not o.get("rbx_proxy")]
    if len(vis) < 2:
        return []
    dg = bpy.context.evaluated_depsgraph_get()
    geo = {}
    for o in vis:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        vs = [o.matrix_world @ v.co for v in me.vertices]
        geo[o.name] = (vs, BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in me.polygons]))
        ev.to_mesh_clear()
    out = []
    for a in vis:
        va = geo[a.name][0]
        step = max(1, len(va) // 400)
        best, who = 1e9, None
        for b in vis:
            if b is a:
                continue
            tb = geo[b.name][1]
            for v in va[::step]:
                hit = tb.find_nearest(v)
                if hit[0] is None:
                    continue
                d = 0.0 if (v - hit[0]).dot(hit[1]) < 0 else hit[3]      # a vertex inside b = attached
                if d < best:
                    best, who = d, b.name
            if best <= tol:
                break
        if best > tol:
            out.append((a.name, best, who))
    return out


def check(collection=None, kind="prop", fix=True):
    """GATE A (asset). Prints one line per finding; returns {'ok', 'findings', 'tris', 'parts'}. A FAIL is fixed, never argued."""
    obs = parts(collection)
    budget = BUDGETS.get(kind, BUDGETS["prop"])
    F = []
    add = lambda lvl, who, msg: F.append((lvl, who, msg))
    if not obs:
        add("FAIL", "-", "no mesh objects in the asset collection")
    total = 0
    names = set()
    for ob in obs:
        n = tris(ob)
        total += n
        if n > TRI_LIMIT:
            add("FAIL", ob.name, "%d triangles > %d (Roblox per-mesh limit; it auto-simplifies badly)" % (n, TRI_LIMIT))
        if kind in ("accessory", "clothing") and n > budget:
            add("FAIL", ob.name, "%d triangles > %d (%s budget)" % (n, budget, kind))
        mats = [m for m in ob.data.materials if m]
        if len(mats) > 1:
            add("FAIL", ob.name, "%d materials; Roblox = one per mesh (split it, or K.merge_by_material on single-material parts)" % len(mats))
        if not mats:
            add("WARN", ob.name, "no material: imports grey (give it K.mat)")
        for m in mats:
            if _procedural(m):
                add("WARN", ob.name, "material %s uses procedural nodes: Roblox gets only flat colour or baked images" % m.name)
            for nd in m.node_tree.nodes if m.use_nodes else []:
                if nd.type == "TEX_IMAGE" and nd.image:
                    w, h = nd.image.size
                    if max(w, h) > 4096:
                        add("FAIL", ob.name, "texture %s is %dx%d > 4096" % (nd.image.name, w, h))
                    elif max(w, h) > 1024:
                        add("INFO", ob.name, "texture %s %dx%d: renders (4K streaming since Jan 2026); 1024 is the spec page, 2048 the avatar cap" % (nd.image.name, w, h))
        _, rot, sca = ob.matrix_world.decompose()
        if any(s < 0 for s in sca):
            add("FAIL", ob.name, "negative scale (flips normals on import): run K.apply()")
        elif ob.modifiers or ob.parent or abs(sca.x - 1) + abs(sca.y - 1) + abs(sca.z - 1) > 1e-4 or rot.angle > 1e-4:
            if fix:
                pass   # export() applies; reported so the build script can do it deliberately
            add("INFO", ob.name, "unapplied modifiers/rotation/scale/parent: K.apply() bakes them before export")
        if len(ob.data.uv_layers) != 1:
            if fix and ensure_uv(ob):
                add("INFO", ob.name, "added box-projection UVs (one set, 0-1)")
            elif len(ob.data.uv_layers) != 1:
                add("FAIL", ob.name, "%d UV sets; Roblox needs exactly one" % len(ob.data.uv_layers))
        if len(ob.data.uv_layers) == 1:
            uvs = [d.uv for d in ob.data.uv_layers[0].data]
            if uvs and (min(min(u.x, u.y) for u in uvs) < -1e-3 or max(max(u.x, u.y) for u in uvs) > 1.001):
                add("WARN", ob.name, "UVs outside 0-1 (Roblox clamps; textures misplace)")
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        nm = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
        bd = sum(1 for e in bm.edges if e.is_boundary)
        zero = sum(1 for f in bm.faces if f.calc_area() < 1e-7)
        bm.free()
        if nm:
            add("WARN", ob.name, "%d non-manifold edges (Roblox wants watertight; collision and lighting suffer)" % nm)
        if bd:
            add("WARN", ob.name, "%d open boundary edges (not watertight; back faces are invisible in Roblox)" % bd)
        if zero:
            add("WARN", ob.name, "%d zero-area faces" % zero)
        lo, hi = _bounds([ob])
        size = hi - lo
        if max(size) > PART_MAX:
            add("FAIL", ob.name, "%.0f studs across > %d (largest Roblox part)" % (max(size), PART_MAX))
        if min(size) < 0.01:
            add("WARN", ob.name, "flat (%.3f studs thick): zero thickness renders one-sided" % min(size))
        piv = ob.matrix_world.translation
        pad = max(size) * 0.5 + 1
        if any(piv[i] < lo[i] - pad or piv[i] > hi[i] + pad for i in range(3)):
            add("WARN", ob.name, "pivot far from the mesh: put it at the base or the hinge (K.set_origin)")
        key = ob.name.lower()
        if key in names:
            add("FAIL", ob.name, "duplicate name (case-insensitive); Studio steps need unique part names")
        names.add(key)
    if kind not in ("accessory", "clothing") and total > budget:
        add("WARN", "*", "%d triangles total > %d %s budget (fine for a hero piece; say why)" % (total, budget, kind))
    if kind in ("accessory", "clothing") and len(obs) > 1:
        add("FAIL", "*", "%s must be ONE mesh (got %d)" % (kind, len(obs)))
    # value structure (art direction): a readable asset has a dark, a mid and a light band, and few near-duplicate colours
    cols = sorted({(m.get("rbx_color") or "#A3A2A5") for ob in obs if not ob.get("rbx_proxy") for m in ob.data.materials if m})
    if cols:
        L = sorted(_luminance(c) ** (1 / 2.2) for c in cols)       # perceptual-ish lightness 0-1
        if L[-1] - L[0] < 0.25 and len(cols) > 1:
            add("WARN", "*", "flat value structure (lightness %.2f-%.2f): add a clearly darker and a lighter band, or it reads as mud" % (L[0], L[-1]))
        near = [(a, b) for i, a in enumerate(L) for b in L[i + 1:] if abs(a - b) < 0.03]
        if len(cols) > 8:
            add("WARN", "*", "%d colours: keep a palette of roles (base, shade, accent, danger/reward), 3-6 is typical" % len(cols))
        if near:
            add("INFO", "*", "%d colour pairs nearly the same lightness: fine for hue accents, muddy for structure" % len(near))
    # sides: the asset faces -Y, so the CHARACTER's left is +X in Blender (it becomes Roblox -X after the export mapping,
    # which is the character's left there too). A "Left..." part on the -X side would rig mirrored.
    for ob in obs:
        nm = ob.name.replace(" ", "").lower()
        if nm.startswith(("left", "right")):
            lo_, hi_ = _bounds([ob])
            cx = (lo_.x + hi_.x) / 2
            if (nm.startswith("left") and cx < -0.05) or (nm.startswith("right") and cx > 0.05):
                add("FAIL", ob.name, "named %s but sits on the character's other side (facing -Y: the character's LEFT is +X)"
                    % ob.name.split()[0])
    for who, d, near in _floating(obs, collection):
        add("WARN", who, "floating: %.2f studs from the nearest part (%s); sink it into what it grows from" % (d, near))
    if obs and not any(ob.get("rbx_shaded") for ob in obs):
        add("INFO", "*", "no baked shading: K.bake_shading() adds AO + a ground gradient (vertex colours) for depth")
    lo, hi = _bounds(obs)
    ok = not any(f[0] == "FAIL" for f in F)
    print("GATE A %s  %s  %d parts  %d tris  size %.2f x %.2f x %.2f studs (w x d x h)" % (
        "PASS" if ok else "FAIL", _col(collection).name, len(obs), total, *(hi - lo)))
    for lvl, who, msg in F:
        print("  %-4s %-18s %s" % (lvl, who, msg))
    return {"ok": ok, "findings": F, "tris": total, "parts": len(obs), "size": list(hi - lo)}


# ---------------------------------------------------------------- export
def R(v):
    """Blender (x, y, z; front -Y, Z up) -> Roblox (x, y, z; front -Z, Y up). A proper rotation: winding and handedness kept."""
    return (-v[0], v[2], v[1])


def _r(x, d=4):
    x = round(x, d)
    return 0.0 if x == 0 else x


def _part_record(ob, dg, has_proxy=False):
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    mw = ob.matrix_world
    nm = mw.to_3x3().inverted().transposed()
    vw = [R(mw @ v.co) for v in me.vertices]
    lo = [min(p[i] for p in vw) for i in range(3)]
    hi = [max(p[i] for p in vw) for i in range(3)]
    c = [(lo[i] + hi[i]) / 2 for i in range(3)]
    V = [_r(p[i] - c[i]) for p in vw for i in range(3)]
    uvl = me.uv_layers.active
    sh = me.color_attributes.get("Shade") if ob.get("rbx_shaded") else None
    N, NI, UV, UI, T, TN, TU = [], {}, [], {}, [], [], []
    C, CI, TC = [], {}, []
    for lt in me.loop_triangles:
        T += list(lt.vertices)
        for k in range(3):
            if sh is not None:
                g = round(sh.data[lt.loops[k]].color_srgb[0], 2)
                if g not in CI:
                    CI[g] = len(C)
                    C.append(g)
                TC.append(CI[g])
            n = (nm @ Vector(lt.split_normals[k])).normalized()
            key = tuple(_r(x, 3) for x in R(n))
            if key not in NI:
                NI[key] = len(N) // 3
                N += key
            TN.append(NI[key])
            if uvl:
                u = uvl.data[lt.loops[k]].uv
                ukey = (_r(u.x), _r(1 - u.y))          # Roblox UV origin is top-left
                if ukey not in UI:
                    UI[ukey] = len(UV) // 2
                    UV += ukey
                TU.append(UI[ukey])
    ntri = len(me.loop_triangles)
    ev.to_mesh_clear()
    m = ob.data.materials[0] if ob.data.materials else None
    size = [hi[i] - lo[i] for i in range(3)]
    coll = ob.get("rbx_collision") or ("Box" if max(size) < 6 else "Default")
    proxy = bool(ob.get("rbx_proxy"))
    return {"name": ob.name, "color": (m.get("rbx_color") if m else None) or "#A3A2A5",
            "material": (m.get("rbx_material") if m else None) or "SmoothPlastic", "collision": coll,
            "anchored": bool(ob.get("rbx_anchored", True)),
            "cancollide": True if proxy else bool(ob.get("rbx_cancollide", not has_proxy)),
            "canquery": True if proxy else bool(ob.get("rbx_canquery", not has_proxy)),
            "castshadow": False if proxy else bool(ob.get("rbx_castshadow", max(size) >= 1.0)),
            "transparency": 1 if proxy else 0, "shaded": sh is not None,
            "center": [_r(x) for x in c], "pivot": [_r(x) for x in R(mw.translation)], "size": [_r(x) for x in size],
            "tris": ntri, "v": V, "n": N, "uv": UV, "t": T, "tn": TN, "tu": TU, "c": C, "tc": TC}


def export(out_dir, collection=None, kind="prop", fbx=True, gate=True, forward="-Z"):
    """GATE A, then write <name>.fbx (Roblox's documented settings), <name>.mesh.json (for `rbx.py preview`) and
    <name>.manifest.json (per-part colour / material / collision / pivot + expected size, for `rbx.py place`).
    Raises on a FAIL. `forward`: FBX forward axis; Blender's default -Z (verify on your first upload, see SKILL.md)."""
    col = _col(collection)
    apply(col)
    rep = check(col, kind=kind) if gate else {"ok": True, "findings": []}
    if not rep["ok"]:
        raise RuntimeError("GATE A FAIL: fix the findings above before export")
    os.makedirs(out_dir, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", col.name)
    dg = bpy.context.evaluated_depsgraph_get()
    has_proxy = any(ob.get("rbx_proxy") for ob in parts(col))
    recs = [_part_record(ob, dg, has_proxy) for ob in sorted(parts(col), key=lambda o: o.name)]
    lo = [min(r["center"][i] - r["size"][i] / 2 for r in recs) for i in range(3)]
    hi = [max(r["center"][i] + r["size"][i] / 2 for r in recs) for i in range(3)]
    paths = {}
    if fbx:
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for ob in parts(col):
            ob.select_set(True)
        p = os.path.join(out_dir, name + ".fbx")
        bpy.ops.export_scene.fbx(filepath=p, use_selection=True, object_types={"MESH", "ARMATURE", "EMPTY"},
                                 apply_scale_options="FBX_SCALE_UNITS", axis_forward=forward, axis_up="Y",
                                 path_mode="COPY", embed_textures=True, add_leaf_bones=False, bake_anim=False,
                                 use_custom_props=True, use_mesh_modifiers=True, mesh_smooth_type="FACE",
                                 colors_type="SRGB", prioritize_active_color=True)
        paths["fbx"] = p
    meta = {"version": 1, "name": name, "kind": kind, "unit": "stud", "axes": "roblox: x=-bx, y=bz, z=by (front -Z)",
            "size": [_r(hi[i] - lo[i]) for i in range(3)], "tris": sum(r["tris"] for r in recs)}
    p = os.path.join(out_dir, name + ".mesh.json")
    with open(p, "w") as f:
        json.dump(dict(meta, parts=recs), f, separators=(",", ":"))
    paths["mesh"] = p
    man = dict(meta, parts=[{k: r[k] for k in r if k not in ("v", "n", "uv", "t", "tn", "tu", "c", "tc")} for r in recs],
               gate=[list(x) for x in rep["findings"]])
    if fbx:
        man["fbx_sha256"] = hashlib.sha256(open(paths["fbx"], "rb").read()).hexdigest()
    p = os.path.join(out_dir, name + ".manifest.json")
    with open(p, "w") as f:
        json.dump(man, f, indent=1)
    paths["manifest"] = p
    print("exported", name, "->", ", ".join(os.path.basename(v) for v in paths.values()))
    return paths


# ---------------------------------------------------------------- look (headless)
def _enum(obj, prop, wanted):
    """set an enum by the first identifier this Blender accepts (never hardcode one: they change between versions)"""
    try:
        items = [i.identifier for i in obj.bl_rna.properties[prop].enum_items]
    except (KeyError, AttributeError):
        items = []
    for w in wanted:
        if w in items:
            setattr(obj, prop, w)
            return w
    for w in wanted:
        try:
            setattr(obj, prop, w)
            return w
        except (TypeError, AttributeError):
            pass
    return None


def snapshot(path, collection=None, views=((1, -1.3, 0.8),), res=768, engine="eevee", bw=False, thumb=False):
    """Render(s) of the asset from direction(s) towards the eye, with a 1x1x1 stud cube and a 5-stud avatar-height post
    beside it for scale. Writes path (or path_1, path_2 ... for several views).
    engine 'eevee' shows the baked shading under a sun (close to Roblox); 'workbench' is flat and fastest.
    The three-distance check: bw=True adds *_bw.png (value structure: does it still read in greyscale?);
    thumb=True adds *_thumb.png at 128 px (does the silhouette read at gameplay distance?)."""
    sc = bpy.context.scene
    if engine == "eevee":
        _enum(sc.render, "engine", ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"))
        if sc.world is None:
            sc.world = bpy.data.worlds.new("World")
        sc.world.use_nodes = True
        bg = next((n for n in sc.world.node_tree.nodes if n.type == "BACKGROUND"), None)
        if bg:
            bg.inputs["Color"].default_value = (0.30, 0.36, 0.45, 1)
            bg.inputs["Strength"].default_value = 0.9
        sund = bpy.data.lights.new("_snapsun", "SUN")
        sund.energy = 3.2
        sund.angle = math.radians(8)
        sun = bpy.data.objects.new("_snapsun", sund)
        sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))
        sc.collection.objects.link(sun)
        _enum(sc.view_settings, "view_transform", ("AgX", "Filmic", "Standard"))
    else:
        sun = None
    hidden = [ob for ob in parts(collection) if ob.get("rbx_proxy") and not ob.hide_render]
    for ob in hidden:
        ob.hide_render = True
    out = _snapshot(path, collection, views, res, engine)
    if bw:
        sc.render.image_settings.color_mode = "BW"
        out += _snapshot(path.replace(".png", "_bw.png"), collection, views[:1], res, engine)
        sc.render.image_settings.color_mode = "RGB"
    if thumb:
        out += _snapshot(path.replace(".png", "_thumb.png"), collection, views[:1], 128, engine)
    if sun:
        bpy.data.objects.remove(sun, do_unlink=True)
    for ob in hidden:
        ob.hide_render = False
    return out


def _snapshot(path, collection, views, res, engine):
    sc = bpy.context.scene
    obs = parts(collection)
    lo, hi = _bounds(obs)
    cy = (lo.y + hi.y) / 2
    tmp = bpy.data.collections.new("_snap")
    sc.collection.children.link(tmp)
    gap = max(0.6, (hi.x - lo.x) * 0.12)
    refs = [box("_ref_stud", (1, 1, 1), (lo.x - gap - 0.5, cy, lo.z + 0.5), "#F2C230", collection=tmp),
            box("_ref_avatar5", (0.5, 0.5, 5), (lo.x - gap * 2 - 1.25, cy, lo.z + 2.5), "#4E7BD8", collection=tmp)]
    lo, hi = _bounds(obs + refs)
    if engine == "eevee":      # a floor in Roblox-baseplate grey, so contact shadows and the ground read
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=max(hi - lo) * 3)
        fl = _from_bm("_snapfloor", bm, tmp)
        fl.location = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z - 0.005)
        fl.data.materials.append(mat("#6B7686"))
    c = (lo + hi) / 2
    rad = max((hi - lo).length / 2, 1.0) * 1.35
    camd = bpy.data.cameras.new("_snapcam")
    camd.lens = 50
    cam = bpy.data.objects.new("_snapcam", camd)
    tmp.objects.link(cam)
    sc.camera = cam
    if engine != "eevee":
        _enum(sc.render, "engine", ("BLENDER_WORKBENCH",))
        sh = sc.display.shading
        _enum(sh, "light", ("STUDIO",))
        _enum(sh, "color_type", ("MATERIAL",))
        sh.show_cavity = True
        sh.show_object_outline = True
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.film_transparent = False
    out = []
    for i, d in enumerate(views):
        d = Vector(d).normalized()
        cam.location = c + d * rad * 3.4
        cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
        p = path if len(views) == 1 else path.replace(".png", "_%d.png" % (i + 1))
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        out.append(p)
    for ob in list(tmp.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.collections.remove(tmp)
    return out
