<#
  Queryopsy - one-command GitHub publisher (Windows PowerShell 5.1+ and PowerShell 7).

  Usage (run inside the extracted "queryopsy" folder):
      powershell -ExecutionPolicy Bypass -File .\publish.ps1            # asks before doing anything
      powershell -ExecutionPolicy Bypass -File .\publish.ps1 -Yes       # no questions
  Options:
      -Name <repo>      repository name (default: queryopsy)
      -Owner <login>    user or organisation (default: the logged-in gh account)
      -Private          create a private repository (default: public)
      -Yes              skip the confirmation prompt
      -DryRun           only print what would happen

  Safe to re-run: an existing repository, labels, Pages site and release are reused/updated.
  Needs: git and GitHub CLI (gh). No tokens or secrets are stored in the repository.
#>
param(
    [string]$Name = "queryopsy",
    [string]$Owner = "",
    [switch]$Private,
    [switch]$Yes,
    [switch]$DryRun
)

$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot

$Version = "1.0.0"
$Tag = "v$Version"
$OrigSlug = "Himanshu-5680/queryopsy"
$Description = "Zero-server SQL forensics and industry case simulator. Python + SQLite in WebAssembly, offline web app and Android APK."
$Topics = @("sql", "sqlite", "python", "pyodide", "webassembly", "data-analysis", "sql-game", "learn-sql",
            "forensics", "offline-first", "pwa", "android", "neo-brutalism", "education", "india")

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

Write-Host ""
Write-Host "  QUERYOPSY  -  GitHub publisher  $Tag" -ForegroundColor Black -BackgroundColor Yellow
Write-Host ""

# 1. Tools ---------------------------------------------------------------
Say "1/9  Checking tools"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Fail "git is not installed. Get it from https://git-scm.com/download/win (or: winget install Git.Git), then reopen PowerShell." }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { Fail "GitHub CLI is not installed. Get it from https://cli.github.com (or: winget install GitHub.cli), then reopen PowerShell." }
Ok ((& git --version) -join " ")
Ok (((& gh --version) | Select-Object -First 1) -join " ")
if (-not (Test-Path "index.html") -or -not (Test-Path "data\cases.json")) { Fail "Run this script from inside the extracted queryopsy folder." }

# 2. Login ---------------------------------------------------------------
Say "2/9  Checking GitHub login"
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

Write-Host ""
Write-Host ("  Owner:       " + $Owner) -ForegroundColor White
Write-Host ("  Repository:  https://github.com/" + $Slug) -ForegroundColor White
Write-Host ("  Visibility:  " + $Visibility) -ForegroundColor White
Write-Host ("  Pages:       " + $PagesUrl) -ForegroundColor White
if ($DryRun) { Write-Host "  Mode:        DRY RUN (nothing will change)" -ForegroundColor Yellow }
Write-Host ""
if ($Private) { Warn "GitHub Pages on private repositories needs a paid plan; the live demo may not deploy." }
if (-not $Yes) {
    $answer = Read-Host "Publish Queryopsy to this account? [y/N]"
    if ($answer -notmatch "^(y|yes)$") { Write-Host "Cancelled. Nothing was changed."; exit 0 }
}

# 3. Personalise links if the repository is not Himanshu-5680/queryopsy ---------
Say "3/9  Preparing files"
if ($Slug -ne $OrigSlug) {
    $exts = @(".md", ".html", ".py", ".yml", ".yaml", ".txt", ".json", ".webmanifest")
    $files = Get-ChildItem -Recurse -File -Force | Where-Object {
        ($exts -contains $_.Extension.ToLower() -or $_.Name -eq "CODEOWNERS") -and
        ($_.FullName -notmatch "[\\/](\.git|vendor|build|dist|release-assets|node_modules|\.venv)[\\/]")
    }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    $changed = 0
    foreach ($f in $files) {
        $text = [System.IO.File]::ReadAllText($f.FullName)
        $new = $text.Replace($OrigSlug, $Slug).Replace("himanshu-5680.github.io/queryopsy", ($Owner.ToLower() + ".github.io/" + $Name)).Replace("@Himanshu-5680", "@" + $Owner)
        if ($new -ne $text) {
            $changed++
            if (-not $DryRun) { [System.IO.File]::WriteAllText($f.FullName, $new, $utf8) }
        }
    }
    Ok ("links updated for " + $Slug + " in " + $changed + " file(s)")
} else {
    Ok "links already point to $Slug"
}

# 4. Local git repository ---------------------------------------------------
Say "4/9  Committing"
if (-not (Test-Path ".git")) {
    $null = Run @("git", "init")
    $null = Run @("git", "symbolic-ref", "HEAD", "refs/heads/main")
}
$email = (Probe @("git", "config", "user.email")).Out
if (-not $email) {
    $id = (Probe @("gh", "api", "user", "--jq", ".id")).Out
    $null = Run @("git", "config", "user.name", $login)
    $null = Run @("git", "config", "user.email", ($id + "+" + $login + "@users.noreply.github.com"))
}
$null = Run @("git", "add", "-A")
$pending = (Probe @("git", "status", "--porcelain")).Out
if ($pending -or $DryRun) {
    $hasHead = (Probe @("git", "rev-parse", "--verify", "HEAD")).Code -eq 0
    $msg = "chore: update Queryopsy"
    if (-not $hasHead) { $msg = "feat: Queryopsy $Tag - zero-server SQL forensics simulator" }
    if ((Run @("git", "commit", "-m", $msg)) -ne 0) { Fail "git commit failed." }
} else {
    Ok "nothing new to commit"
}
$null = Run @("git", "branch", "-M", "main")

# 5. Repository on GitHub ---------------------------------------------------
Say "5/9  Creating the GitHub repository"
$exists = (Probe @("gh", "repo", "view", $Slug, "--json", "name")).Code -eq 0
if ($exists) {
    Ok "repository already exists - reusing it"
} else {
    if ((Run @("gh", "repo", "create", $Slug, "--$Visibility", "--description", $Description, "--homepage", $PagesUrl, "--disable-wiki")) -ne 0) { Fail "gh repo create failed." }
}
$remoteUrl = "https://github.com/$Slug.git"
$current = (Probe @("git", "remote", "get-url", "origin")).Out
if (-not $current) { $null = Run @("git", "remote", "add", "origin", $remoteUrl) }
elseif ($current -ne $remoteUrl) { $null = Run @("git", "remote", "set-url", "origin", $remoteUrl) }
if ((Run @("git", "push", "-u", "origin", "main")) -ne 0) {
    Fail "git push failed. If GitHub mentions 'workflow' scope run: gh auth refresh -s workflow   then re-run this script."
}
Ok "pushed main"

# 6. Settings, topics and security features ----------------------------------
Say "6/9  Configuring the repository"
$editArgs = @("gh", "repo", "edit", $Slug, "--description", $Description, "--homepage", $PagesUrl,
              "--enable-issues", "--enable-discussions", "--enable-wiki=false", "--delete-branch-on-merge")
foreach ($t in $Topics) { $editArgs += @("--add-topic", $t) }
if ((Run $editArgs) -ne 0) { Warn "gh repo edit reported a problem (settings may be partly applied)." } else { Ok "description, homepage, topics, issues, discussions on, wiki off" }
$null = Run @("gh", "api", "-X", "PUT", "repos/$Slug/vulnerability-alerts", "--silent")
$null = Run @("gh", "api", "-X", "PUT", "repos/$Slug/automated-security-fixes", "--silent")
$null = Run @("gh", "api", "-X", "PUT", "repos/$Slug/private-vulnerability-reporting", "--silent")
Ok "Dependabot alerts, security updates and private vulnerability reporting requested"

# 7. Labels ----------------------------------------------------------------
Say "7/9  Labels"
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
Say "8/9  GitHub Pages"
$pagesInfo = Probe @("gh", "api", "repos/$Slug/pages")
if ($pagesInfo.Code -eq 0) {
    $null = Run @("gh", "api", "-X", "PUT", "repos/$Slug/pages", "-f", "build_type=workflow", "--silent")
    Ok "Pages already enabled - source set to GitHub Actions"
} else {
    if ((Run @("gh", "api", "-X", "POST", "repos/$Slug/pages", "-f", "build_type=workflow", "--silent")) -eq 0) { Ok "Pages enabled (source: GitHub Actions)" }
    else { Warn "Could not enable Pages automatically. Open Settings > Pages and choose 'GitHub Actions'." }
}
$dispatched = $false
for ($i = 0; $i -lt 6 -and -not $dispatched; $i++) {
    if ((Run @("gh", "workflow", "run", "pages.yml", "--repo", $Slug, "--ref", "main")) -eq 0) { $dispatched = $true }
    elseif (-not $DryRun) { Start-Sleep -Seconds 5 }
}
if ($dispatched) { Ok "Pages deployment started (takes about 1-2 minutes)" } else { Warn "Start it later from the Actions tab: 'Deploy to GitHub Pages' > Run workflow." }

# 9. Release ---------------------------------------------------------------
Say "9/9  Release $Tag"
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
Write-Host ("  Live site  : " + $PagesUrl + "   (live after the Pages workflow finishes)")
Write-Host ("  Release    : https://github.com/" + $Slug + "/releases/tag/" + $Tag)
Write-Host ("  Actions    : https://github.com/" + $Slug + "/actions")
Write-Host ""
