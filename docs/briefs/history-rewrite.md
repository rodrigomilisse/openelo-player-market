# Brief: moving to a clean repository without assistant authorship

To do later. Goal: the same history in a new repository, with every commit
authored by the owner and no assistant lines, original dates kept, and no pull
requests. GitHub cannot delete or hide a single pull request, so the old
repository is deleted (or made private) once the new one is up.

## What needs changing

- 22 commits have `Claude <noreply@anthropic.com>` as author and committer
  (made in a cloud session whose git identity was set that way).
- Many commit messages end with `Co-Authored-By: Claude …` and
  `Claude-Session: …` lines.
- The merge commit of PR #1 names the branch `claude/kind-faraday-kva6wo`.
- PR #1's description ends with a "Generated with Claude Code" footer (gone with
  the old repository).
- `docs/briefs/redis-projection.md` line 225 says "Ask Claude to write it": an
  instruction, not authorship; edit it if wanted.

## Steps (on your own machine)

1. Clone and bring every branch's work onto `master`:

   ```
   git clone https://github.com/rodrigomilisse/openelo-player-market.git openelo-clean
   cd openelo-clean
   git merge --ff-only origin/claude/kind-faraday-kva6wo   # or a plain merge if master moved
   ```

2. Rewrite authorship and messages (`pip install git-filter-repo`). Author and
   committer dates are kept; file contents are untouched.

   ```
   echo 'Márcio Caetano <rodrigomilisse@gmail.com> Claude <noreply@anthropic.com>' > ../mailmap
   git filter-repo --force --mailmap ../mailmap --message-callback '
   import re
   message = re.sub(rb"\n*(Co-Authored-By: Claude[^\n]*|Claude-Session:[^\n]*)", b"", message)
   message = message.replace(b"rodrigomilisse/claude/kind-faraday-kva6wo", b"research")
   return message.rstrip() + b"\n"'
   ```

3. Check:

   ```
   git log --all --format='%an <%ae> / %cn <%ce>' | sort | uniq -c   # only you
   git log --all --format=%B | grep -ci claude                       # 0
   git log --format='%h %ad %cd %an' --date=short | head             # dates unchanged
   ```

4. Create an empty repository on GitHub (no README or licence) and push:

   ```
   git remote add origin https://github.com/rodrigomilisse/<new-name>.git
   git push -u origin master
   ```

5. Delete the old repository (Settings → General → Danger Zone), or make it
   private to keep a copy.

## Afterwards

- Claude Code: turn off attribution lines in `.claude/settings.json`
  (`"includeCoAuthoredBy": false` in older versions; the `"attribution"`
  setting with empty text in newer ones).
- Cloud sessions: set `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`
  and `GIT_COMMITTER_EMAIL` in the environment's variables so commits are yours.
- Attach the new repository to future sessions; links to the old repository and
  old commit ids stop working.
