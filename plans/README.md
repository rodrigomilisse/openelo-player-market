# Animation plans

Written by the `improve-animations` skill on commit d9b14b1. The audit covered the site's CSS
and DOM motion code only, not the particle and camera easing in `scene.js`.

| # | Title | Severity | Status |
|---|---|---|---|
| 001 | Add shared easing tokens | LOW | TODO |
| 002 | Button press feedback and hover guard | MEDIUM | TODO |
| 003 | Gate and tune the order-confirmation flash | MEDIUM | TODO |
| 004 | Page-arrival fade | MEDIUM | TODO |

Run 001 first: 002, 003 and 004 use its `--ease-out` token. The other three are independent of
each other. Not planned yet: the mobile header scroll-hide easing, the staggered equation reveal
on the player page, and the missed opportunities (sliding nav underline, sliding toggles,
sheet and search-popover transitions).
