param(
    [string]$ZapApiBase = "http://localhost:8090",
    [string]$TargetBase = "http://nginx:80",
    [string]$WordlistDir = ".\security\wordlists",
    [string]$ReportDir = ".\security\reports",
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$correlationId = "sec-scan-$timestamp"
$reportPath = Join-Path $ReportDir "zap_paths_$timestamp.json"

if (-not (Test-Path -LiteralPath $WordlistDir)) {
    throw "Wordlist directory not found: $WordlistDir"
}

if (-not (Test-Path -LiteralPath $ReportDir)) {
    New-Item -ItemType Directory -Path $ReportDir | Out-Null
}

$wordlistFiles = Get-ChildItem -Path $WordlistDir -File
if ($wordlistFiles.Count -eq 0) {
    throw "No wordlist files found in: $WordlistDir"
}

$allLines = foreach ($file in $wordlistFiles) {
    Get-Content -LiteralPath $file.FullName
}

$paths = $allLines |
    Where-Object { $_ -and -not $_.StartsWith("#") } |
    ForEach-Object { $_.Trim().TrimStart('/') } |
    Where-Object { $_ -ne "" } |
    Select-Object -Unique

if ($paths.Count -eq 0) {
    throw "No valid paths found after filtering all wordlist files."
}

Write-Host "Preparing OWASP ZAP path enumeration against $TargetBase"
Write-Host "Wordlist files: $($wordlistFiles.Count)"
Write-Host "Correlation-ID: $correlationId"

# Wait for ZAP API readiness to avoid startup race conditions in automated runs.
$zapDeadline = (Get-Date).AddSeconds(90)
$zapReady = $false
while ((Get-Date) -lt $zapDeadline) {
    try {
        $null = Invoke-RestMethod -Method Get -Uri "$ZapApiBase/JSON/core/view/version/"
        $zapReady = $true
        break
    } catch {
        Start-Sleep -Milliseconds 500
    }
}

if (-not $zapReady) {
    throw "Timed out waiting for ZAP API readiness at $ZapApiBase"
}

# Remove and re-add a deterministic replacer rule to avoid duplicate rule buildup.
try {
    Invoke-RestMethod -Method Get -Uri "$ZapApiBase/JSON/replacer/action/removeRule/?description=scan-cid"
} catch {
    # Ignore if rule does not exist yet.
}

Invoke-RestMethod -Method Get -Uri "$ZapApiBase/JSON/replacer/action/addRule/?description=scan-cid&enabled=true&matchType=REQ_HEADER&matchRegex=false&matchString=Correlation-ID&replacement=$correlationId" | Out-Null

$before = [int](Invoke-RestMethod -Method Get -Uri "$ZapApiBase/JSON/core/view/numberOfMessages/").numberOfMessages

foreach ($path in $paths) {
    $url = "$TargetBase/$path"
    $encodedUrl = [System.Uri]::EscapeDataString($url)
    Invoke-RestMethod -Method Get -Uri "$ZapApiBase/JSON/core/action/accessUrl/?url=$encodedUrl&followRedirects=true" | Out-Null
}

$expected = $before + $paths.Count
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$current = $before

while ($current -lt $expected -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 500
    $current = [int](Invoke-RestMethod -Method Get -Uri "$ZapApiBase/JSON/core/view/numberOfMessages/").numberOfMessages
}

$seenUrls = (Invoke-RestMethod -Method Get -Uri "$ZapApiBase/JSON/core/view/urls/").urls |
    Where-Object { $_ -like "$TargetBase/*" } |
    Select-Object -Unique

$discoveredPaths = $seenUrls |
    ForEach-Object {
        try {
            ([Uri]$_).AbsolutePath
        } catch {
            $null
        }
    } |
    Where-Object { $_ } |
    Select-Object -Unique

$report = [ordered]@{
    generated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    target = $TargetBase
    correlation_id = $correlationId
    wordlist_directory = $WordlistDir
    wordlist_files = $wordlistFiles.FullName
    wordlist_file_count = $wordlistFiles.Count
    attempted_path_count = $paths.Count
    zap_message_count_before = $before
    zap_message_count_after = $current
    discovered_path_count = $discoveredPaths.Count
    discovered_paths = $discoveredPaths
}

$json = $report | ConvertTo-Json -Depth 5
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($reportPath, $json, $utf8NoBom)

Write-Host "Report: $reportPath"
Write-Host "Correlation-ID: $correlationId"
