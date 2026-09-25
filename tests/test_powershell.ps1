$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
foreach ($file in Get-ChildItem (Join-Path $project 'exporter') -Filter '*.ps1') {
    $tokens=$null; $issues=$null
    [System.Management.Automation.Language.Parser]::ParseFile($file.FullName,[ref]$tokens,[ref]$issues) > $null
    if($issues.Count) { throw ($issues | Out-String) }
}
$fixture=Join-Path ([IO.Path]::GetTempPath()) ('step-test-'+[guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path $fixture | Out-Null
    foreach($name in @('One.SLDPRT','Two.SLDPRT','All.SLDASM')) { [IO.File]::WriteAllText((Join-Path $fixture $name),'test inventory only') }
    foreach($folder in @('STEP exports','sample step files','.step-export-queue')) {
        $path=Join-Path $fixture $folder
        New-Item -ItemType Directory -Path $path | Out-Null
        [IO.File]::WriteAllText((Join-Path $path 'Ignored.SLDPRT'),'test inventory only')
    }
    $shell=(Get-Process -Id $PID).Path
    $actual=@(& $shell -NoProfile -File (Join-Path $project 'exporter/Export-SolidWorks.ps1') -Root $fixture -InventoryOnly)
    if($LASTEXITCODE -ne 0 -or $actual.Count -ne 3) { throw "Three-file inventory failed: $actual" }
    if(@(Compare-Object ($actual | Sort-Object) @('All.SLDASM','One.SLDPRT','Two.SLDPRT')).Count) { throw 'Wrong files selected.' }
    'PowerShell syntax and three-file inventory tests passed.'
} finally { Remove-Item -LiteralPath $fixture -Recurse -Force }
