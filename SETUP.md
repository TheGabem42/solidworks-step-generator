# Using a compatible SOLIDWORKS machine

The scripts are prepared, but their successful export and hidden-component behavior still require integration testing with a compatible SOLIDWORKS installation. The installed 2025 reader rejected all supplied native files. Use desktop SOLIDWORKS 2026 or newer for these samples, with a license that permits opening them and an interactive Windows desktop session.

## Windows only

1. Extract `STEP Exporter.zip` into your project folder. Keep the `exporter` directory beside the launchers.
2. Install and activate compatible SOLIDWORKS, launch it once, and finish any first-run dialogs. Close any open documents.
3. Place the native parts and assemblies beside `Export STEP (Windows).cmd`, or in subfolders. Keep all assembly references available. Pack and Go is useful when moving a project between machines.
4. Double-click `Export STEP (Windows).cmd`.

Results belong in `STEP exports` in that project folder. `export-report.json` records each success/failure and excluded assembly components. Separate files are created for every discovered part and assembly. Failed conversions leave older successful exports in place, so check the current report.

## Mac with a separate Windows machine

Use one project folder on a file share accessible by both computers. The Mac still uses the folder containing its launcher, without a folder picker.

1. Extract the bundle into that shared project folder. Install Python 3.10 or newer on the Mac if `python3` is unavailable.
2. On Windows, complete the SOLIDWORKS setup above, then double-click `Start Mac Worker (Windows).cmd` from the shared project folder. Leave its terminal and interactive Windows session running. It creates `.step-export-queue` beside the launchers.
3. On the Mac, mount that same share, put the native files into the shared project folder, and double-click `Export STEP (Mac).command` there.

The Mac detects the worker's queue automatically, submits the native models, and copies the successful results into the project's `STEP exports` folder. No Parallels installation is needed for this shared-folder mode. The worker must be running before the Mac launcher starts. Assembly references must be inside the submitted folder tree; files that exist only at old absolute paths on another computer are not included.

If the Mac project must remain in a separate local folder, put a `step-export-settings.json` beside its launcher with the mounted queue path, for example:

```json
{"queue": "/Volumes/CADShare/STEP project/.step-export-queue"}
```

This is a one-time setting. It does not introduce a folder prompt.

## Mac with Parallels

Install compatible SOLIDWORKS in the Windows VM, enable Parallels home-folder sharing, and keep the project under the Mac home folder. With Python 3.10+ available, double-click `Export STEP (Mac).command`. If there is no configured shared worker, the launcher starts the single Windows VM automatically.

When multiple Windows VMs exist, select one once in `step-export-settings.json`:

```json
{"vm": "Windows 11"}
```

## Remaining acceptance checks

Before relying on exports, run the supplied native models with the compatible reader and compare the generated files against the reference STEPs using `exporter/geometry_check.py`. Also verify a real assembly with hidden, suppressed, repeated, and nested components. The existing workflow and comparator tests do not establish that the native exporter passes these checks.
