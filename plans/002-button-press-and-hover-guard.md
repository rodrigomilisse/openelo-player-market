# 002 — Button press feedback and hover guard

- **Status**: TODO
- **Commit**: d9b14b1
- **Severity**: MEDIUM
- **Category**: Physicality, Accessibility
- **Estimated scope**: 1 file (`frontend/web/site/site.css`), about 4 lines
- **Depends on**: 001 (uses `--ease-out`)

## Problem

`.button` lifts on hover with no guard, so touch devices fire a false hover on tap. It also has
no press feedback on `:active`.

```css
/* frontend/web/site/site.css:154-155, current */
  transition: transform 160ms ease, box-shadow 160ms ease }
.button:hover { transform: translateY(-1px); box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.45), 0 10px 24px rgba(var(--shade), calc(0.35 * var(--shade-k))) }
```

## Target

```css
  transition: transform 160ms var(--ease-out), box-shadow 160ms ease }
@media (hover: hover) and (pointer: fine) {
  .button:hover { transform: translateY(-1px); box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.45), 0 10px 24px rgba(var(--shade), calc(0.35 * var(--shade-k))) }
}
.button:active { transform: scale(0.97) }
```

`:active` comes after `:hover` and is outside the media query, so a press shrinks the button on
both mouse and touch.

## Repo conventions to follow

One rule per line, long declarations on one line, as in the surrounding file.

## Steps

1. Change `transform 160ms ease` to `transform 160ms var(--ease-out)` on the `.button` rule (line 154). Leave `box-shadow 160ms ease`.
2. Wrap the existing `.button:hover` rule (line 155) in `@media (hover: hover) and (pointer: fine) { ... }`, unchanged inside.
3. Add `.button:active { transform: scale(0.97) }` after the media block.

## Boundaries

- Do NOT touch `.button-gold` or other button variants.
- Do NOT add `will-change`.
- If line 154-155 no longer matches the excerpt above, STOP and report.

## Verification

- **Mechanical**: `node --test frontend/web/build/guard.test.mjs` passes.
- **Feel check**:
  - On desktop, hover lifts 1px, and pressing shrinks slightly and springs back.
  - In DevTools device mode with touch, tapping a button does not leave it lifted.
  - Playback at 10% in the Animations panel shows no overshoot.
- **Done when**: both behaviours above hold in the light and dark themes.
