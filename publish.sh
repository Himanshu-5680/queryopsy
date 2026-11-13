#!/usr/bin/env bash
# Queryopsy - one-command GitHub publisher (macOS / Linux / Git Bash / WSL).
#
#   bash publish.sh            # asks before doing anything
#   bash publish.sh --yes      # no questions
# Options: --name <repo> (default queryopsy)  --owner <login|org>  --private  --yes  --dry-run
# Safe to re-run: an existing repository, labels, Pages site and release are reused/updated.
set -u

VERSION="1.0.0"; TAG="v$VERSION"; ORIG_SLUG="Himanshu-5680/queryopsy"
NAME="queryopsy"; OWNER=""; VISIBILITY="public"; YES=0; DRY=0
DESCRIPTION="Zero-server SQL forensics and industry case simulator. Python + SQLite in WebAssembly, offline web app and Android APK."
TOPICS=(sql sqlite python pyodide webassembly data-analysis sql-game learn-sql forensics offline-first pwa android neo-brutalism education india)

while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="$2"; shift 2 ;;
    --owner) OWNER="$2"; shift 2 ;;
    --private) VISIBILITY="private"; shift ;;
    --yes|-y) YES=1; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
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

echo; c "30;43" "  QUERYOPSY  -  GitHub publisher  $TAG  "; echo

say "1/9  Checking tools"
command -v git >/dev/null || fail "git is not installed (https://git-scm.com)."
command -v gh >/dev/null || fail "GitHub CLI is not installed (https://cli.github.com)."
ok "$(git --version)"; ok "$(gh --version | head -n1)"
[ -f index.html ] && [ -f data/cases.json ] || fail "Run this script from inside the extracted queryopsy folder."

say "2/9  Checking GitHub login"
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

echo
echo "  Owner:       $OWNER"
echo "  Repository:  https://github.com/$SLUG"
echo "  Visibility:  $VISIBILITY"
echo "  Pages:       $PAGES_URL"
[ "$DRY" = 1 ] && c "33" "  Mode:        DRY RUN (nothing will change)"
echo
[ "$VISIBILITY" = private ] && warn "GitHub Pages on private repositories needs a paid plan."
if [ "$YES" != 1 ]; then
  read -r -p "Publish Queryopsy to this account? [y/N] " ans
  case "$ans" in y|Y|yes|YES) ;; *) echo "Cancelled. Nothing was changed."; exit 0 ;; esac
fi

say "3/9  Preparing files"
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
           -not -path './.git/*' -not -path './vendor/*' -not -path './build/*' -not -path './dist/*' -not -path './release-assets/*' -not -path './.venv/*' -print0)
  ok "links updated for $SLUG in $n file(s)"
else
  ok "links already point to $SLUG"
fi

say "4/9  Committing"
if [ ! -d .git ]; then run git init; run git symbolic-ref HEAD refs/heads/main; fi
if [ -z "$(git config user.email 2>/dev/null)" ]; then
  ID="$(gh api user --jq .id 2>/dev/null)"
  run git config user.name "$LOGIN"; run git config user.email "$ID+$LOGIN@users.noreply.github.com"
fi
run git add -A
if [ "$DRY" = 1 ] || [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  MSG="chore: update Queryopsy"; quiet git rev-parse --verify HEAD || MSG="feat: Queryopsy $TAG - zero-server SQL forensics simulator"
  run git commit -m "$MSG" || fail "git commit failed."
else
  ok "nothing new to commit"
fi
run git branch -M main

say "5/9  Creating the GitHub repository"
if quiet gh repo view "$SLUG" --json name; then
  ok "repository already exists - reusing it"
else
  run gh repo create "$SLUG" "--$VISIBILITY" --description "$DESCRIPTION" --homepage "$PAGES_URL" --disable-wiki || fail "gh repo create failed."
fi
URL="https://github.com/$SLUG.git"; CUR="$(git remote get-url origin 2>/dev/null || true)"
if [ -z "$CUR" ]; then run git remote add origin "$URL"; elif [ "$CUR" != "$URL" ]; then run git remote set-url origin "$URL"; fi
run git push -u origin main || fail "git push failed. If GitHub mentions 'workflow' scope: gh auth refresh -s workflow, then re-run."
ok "pushed main"

say "6/9  Configuring the repository"
EDIT=(gh repo edit "$SLUG" --description "$DESCRIPTION" --homepage "$PAGES_URL" --enable-issues --enable-discussions --enable-wiki=false --delete-branch-on-merge)
for t in "${TOPICS[@]}"; do EDIT+=(--add-topic "$t"); done
if run "${EDIT[@]}"; then ok "description, homepage, topics, issues, discussions on, wiki off"; else warn "gh repo edit reported a problem."; fi
run gh api -X PUT "repos/$SLUG/vulnerability-alerts" --silent
run gh api -X PUT "repos/$SLUG/automated-security-fixes" --silent
run gh api -X PUT "repos/$SLUG/private-vulnerability-reporting" --silent
ok "Dependabot alerts, security updates and private vulnerability reporting requested"

say "7/9  Labels"
n=0
while IFS=$'\t' read -r lname lcolor ldesc; do
  [ -n "$lname" ] || continue
  run gh label create "$lname" --repo "$SLUG" --color "$lcolor" --description "$ldesc" --force && n=$((n+1))
done < .github/labels.tsv
ok "$n labels created or updated"

say "8/9  GitHub Pages"
if quiet gh api "repos/$SLUG/pages"; then
  run gh api -X PUT "repos/$SLUG/pages" -f build_type=workflow --silent; ok "Pages already enabled - source set to GitHub Actions"
elif run gh api -X POST "repos/$SLUG/pages" -f build_type=workflow --silent; then
  ok "Pages enabled (source: GitHub Actions)"
else
  warn "Could not enable Pages automatically. Open Settings > Pages and choose 'GitHub Actions'."
fi
started=0
for _ in 1 2 3 4 5 6; do
  if run gh workflow run pages.yml --repo "$SLUG" --ref main; then started=1; break; fi
  sleep 5
done
[ "$started" = 1 ] && ok "Pages deployment started (about 1-2 minutes)" || warn "Start it from Actions > 'Deploy to GitHub Pages' > Run workflow."

say "9/9  Release $TAG"
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
echo "  Live site  : $PAGES_URL   (live after the Pages workflow finishes)"
echo "  Release    : https://github.com/$SLUG/releases/tag/$TAG"
echo "  Actions    : https://github.com/$SLUG/actions"
echo
