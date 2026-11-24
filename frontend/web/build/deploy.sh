#!/usr/bin/env bash
# The only supported way to publish the site. It runs the guard tests, builds, verifies the built folder, then uploads it.
#   build/deploy.sh preview                          a noindex preview (safe with mock or real data)
#   build/deploy.sh production https://your-domain   the public site; refuses unless the production gate passes
# Needs: node 20+, and `wrangler login` done once. Read build/README.md first.
set -euo pipefail
cd "$(dirname "$0")/.."
mode="${1:-}"
project="${OPENELO_PAGES_PROJECT:-openelo}"

node --test build/guard.test.mjs
case "$mode" in
  preview)    node build/build.mjs; branch=preview ;;
  production) node build/build.mjs --production --site-url "${2:?production needs the site URL, e.g. https://openelo.com}"; branch=main ;;
  *)          echo "usage: build/deploy.sh preview | production https://your-domain" >&2; exit 2 ;;
esac
node build/verify.mjs dist
npx wrangler pages deploy dist --project-name "$project" --branch "$branch"
