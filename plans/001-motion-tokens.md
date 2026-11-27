# 001 — Add shared easing and duration tokens

- **Status**: TODO
- **Commit**: d9b14b1
- **Severity**: LOW
- **Category**: Cohesion and tokens
- **Estimated scope**: 1 file (`frontend/web/site/site.css`), about 5 lines

## Problem

The site has no shared motion tokens. Durations and curves are typed by hand in each rule
(`160ms ease`, `300ms ease`, `400ms ease`, `500ms ease`, `0.28s ease`, and one
`cubic-bezier(0.2, 0.7, 0.2, 1)` in `player.css:38`). Plans 002 to 004 need strong shared curves.

```css
/* frontend/web/site/site.css:2-4, current */
:root {
  color-scheme: dark;
  --night: #060B14;
```

## Target

```css
:root {
  color-scheme: dark;
  --ease-out: cubic-bezier(0.23, 1, 0.32, 1);
  --ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);
  --night: #060B14;
```

Tokens are theme-independent, so they go only in the dark `:root` block. The light theme block
(`:root[data-theme="light"]`) inherits them.

## Repo conventions to follow

Tokens are CSS custom properties at the top of `site.css`. There is no build step and no
other token file.

## Steps

1. In `frontend/web/site/site.css`, insert the two `--ease-*` lines directly after `color-scheme: dark;`.

## Boundaries

- Do NOT change any existing `transition` or `animation` here. Later plans do that.
- Do NOT add duration tokens (the budget is per element, so durations stay inline).
- Do NOT touch `frontend/web/build/` or any `robots`, `_headers` or `config.js` file.

## Verification

- **Mechanical**: `node --test frontend/web/build/guard.test.mjs` passes.
- **Feel check**: nothing should look different. Open the site, check the console for CSS errors.
- **Done when**: `grep -n "ease-out" frontend/web/site/site.css` shows the new token.
