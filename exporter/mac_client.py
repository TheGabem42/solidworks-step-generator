"""Submit local models to an interactive Windows SOLIDWORKS worker via a share."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import zipfile

SKIP = {'step exports', '.git', '.step-export-queue'}

def models(root: Path):
    for directory, folders, names in os.walk(root, followlinks=False):
        folders[:] = sorted(n for n in folders if n.casefold() not in SKIP
                            and not (Path(directory) / n).is_symlink()
                            and not (Path(directory) == root and n in {'sample step files', 'verification'}))
        for name in sorted(names):
            path = Path(directory) / name
            if (path.suffix.lower() in {'.sldprt', '.sldasm'}
                    and not name.startswith('~$') and not path.is_symlink()):
                yield path


def make_package(root: Path, target: Path):
    paths = list(models(root))
    if not paths:
        raise RuntimeError('No SLDPRT or SLDASM files found.')
    # A case-sensitive Mac disk can hold files a Windows disk cannot distinguish.
    seen = set()
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            relative = path.relative_to(root).as_posix()
            key = relative.casefold()
            if key in seen:
                raise RuntimeError(f'Windows filename collision: {relative}')
            if any(any(c in piece for c in '<>:"\\|?*') or piece.endswith((' ', '.'))
                   for piece in path.relative_to(root).parts):
                raise RuntimeError(f'Filename is not compatible with Windows: {relative}')
            seen.add(key)
            archive.write(path, relative)
    (target.parent / 'manifest.json').write_text(json.dumps([p.relative_to(root).as_posix() for p in paths]))
    return len(paths)


def import_results(job: Path, root: Path):
    report_path = job / 'result' / 'export-report.json'
    if not report_path.is_file():
        log = job / 'worker.log'
        if log.exists():
            data = log.read_bytes()
            encoding = 'utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
            raise RuntimeError(data.decode(encoding, errors='replace'))
        raise RuntimeError('Worker produced no report.')
    rows = json.loads(report_path.read_text(encoding='utf-8-sig'))
    if isinstance(rows, dict):
        rows = [rows]
    manifest = job / 'manifest.json'
    if manifest.exists():
        expected = json.loads(manifest.read_text())
        received = {row['source'].replace('\\', '/') for row in rows}
        for source in expected:
            if source not in received:
                rows.append({'source': source, 'status': 'failed',
                             'message': 'Worker stopped before processing this model.'})
    if not rows:
        raise RuntimeError('Worker returned an empty report.')
    output = root / 'STEP exports'
    output.mkdir(exist_ok=True)
    for row in rows:
        relative = Path(row['source'].replace('\\', '/'))
        if relative.is_absolute() or '..' in relative.parts:
            raise RuntimeError('Worker report contains an invalid source path.')
        target = output / (str(relative) + '.step')
        if row['status'] == 'exported':
            source = job / 'result' / (str(relative) + '.step')
            target.parent.mkdir(parents=True, exist_ok=True)
            # Copy beside destination, then atomically replace the old success.
            temp = target.with_name('.' + target.name + '.' + uuid.uuid4().hex)
            try:
                import shutil
                shutil.copyfile(source, temp)
                os.replace(temp, target)
            finally:
                temp.unlink(missing_ok=True)
        row['output'] = str(target)
    (output / 'export-report.json').write_text(json.dumps(rows, indent=2) + '\n')
    return rows


def configured_queue(root: Path):
    config = root / 'step-export-settings.json'
    if config.exists():
        queue = json.loads(config.read_text()).get('queue')
        if queue:
            path = Path(queue).expanduser()
            if not path.is_absolute():
                path = root / path
            if not path.is_dir():
                raise RuntimeError(f'Shared folder unavailable: {path}')
            return path
    local_queue = root / '.step-export-queue'
    if (local_queue / 'worker-heartbeat.txt').is_file():
        return local_queue
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--queue', type=Path)
    parser.add_argument('--inventory', action='store_true')
    parser.add_argument('--retrieve', type=Path, help='Retrieve a completed shared-folder job')
    parser.add_argument('--timeout', type=float, default=7200)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.inventory:
        paths = list(models(root))
        for path in paths:
            print(path.relative_to(root))
        print(f'{len(paths)} models')
        return 0
    if args.retrieve:
        rows = import_results(args.retrieve, root)
        return 1 if any(row['status'] != 'exported' for row in rows) else 0
    if not list(models(root)):
        print('No SLDPRT or SLDASM files found beside the launcher or in its subfolders.')
        return 0
    queue = args.queue or configured_queue(root)
    if queue is None:
        from parallels import run
        return run(root)
    marker = queue / 'worker-heartbeat.txt'
    if not marker.exists() or time.time() - marker.stat().st_mtime > 120:
        raise RuntimeError('Start "Start Mac Worker (Windows).cmd" on the Windows desktop first, using this same shared folder. The worker is offline or busy.')
    job = queue / ('job-' + uuid.uuid4().hex)
    job.mkdir()
    count = make_package(root, job / 'input.zip')
    (job / 'ready').touch()  # Publish only after ZIP is closed.
    print(f'Submitted {count} models. Job: {job.name}', flush=True)
    print('Leave the Windows worker running. Waiting for STEP exports…', flush=True)
    started = time.monotonic()
    next_notice = started + 60
    while not (job / 'finished.json').exists():
        if time.monotonic() - started > args.timeout:
            raise RuntimeError(f'Timed out; the job remains at {job}. It may still be running. Retrieve later with --retrieve followed by the job path.')
        if time.monotonic() >= next_notice:
            print('Still waiting for Windows conversion…', flush=True)
            next_notice += 60
        time.sleep(2)
    rows = import_results(job, root)
    failed = sum(row['status'] != 'exported' for row in rows)
    for row in rows:
        print(f"{row['status'].upper()}: {row['source']} — {row['message']}")
    print(f'Finished: {len(rows) - failed} exported, {failed} failed. See STEP exports/export-report.json.')
    print(f'Job retained in the shared folder: {job.name}')
    return 1 if failed else 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (Exception, KeyboardInterrupt) as exc:
        print(f'Export stopped: {exc}', file=sys.stderr)
        sys.exit(1)
