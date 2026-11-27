# 003 — Gate and tune the order-confirmation flash

- **Status**: TODO
- **Commit**: d9b14b1
- **Severity**: MEDIUM
- **Category**: Accessibility, Easing
- **Estimated scope**: 1 file (`frontend/web/site/trade.html`), about 4 lines
- **Depends on**: 001

## Problem

The confirmation line after an order uses a 900ms plain-`ease` keyframe with a vertical move and
no reduced-motion path. Traders see it on every confirmation.

```css
/* frontend/web/site/trade.html:58-59, current */
  .done.flash { animation: flash 900ms ease }
  @keyframes flash { from { opacity: 0; transform: translateY(4px) } to { opacity: 1; transform: none } }
```

The script restarts it deliberately (`done.classList.remove('flash'); void done.offsetWidth;
done.classList.add('flash')`, lines 275 and 297). Keep that, and keep it a keyframe: it must
restart from zero on each order.

## Target

```css
  .done.flash { animation: flash 300ms var(--ease-out) }
  @keyframes flash { from { opacity: 0; transform: translateY(4px) } to { opacity: 1; transform: none } }
  @media (prefers-reduced-motion: reduce) { .done.flash { animation: flash-fade 200ms ease } @keyframes flash-fade { from { opacity: 0 } } }
```

Reduced motion keeps the opacity feedback and drops the movement.

## Steps

1. In the `<style>` block of `trade.html`, change line 58 as in Target (300ms, `var(--ease-out)`).
2. Add the `@media (prefers-reduced-motion: reduce)` line after the `@keyframes flash` line.

## Boundaries

- Do NOT touch the JavaScript that retriggers the flash.
- Do NOT change the confirmation text.
- If lines 58-59 do not match, STOP and report.

## Verification

- **Mechanical**: `node --test frontend/web/build/guard.test.mjs` passes.
- **Feel check**: place an order twice in a row. The line appears quickly both times and does
  not stay faded. With reduced motion on (DevTools, Rendering), it fades in without moving.
- **Done when**: both of the above hold.
