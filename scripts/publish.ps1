param(
    [string]$RemoteUrl = "https://github.com/fishman7337/sp-daaa-pai-ca2-gobest-trip-safety-predictor.git"
)

$ErrorActionPreference = "Stop"

if (-not (git rev-parse --is-inside-work-tree 2>$null)) {
    throw "Run this script from the repository root."
}

if (-not (git remote get-url origin 2>$null)) {
    git remote add origin $RemoteUrl
} else {
    git remote set-url origin $RemoteUrl
}

git status --short --branch
git push -u origin main
git push origin v0.1.0
