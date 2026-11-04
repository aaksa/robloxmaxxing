#!/usr/bin/env python3
"""rbx.py - hand Blender exports to Roblox Studio (talks to Studio's built-in MCP server over stdio, and to Open Cloud).

usage:
  rbx.py studios                                   list open Studio instances
  rbx.py user                                      the logged-in Studio user id (the default upload creator)
  rbx.py preview <out/Name.mesh.json> [--at x,y,z] build it in Studio from raw mesh data (EditableMesh): no key, no
                                                   upload, seconds; NOT saved with the place - it is the look/iterate step
  rbx.py upload <out/Name.fbx> [--user-id N | --group-id N] [--name N] [--dry-run]
                                                   Open Cloud: create the Model asset, or update it in place when the
                                                   registry (rbx_assets.json next to the file) already knows it
  rbx.py place <out/Name.manifest.json> --asset-id N [--at x,y,z] [--fix-scale] [--keep-preview]
                                                   insert the uploaded asset, apply the manifest (colour, material,
                                                   collision, anchored), check its size and facing against the manifest
  rbx.py apply <out/Name.manifest.json> [--path Workspace.Name]
                                                   apply the manifest to a model you imported by hand (3D Importer)
  rbx.py capture <Name> [--out shot.png] [--dir 1,0.6,-1.3]
                                                   screenshot the model from a direction (Roblox axes, front = -Z)
  rbx.py luau <file.luau> [--dm Edit]              run a Luau file
  rbx.py tools                                     list the Studio MCP tools

Common: --studio <name substring> picks the Studio instance (default: the only/first one).
API key (upload only): env ROBLOX_API_KEY, or the macOS Keychain item "roblox-open-cloud" (never passed on the command line).
"""
import base64, hashlib, json, os, queue, subprocess, sys, threading, time, urllib.error, urllib.request, uuid

BIN = os.environ.get("STUDIO_MCP", "/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP")
API = "https://apis.roblox.com/assets/v1"
LUAU_CHUNK = 400_000          # characters of Luau per execute_luau call


# ------------------------------------------------------------------ Studio MCP client
class Studio:
    def __init__(self, want=None):
        if not os.path.exists(BIN):
            sys.exit("StudioMCP not found at %s (Studio > Assistant > Manage MCP Servers, or set STUDIO_MCP)" % BIN)
        self.p = subprocess.Popen([BIN], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self.q = queue.Queue()
        self.n = 0
        threading.Thread(target=self._read, daemon=True).start()
        self.req("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "robloxmaxxing", "version": "1"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.id = self._pick(want)

    def _read(self):
        for line in self.p.stdout:
            try:
                self.q.put(json.loads(line))
            except ValueError:
                pass

    def _send(self, o):
        self.p.stdin.write(json.dumps(o) + "\n")
        self.p.stdin.flush()

    def req(self, method, params, timeout=600):
        self.n += 1
        rid = self.n
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        end = time.time() + timeout
        while time.time() < end:
            try:
                m = self.q.get(timeout=1)
            except queue.Empty:
                continue
            if m.get("id") == rid:
                if "error" in m:
                    raise RuntimeError(json.dumps(m["error"]))
                return m["result"]
        raise RuntimeError("timeout waiting for " + method)

    def call(self, tool, args, image_to=None):
        r = self.req("tools/call", {"name": tool, "arguments": args})
        out = []
        for c in r.get("content", []):
            if c.get("type") == "text":
                out.append(c["text"])
            elif c.get("type") == "image" and image_to:
                with open(image_to, "wb") as f:
                    f.write(base64.b64decode(c["data"]))
                out.append("saved " + image_to)
        text = "\n".join(out)
        if r.get("isError"):
            raise RuntimeError("[%s] %s" % (tool, text))
        return text

    def _pick(self, want):
        for _ in range(20):
            try:
                s = json.loads(self.call("list_roblox_studios", {})).get("studios", [])
            except Exception:
                s = []
            if s:
                if want:
                    s = [x for x in s if want.lower() in x["name"].lower()] or sys.exit("no Studio named like %r" % want)
                return s[0]["id"]
            time.sleep(1)
        sys.exit("no Roblox Studio connected: open Studio and enable its MCP server (Assistant > Manage MCP Servers)")

    def luau(self, code, dm="Edit"):
        return self.call("execute_luau", {"code": code, "datamodel_type": dm, "studio_id": self.id})

    def close(self):
        self.p.kill()


def lstr(s):
    """a Luau long-string literal"""
    eq = "="
    while ("]" + eq + "]") in s:
        eq += "="
    return "[" + eq + "[" + s + "]" + eq + "]"


def nums(a):
    return " ".join(("%d" % x) if isinstance(x, int) else ("%g" % x) for x in a)


# ------------------------------------------------------------------ Luau
LUAU_HELPERS = r"""
local AS = game:GetService("AssetService")
local function nums(s) local t = table.create(#s // 4) for x in string.gmatch(s, "%S+") do t[#t + 1] = tonumber(x) end return t end
local function enum(E, name, fallback) local ok, v = pcall(function() return E[name] end) if ok and v then return v end return fallback end
"""

PART_LUAU = r"""
local P = game:GetService("HttpService"):JSONDecode(%(meta)s)
local V, N, UV, T, TN, TU = nums(%(v)s), nums(%(n)s), nums(%(uv)s), nums(%(t)s), nums(%(tn)s), nums(%(tu)s)
local C, TC = nums(%(c)s), nums(%(tc)s)
local model
for _, c in ipairs(workspace:GetChildren()) do
  if c.Name == %(model)s and c:GetAttribute("RbxPreview") then model = c end
end
if not model then error("preview model missing") end
local em = AS:CreateEditableMesh()
local vid, nid, uid = table.create(#V // 3), table.create(#N // 3), table.create(#UV // 2)
for i = 1, #V, 3 do vid[#vid + 1] = em:AddVertex(Vector3.new(V[i], V[i + 1], V[i + 2])) end
for i = 1, #N, 3 do nid[#nid + 1] = em:AddNormal(Vector3.new(N[i], N[i + 1], N[i + 2])) end
for i = 1, #UV, 2 do uid[#uid + 1] = em:AddUV(Vector2.new(UV[i], UV[i + 1])) end
local cid = table.create(#C)
for i = 1, #C do cid[i] = em:AddColor(Color3.new(C[i], C[i], C[i]), 1) end
for k = 1, #T, 3 do
  local f = em:AddTriangle(vid[T[k] + 1], vid[T[k + 1] + 1], vid[T[k + 2] + 1])
  em:SetFaceNormals(f, {nid[TN[k] + 1], nid[TN[k + 1] + 1], nid[TN[k + 2] + 1]})
  if #TU > 0 then em:SetFaceUVs(f, {uid[TU[k] + 1], uid[TU[k + 1] + 1], uid[TU[k + 2] + 1]}) end
  if #TC > 0 then em:SetFaceColors(f, {cid[TC[k] + 1], cid[TC[k + 1] + 1], cid[TC[k + 2] + 1]}) end
  if k %% 3000 == 1 then task.wait() end
end
local mp = AS:CreateMeshPartAsync(Content.fromObject(em), {CollisionFidelity = enum(Enum.CollisionFidelity, P.collision, Enum.CollisionFidelity.Default)})
mp.Name = P.name
mp.Color = Color3.fromHex(P.color)
mp.Material = enum(Enum.Material, P.material, Enum.Material.SmoothPlastic)
mp.Anchored, mp.CanCollide, mp.CastShadow = P.anchored, P.cancollide, P.castshadow
mp.CanQuery = P.canquery ~= false
mp.Transparency = P.transparency or 0
local c = Vector3.new(table.unpack(P.center))
mp.CFrame = model.WorldPivot * CFrame.new(c)
mp.PivotOffset = CFrame.new(Vector3.new(table.unpack(P.pivot)) - c)
mp:SetAttribute("RbxPreview", true)
mp.Parent = model
return string.format("%%s %%d tris size %%.2f,%%.2f,%%.2f", mp.Name, #T // 3, mp.Size.X, mp.Size.Y, mp.Size.Z)
"""


def _at(s):
    return [float(x) for x in s.split(",")] if s else [0.0, 0.0, 0.0]


def cmd_preview(st, path, at=None):
    data = json.load(open(path))
    name = data["name"]
    x, y, z = _at(at)
    head = LUAU_HELPERS + """
for _, c in ipairs(workspace:GetChildren()) do if c.Name == %s and c:GetAttribute("RbxPreview") then c:Destroy() end end
local m = Instance.new("Model"); m.Name = %s; m:SetAttribute("RbxPreview", true)
m.WorldPivot = CFrame.new(%g, %g, %g); m.Parent = workspace
return "model " .. m:GetFullName()
""" % (lstr(name), lstr(name), x, y, z)
    print(st.luau(head))
    for p in data["parts"]:
        meta = {k: p[k] for k in ("name", "color", "material", "collision", "anchored", "cancollide", "castshadow", "center", "pivot",
                                  "canquery", "transparency") if k in p}
        code = LUAU_HELPERS + PART_LUAU % {"meta": lstr(json.dumps(meta)), "model": lstr(name), "v": lstr(nums(p["v"])),
                                           "n": lstr(nums(p["n"])), "uv": lstr(nums(p["uv"])), "t": lstr(nums(p["t"])),
                                           "tn": lstr(nums(p["tn"])), "tu": lstr(nums(p["tu"])),
                                           "c": lstr(nums(p.get("c", []))), "tc": lstr(nums(p.get("tc", [])))}
        if len(code) > 4 * LUAU_CHUNK:
            print("  ! %s is large (%d KB of Luau); it may be slow" % (p["name"], len(code) // 1024))
        print("  " + st.luau(code))
    print("preview %s: %d parts, %d tris, expected size %s studs (temporary: not saved with the place)" % (
        name, len(data["parts"]), data["tris"], "x".join("%.2f" % s for s in data["size"])))


# ------------------------------------------------------------------ manifest -> Studio
APPLY_LUAU = r"""
local M = game:GetService("HttpService"):JSONDecode(%(man)s)
local function enum(E, name, fallback) local ok, v = pcall(function() return E[name] end) if ok and v then return v end return fallback end
local root = %(root)s
if not root then return "ERROR: model not found" end
local byname, out, used = {}, {}, {}
for _, p in ipairs(M.parts) do byname[string.lower(p.name)] = p end
local meshes = {}
for _, d in ipairs(root:GetDescendants()) do if d:IsA("MeshPart") then table.insert(meshes, d) end end
for _, mp in ipairs(meshes) do
  local key = string.lower(mp.Name)
  local p = byname[key] or byname[(string.gsub(key, "%%.%%d+$", ""))]
  if p then
    used[p.name] = mp
    mp.Color = Color3.fromHex(p.color)
    mp.Material = enum(Enum.Material, p.material, mp.Material)
    mp.Anchored, mp.CanCollide, mp.CastShadow = p.anchored, p.cancollide, p.castshadow
    if p.canquery ~= nil then mp.CanQuery = p.canquery end
    if p.transparency ~= nil then mp.Transparency = p.transparency end
    local ok = pcall(function() mp.CollisionFidelity = enum(Enum.CollisionFidelity, p.collision, mp.CollisionFidelity) end)
    if not ok then table.insert(out, "  collision not settable on " .. mp.Name .. " (set it in Properties)") end
  else
    table.insert(out, "  unmatched MeshPart " .. mp:GetFullName())
  end
end
for _, p in ipairs(M.parts) do if not used[p.name] then table.insert(out, "  manifest part missing in Studio: " .. p.name) end end
-- size: extents vs the manifest (catches the metre/stud conversion)
local ext = root:IsA("Model") and root:GetExtentsSize() or root.Size
local want = Vector3.new(table.unpack(M.size))
local ratio = math.max(ext.X, ext.Y, ext.Z) / math.max(want.X, want.Y, want.Z)
table.insert(out, 1, string.format("size %%.2f x %%.2f x %%.2f studs (manifest %%.2f x %%.2f x %%.2f), ratio %%.3f%%s",
  ext.X, ext.Y, ext.Z, want.X, want.Y, want.Z, ratio, math.abs(ratio - 1) > 0.03 and "  <- SCALE MISMATCH" or "  ok"))
if math.abs(ratio - 1) > 0.03 and %(fix)s and root:IsA("Model") then root:ScaleTo(root:GetScale() / ratio); table.insert(out, 2, "  rescaled to match") end
-- facing: per axis, the pair of parts furthest apart ON THAT AXIS must keep its sign (one overall pair can miss a front/back flip)
local pv = root:IsA("Model") and root:GetPivot() or root.CFrame
local flips, tested = {}, {}
for _, ax in ipairs({"X", "Y", "Z"}) do
  local best, a, b = 0.05, nil, nil
  for i = 1, #M.parts do for j = i + 1, #M.parts do
    local pi, pj = M.parts[i], M.parts[j]
    if used[pi.name] and used[pj.name] then
      local d = math.abs(Vector3.new(table.unpack(pi.center))[ax] - Vector3.new(table.unpack(pj.center))[ax])
      if d > best then best, a, b = d, pi, pj end
    end
  end end
  if a then
    local want = Vector3.new(table.unpack(a.center))[ax] - Vector3.new(table.unpack(b.center))[ax]
    local got = pv:VectorToObjectSpace(used[a.name].Position - used[b.name].Position)[ax]
    table.insert(tested, ax)
    if math.sign(want) ~= math.sign(got) then table.insert(flips, ax) end
  end
end
if #tested == 0 then
  table.insert(out, 2, "facing: not testable (parts share one centre); compare a capture with the Blender snapshot")
elseif #flips == 0 then
  table.insert(out, 2, "facing ok (axes tested: " .. table.concat(tested, ",") .. ")")
else
  table.insert(out, 2, "FACING FLIPPED on " .. table.concat(flips, ",") .. " (re-export with forward='Z', or rotate 180)")
end
return table.concat(out, "\n")
"""


def _apply(st, man, root_expr, fix=False):
    code = APPLY_LUAU % {"man": lstr(json.dumps({"size": man["size"], "parts": man["parts"]})), "root": root_expr,
                         "fix": "true" if fix else "false"}
    return st.luau(code)


def cmd_apply(st, manifest, path=None):
    man = json.load(open(manifest))
    path = path or "Workspace." + man["name"]
    expr = "(function() local o = game for s in string.gmatch(%s, '[^%%.]+') do o = (o == game and (game:FindFirstChild(s) or game:GetService(s))) or o:FindFirstChild(s) if not o then return nil end end return o end)()" % lstr(path)
    print(_apply(st, man, expr))


def cmd_place(st, manifest, asset_id, at=None, fix=False, keep_preview=False):
    man = json.load(open(manifest))
    name = man["name"]
    print(st.call("insert_asset", {"assetId": str(asset_id), "assetName": name, "studio_id": st.id}))
    x, y, z = _at(at)
    root = """(function()
  local hit = nil
  for _, c in ipairs(workspace:GetChildren()) do
    if c.Name == %s and not c:GetAttribute("RbxPreview") and not c:GetAttribute("RbxAsset") then hit = c end
  end
  if hit then
    if hit:IsA("Model") then hit:PivotTo(CFrame.new(%g, %g, %g)) end
    hit:SetAttribute("RbxAsset", %s)
  end
  return hit
end)()""" % (lstr(name), x, y, z, lstr(str(asset_id)))
    print(_apply(st, man, root, fix))
    if not keep_preview:
        print(st.luau("local n = 0 for _, c in ipairs(workspace:GetChildren()) do if c.Name == %s and c:GetAttribute('RbxPreview') then c:Destroy() n += 1 end end return 'removed ' .. n .. ' preview(s)'" % lstr(name)))


def cmd_capture(st, name, out=None, direction="1,0.6,-1.3"):
    d = _at(direction)
    code = """
local m = workspace:FindFirstChild(%s)
if not m then return "" end
local cf, size
if m:IsA("Model") then cf, size = m:GetBoundingBox() else cf, size = m.CFrame, m.Size end
local dir = Vector3.new(%g, %g, %g).Unit
local eye = cf.Position + dir * math.max(size.Magnitude * 1.6, 6)
return string.format("%%g,%%g,%%g|%%g,%%g,%%g", eye.X, eye.Y, eye.Z, cf.Position.X, cf.Position.Y, cf.Position.Z)
""" % (lstr(name), *d)
    r = st.luau(code).strip()
    if "|" not in r:
        sys.exit("model %s not found in Workspace" % name)
    eye, look = ([float(v) for v in s.split(",")] for s in r.split("|"))
    out = out or name + ".png"
    print(st.call("screen_capture", {"capture_id": "rbx_" + name, "studio_id": st.id, "camera_position": eye,
                                     "look_at_position": look}, image_to=out))


# ------------------------------------------------------------------ Open Cloud upload
def api_key():
    k = os.environ.get("ROBLOX_API_KEY")
    if k:
        return k.strip()
    try:
        return subprocess.run(["security", "find-generic-password", "-s", "roblox-open-cloud", "-w"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return None


def _multipart(fields, file_field, file_path, ctype):
    b = "----rbx" + uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (b, k, v)).encode())
    parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\nContent-Type: %s\r\n\r\n"
                  % (b, file_field, os.path.basename(file_path), ctype)).encode())
    parts.append(open(file_path, "rb").read())
    parts.append(("\r\n--%s--\r\n" % b).encode())
    return b"".join(parts), "multipart/form-data; boundary=" + b


def _http(method, url, key, body=None, ctype=None):
    req = urllib.request.Request(url, data=body, method=method, headers={"x-api-key": key, **({"Content-Type": ctype} if ctype else {})})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit("Open Cloud %s %s -> HTTP %d: %s" % (method, url.split("/v1/")[-1], e.code, e.read().decode(errors="replace")[:600]))


CTYPES = {".fbx": "model/fbx", ".gltf": "model/gltf+json", ".glb": "model/gltf-binary", ".rbxm": "model/x-rbxm", ".rbxmx": "model/x-rbxm"}


def cmd_upload(path, name=None, user_id=None, group_id=None, dry=False, studio=None, description=None):
    ext = os.path.splitext(path)[1].lower()
    if ext not in CTYPES:
        sys.exit("Open Cloud Model uploads take .fbx/.gltf/.glb/.rbxm (not %s); export FBX from Blender" % ext)
    if os.path.getsize(path) > 20 * 1024 * 1024:
        sys.exit("%s is over the 20 MB Open Cloud limit" % path)
    name = name or os.path.splitext(os.path.basename(path))[0]
    reg_path = os.path.join(os.path.dirname(os.path.abspath(path)), "rbx_assets.json")
    reg = json.load(open(reg_path)) if os.path.exists(reg_path) else {}
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    prev = reg.get(name)
    if prev and prev.get("sha256") == sha:
        print("unchanged since asset %s (revision %s): nothing to upload" % (prev["assetId"], prev.get("revision")))
        return prev["assetId"]
    if not user_id and not group_id:
        st = Studio(studio)
        user_id = st.luau('return game:GetService("StudioService"):GetUserId()').strip()
        st.close()
    creator = {"groupId": str(group_id)} if group_id else {"userId": str(user_id)}
    update = bool(prev) and ext == ".fbx"
    request = ({"assetId": str(prev["assetId"]), "assetType": "Model", "creationContext": {"creator": creator}} if update else
               {"assetType": "Model", "displayName": name, "description": description or "Built in Blender with robloxmaxxing",
                "creationContext": {"creator": creator}})
    url = API + ("/assets/%s" % prev["assetId"] if update else "/assets")
    print("%s %s  (%s, %d KB, creator %s)" % ("PATCH" if update else "POST", url, CTYPES[ext], os.path.getsize(path) // 1024, creator))
    print("request:", json.dumps(request))
    if dry:
        print("dry run: nothing sent")
        return None
    key = api_key()
    if not key:
        sys.exit("no API key. Create one at https://create.roblox.com/dashboard/credentials (Access: Assets, Read+Write),\n"
                 "copy it, then store it ONCE in the Keychain from the clipboard (the typed -w prompt cuts keys at 128 chars):\n"
                 "  security add-generic-password -U -s roblox-open-cloud -a \"$USER\" -w \"$(pbpaste)\" && pbcopy </dev/null\n"
                 "(or export ROBLOX_API_KEY in your shell).")
    if len(key) == 128:
        print("! the stored key is exactly 128 characters: the Keychain prompt probably cut it. Re-store it from the clipboard:\n"
              "  security add-generic-password -U -s roblox-open-cloud -a \"$USER\" -w \"$(pbpaste)\" && pbcopy </dev/null")
    body, ctype = _multipart({"request": json.dumps(request)}, "fileContent", path, CTYPES[ext])
    op = _http("PATCH" if update else "POST", url, key, body, ctype)
    opid = (op.get("path") or op.get("operationId") or "").split("/")[-1]
    if not opid:
        sys.exit("unexpected response: %s" % json.dumps(op)[:400])
    for i in range(90):
        r = _http("GET", API + "/operations/" + opid, key)
        if r.get("done"):
            break
        time.sleep(min(2 + i, 10))
    else:
        sys.exit("still processing after ~10 min; operation %s" % opid)
    if "error" in r or "response" not in r:
        sys.exit("upload failed: %s" % json.dumps(r.get("error") or r)[:600])
    res = r["response"]
    aid = res.get("assetId") or res.get("path", "").split("/")[-1]
    mod = res.get("moderationResult", {}).get("moderationState", "?")
    reg[name] = {"assetId": aid, "revision": res.get("revisionId"), "sha256": sha, "file": os.path.basename(path),
                 "moderation": mod, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
    json.dump(reg, open(reg_path, "w"), indent=1)
    print("asset %s revision %s moderation %s  (registry: %s)" % (aid, res.get("revisionId"), mod, reg_path))
    return aid


# ------------------------------------------------------------------ main
def opt(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, studio = a[0], opt(a, "--studio")
    if cmd == "upload":
        cmd_upload(a[1], opt(a, "--name"), opt(a, "--user-id"), opt(a, "--group-id"), "--dry-run" in a, studio, opt(a, "--description"))
        return
    st = Studio(studio)
    try:
        if cmd == "studios":
            print(st.call("list_roblox_studios", {}))
        elif cmd == "tools":
            for t in st.req("tools/list", {}).get("tools", []):
                print("%-28s %s" % (t["name"], (t.get("description") or "").split("\n")[0][:110]))
        elif cmd == "user":
            print(st.luau('return game:GetService("StudioService"):GetUserId()'))
        elif cmd == "preview":
            cmd_preview(st, a[1], opt(a, "--at"))
        elif cmd == "place":
            cmd_place(st, a[1], opt(a, "--asset-id") or sys.exit("--asset-id needed (from rbx.py upload)"), opt(a, "--at"),
                      "--fix-scale" in a, "--keep-preview" in a)
        elif cmd == "apply":
            cmd_apply(st, a[1], opt(a, "--path"))
        elif cmd == "capture":
            cmd_capture(st, a[1], opt(a, "--out"), opt(a, "--dir", "1,0.6,-1.3"))
        elif cmd == "luau":
            print(st.luau(open(a[1]).read(), opt(a, "--dm", "Edit")))
        else:
            sys.exit("unknown command %r (see --help)" % cmd)
    finally:
        st.close()


if __name__ == "__main__":
    main()
