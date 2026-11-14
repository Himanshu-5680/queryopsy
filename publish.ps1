<#
  Queryopsy - one-command GitHub publisher (Windows PowerShell 5.1+ and PowerShell 7).

  Usage (run inside the extracted "queryopsy" folder):
      powershell -ExecutionPolicy Bypass -File .\publish.ps1            # asks before doing anything
      powershell -ExecutionPolicy Bypass -File .\publish.ps1 -Yes       # no questions
  Options:
      -Name <repo>      repository name (default: queryopsy)
      -Owner <login>    user or organisation (default: the logged-in gh account)
      -Private          create a private repository (default: public)
      -NoPRs            push everything in one commit instead of building the history from pull requests
      -Yes              skip the confirmation prompt
      -DryRun           only print what would happen

  On a brand-new (empty) repository the history is built from .github/pr-plan.tsv: a skeleton commit on
  main, then one branch + pull request per feature area, each merged automatically. Every commit carries
  the Co-authored-by trailers below. Re-running on a repository that already has commits just syncs any
  changes in one commit (no new pull requests). Needs git and GitHub CLI (gh). No secrets are stored.
#>
param(
    [string]$Name = "queryopsy",
    [string]$Owner = "",
    [switch]$Private,
    [switch]$NoPRs,
    [switch]$Yes,
    [switch]$DryRun
)

$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot

$Version = "1.1.0"
$Tag = "v$Version"
$OrigSlug = "Himanshu-5680/queryopsy"
$CoAuthors = @(
    "Co-authored-by: pavitra-prabhakar <himanshupathakhimanshu@gmail.com>",
    "Co-authored-by: vectornomadhp88 <himanshupc88@gmail.com>"
)
$Description = "Zero-server SQL forensics and industry case simulator. Python + SQLite in WebAssembly, offline web app and Android APK."
$Topics = @("sql", "sqlite", "python", "pyodide", "webassembly", "data-analysis", "sql-game", "learn-sql",
            "forensics", "offline-first", "pwa", "android", "detective-game", "education", "india")
$Utf8 = New-Object System.Text.UTF8Encoding($false)

function Say([string]$msg) { Write-Host $msg -ForegroundColor Cyan }
function Ok([string]$msg) { Write-Host ("  [ok] " + $msg) -ForegroundColor Green }
function Warn([string]$msg) { Write-Host ("  [!] " + $msg) -ForegroundColor Yellow }
function Fail([string]$msg) { Write-Host ("[x] " + $msg) -ForegroundColor Red; exit 1 }

# Run a native command, echo it first; returns the exit code. In -DryRun mode nothing is executed.
function Run([string[]]$cmd) {
    Write-Host ("  > " + ($cmd -join " ")) -ForegroundColor DarkGray
    if ($DryRun) { return 0 }
    $rest = @()
    if ($cmd.Count -gt 1) { $rest = $cmd[1..($cmd.Count - 1)] }
    & $cmd[0] $rest | Out-Host
    return $LASTEXITCODE
}

# Run quietly (read-only checks); returns @{ Code; Out }.
function Probe([string[]]$cmd) {
    $rest = @()
    if ($cmd.Count -gt 1) { $rest = $cmd[1..($cmd.Count - 1)] }
    $out = & $cmd[0] $rest 2>$null
    return @{ Code = $LASTEXITCODE; Out = (($out | Out-String).Trim()) }
}

# Write a text file with LF line endings and no BOM (used for commit messages and PR bodies).
function Write-Lf([string]$path, [string[]]$lines) {
    if ($DryRun) { return }
    [System.IO.File]::WriteAllText($path, (($lines -join "`n") + "`n"), $Utf8)
}

# Commit what is staged with a title, a summary paragraph and the co-author trailers.
function Commit-WithTrailers([string]$title, [string]$summary) {
    $msgFile = Join-Path (Get-Location) ".git\QUERYOPSY_COMMIT_MSG"
    $lines = @($title, "")
    if ($summary) { $lines += @($summary, "") }
    $lines += $CoAuthors
    Write-Lf $msgFile $lines
    return (Run @("git", "commit", "-q", "-F", $msgFile))
}

function Has-Staged {
    if ($DryRun) { return $true }
    $null = & git diff --cached --quiet 2>$null
    return ($LASTEXITCODE -ne 0)
}

Write-Host ""
Write-Host "  QUERYOPSY  -  GitHub publisher  $Tag" -ForegroundColor Black -BackgroundColor Yellow
Write-Host ""

# 1. Tools ---------------------------------------------------------------
Say "1/10  Checking tools"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Fail "git is not installed. Get it from https://git-scm.com/download/win (or: winget install Git.Git), then reopen PowerShell." }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { Fail "GitHub CLI is not installed. Get it from https://cli.github.com (or: winget install GitHub.cli), then reopen PowerShell." }
Ok ((& git --version) -join " ")
Ok (((& gh --version) | Select-Object -First 1) -join " ")
if (-not (Test-Path "index.html") -or -not (Test-Path "data\cases.json")) { Fail "Run this script from inside the extracted queryopsy folder." }

# 2. Login ---------------------------------------------------------------
Say "2/10  Checking GitHub login"
$auth = Probe @("gh", "auth", "status", "--hostname", "github.com")
if ($auth.Code -ne 0) {
    Warn "Not logged in to GitHub CLI - opening the login flow (choose your browser)."
    & gh auth login --hostname github.com --git-protocol https --web --scopes workflow
    if ($LASTEXITCODE -ne 0) { Fail "gh auth login failed." }
}
$statusText = (& gh auth status --hostname github.com 2>&1 | Out-String)
if (($statusText -match "Token scopes") -and ($statusText -notmatch "workflow")) {
    Warn "Your gh token lacks the 'workflow' scope (needed to push .github/workflows). Refreshing..."
    & gh auth refresh --hostname github.com --scopes workflow
    if ($LASTEXITCODE -ne 0) { Fail "gh auth refresh failed." }
}
$null = & gh auth setup-git 2>$null
$login = (Probe @("gh", "api", "user", "--jq", ".login")).Out
if (-not $login) { Fail "Could not read your GitHub username (gh api user)." }
if (-not $Owner) { $Owner = $login }
$Slug = "$Owner/$Name"
$PagesUrl = "https://" + $Owner.ToLower() + ".github.io/" + $Name + "/"
$Visibility = "public"
if ($Private) { $Visibility = "private" }
$RepoExists = (Probe @("gh", "repo", "view", $Slug, "--json", "name")).Code -eq 0
$RemoteHasCommits = $false
if ($RepoExists) {
    $env:GIT_TERMINAL_PROMPT = "0"
    $heads = Probe @("git", "ls-remote", "--heads", "https://github.com/$Slug.git")
    Remove-Item Env:\GIT_TERMINAL_PROMPT -ErrorAction SilentlyContinue
    if ($heads.Out) { $RemoteHasCommits = $true }
}
$Mode = "pull requests (skeleton on main + one PR per feature, auto-merged)"
if ($NoPRs) { $Mode = "single commit (-NoPRs)" }
if ($RemoteHasCommits) { $Mode = "sync changes (repository already has commits, no new PRs)" }

Write-Host ""
Write-Host ("  Owner:       " + $Owner) -ForegroundColor White
Write-Host ("  Repository:  https://github.com/" + $Slug) -ForegroundColor White
Write-Host ("  Visibility:  " + $Visibility) -ForegroundColor White
Write-Host ("  Pages:       " + $PagesUrl) -ForegroundColor White
Write-Host ("  History:     " + $Mode) -ForegroundColor White
Write-Host  "  Co-authors:  pavitra-prabhakar, vectornomadhp88" -ForegroundColor White
if ($DryRun) { Write-Host "  Mode:        DRY RUN (nothing will change)" -ForegroundColor Yellow }
Write-Host ""
if ($Private) { Warn "GitHub Pages on private repositories needs a paid plan; the live demo may not deploy." }
if (-not $Yes) {
    $answer = Read-Host "Publish Queryopsy to this account? [y/N]"
    if ($answer -notmatch "^(y|yes)$") { Write-Host "Cancelled. Nothing was changed."; exit 0 }
}

# 3. Personalise links if the repository is not Himanshu-5680/queryopsy ---------
Say "3/10  Preparing files"
if ($Slug -ne $OrigSlug) {
    $exts = @(".md", ".html", ".py", ".yml", ".yaml", ".txt", ".json", ".webmanifest")
    $files = Get-ChildItem -Recurse -File -Force | Where-Object {
        ($exts -contains $_.Extension.ToLower() -or $_.Name -eq "CODEOWNERS") -and
        ($_.FullName -notmatch "[\\/](\.git|\.git-old-[^\\/]*|vendor|build|dist|release-assets|node_modules|\.venv)[\\/]")
    }
    $changed = 0
    foreach ($f in $files) {
        $text = [System.IO.File]::ReadAllText($f.FullName)
        $new = $text.Replace($OrigSlug, $Slug).Replace("himanshu-5680.github.io/queryopsy", ($Owner.ToLower() + ".github.io/" + $Name)).Replace("@Himanshu-5680", "@" + $Owner)
        if ($new -ne $text) {
            $changed++
            if (-not $DryRun) { [System.IO.File]::WriteAllText($f.FullName, $new, $Utf8) }
        }
    }
    Ok ("links updated for " + $Slug + " in " + $changed + " file(s)")
} else {
    Ok "links already point to $Slug"
}

# 4. Repository on GitHub ---------------------------------------------------
Say "4/10  GitHub repository"
if ($RepoExists) {
    Ok "repository already exists - reusing it"
} else {
    if ((Run @("gh", "repo", "create", $Slug, "--$Visibility", "--description", $Description, "--homepage", $PagesUrl, "--disable-wiki")) -ne 0) { Fail "gh repo create failed." }
    Ok "created https://github.com/$Slug"
}

# 5. Local repository and first push -------------------------------------------
Say "5/10  Committing and pushing main"
$remoteUrl = "https://github.com/$Slug.git"
$BuildFromPRs = (-not $RemoteHasCommits) -and (-not $NoPRs)
if ((-not $RemoteHasCommits) -and (Test-Path ".git")) {
    # A brand-new remote: start a clean history. The old local history is kept, renamed, never deleted.
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    Warn "Existing local .git moved to .git-old-$stamp (the new GitHub repository starts a fresh history)."
    if (-not $DryRun) { Rename-Item -Force -Path ".git" -NewName (".git-old-" + $stamp) }
}
if (-not (Test-Path ".git")) {
    $null = Run @("git", "init", "-q")
    $null = Run @("git", "symbolic-ref", "HEAD", "refs/heads/main")
}
$null = Run @("git", "config", "core.autocrlf", "false")
$email = (Probe @("git", "config", "user.email")).Out
if (-not $email) {
    $id = (Probe @("gh", "api", "user", "--jq", ".id")).Out
    $null = Run @("git", "config", "user.name", $login)
    $null = Run @("git", "config", "user.email", ($id + "+" + $login + "@users.noreply.github.com"))
}
$current = (Probe @("git", "remote", "get-url", "origin")).Out
if (-not $current) { $null = Run @("git", "remote", "add", "origin", $remoteUrl) }
elseif ($current -ne $remoteUrl) { $null = Run @("git", "remote", "set-url", "origin", $remoteUrl) }

# Read the history plan (branch, labels, title, paths, summary).
$Plan = @()
if (Test-Path ".github/pr-plan.tsv") {
    foreach ($line in (Get-Content ".github/pr-plan.tsv")) {
        if ((-not $line.Trim()) -or $line.StartsWith("#")) { continue }
        $p = $line.Split("`t")
        if ($p.Count -lt 5) { continue }
        $Plan += New-Object PSObject -Property @{ Branch = $p[0]; Labels = $p[1]; Title = $p[2]; Paths = $p[3]; Summary = $p[4] }
    }
}
if ($BuildFromPRs -and $Plan.Count -lt 2) { Warn "No usable .github/pr-plan.tsv - falling back to a single commit."; $BuildFromPRs = $false }

if ($RemoteHasCommits) {
    # Re-run: line up with GitHub's main without touching the files on disk, then commit any differences.
    if ((Run @("git", "fetch", "-q", "origin", "main")) -ne 0) { Fail "git fetch failed." }
    $null = Run @("git", "symbolic-ref", "HEAD", "refs/heads/main")
    $null = Run @("git", "reset", "-q", "origin/main")
    $null = Run @("git", "add", "-A")
    if (Has-Staged) {
        if ((Commit-WithTrailers "chore: update Queryopsy" "Sync local changes made by the publish script.") -ne 0) { Fail "git commit failed." }
    } else { Ok "nothing new to commit" }
} elseif ($BuildFromPRs) {
    $skeleton = $Plan | Where-Object { $_.Branch -eq "main" } | Select-Object -First 1
    $paths = @($skeleton.Paths.Split(" ") | Where-Object { $_ -and (Test-Path $_) })
    $null = Run (@("git", "add", "--") + $paths)
    if ((Commit-WithTrailers $skeleton.Title $skeleton.Summary) -ne 0) { Fail "git commit failed." }
} else {
    $null = Run @("git", "add", "-A")
    if ((Commit-WithTrailers "feat: Queryopsy $Tag - zero-server SQL forensics simulator" "Offline SQL forensics simulator: Python engine on Pyodide, 6 cases / 24 levels, web app, Android app, tests and GitHub automation.") -ne 0) { Fail "git commit failed." }
}
if ((Run @("git", "push", "-u", "origin", "main")) -ne 0) {
    Fail "git push failed. If GitHub mentions 'workflow' scope run: gh auth refresh -s workflow   then re-run this script."
}
Ok "pushed main"

# 6. Settings, topics and security features ----------------------------------
Say "6/10  Configuring the repository"
$editArgs = @("gh", "repo", "edit", $Slug, "--description", $Description, "--homepage", $PagesUrl,
              "--enable-issues", "--enable-discussions", "--enable-wiki=false", "--enable-merge-commit", "--delete-branch-on-merge")
foreach ($t in $Topics) { $editArgs += @("--add-topic", $t) }
if ((Run $editArgs) -ne 0) { Warn "gh repo edit reported a problem (settings may be partly applied)." } else { Ok "description, homepage, topics, issues, discussions on, wiki off" }
$null = Run @("gh", "api", "-X", "PUT", "repos/$Slug/vulnerability-alerts", "--silent")
$null = Run @("gh", "api", "-X", "PUT", "repos/$Slug/automated-security-fixes", "--silent")
$null = Run @("gh", "api", "-X", "PUT", "repos/$Slug/private-vulnerability-reporting", "--silent")
Ok "Dependabot alerts, security updates and private vulnerability reporting requested"

# 7. Labels ----------------------------------------------------------------
Say "7/10  Labels"
$labelCount = 0
foreach ($line in (Get-Content ".github/labels.tsv")) {
    if (-not $line.Trim()) { continue }
    $parts = $line.Split("`t")
    if ($parts.Count -lt 3) { continue }
    $code = Run @("gh", "label", "create", $parts[0], "--repo", $Slug, "--color", $parts[1], "--description", $parts[2], "--force")
    if ($code -eq 0) { $labelCount++ }
}
Ok "$labelCount labels created or updated"

# 8. GitHub Pages (built by .github/workflows/pages.yml) ----------------------
Say "8/10  GitHub Pages"
$pagesInfo = Probe @("gh", "api", "repos/$Slug/pages")
if ($pagesInfo.Code -eq 0) {
    $null = Run @("gh", "api", "-X", "PUT", "repos/$Slug/pages", "-f", "build_type=workflow", "--silent")
    Ok "Pages already enabled - source set to GitHub Actions"
} else {
    if ((Run @("gh", "api", "-X", "POST", "repos/$Slug/pages", "-f", "build_type=workflow", "--silent")) -eq 0) { Ok "Pages enabled (source: GitHub Actions)" }
    else { Warn "Could not enable Pages automatically. Open Settings > Pages and choose 'GitHub Actions'." }
}

# 9. Pull requests ------------------------------------------------------------
Say "9/10  Pull requests"
$Merged = 0
function Open-And-Merge($item, [string]$branch) {
    # Commit is already made on $branch (based on origin/main). Push, open the PR, merge it, sync.
    $prFile = Join-Path (Get-Location) ".git\QUERYOPSY_PR_BODY"
    $mergeFile = Join-Path (Get-Location) ".git\QUERYOPSY_MERGE_MSG"
    $fileLines = @()
    foreach ($fp in $item.Paths.Split(" ")) { if ($fp) { $fileLines += ("- ``" + $fp + "``") } }
    $body = @("## Summary", "", $item.Summary, "", "## Files", "") + $fileLines + @("",
              "## Checklist", "",
              "- [x] Part of the Queryopsy $Tag import, split into reviewable pull requests",
              "- [x] No secrets, tokens or signing material",
              "- [x] Offline only: no CDN, analytics or network calls",
              "") + $CoAuthors
    Write-Lf $prFile $body
    Write-Lf $mergeFile (@($item.Title, "") + $CoAuthors)
    if ((Run @("git", "push", "-q", "-u", "origin", $branch)) -ne 0) { Fail "git push of $branch failed." }
    $prArgs = @("gh", "pr", "create", "--repo", $Slug, "--base", "main", "--head", $branch, "--title", $item.Title, "--body-file", $prFile)
    foreach ($l in $item.Labels.Split(",")) { if ($l.Trim() -and ($l.Trim() -ne "-")) { $prArgs += @("--label", $l.Trim()) } }
    $created = $false
    for ($i = 0; $i -lt 4 -and -not $created; $i++) {
        if ((Run $prArgs) -eq 0) { $created = $true } else { Start-Sleep -Seconds 3 }
    }
    $merged = $false
    if ($created) {
        for ($i = 0; $i -lt 8 -and -not $merged; $i++) {
            if ($i -gt 0) { Start-Sleep -Seconds 4 }
            if ((Run @("gh", "pr", "merge", $branch, "--repo", $Slug, "--merge", "--delete-branch", "--body-file", $mergeFile)) -eq 0) { $merged = $true }
        }
    }
    if (-not $merged) {
        # Fallback: fast-forward main to the branch (GitHub then marks the PR as merged) and delete the branch.
        Warn "Could not merge $branch through the API - fast-forwarding main instead."
        if ((Run @("git", "push", "-q", "origin", ($branch + ":main"))) -ne 0) { Fail "Could not update main with $branch. Fix the problem and re-run." }
        $null = Run @("git", "push", "-q", "origin", "--delete", $branch)
    }
    if ((Run @("git", "fetch", "-q", "origin", "main")) -ne 0) { Fail "git fetch failed." }
    return $true
}

if ($BuildFromPRs) {
    $branches = @()
    foreach ($item in ($Plan | Where-Object { $_.Branch -ne "main" })) {
        $paths = @($item.Paths.Split(" ") | Where-Object { $_ -and (Test-Path $_) })
        if ($paths.Count -eq 0) { continue }
        $null = Run @("git", "checkout", "-q", "-B", $item.Branch, "origin/main")
        $null = Run (@("git", "add", "--") + $paths)
        if (-not (Has-Staged)) { Ok ("nothing to add for " + $item.Branch); continue }
        if ((Commit-WithTrailers $item.Title $item.Summary) -ne 0) { Fail ("git commit failed on " + $item.Branch) }
        $null = Open-And-Merge $item $item.Branch
        $branches += $item.Branch
        $Merged++
        Ok ("merged #" + $Merged + "  " + $item.Title)
    }
    # Anything not covered by the plan goes in one last pull request.
    $null = Run @("git", "checkout", "-q", "-B", "chore/sync-remaining", "origin/main")
    $null = Run @("git", "add", "-A")
    if ((-not $DryRun) -and (Has-Staged)) {
        $rest = New-Object PSObject -Property @{ Branch = "chore/sync-remaining"; Labels = "enhancement"; Title = "chore: add remaining project files"; Paths = "(files not listed in .github/pr-plan.tsv)"; Summary = "Files that were not part of any planned pull request." }
        if ((Commit-WithTrailers $rest.Title $rest.Summary) -ne 0) { Fail "git commit failed." }
        $null = Open-And-Merge $rest $rest.Branch
        $branches += $rest.Branch
        $Merged++
        Ok ("merged #" + $Merged + "  " + $rest.Title)
    }
    $null = Run @("git", "checkout", "-q", "-B", "main", "origin/main")
    $null = Run @("git", "branch", "-q", "--set-upstream-to=origin/main", "main")
    foreach ($b in ($branches + @("chore/sync-remaining"))) { $null = & git branch -q -D $b 2>$null }
    Ok "$Merged pull requests created and merged"
} elseif ($NoPRs) {
    Ok "skipped (-NoPRs)"
} else {
    Ok "skipped (only on a brand-new repository; use a new -Name or an empty repository to get the PR history)"
}

# Final check: GitHub's main must contain exactly the files on disk.
if (-not $DryRun) {
    $null = & git fetch -q --prune origin 2>$null
    $dirty = (Probe @("git", "status", "--porcelain")).Out
    $localTree = (Probe @("git", "rev-parse", "HEAD^{tree}")).Out
    $remoteTree = (Probe @("git", "rev-parse", "origin/main^{tree}")).Out
    if ((-not $dirty) -and ($localTree -eq $remoteTree)) { Ok "GitHub main matches the local folder exactly" }
    else { Warn "GitHub main differs from the local folder - re-run the script to sync." }
}

# 10. Pages deployment and release --------------------------------------------
Say "10/10  Deploy and release $Tag"
$dispatched = $false
for ($i = 0; $i -lt 6 -and -not $dispatched; $i++) {
    if ((Run @("gh", "workflow", "run", "pages.yml", "--repo", $Slug, "--ref", "main")) -eq 0) { $dispatched = $true }
    elseif (-not $DryRun) { Start-Sleep -Seconds 5 }
}
if ($dispatched) { Ok "Pages deployment started (takes about 1-2 minutes)" } else { Warn "Start it later from the Actions tab: 'Deploy to GitHub Pages' > Run workflow." }
$assets = @()
foreach ($a in @("release-assets/Queryopsy-v$Version.apk", "release-assets/queryopsy-web-v$Version.zip")) {
    if (Test-Path $a) { $assets += $a } else { Warn "missing $a (skipped)" }
}
$relExists = (Probe @("gh", "release", "view", $Tag, "--repo", $Slug, "--json", "tagName")).Code -eq 0
if ($relExists) {
    if ($assets.Count -gt 0) { $null = Run (@("gh", "release", "upload", $Tag, "--repo", $Slug, "--clobber") + $assets) }
    $null = Run @("gh", "release", "edit", $Tag, "--repo", $Slug, "--latest")
    Ok "release already existed - assets refreshed"
} else {
    $code = Run (@("gh", "release", "create", $Tag, "--repo", $Slug, "--target", "main", "--title", "Queryopsy $Tag",
                   "--notes-file", "docs/release-notes/$Tag.md", "--latest") + $assets)
    if ($code -ne 0) { Warn "gh release create failed - re-run the script to retry." } else { Ok "release created" }
}

Write-Host ""
Write-Host "  DONE" -ForegroundColor Black -BackgroundColor Green
Write-Host ("  Repository : https://github.com/" + $Slug)
Write-Host ("  Pull reqs  : https://github.com/" + $Slug + "/pulls?q=is%3Apr+is%3Amerged")
Write-Host ("  Live site  : " + $PagesUrl + "   (live after the Pages workflow finishes)")
Write-Host ("  Release    : https://github.com/" + $Slug + "/releases/tag/" + $Tag)
Write-Host ("  Actions    : https://github.com/" + $Slug + "/actions")
Write-Host ""
