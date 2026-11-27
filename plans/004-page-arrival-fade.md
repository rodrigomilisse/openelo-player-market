# 004 — Page-arrival fade

- **Status**: TODO
- **Commit**: d9b14b1
- **Severity**: MEDIUM
- **Category**: Easing and duration
- **Estimated scope**: 1 file (`frontend/web/site/site.css`), 1 line
- **Depends on**: 001
- **Needs a human feel-check**: the 250ms delay may be timed to the camera flight

## Problem

After a page change, `main` fades in over 500ms with plain `ease` after a 250ms delay, about
750ms before content is fully visible. Entrances should use ease-out.

```css
/* frontend/web/site/site.css:226-227, current */
main { transition: opacity 500ms ease 250ms }
main.is-arriving { opacity: 0; transition: none }
```

`router.js:67-69` adds `is-arriving` and removes it two animation frames later.

## Target

```css
main { transition: opacity 350ms var(--ease-out) 250ms }
```

Keep the 250ms delay: it likely lets the camera start moving first, and `scene.js` is out of
scope. If the delay looks wrong, report it instead of changing it.

## Steps

1. Edit line 226 of `frontend/web/site/site.css` as in Target.

## Boundaries

- Do NOT change `router.js`, `scene.js` or the existing reduced-motion rule (line 236).
- If line 226 does not match, STOP and report.

## Verification

- **Mechanical**: `node --test frontend/web/build/guard.test.mjs` passes.
- **Feel check**: click through five pages (rankings, a player, market, trade, back). Content
  should appear promptly without a pop, and quick successive clicks should not flicker. With
  reduced motion on, pages swap with no fade.
- **Done when**: the arrival feels faster than before and nothing flickers.
