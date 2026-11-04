# robloxmaxxing

An agent skill for **Claude Code** and **Google Antigravity**: build Roblox assets in Blender with code, check them against Roblox's rules, and move them into Roblox Studio.

- `blender/rbx_kit.py`: stud-native low-poly builders, GATE A (20k triangles per mesh, one material, one UV set, avatar budgets), FBX export plus a preview mesh and a manifest.
- `scripts/rbx.py`: talks to Roblox Studio's built-in MCP server and to Open Cloud. `preview` (EditableMesh, no upload), `upload`, `place`, `apply`, `capture`.
- `references/`: Roblox's import rules as of November 2026, and the modeling recipe.

## Install

You need a Mac with [Claude Code](https://claude.com/claude-code) or [Antigravity](https://antigravity.google), Blender 5.x, Python 3.9+ and Roblox Studio with its MCP server turned on (Studio: Assistant > Manage MCP Servers). An Open Cloud API key is only needed for `upload`; preview works without it.

```bash
git clone https://github.com/aaksa/robloxmaxxing.git
cd robloxmaxxing
```

For Claude Code:

```bash
bash install.sh
```

For Antigravity:

```bash
bash install.sh --antigravity
```

`install.sh` checks the requirements and links this folder into the agent's skills directory: `~/.claude/skills/robloxmaxxing` for Claude Code, `~/.gemini/config/skills/robloxmaxxing` for Antigravity. It downloads nothing. Use `--copy` to copy it instead of linking, or `--dir PATH` for another location (for example `.agents/skills/robloxmaxxing` inside one Antigravity workspace).

Then open your agent and ask for a Roblox asset, for example "make a low-poly crab monster for my Roblox game", or run `/robloxmaxxing`. The skill drives Blender and Roblox Studio through its own scripts, so the agent only needs to be able to run shell commands.

## Try the example

```bash
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P examples/chest/build.py -- --out examples/chest/out
python3 -I scripts/rbx.py preview examples/chest/out/TreasureChest.mesh.json --at 0,0.5,-12
```
See `SKILL.md` for the full pipeline.
