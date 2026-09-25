"""Run the Windows exporter in a local Parallels VM; never ask for a folder."""
from __future__ import annotations
import base64
import json
from pathlib import Path
import subprocess
import sys

PRLCTL = Path('/Applications/Parallels Desktop.app/Contents/MacOS/prlctl')

def ps_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"

def windows_path(path: Path, home: Path | None = None) -> str:
    home = (home or Path.home()).resolve()
    try:
        relative = path.resolve().relative_to(home)
    except ValueError:
        raise RuntimeError('Place the project folder inside your Mac home folder so Parallels can access it.')
    return '\\\\Mac\\Home\\' + str(relative).replace('/', '\\')

def encoded_command(script: str) -> str:
    return base64.b64encode(script.encode('utf-16-le')).decode('ascii')

def run_powershell(vm: str, script: str, capture=False):
    return subprocess.run([str(PRLCTL), 'exec', vm, '--current-user', 'powershell.exe',
                           '-NoLogo', '-NoProfile', '-OutputFormat', 'Text', '-ExecutionPolicy', 'Bypass',
                           '-EncodedCommand', encoded_command(script)],
                          capture_output=capture, text=True)

def select_vm(config: dict, vms: list[dict]) -> dict:
    wanted = config.get('vm')
    if wanted:
        matches = [v for v in vms if wanted in {v['name'], v['uuid']}]
    else:
        matches = [v for v in vms if 'windows' in v['name'].lower()]
    if len(matches) != 1:
        raise RuntimeError('Could not identify one Windows VM. Set "vm" in step-export-settings.json to its name. No folder selection is needed.')
    return matches[0]

def run(root: Path) -> int:
    if not PRLCTL.is_file():
        raise RuntimeError('Mac conversion requires a Windows VM with SOLIDWORKS and Parallels installed, or a configured Windows worker.')
    config_path = root / 'step-export-settings.json'
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    result = subprocess.run([str(PRLCTL), 'list', '-a', '--json'], capture_output=True, text=True, check=True)
    vm = select_vm(config, json.loads(result.stdout))
    if vm['status'] != 'running':
        print(f"Starting {vm['name']}…", flush=True)
        subprocess.run([str(PRLCTL), 'start', vm['uuid']], check=True)
    root_win = windows_path(root)
    script_win = windows_path(Path(__file__).resolve().parent / 'Export-SolidWorks.ps1')
    script = f"""$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if (-not (Test-Path -LiteralPath {ps_literal(root_win)})) {{ throw 'Enable Parallels sharing of your Mac home folder.' }}
& {ps_literal(script_win)} -Root {ps_literal(root_win)}
exit $LASTEXITCODE
"""
    print(f"Converting in {vm['name']}. Output: {root / 'STEP exports'}", flush=True)
    return run_powershell(vm['uuid'], script).returncode

if __name__ == '__main__':
    try:
        sys.exit(run(Path(__file__).resolve().parent.parent))
    except (Exception, KeyboardInterrupt) as exc:
        print(f'Export stopped: {exc}', file=sys.stderr)
        sys.exit(1)
