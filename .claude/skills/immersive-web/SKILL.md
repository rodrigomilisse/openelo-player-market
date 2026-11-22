---
name: immersive-web
description: Playbook for building a website or web app at the level of an Awwwards-style immersive site, with a real-time Three.js scene behind glass UI, a scroll-driven camera, particles, and dark and light themes. Lists which skills and MCP servers to load, which stack to pick, the techniques, the owner's design taste and working habits, the quality floor, and a tested way to screenshot the result. Use it when starting or redesigning such a site, or adding a page to one. Not for plain forms, admin screens or documentation pages.
---

# Immersive web frontend

This playbook is portable: nothing in it is specific to one product. The project's own brief,
README and design decisions always win over it. Where a project has already chosen
something (colours, type, stack), follow the project.

**To reuse it in another project**, copy this folder (`immersive-web/`) into that project's
`.claude/skills/`. To have it in every project, copy it into `~/.claude/skills/` on your own
machine, or upload it as a skill on claude.ai so cloud sessions get it too. It also works as
plain text: paste it into a `CLAUDE.md`.

What's here:

| Path | What it is |
|---|---|
| `SKILL.md` | This playbook |
| `starter/` | A working page with the theme script, tokens for both themes, liquid glass, a pointer-lit highlight, a theme toggle, and a Three.js scene with a scroll camera, twinkling points, bloom, phone and reduced-motion handling. Tested in desktop, phone, light and reduced-motion modes. |
| `scripts/screenshot.cjs` | Screenshots any served site in four states (desktop dark, desktop light, phone, reduced motion) and reports console errors, failed requests and horizontal scroll |

## 1. Load before you start

**Skills.** Load the ones your session lists and skip the rest.

- **frontend-design** (Anthropic). Load it for any new page, section or visual direction,
  and follow its process: a token plan, a review against the brief, the build, then a
  screenshot critique. If your session doesn't list it, get it from
  `github.com/anthropics/skills` (`skills/frontend-design/`) or install it with
  `npx skills add https://github.com/anthropics/skills --skill frontend-design`. A copy is
  also in the `anthropics/claude-code` repo as the plugin `plugins/frontend-design`.
- **dataviz**: before any chart. Use its method with the project's own colour tokens.
- **run**: to launch the site and take screenshots.
- **code-review**, **simplify**, **security-review**: before handing work back.
- **built-in-browser** or **chrome-browser**: to show the site in the owner's own browser.
- **artifact-design**: only for a throwaway preview published as an Artifact, never for the
  project's code.

**MCP servers.** Put these in the project's `.mcp.json`:

```json
{
  "mcpServers": {
    "playwright": { "command": "npx", "args": ["@playwright/mcp@latest"] },
    "shadcn": { "command": "npx", "args": ["shadcn@latest", "mcp"] }
  }
}
```

Playwright is for screenshots and clicking through pages. shadcn only matters for a React
app that uses shadcn/ui. A static site uses no component library.

**Worked example.** `github.com/rodrigomilisse/openelo-player-market`, branch
`frontend-web`, folder `frontend/web/`, is a full site built this way. Its
`design/README.md` ("How this level is made") and `site/README.md` ("The living scene") are
the best reading for each technique. When the playbook is too short, read the code there:

| Module | What to read it for |
|---|---|
| `site/scene.js` | Particle formations and physics, keyframes, page spots, the scroll tour |
| `site/router.js` | Page changes without a reload, keep-alive, prefetch |
| `design/stadium.js` | The scene kit |
| `site/site.css` | Tokens and glass |

## 2. Pick the stack

**A public site** (marketing, content, data to browse; it should be indexable and fast):
**no build step.** Plain HTML pages and native ES modules. Load Three.js from jsDelivr
through an import map, at an exact version (the starter uses `0.160.0`), and put the same
map on every page. Fonts come from Google Fonts. Draw charts as hand-written SVG; add a chart
library only if the project already has one. Run it with `python3 -m http.server` from the
folder that holds every imported file, because ES modules don't load over `file://`.

**An app behind a login**: React, TypeScript and Vite as a single-page app, with no server
rendering, since nothing behind a login needs indexing. Generate API types from OpenAPI
(`openapi-typescript`), mock missing endpoints with Mock Service Worker, and manage server
state with TanStack Query. Writes carry an `Idempotency-Key`. A Vite dev proxy puts the
browser on one origin, so the backend needs no CORS.

**From Three.js**, these are the pieces this level uses: `WebGLRenderer`, `FogExp2`,
`Points` with a `ShaderMaterial`, `CatmullRomCurve3`, `camera.setViewOffset`, and
`EffectComposer` with `RenderPass`, `UnrealBloomPass` and `OutputPass`.

**Add only when asked**: GSAP, Lenis smooth scroll, glTF models from Blender, sound with
Web Audio.

**Hosting and services** (defaults chosen before):
- a static host: Cloudflare Pages or Netlify
- a form endpoint for a waitlist: Formspree, Buttondown or a Supabase function
- cookie-free analytics: Plausible
- email routing: Cloudflare Email Routing

Keep every outside service behind a `config.js` setting. An empty setting means "not
connected", and the site still works.

## 3. Architecture patterns

- **One fixed full-screen `<canvas>`** behind the page (`position: fixed; z-index: 0`), with
  the page scrolling over it. Add `aria-hidden="true"`.
- **One data module.** Pages never fetch directly. It returns real data when present and a
  seeded fictional mock world otherwise, in the same shapes, so real data later changes one
  file. Write the shapes down as a data contract in the README.
- **A shared shell** (header, footer, formatters, `escape`) injected by one module, so every
  page carries the same chrome.
- **Page changes that keep the scene alive.** A small router fetches the next page, swaps
  its `<main>`, styles and script, and re-targets the running scene. Visited pages stay in
  memory, and links prefetch on hover or focus. A plain page load is the fallback.
- **Every page tells the scene what it wants**: shapes, camera keyframes and colours.
  Keyframes can anchor to elements (`'#section-id'`: when it's centred on screen) rather than
  scroll fractions.
- **Stages**: near-empty sections (`min-height: 88vh`) where the scene plays in the open,
  with one line of caption at most.
- **A scroll tour**: keep scrolling past the end of a page and a ring fills; the camera then
  flies to the next page's spot in the scene and opens it there.
- **Working docs beside the code**:
  - the folder's README records design decisions as they are made
  - `FEATURES.md` lists what the frontend assumes from a backend that doesn't exist yet
  - `CONNECT.md` lists the outside services still to connect, with cost and the setting each needs

## 4. Techniques that make it feel this good

1. **A real-time 3D scene, not a picture or video.** Beware "video scrubbing" sites, which
   play pre-rendered frames on scroll: they look 3D but move along one path only.
2. **Additive blending wherever light should glow**: `blending: THREE.AdditiveBlending` and
   `depthWrite: false`, so overlaps brighten like light does.
3. **Glow without post-processing**: draw a line as two tubes, a thin bright core and a wide
   faint shell. For halos, use sprites with a radial-gradient canvas texture.
4. **A custom point shader**: each point gets a random phase that twinkles its alpha, and
   its size scales with distance. Thousands of lights cost one draw call.
5. **Particle formations**: the page's data, made of points (a line, a number, a shape).
   Each point is sprung to its place, morphs staggered between shapes as you scroll, gets
   kicked by pointer swipes and drifts back over a few seconds. Fast points glow.
6. **Fog** (`FogExp2` in the ground colour) fades the distance and gives depth for free.
7. **Scroll drives the camera, eased.** Scroll becomes a 0 to 1 progress, smoothed every
   frame (`value += (target - value) * 0.07`), which moves the camera along a
   `CatmullRomCurve3` (`getPointAt`). Blend from a wide shot into a closer view with `smoothstep`.
8. **The pointer adds a small parallax**, eased the same way.
9. **Clear a text column**: `camera.setViewOffset(w, h, -w * shift, 0, w, h)` moves the
   scene's centre beside the hero text instead of under it. Turn it off on phones.
10. **Bloom on larger screens only**: `UnrealBloomPass` at a 256×256 resolution is cheap enough.
11. **Film grain**: an SVG `feTurbulence` noise as a fixed overlay at about 8% opacity with
    `mix-blend-mode: overlay`.
12. **Liquid glass** for all UI over the scene:
    - a translucent fill and a bright gradient edge (a `border-box` background)
    - `backdrop-filter: url(#liquid-refraction) blur(10px) saturate(1.6)`: an SVG
      `feDisplacementMap` refraction in Chromium, with a plain blur declared first as the fallback
    - a radial highlight that follows the pointer through CSS variables
13. **Two themes from one scene.** Dark: additive glow and bloom. Light: points blended
    normally (adding light to white shows nothing), no bloom, and decorative lights faded.
    The scene reads the ground colour from the CSS tokens and listens for a `themechange` event.

The starter implements 2, 4, 6, 7, 8, 9, 10, 11, 12 and 13.

## 5. Taste: the owner's preferences

These carry from one project to the next unless the brief says otherwise.

**Look**
- A dark ground by default (a deep navy night, `#060B14`, not tinted black). A light theme
  is an overcast day in grey-white (`#E6EAF0`), not a grey dusk. The theme follows the
  system until the reader picks one; an inline script at the top of `<head>` applies it
  before first paint.
- **Each colour means one thing.** One accent for the number the product is about, and it is
  reserved for that. Use blue for rising and orange for falling, **never green and red**
  (colour-blind safe). Every colour has a dark and a light value.
- **Type**: a condensed display face (heavy, italic, uppercase for `h1`) with a
  semi-condensed UI face from the same family, and tabular figures everywhere. Choose the
  family for the subject; Barlow Condensed and Barlow Semi Condensed were the last pair.
- **Photos as tall vertical panels on the side, never a banner on top**: black and white,
  tinted in the page colour, a name set vertically in outlined italic capitals.
- **Glass panels carry all UI** over the scene.

**Feel**
- **Fewer buttons, more motion**: text tabs with a sliding underline, sliders,
  slide-to-confirm or hold-to-confirm, charts you scrub that drive the headline numbers.
- Motion comes from the scene (scroll, pointer, particles forming data), not from fade-in
  entrances on every section or hover lifts on every card.
- A loud mode and a quiet mode can share one site. Browsing is loud: a living scene and
  italic display type. The reader's own money or settings are quiet: a dimmed, still scene
  and upright type.

**Rejected before, so don't propose them unasked**:
- generic consumer-fintech and neobank layouts (light cards, pill buttons)
- sports-media editorial and broadsheet layouts
- the frontend-design skill's list of generated-page tells:
  - ALL-CAPS eyebrow labels
  - meta strings joined with middle dots (use commas)
  - `→` on links
  - one accented word in a headline
  - numbered markers on content that isn't a sequence
  - identical rounded cards with the same soft shadow
  - gradient washes as decoration

**Working habits**
- **For a new direction, build two or three runnable alternatives side by side** and let
  the owner choose. Keep the chosen one; remove the others in their own commit.
- **Label anything mock, simulated, projected or draft on the page itself**, not only in
  the README.
- Write each decision into the folder's README as it is made, under a "Design language"
  heading.
- Copy is plain, in sentence case, and written from the reader's side. A button names its
  action, and an error says what happened and what to do next. Never invent statistics.

## 6. Quality floor

- **Escape every string** that goes into `innerHTML`.
- **Money is integer**: minor units, formatted with integer division and remainder, never
  float arithmetic.
- **Reduced motion**: render still frames, with no animation loop and no automatic camera
  flights. Redraw only on resize, scroll or a state change.
- **Phones** (860px and narrower): half the particles, no bloom, pixel ratio capped at 1.5,
  no view offset, one column, no horizontal scroll at 390px.
- **Keyboard and screen readers**: real `<button>` and `<a href>` elements, a visible focus
  ring in the accent colour, `aria-pressed` or `aria-checked` on toggles, `aria-label` on
  icon-only buttons, `aria-hidden` on the canvas and grain.
- **Contrast** of at least 4.5:1 for text in both themes. Colours that must be told apart
  also differ in lightness.
- **Numbers** come from one `Intl.NumberFormat` locale, with a real minus sign (−), and
  dates are formatted in UTC.
- **Every page** has a title, a description, Open Graph tags, a favicon, and the theme
  script first in `<head>`.
- **Pin every CDN version** exactly, the same on every page.

## 7. Check your work

1. Serve the site from the folder that holds every imported file.
2. Screenshot every changed page in all four states:
   ```bash
   node .claude/skills/immersive-web/scripts/screenshot.cjs http://localhost:8000/ shots index.html
   ```
   Set `THEME_KEY` to the site's `localStorage` key and `SCROLL=1200` to shoot further down
   the page. The script exits non-zero if anything failed or scrolls sideways.
3. Look at the screenshots yourself. Critique them against the brief and section 5, then
   remove one thing that doesn't earn its place.
4. Send the owner the screenshots.

**In a Claude Code cloud session**, the network policy blocks jsDelivr and unpkg (the proxy
answers `CONNECT` with 403). Google Fonts and the npm registry are allowed. Chromium and
Playwright come pre-installed: use `require('playwright')` and don't run
`playwright install`. To get the scene rendering, install Three.js locally and let the
script serve it in place of the CDN. Here `$SCRATCH` is your scratchpad directory, or any
folder outside the project:

```bash
mkdir -p "$SCRATCH/three" && cd "$SCRATCH/three" && npm init -y >/dev/null && npm install three@0.160.0
```

```bash
THREE_DIR="$SCRATCH/three" node .claude/skills/immersive-web/scripts/screenshot.cjs http://localhost:8000/ shots index.html
```

Tested on 22 November 2026: with SwiftShader (the script's launch flags), headless Chromium
renders the scene, bloom, glass and both themes. Without `THREE_DIR`, the script lists the
blocked CDN files.

## 8. Ship

- Commit messages: a subject naming what changed ("Site: …", "Light theme: …",
  "Player page: …") and a body saying what and why.
- Update the README, `FEATURES.md` and `CONNECT.md` in the same commit as the change.
- Deploy to a static host. The publish folder must contain every file the pages import,
  including any imported from outside the site folder. Keep generated data out of git and
  let the job that produces it deploy it.
