# robloxmaxxing

An agent skill for **Claude Code** and **Google Antigravity**: build Roblox assets in Blender with code, check them against Roblox's rules, and move them into Roblox Studio.

- `blender/rbx_kit.py`: stud-native low-poly builders, GATE A (20k triangles per mesh, one material, one UV set, avatar budgets), FBX export plus a preview mesh and a manifest.
- `scripts/rbx.py`: talks to Roblox Studio's built-in MCP server and to Open Cloud. `preview` (EditableMesh, no upload), `upload`, `place`, `apply`, `capture`.
- `references/`: Roblox's import rules as of November 2026, and the modeling recipe.
- `references/reels.md`: making a reel or short film set in a Roblox-style world (rendered in Blender), with the research behind it in `references/research/`.
- `scripts/luma_trace.py`: finds brightness flashes and dark dips in a rendered film.

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

## Reels in a Roblox world

The skill also covers films: a voice-over turned into a 30-40 second vertical reel that plays out in a blocky Roblox-style world, rendered in Blender. Nothing is uploaded to Roblox in this lane.

[`references/reels.md`](references/reels.md) is the working manual. It was written after one reel went through three cuts in a day, and covers:

- **World:** how to make it read as big and alive. Countries are built at district scale, hundreds of looping movers run on a few keys each, and there is one on-screen event for every spoken claim.
- **Hook:** how to build the first 3-5 seconds. The voice starts on frame 1, the premise is shown in frame 1 as a flash-forward, the result is withheld, and the setup comes afterwards as a rewind.
- **Camera:** lenses for 9:16, dives and whips, the dead hold before a punch, and a decaying shake.
- **Light and transitions:** one lighting arc from afternoon to dusk, and transitions hidden in motion with no flashes and no cuts through black.
- **Overlay and sound:** a scoreboard that keeps the open question on screen, an ask that appears early and is phrased as a real question, and a mix that keeps the voice at least 10 LU over the music.
- **Lessons:** the mistakes that each cost a render.

The evidence is in two reports, with sources and a grade for each claim:

- [`references/research/short-video-retention.md`](references/research/short-video-retention.md): what keeps viewers watching a 30-40 second reel. It ranks 22 techniques and lists popular rules that are unsupported.
- [`references/research/reel-hook-and-camera-craft.md`](references/research/reel-hook-and-camera-craft.md): how strong openings are built second by second, plus a catalogue of camera, effect, animation and sound techniques.

The short version of the research: starting the voice in the first second is the only opening feature with field data behind it. Camera moves, transitions, effects and scoreboards have no retention measurements in short-form video, so treat them as craft.

After any camera change, check the render for flashes:

```bash
python3 -I scripts/luma_trace.py plates.mp4
```

A one-frame jump almost always means a whip pan passes through an object.
