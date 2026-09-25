# Run on an interactive Windows desktop, not as a service or SSH session.
[CmdletBinding()]
param([string]$Queue)
$ErrorActionPreference = 'Stop'
if (-not $Queue) { $Queue = Join-Path (Split-Path $PSScriptRoot -Parent) '.step-export-queue' }
New-Item -ItemType Directory -Path $Queue -Force | Out-Null
$Queue = (Resolve-Path -LiteralPath $Queue).Path
$workerLock = [IO.File]::Open((Join-Path $Queue '.worker.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
try {
    Write-Host "Watching $Queue. Leave this window open. Press Ctrl+C to stop."
    while ($true) {
        [IO.File]::WriteAllText((Join-Path $Queue 'worker-heartbeat.txt'), [DateTime]::UtcNow.ToString('o'))
        foreach ($job in Get-ChildItem -LiteralPath $Queue -Directory -Filter 'job-*') {
            if (-not (Test-Path -LiteralPath (Join-Path $job.FullName 'ready'))) { continue }
            if (Test-Path -LiteralPath (Join-Path $job.FullName 'finished.json')) { continue }
            # Interrupted jobs are retained for inspection; never silently run twice.
            if (Test-Path -LiteralPath (Join-Path $job.FullName 'running')) { continue }
            New-Item -ItemType File -Path (Join-Path $job.FullName 'running') | Out-Null
            $work = Join-Path $env:TEMP ('step-export-' + [guid]::NewGuid().ToString('N'))
            $code = 1
            try {
                New-Item -ItemType Directory -Path $work | Out-Null
                # Only source CAD models are accepted, never scripts from the share.
                Add-Type -AssemblyName System.IO.Compression.FileSystem
                $archive = [IO.Compression.ZipFile]::OpenRead((Join-Path $job.FullName 'input.zip'))
                try {
                    foreach ($entry in $archive.Entries) {
                        $target = [IO.Path]::GetFullPath((Join-Path $work $entry.FullName))
                        if (-not $target.StartsWith($work + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid ZIP path.' }
                        if ([IO.Path]::GetExtension($target).ToLowerInvariant() -notin @('.sldprt', '.sldasm')) { throw 'Only SLDPRT/SLDASM files are accepted.' }
                        New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
                        [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $false)
                    }
                } finally { $archive.Dispose() }
                & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'Export-SolidWorks.ps1') -Root $work *> (Join-Path $job.FullName 'worker.log')
                $code = $LASTEXITCODE
                $result = Join-Path $work 'STEP exports'
                if (Test-Path -LiteralPath $result) {
                    Copy-Item -LiteralPath $result -Destination (Join-Path $job.FullName 'result') -Recurse
                }
            } catch {
                $_ | Out-String | Add-Content -LiteralPath (Join-Path $job.FullName 'worker.log')
            } finally {
                @{exitCode=$code} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $job.FullName 'finished.tmp') -Encoding UTF8
                Move-Item -LiteralPath (Join-Path $job.FullName 'finished.tmp') -Destination (Join-Path $job.FullName 'finished.json')
                if (Test-Path -LiteralPath $work) { Remove-Item -LiteralPath $work -Recurse -Force }
            }
            Write-Host "Completed $($job.Name) (exit $code)"
        }
        Start-Sleep -Seconds 2
    }
} finally {
    Remove-Item -LiteralPath (Join-Path $Queue 'worker-heartbeat.txt') -ErrorAction SilentlyContinue
    $workerLock.Dispose()
}
