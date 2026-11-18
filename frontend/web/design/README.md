# Web design prototypes

Clickable design prototypes for the web client (ADR-0019). They are references for the
look and feel, not production code: data is fictional sample data from `sample-data.js`,
and no page talks to the backend.

## Running them

The pages load ES modules, which browsers refuse over `file://`. Serve the folder:

```sh
cd frontend/web/design
python3 -m http.server 8000   # then open http://localhost:8000/matchnight.html
```

| Page | Leans | What it shows |
|---|---|---|
| `matchnight.html` | football | One player's page. Photo fixed on the left; scrolling flies the camera along his price and rating through the season; ends at the order book and order form. |
| `market.html` | trading | Every player's season racing in parallel lanes. Switch between price, OpenElo or both; picking a player flies the camera to his lane. |
| `trade.html` | trading | One-screen terminal. The week's price meets the order book as a 3D depth wall; pointing at a book row lights its bar. |
| `stats.html` | football | Rating anatomy. Camera flies along the rating through a goal frame per match; match log and "rating leads, price follows" computed from the series. |
| `portfolio.html` | both | Holdings as lanes of return over a "what you paid" floor, with the next matchdays glowing ahead. |

## Design language

Decided with the owner during the design round of November 2026:

- **Night stadium.** Dark navy ground, a live 3D stadium behind every page: twinkling crowd
  lights in the stands, four floodlights, drifting dust, a pitch grid.
- **Two lines per player.** Share price is a blue ribbon, OpenElo rating a gold ribbon. Seeing
  the rating move after a match and the price follow is the core feeling of the product.
- **The new-share price is a ceiling.** Drawn as a dashed orange line or plane above the price;
  the curve always sells at it, so holders sell below it.
- **Rising blue, falling orange.** Never green and red (colour-blind safe). Gold is reserved for
  the rating.
- **Photos as tall vertical panels on the side**, never as a banner on top. Black and white, tinted
  in the page's colour, with the surname set vertically in outlined italic capitals.
- **Glass panels** (blurred, translucent) carry all UI over the 3D scene.
- **Type**: Barlow Condensed for display, Barlow Semi Condensed for UI, tabular figures.
- **Money in whole hundredths of a credit**, never floats (`ticket.js`).

Rejected in the same round: consumer-fintech and sports-editorial looks (kept on the Archive
page of the design canvas, linked below).

## Shared modules

- `stadium.js`: the Three.js scene kit. `createStage` (renderer, camera, render loop,
  reduced-motion fallback, an optional shift to clear a side panel), `addStadium`, `addRibbon`
  (glowing tube plus a faint curtain to the ground, fadeable), `addPillar`, `addDashedLine`,
  `textSprite`, `scrollTracker`, `pointerTracker`.
- `design.css`: tokens and components (glass, legend swatches, chips, segmented buttons,
  order-book rows, order form, tables).
- `ticket.js`: order form behaviour and order-book rendering.
- `sample-data.js`: the fictional players, series, matches and fixtures.

## How this level is made

What makes these pages feel like Igloo Inc or Lusion rather than a dashboard:

1. **A real-time 3D scene behind the page**, not a picture. Three.js r160 from jsDelivr as an
   ES module. One fixed full-screen `<canvas>`, the page scrolls over it.
2. **Additive blending everywhere light should glow.** Tubes, halos, crowd points and floodlights
   use `THREE.AdditiveBlending` with `depthWrite: false`, so overlaps brighten like light does.
3. **Glow without post-processing.** Each ribbon is two tubes: a thin bright core and a wide
   faint shell. Halos are sprites with a radial-gradient canvas texture.
4. **A custom point shader for the crowd.** Each point gets a random phase; the vertex shader
   twinkles its alpha and scales its size with distance. Thousands of lights for one draw call.
5. **Fog** (`FogExp2` in the background colour) fades everything distant into the night and
   gives depth for free.
6. **Scroll drives the camera, eased.** Scroll position becomes a 0 to 1 progress, smoothed every
   frame (`value += (target - value) * 0.07`), which drives a camera along the data curve
   (`CatmullRomCurve3.getPointAt`). The camera starts on a wide shot and blends into a chase
   view with `smoothstep`.
7. **The pointer adds a small parallax**, eased the same way. Small, constant, physical.
8. **Clearing a side panel**: `camera.setViewOffset` shifts the projection so the scene's centre
   sits beside a fixed panel instead of under it.
9. **Film grain**: an SVG `feTurbulence` noise as a fixed overlay at 9% opacity, `mix-blend-mode: overlay`.
10. **Glass UI**: `backdrop-filter: blur(18px) saturate(1.3)` on a translucent fill with a faint edge.
11. **Reduced motion**: with `prefers-reduced-motion`, render one still frame and only redraw on
    resize or a state change (`stage.refresh()`).

Next steps to go further, not built yet: bloom post-processing (`UnrealBloomPass`), smooth scroll
with Lenis driven from one ticker, modelled assets (stadium, kit) in glTF from Blender, sound
with Web Audio.

## References

- Live sites at this level: Igloo Inc (Awwwards Site of the Year 2024), Lusion, Bruno Simon's
  portfolio, Immersive Garden's Cartier pavilion. Collection: https://www.awwwards.com/awwwards/collections/webgl/
- Stack and techniques: https://tympanus.net/codrops/2026/07/15/the-architecture-behind-trionn-coordinating-gsap-three-js-lenis-and-web-audio/,
  https://lastres.ai/guides/scroll-effects/, https://www.utsubo.com/blog/best-threejs-websites-2026
- 3D commerce examples (instancing, raycasting, camera tweening): https://github.com/dhiasaied/FERROVA-,
  https://github.com/thebuggeddev/football-stadium
- Beware "video scrubbing" sites: AI video frames played on scroll look 3D but only move along
  one path. Real 3D lets you look and click anywhere.
- Anthropic's frontend-design skill (`.claude/skills/frontend-design/`) for choosing a direction
  before coding.

## Assets

`player.jpg`: photo by Alex Rizzardi on Unsplash, used as a stand-in under the Unsplash License.
It shows real people and real sponsor logos; replace it before launch (player image rights are
an open question).

Design canvas with the earlier rounds: https://claude.ai/artifact/JdB17FXjVqRfpnFH8xV7cj
