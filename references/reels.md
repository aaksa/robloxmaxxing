# Reels set in a Roblox world (the film lane)

How to turn a voice-over into a 30-40 s vertical reel that plays out in a blocky Roblox-style world, rendered in Blender (EEVEE) and
finished with a caption/headline overlay and a designed sound mix. Written after the "Dua AI mimpin negara" reel (12 Nov 2026): three
cuts in one day, the first rejected as small and static, the second for a weak hook. Everything here is what fixed those two verdicts.
Evidence and sources are in `research/short-video-retention.md` and `research/reel-hook-and-camera-craft.md`; read them before
designing a hook or a CTA instead of researching again.

This lane makes a film, not a game asset: nothing is uploaded, GATE A / GATE S do not apply, and `rbx_kit` is optional (any stud-scale
box/cylinder builder works). What does apply from the rest of the skill: the Roblox look (blocky, bevelled, saturated, baseplate
checker), stud-like proportions, and never putting a brand mascot or a real person's likeness in as a character.

## Pipeline
| stage | do | check |
|---|---|---|
| 1. voice | transcribe to word timings (frame = seconds x 30, frame 0 = first sound); write the caption script with `[beat]` names | every beat cut lands on a word |
| 2. world | one build script: static world + everything that loops | low-res stills from every beat |
| 3. performance | per-beat events keyed to WORD frames, never to guessed times | a contact sheet reads as the script |
| 4. camera | waypoint spline through every beat; whips between them | `scripts/luma_trace.py` shows no one-frame jumps |
| 5. render | full range in 2-3 parallel processes into numbered JPEGs; finished frames are skipped | frame count = film length |
| 6. overlay + sound | headline per beat, word chips, HUD, CTA; SFX on every action; mix | -14 LUFS, voice clear |

Keep three files: the world (static + looping life), the film (cast, performance, light, camera), the sound design (events from the
same word frames). A change then touches one file and a known frame range.

## What "too small and static" meant, and the fix
The first cut had two 7 m islands, one building each, eight citizens standing still and a camera that drifted. The rebuild:

- **Scale.** Each country about 75 x 160 m on a sea, split by a river, seen from a creator's platform floating above. Districts with
  different jobs: capital, downtown towers, housing, industry + port, military base, a mountain carrying the country's name, roads.
- **Identity per country, one art direction.** Same blocks, bevels and materials; different ground colour, palette, landmark set,
  trees and lighting accents (white/green civic vs sand/purple/neon festival).
- **Ambient life that costs nothing to bake.** Give every looping thing 2-3 keys and an F-curve `CYCLES` modifier instead of a key
  per frame: traffic on lanes, walkers going back and forth, patrols, a helicopter orbit, ships, cranes, smoke puffs, windmills, a
  ferris wheel, flags, river foam. Hundreds of movers, a few thousand keys.
- **Events that answer the script.** Districts rise on "I built two countries"; a crowd claps on "the speeches are good"; a banner
  unrolls on "promises"; hologram megaprojects on "visions"; fireworks on "dance"; a protest and a queue outside a closed office in
  the comparison beat; two convoys meeting at a border gate on "political decisions". One event per claim, on its word.
- **Depth in every shot.** Foreground (crowd heads, a railing, a passing bus), subject, skyline. Thin haze sheets far back.
- **A camera that travels.** Aerial -> city -> crowd level -> face and back, never a locked-off shot.

```python
def keys(ob, path, kv, cyc=False, interp='LINEAR'):          # sparse keys; cyc=True loops them forever
    for f, v in kv: setattr(ob, path, v); ob.keyframe_insert(path, frame=f)
    for fc in fcurves(ob):                                    # Blender 5: walk action.layers[].strips[].channelbags[].fcurves
        if fc.data_path == path:
            for kp in fc.keyframe_points: kp.interpolation = interp
            if cyc and not len(fc.modifiers): fc.modifiers.new('CYCLES')
keys(car, 'location', [(-phase, a), (T - phase, b)], cyc=True)                                   # a lane
keys(walker, 'location', [(-ph, a), (T - ph, b), (2 * T - ph, a)], cyc=True)                      # there and back
keys(walker, 'rotation_euler', [(-ph, fwd), (T - ph, back), (2 * T - ph, fwd)], cyc=True, interp='CONSTANT')
```
Build-up and tear-down of a district: parent it to an empty at ground level and key the empty's Z scale .001 -> 1 with an
ease-out-back over ~14 frames, staggered by district.

## The hook (first 3-5 s)
Rejected hook: the presenter talking to camera for 2.5 s in front of an empty baseplate, then each robot alone on a pedestal against
sky. It stated the premise and showed none of it. What the research and the rebuild agree on:

1. **Voice from frame 1, proposition by second 3.** The only opening feature with field data (speech in the first 3 s: +11.7 %
   retention at 3 s, +24.7 % at 10 s; correlational, Facebook brand Reels).
2. **Show the premise in frame 1; withhold only the result.** Open on the extreme state, mid-action (a flash-forward of the
   finished world with both rulers in it), not on "day one". Do the setup AFTER: "so here's what I did" becomes a rewind.
3. **Frame 0 is the thumbnail.** Readable with the sound off: a large face, both contestants, the world, one short headline.
4. **Escalate inside the 5 s.** Each shot bigger than the last: face + world -> a hit (crowns land, shockwave, a decaying shake) ->
   a dive to contestant 1 in action -> contestant 2 held dead still in near-silence -> the payoff on the stressed word.
5. **Scale sells it.** For a symbolic hook the rulers can be 30x their real size, towering over their capitals; they vanish in the
   rewind and the story continues at normal scale.
6. **One headline, light text.** Dense text over a voice correlates with lower retention; keep the hook to one short headline plus
   the word chips.

Camera for the hook (working values that held up; see the research for which numbers are sourced):
- The first move is already under way on frame 0: an arc + push that lands by frame 8 (ease-out), then a slow counter-drift.
- In 9:16 go wide: 24-28 mm for a face with two background subjects, 18-20 mm looking up at something huge. A portrait lens shows
  the horizontal slice of a landscape lens about 1.78x longer.
- Dives and whips: 7-10 frames of travel, rendered on ones with motion blur (shutter about 0.4-0.5), as real camera moves, not zooms.
- The punch: a dead hold of 4-6 frames before the word, then a physical dolly forward on it, plus a decaying shake (amplitude falls
  with the square of time, ~12 frames). One shake system only.
- Deep focus (f/11-f/16) whenever something far away must read behind a near face.

## Light
- Backlight the world: sun from the far horizon gives every tower a rim and throws shadows toward the lens. Fill from the camera
  side with a cool, shadowless sun.
- One slow arc beats a fixed look: afternoon -> golden hour from the midpoint -> dusk with the city lit for the ending. Key sun
  rotation, colour and energy, the sky ramp colours and the haze tint at three or four frames; nothing ever pops.
- Each lead gets a key in their own colour temperature and an edge light; emissive windows, lamps and light beams (translucent
  cones on a looping sway) carry the dusk.
- A change of global exposure or look after frames exist means re-rendering everything. To grade only a section, key world
  strength and haze tint for that range and ease back to the film's values before the first frame you are keeping.

## Transitions
- Hide cuts in motion that has a reason: a whip, a dive through cloud layers placed on the camera's path, a bus or a jet crossing
  the lens, following a thrown object down.
- **A whip must not pass through geometry.** Through a dark tower it reads as a cut through black; through a white pylon as a
  flash. Add a waypoint that arcs over, then re-render only that range. Run `scripts/luma_trace.py` after every camera change.
- Avoid flash frames, dips to black/white, light leaks and bloom pulses. The W3C limit is three flashes per second; the working
  limit here is zero.

## Overlay and CTA
- A persistent scoreboard HUD (two bars that never settle, a clock that follows the lighting arc) keeps the open question on
  screen. Unmeasured as a retention device; it is there so the vote exists before the end.
- **Seed the ask early.** Average Reel watch time is about 8.5 s; an ask that only appears at second 30 is seen by few. Put the
  question ("which would you choose? write it in the comments") on screen from the first scene that shows both options.
- **Phrase the ask as a real question.** Instagram names "comment with a specific word" as content it may not recommend. A genuine
  two-way opinion vote is a grey zone; a keyword demand is the risky form.
- Check every overlay element against the picture at its own beat (a comment box once covered a character's face; a HUD once sat
  under the headline).

## Sound
- A sound on every action, from the same word frames as the picture; vary repeated effects (orienting to a repeated effect fades
  after about the third).
- Voice at least 10 LU over music (listeners prefer more than mix engineers do); duck music and effects under speech.
- Near-silence for 0.3-0.4 s before the key word, then the hit: transient + low thump + tail, on the contact frame. If sync has
  to err, err late (early is detected at about 45 ms, late at about 125 ms).
- Cut the music on a beat and animate dancing to its tempo (frames per beat = 60 / bpm x fps).
- Master to about -14 LUFS, -1 dBTP (a community convention, not a published platform rule).

## Rendering without wasting hours
- Low-res stills (35-50 %, 6-8 samples) of 20-30 frames after every structural change; full-res timing on 3-4 frames before a long run.
- Split the range across 2-3 Blender processes writing numbered JPEGs; skip frames that exist, so a crash resumes.
- Re-render only what changed: with a Catmull-Rom camera a moved waypoint affects its two neighbouring segments on each side.
  Render the range into a separate folder, then copy the frames over the old ones.
- Ask for all change requests in one batch before a full render; a full world took about 2 h, an 80-frame fix about 5 min.

## Lessons (each cost a render)
- A looping bob keyed on an object's own `location` pins it where it was built; assigning a location afterwards does nothing
  (two "docked" ships sat at the world origin, behind the presenter). Travel on an outer empty, bob on an inner one.
- Hide-keys only cover children that exist when they are written: create the parachute, then hide the character.
- Things built for one beat stay in the world: panels hung over a bridge blocked the next scene shot from the same spot. Give
  every beat-specific prop an exit.
- A camera placed "in the crowd" must be at head height (about 1.8 m for 1.3 m citizens), not above them, or there is no foreground.
- Check where a low camera stands: one was inside a palm tree.
- Portrait frames are narrow. Two side-by-side countries do not fit; split them with a river running away from the lens, or stack
  them low-left / high-right.
- An actor twice the size of the crowd still reads small on a balcony; put their face on giant screens beside them.
- A static hero shot needs the world built behind it; an empty baseplate behind a talking head is the weakest possible frame.

## Honest limits
- No source measures camera moves, transitions, effects, scoreboards or loops against retention in short-form video. They are
  craft; say so when asked what is "proven".
- Nothing found tests animated characters or Indonesian audiences; every finding is a transfer from live action, ads, film or radio.
- A reel like this is staged. If it teases the result of a real simulation, say which parts are illustration.
