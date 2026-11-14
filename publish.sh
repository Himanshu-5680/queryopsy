#!/usr/bin/env bash
# Queryopsy - one-command GitHub publisher (macOS / Linux / Git Bash / WSL).
#
#   bash publish.sh            # asks before doing anything
#   bash publish.sh --yes      # no questions
# Options: --name <repo> (default queryopsy)  --owner <login|org>  --private  --no-prs  --yes  --dry-run
# On a brand-new repository the history is built from .github/pr-plan.tsv (skeleton on main + one auto-merged
# PR per feature area). Every commit carries the Co-authored-by trailers. Re-running only syncs changes.
set -u

VERSION="1.1.0"; TAG="v$VERSION"; ORIG_SLUG="Himanshu-5680/queryopsy"
NAME="queryopsy"; OWNER=""; VISIBILITY="public"; YES=0; DRY=0; NOPRS=0
CO_AUTHORS="Co-authored-by: pavitra-prabhakar <himanshupathakhimanshu@gmail.com>
Co-authored-by: vectornomadhp88 <himanshupc88@gmail.com>"
DESCRIPTION="Zero-server SQL forensics and industry case simulator. Python + SQLite in WebAssembly, offline web app and Android APK."
TOPICS=(sql sqlite python pyodide webassembly data-analysis sql-game learn-sql forensics offline-first pwa android detective-game education india)

while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="$2"; shift 2 ;;
    --owner) OWNER="$2"; shift 2 ;;
    --private) VISIBILITY="private"; shift ;;
    --no-prs) NOPRS=1; shift ;;
    --yes|-y) YES=1; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1"; exit 2 ;;
  esac
done

cd "$(dirname "$0")"
c() { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }
say() { c "1;36" "$1"; }
ok() { c "32" "  [ok] $1"; }
warn() { c "33" "  [!] $1"; }
fail() { c "31" "[x] $1"; exit 1; }
run() { c "90" "  > $*"; [ "$DRY" = 1 ] && return 0; "$@"; }
quiet() { "$@" >/dev/null 2>&1; }
has_staged() { [ "$DRY" = 1 ] && return 0; ! git diff --cached --quiet 2>/dev/null; }
commit_with_trailers() {   # $1 title, $2 summary
  local f=.git/QUERYOPSY_COMMIT_MSG
  [ "$DRY" = 1 ] || { printf '%s\n\n' "$1"; [ -n "${2:-}" ] && printf '%s\n\n' "$2"; printf '%s\n' "$CO_AUTHORS"; } > "$f"
  run git commit -q -F "$f"
}

echo; c "30;43" "  QUERYOPSY  -  GitHub publisher  $TAG  "; echo

say "1/10  Checking tools"
command -v git >/dev/null || fail "git is not installed (https://git-scm.com)."
command -v gh >/dev/null || fail "GitHub CLI is not installed (https://cli.github.com)."
ok "$(git --version)"; ok "$(gh --version | head -n1)"
[ -f index.html ] && [ -f data/cases.json ] || fail "Run this script from inside the extracted queryopsy folder."

say "2/10  Checking GitHub login"
if ! quiet gh auth status --hostname github.com; then
  warn "Not logged in to GitHub CLI - starting gh auth login."
  gh auth login --hostname github.com --git-protocol https --web --scopes workflow || fail "gh auth login failed."
fi
STATUS="$(gh auth status --hostname github.com 2>&1)"
if echo "$STATUS" | grep -q "Token scopes" && ! echo "$STATUS" | grep -q "workflow"; then
  warn "Adding the 'workflow' scope (needed to push .github/workflows)."
  gh auth refresh --hostname github.com --scopes workflow || fail "gh auth refresh failed."
fi
quiet gh auth setup-git
LOGIN="$(gh api user --jq .login 2>/dev/null)"; [ -n "$LOGIN" ] || fail "Could not read your GitHub username."
[ -n "$OWNER" ] || OWNER="$LOGIN"
SLUG="$OWNER/$NAME"
OWNER_LC="$(printf '%s' "$OWNER" | tr '[:upper:]' '[:lower:]')"
PAGES_URL="https://$OWNER_LC.github.io/$NAME/"
REMOTE_URL="https://github.com/$SLUG.git"
REPO_EXISTS=0; REMOTE_HAS_COMMITS=0
if quiet gh repo view "$SLUG" --json name; then
  REPO_EXISTS=1
  [ -n "$(GIT_TERMINAL_PROMPT=0 git ls-remote --heads "$REMOTE_URL" 2>/dev/null)" ] && REMOTE_HAS_COMMITS=1
fi
MODE="pull requests (skeleton on main + one PR per feature, auto-merged)"
[ "$NOPRS" = 1 ] && MODE="single commit (--no-prs)"
[ "$REMOTE_HAS_COMMITS" = 1 ] && MODE="sync changes (repository already has commits, no new PRs)"

echo
echo "  Owner:       $OWNER"
echo "  Repository:  https://github.com/$SLUG"
echo "  Visibility:  $VISIBILITY"
echo "  Pages:       $PAGES_URL"
echo "  History:     $MODE"
echo "  Co-authors:  pavitra-prabhakar, vectornomadhp88"
[ "$DRY" = 1 ] && c "33" "  Mode:        DRY RUN (nothing will change)"
echo
[ "$VISIBILITY" = private ] && warn "GitHub Pages on private repositories needs a paid plan."
if [ "$YES" != 1 ]; then
  read -r -p "Publish Queryopsy to this account? [y/N] " ans
  case "$ans" in y|Y|yes|YES) ;; *) echo "Cancelled. Nothing was changed."; exit 0 ;; esac
fi

say "3/10  Preparing files"
if [ "$SLUG" != "$ORIG_SLUG" ]; then
  n=0
  while IFS= read -r -d '' f; do
    if grep -q -e "$ORIG_SLUG" -e "himanshu-5680.github.io/queryopsy" -e "@Himanshu-5680" "$f"; then
      n=$((n+1))
      if [ "$DRY" != 1 ]; then
        sed -e "s#$ORIG_SLUG#$SLUG#g" -e "s#himanshu-5680.github.io/queryopsy#$OWNER_LC.github.io/$NAME#g" -e "s#@Himanshu-5680#@$OWNER#g" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
      fi
    fi
  done < <(find . -type f \( -name '*.md' -o -name '*.html' -o -name '*.py' -o -name '*.yml' -o -name '*.yaml' -o -name '*.txt' -o -name '*.json' -o -name '*.webmanifest' -o -name CODEOWNERS \) \
           -not -path './.git/*' -not -path './.git-old-*' -not -path './vendor/*' -not -path './build/*' -not -path './dist/*' -not -path './release-assets/*' -not -path './.venv/*' -print0)
  ok "links updated for $SLUG in $n file(s)"
else
  ok "links already point to $SLUG"
fi

say "4/10  GitHub repository"
if [ "$REPO_EXISTS" = 1 ]; then
  ok "repository already exists - reusing it"
else
  run gh repo create "$SLUG" "--$VISIBILITY" --description "$DESCRIPTION" --homepage "$PAGES_URL" --disable-wiki || fail "gh repo create failed."
  ok "created https://github.com/$SLUG"
fi

say "5/10  Committing and pushing main"
BUILD_FROM_PRS=0; [ "$REMOTE_HAS_COMMITS" = 0 ] && [ "$NOPRS" = 0 ] && BUILD_FROM_PRS=1
if [ "$REMOTE_HAS_COMMITS" = 0 ] && [ -d .git ]; then
  STAMP="$(date +%Y%m%d-%H%M%S)"
  warn "Existing local .git moved to .git-old-$STAMP (the new GitHub repository starts a fresh history)."
  [ "$DRY" = 1 ] || mv .git ".git-old-$STAMP"
fi
if [ ! -d .git ]; then run git init -q; run git symbolic-ref HEAD refs/heads/main; fi
run git config core.autocrlf false
if [ -z "$(git config user.email 2>/dev/null)" ]; then
  ID="$(gh api user --jq .id 2>/dev/null)"
  run git config user.name "$LOGIN"; run git config user.email "$ID+$LOGIN@users.noreply.github.com"
fi
CUR="$(git remote get-url origin 2>/dev/null || true)"
if [ -z "$CUR" ]; then run git remote add origin "$REMOTE_URL"; elif [ "$CUR" != "$REMOTE_URL" ]; then run git remote set-url origin "$REMOTE_URL"; fi

PLAN=.github/pr-plan.tsv
plan_rows() { [ -f "$PLAN" ] && grep -v '^#' "$PLAN" | grep -v '^[[:space:]]*$'; }
existing_paths() { local p out=(); for p in $1; do [ -e "$p" ] && out+=("$p"); done; printf '%s\n' "${out[@]+"${out[@]}"}"; }
if [ "$BUILD_FROM_PRS" = 1 ] && [ "$(plan_rows | wc -l)" -lt 2 ]; then warn "No usable $PLAN - single commit instead."; BUILD_FROM_PRS=0; fi

if [ "$REMOTE_HAS_COMMITS" = 1 ]; then
  run git fetch -q origin main || fail "git fetch failed."
  run git symbolic-ref HEAD refs/heads/main
  run git reset -q origin/main
  run git add -A
  if has_staged; then commit_with_trailers "chore: update Queryopsy" "Sync local changes made by the publish script." || fail "git commit failed."
  else ok "nothing new to commit"; fi
elif [ "$BUILD_FROM_PRS" = 1 ]; then
  IFS=$'\t' read -r _ _ s_title s_paths s_summary < <(plan_rows | awk -F'\t' '$1=="main"' | head -n1)
  mapfile -t P < <(existing_paths "$s_paths")
  run git add -- "${P[@]}"
  commit_with_trailers "$s_title" "$s_summary" || fail "git commit failed."
else
  run git add -A
  commit_with_trailers "feat: Queryopsy $TAG - zero-server SQL forensics simulator" "Offline SQL forensics simulator: Python engine on Pyodide, 6 cases / 24 levels, web app, Android app, tests and GitHub automation." || fail "git commit failed."
fi
run git push -u origin main || fail "git push failed. If GitHub mentions 'workflow' scope: gh auth refresh -s workflow, then re-run."
ok "pushed main"

say "6/10  Configuring the repository"
EDIT=(gh repo edit "$SLUG" --description "$DESCRIPTION" --homepage "$PAGES_URL" --enable-issues --enable-discussions --enable-wiki=false --enable-merge-commit --delete-branch-on-merge)
for t in "${TOPICS[@]}"; do EDIT+=(--add-topic "$t"); done
if run "${EDIT[@]}"; then ok "description, homepage, topics, issues, discussions on, wiki off"; else warn "gh repo edit reported a problem."; fi
run gh api -X PUT "repos/$SLUG/vulnerability-alerts" --silent
run gh api -X PUT "repos/$SLUG/automated-security-fixes" --silent
run gh api -X PUT "repos/$SLUG/private-vulnerability-reporting" --silent
ok "Dependabot alerts, security updates and private vulnerability reporting requested"

say "7/10  Labels"
n=0
while IFS=$'\t' read -r -u 3 lname lcolor ldesc; do
  [ -n "$lname" ] || continue
  run gh label create "$lname" --repo "$SLUG" --color "$lcolor" --description "$ldesc" --force && n=$((n+1))
done 3< .github/labels.tsv
ok "$n labels created or updated"

say "8/10  GitHub Pages"
if quiet gh api "repos/$SLUG/pages"; then
  run gh api -X PUT "repos/$SLUG/pages" -f build_type=workflow --silent; ok "Pages already enabled - source set to GitHub Actions"
elif run gh api -X POST "repos/$SLUG/pages" -f build_type=workflow --silent; then
  ok "Pages enabled (source: GitHub Actions)"
else
  warn "Could not enable Pages automatically. Open Settings > Pages and choose 'GitHub Actions'."
fi

say "9/10  Pull requests"
MERGED=0; BRANCHES=()
open_and_merge() {   # $1 branch $2 labels $3 title $4 paths $5 summary ; commit already made on $1
  local branch="$1" prf=.git/QUERYOPSY_PR_BODY mf=.git/QUERYOPSY_MERGE_MSG i created=0 merged=0 l
  if [ "$DRY" != 1 ]; then
    { printf '## Summary\n\n%s\n\n## Files\n\n' "$5"; for l in $4; do printf -- '- `%s`\n' "$l"; done
      printf '\n## Checklist\n\n- [x] Part of the Queryopsy %s import, split into reviewable pull requests\n- [x] No secrets, tokens or signing material\n- [x] Offline only: no CDN, analytics or network calls\n\n%s\n' "$TAG" "$CO_AUTHORS"; } > "$prf"
    printf '%s\n\n%s\n' "$3" "$CO_AUTHORS" > "$mf"
  fi
  run git push -q -u origin "$branch" || fail "git push of $branch failed."
  local args=(gh pr create --repo "$SLUG" --base main --head "$branch" --title "$3" --body-file "$prf")
  IFS=',' read -r -a LBL <<< "$2"; for l in "${LBL[@]+"${LBL[@]}"}"; do [ -n "$l" ] && [ "$l" != "-" ] && args+=(--label "$l"); done
  for i in 1 2 3 4; do if run "${args[@]}"; then created=1; break; fi; sleep 3; done
  if [ "$created" = 1 ]; then
    for i in 1 2 3 4 5 6 7 8; do
      [ "$i" -gt 1 ] && sleep 4
      if run gh pr merge "$branch" --repo "$SLUG" --merge --delete-branch --body-file "$mf"; then merged=1; break; fi
    done
  fi
  if [ "$merged" = 0 ]; then
    warn "Could not merge $branch through the API - fast-forwarding main instead."
    run git push -q origin "$branch:main" || fail "Could not update main with $branch. Fix the problem and re-run."
    run git push -q origin --delete "$branch"
  fi
  run git fetch -q origin main || fail "git fetch failed."
}

if [ "$BUILD_FROM_PRS" = 1 ]; then
  while IFS=$'\t' read -r -u 3 branch labels title paths summary; do
    [ "$branch" = main ] && continue
    mapfile -t P < <(existing_paths "$paths")
    [ ${#P[@]} -gt 0 ] && [ -n "${P[0]}" ] || continue
    run git checkout -q -B "$branch" origin/main
    run git add -- "${P[@]}"
    if ! has_staged; then ok "nothing to add for $branch"; continue; fi
    commit_with_trailers "$title" "$summary" || fail "git commit failed on $branch"
    open_and_merge "$branch" "$labels" "$title" "$paths" "$summary"
    BRANCHES+=("$branch"); MERGED=$((MERGED+1))
    ok "merged #$MERGED  $title"
  done 3< <(plan_rows)
  run git checkout -q -B chore/sync-remaining origin/main
  run git add -A
  if [ "$DRY" != 1 ] && has_staged; then
    commit_with_trailers "chore: add remaining project files" "Files that were not part of any planned pull request." || fail "git commit failed."
    open_and_merge chore/sync-remaining enhancement "chore: add remaining project files" "(files not listed in .github/pr-plan.tsv)" "Files that were not part of any planned pull request."
    MERGED=$((MERGED+1)); ok "merged #$MERGED  chore: add remaining project files"
  fi
  run git checkout -q -B main origin/main
  run git branch -q --set-upstream-to=origin/main main
  for b in "${BRANCHES[@]+"${BRANCHES[@]}"}" chore/sync-remaining; do quiet git branch -q -D "$b"; done
  ok "$MERGED pull requests created and merged"
elif [ "$NOPRS" = 1 ]; then
  ok "skipped (--no-prs)"
else
  ok "skipped (only on a brand-new repository; use a new --name or an empty repository to get the PR history)"
fi

if [ "$DRY" != 1 ]; then
  quiet git fetch -q --prune origin
  if [ -z "$(git status --porcelain)" ] && [ "$(git rev-parse 'HEAD^{tree}')" = "$(git rev-parse 'origin/main^{tree}')" ]; then
    ok "GitHub main matches the local folder exactly"
  else
    warn "GitHub main differs from the local folder - re-run the script to sync."
  fi
fi

say "10/10  Deploy and release $TAG"
started=0
for _ in 1 2 3 4 5 6; do
  if run gh workflow run pages.yml --repo "$SLUG" --ref main; then started=1; break; fi
  sleep 5
done
[ "$started" = 1 ] && ok "Pages deployment started (about 1-2 minutes)" || warn "Start it from Actions > 'Deploy to GitHub Pages' > Run workflow."
ASSETS=()
for a in "release-assets/Queryopsy-v$VERSION.apk" "release-assets/queryopsy-web-v$VERSION.zip"; do
  if [ -f "$a" ]; then ASSETS+=("$a"); else warn "missing $a (skipped)"; fi
done
if quiet gh release view "$TAG" --repo "$SLUG" --json tagName; then
  [ ${#ASSETS[@]} -gt 0 ] && run gh release upload "$TAG" --repo "$SLUG" --clobber "${ASSETS[@]}"
  run gh release edit "$TAG" --repo "$SLUG" --latest
  ok "release already existed - assets refreshed"
else
  if run gh release create "$TAG" --repo "$SLUG" --target main --title "Queryopsy $TAG" --notes-file "docs/release-notes/$TAG.md" --latest ${ASSETS[@]+"${ASSETS[@]}"}; then
    ok "release created"; else warn "gh release create failed - re-run to retry."; fi
fi

echo; c "30;42" "  DONE  "
echo "  Repository : https://github.com/$SLUG"
echo "  Pull reqs  : https://github.com/$SLUG/pulls?q=is%3Apr+is%3Amerged"
echo "  Live site  : $PAGES_URL   (live after the Pages workflow finishes)"
echo "  Release    : https://github.com/$SLUG/releases/tag/$TAG"
echo "  Actions    : https://github.com/$SLUG/actions"
echo
