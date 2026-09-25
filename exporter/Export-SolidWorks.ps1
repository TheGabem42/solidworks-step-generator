# Requires Windows PowerShell 5.1 and licensed desktop SOLIDWORKS.
[CmdletBinding()]
param([string]$Root = (Split-Path $PSScriptRoot -Parent), [switch]$InventoryOnly)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = [IO.Path]::GetFullPath($Root).TrimEnd([IO.Path]::DirectorySeparatorChar)
$outputRoot = Join-Path $Root 'STEP exports'

function Get-Models([string]$Folder) {
    foreach ($entry in Get-ChildItem -LiteralPath $Folder -Force) {
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
        if ($entry.PSIsContainer) {
            if ($entry.Name -notin @('STEP exports', '.git', '.step-export-queue') -and $entry.FullName -notin @((Join-Path $Root 'sample step files'), (Join-Path $Root 'verification'))) {
                Get-Models $entry.FullName
            }
        } elseif ($entry.Extension.ToLowerInvariant() -in @('.sldprt', '.sldasm')) {
            if (-not $entry.Name.StartsWith('~$')) { $entry }
        }
    }
}
$models = @(Get-Models $Root | Sort-Object FullName)
if ($InventoryOnly) {
    $models | ForEach-Object { $_.FullName.Substring($Root.Length + 1) }
    exit 0
}
if (-not $models.Count) { Write-Output 'No SLDPRT or SLDASM files found.'; exit 0 }

# Use the installed enumeration assembly, never guessed preference numbers.
$progID = [Microsoft.Win32.Registry]::ClassesRoot.OpenSubKey('SldWorks.Application\CLSID')
if (-not $progID) { throw 'Desktop SOLIDWORKS is not installed. Use SOLIDWORKS 2026 or newer for the supplied examples.' }
$clsid = $progID.GetValue(''); $progID.Close()
$serverKey = [Microsoft.Win32.Registry]::ClassesRoot.OpenSubKey("CLSID\$clsid\LocalServer32")
$server = [string]$serverKey.GetValue(''); $serverKey.Close()
if ($server -match '^"([^"]+)"') { $exe = $Matches[1] }
elseif ($server -match '^(.*?\.exe)') { $exe = $Matches[1] }
else { throw "Cannot locate SOLIDWORKS from its registration: $server" }
$dll = Get-ChildItem -LiteralPath (Split-Path $exe) -Filter 'SolidWorks.Interop.swconst.dll' -Recurse | Select-Object -First 1
if (-not $dll) { throw 'Cannot find SolidWorks.Interop.swconst.dll in the SOLIDWORKS installation.' }
Add-Type -Path $dll.FullName
$apiDll = Join-Path $dll.DirectoryName 'SolidWorks.Interop.sldworks.dll'
if (-not (Test-Path -LiteralPath $apiDll)) { throw 'Cannot find SolidWorks.Interop.sldworks.dll beside swconst.dll.' }
Add-Type -Path $apiDll

# Compile against the installed SolidWorks interfaces; avoid late-bound COM.
Add-Type -Path (Join-Path $PSScriptRoot 'SolidWorksEngine.cs') -ReferencedAssemblies @($dll.FullName, $apiDll)
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
$lock = $null; $session = $null
$rows = [Collections.Generic.List[object]]::new()
try {
    $lock = [IO.File]::Open((Join-Path $outputRoot '.export.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    $session = New-Object StepSession
    Write-Output "SOLIDWORKS revision $($session.Revision)"
    $index = 0
    foreach ($file in $models) {
        $index++
        $relative = $file.FullName.Substring($Root.Length + 1)
        $destination = Join-Path $outputRoot ($relative + '.step')
        Write-Output "[$index/$($models.Count)] $relative"
        $row = $session.Export($file.FullName, $destination)
        $row.source = $relative
        $rows.Add($row)
        Write-Output "  $($row.status.ToUpper()): $($row.message)"
        ConvertTo-Json -InputObject $rows.ToArray() -Depth 8 | Set-Content -LiteralPath (Join-Path $outputRoot 'export-report.json') -Encoding UTF8
    }
} finally {
    if ($session) { $session.Dispose() }
    if ($lock) { $lock.Dispose() }
}
$failed = @($rows | Where-Object status -eq 'failed').Count
Write-Output "Finished: $($rows.Count - $failed) exported, $failed failed. See STEP exports\export-report.json."
if ($failed) { exit 1 }
