"""Example asset: a low-poly treasure chest whose lid opens (its pivot sits on the hinge).
Run:  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P examples/chest/build.py -- --out examples/chest/out
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "blender"))
import rbx_kit as K

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else os.path.join(HERE, "out")

WOOD, DARK, GOLD = "#8A5A33", "#5E3B20", "#E2B33C"
W, D, H = 4.0, 2.6, 1.8            # studs: about knee-high next to a 5-stud avatar

K.setup()
K.asset("TreasureChest")
K.box("Body", (W, D, H), (0, 0, H / 2), WOOD, material="WoodPlanks", bevel=0.06)
# lid: half-cylinder on its side, pivot on the back hinge line so a script can open it with one rotation
lid = K.cyl("Lid", D / 2, W, (0, 0, H), WOOD, material="WoodPlanks", verts=10, rot=(0, 90, 0), origin=(0, D / 2, H))
K.box("LidCut", (W + 0.02, D + 0.02, D / 2 + 0.02), (0, 0, H - D / 4), WOOD)   # boolean cutter: keep the top half
md = lid.modifiers.new("cut", "BOOLEAN")
md.operation = "DIFFERENCE"
md.object = K.bpy.data.objects["LidCut"]
K.apply()
K.bpy.data.objects.remove(K.bpy.data.objects["LidCut"], do_unlink=True)
lid.data.materials.clear()
lid.data.materials.append(K.mat(WOOD, "WoodPlanks"))
lid["rbx_collision"] = "Hull"
# gold bands and the lock
for i, x in enumerate((-W * 0.33, W * 0.33)):
    K.box("Band%d" % (i + 1), (0.3, D + 0.08, H + 0.04), (x, 0, H / 2), GOLD, material="Metal")
K.box("Lock", (0.6, 0.2, 0.7), (0, -D / 2 - 0.1, H * 0.78), GOLD, material="Metal", bevel=0.04)
K.box("Base", (W + 0.2, D + 0.2, 0.2), (0, 0, 0.1), DARK, material="Wood", origin="bottom")

K.merge_by_material(keep=("Lid",))     # bands + lock -> one gold part; lid stays its own part (it moves)
paths = K.export(OUT, kind="prop")
K.snapshot(os.path.join(OUT, "TreasureChest.png"), views=((1, -1.3, 0.8), (-1, 1.2, 0.6)))
