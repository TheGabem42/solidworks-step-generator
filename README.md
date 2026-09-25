# Folder → STEP exporter

Put your `.SLDPRT` / `.SLDASM` files beside the launcher and double-click it. Output belongs in **STEP exports** in that same folder. **No folder picker is used.** Subfolders are scanned as well; the supplied `sample step files` and the development `verification` folders are excluded from normal runs. There is no artificial three-file limit.

## Current status

The folder workflow and verification tools are implemented. **Conversion of the supplied models is not working with the software currently installed.** A real run in the local Windows VM found SOLIDWORKS 2025 (revision 33.4.1), which rejected all 26 supplied native models with `swFutureVersion` (8192). Those models need a newer reader.

The preferred free standalone route has now been investigated, including your Bambu importer and a real trial of cadmpeg 0.6.0. The Bambu code reads saved display triangles and does not support assemblies or exact CAD surfaces. cadmpeg generated incomplete/invalid geometry on the supplied examples; none of the four trial conversions passed verification. It is not used by these launchers. See [the evaluation](verification/BACKEND-EVALUATION.md).

The practical fallback is compatible desktop SOLIDWORKS on Windows, either locally, in Parallels, or on a shared Windows machine used by the Mac launcher. See [SETUP.md](SETUP.md). The current SW 2025 installation must be upgraded or replaced with a compatible reader before the supplied examples can be verified. CAD Exchanger and HOOPS Exchange remain commercial alternatives; neither is bundled. No CAD files have been uploaded to a conversion service.

## Current launchers (SOLIDWORKS backend)

- **Windows:** double-click `Export STEP (Windows).cmd`. Requires compatible, licensed desktop SOLIDWORKS and the accompanying `exporter` directory.
- **Mac:** double-click `Export STEP (Mac).command`. Requires Python 3.10+ and a Parallels Windows VM containing compatible SOLIDWORKS. It identifies the single Windows VM automatically, starts it if needed, and uses the project folder through Parallels home-folder sharing. It does not ask you for a folder.
- If multiple Windows VMs exist, an optional `step-export-settings.json` can specify `{"vm": "Windows 11"}`.
- SOLIDWORKS may be running with no documents open. The exporter refuses a session containing open documents because temporary visibility changes must be discarded safely. Close documents before a batch and do not work in that session during conversion.

The Windows 2025 installation here cannot convert the supplied 2026 models. The launcher reports this instead of producing incomplete geometry.

An older shared-folder worker remains available for a separate Windows computer. `Start Mac Worker (Windows).cmd` uses `.step-export-queue` beside itself without prompting. A Mac can use the same project/queue on a mounted share, or an optional settings file containing `{"queue": "/Volumes/share/.step-export-queue"}`. The usual Parallels path does not require this worker.

## Files and visibility

- One STEP AP214 file per discovered native part or assembly, preserving subfolders.
- `Base.SLDPRT` becomes `STEP exports/Base.SLDPRT.step`. The native extension distinguishes a part and assembly sharing a name.
- Uses the source's last-saved configuration/display state.
- Hidden assembly occurrences and hidden subassembly trees are suppressed in memory before export; already suppressed components stay excluded.
- Every discovered part is exported independently even if one of its assembly occurrences is hidden.
- If excluding a hidden occurrence also suppresses a visible occurrence through a shared configuration, export fails instead of silently losing geometry.
- Sources are read-only and never saved. Temporary changes are discarded; changed export preferences are restored.
- Existing good exports are replaced only after conversion succeeds. A failed rerun leaves the previous file in place; consult the current report before treating it as current.
- Assemblies need their referenced part files. Dropping an assembly alone does not manufacture missing source geometry. Keep references available with their folder structure, or use Pack and Go.
- Virtual components appear within an assembly but need to be saved as individual native files for separate exports. Individual hidden bodies inside a part follow the translator's behavior; the explicit filter handles assembly components.

## Verification

See `verification/STATUS.md` and its JSON/log files for the current evidence.

Executed checks:

- 12 Python tests passed for discovery, packaging, result handling, VM selection and paths.
- 6 FreeCAD/OpenCascade geometry tests passed, including a moved hole with equal volume and bounds, wrong scale, displaced instances and missing duplicate instances.
- PowerShell parsing and a real three-file inventory test passed.
- All 12 reference STEP files were measured with FreeCAD. Eleven pass its B-rep validity test; `Tolomatic + plate.STEP` fails. A validity failure does not by itself prove that the entire reference shape is wrong.
- All 26 native sample files were attempted in SOLIDWORKS 2025 and rejected as newer-version files. A separate cadmpeg trial on three parts and one assembly produced three STEP files and one refusal, with zero passing geometry comparisons. **No accurate conversion of these models or native assembly-visibility integration test has been established.**
- SHA-256 checks confirmed all 38 original CAD/reference files remained unchanged.

The geometry comparator matches individual solids with instance counts, placement, bounds, volume, area, and bidirectional Boolean subtraction. A STEP header check alone is not proof of geometric accuracy. Surface-only and mixed solid/surface comparisons are explicitly unsupported by this verifier.

Developer checks:

```sh
python3 -m unittest discover -s tests -v
pwsh -NoProfile -File tests/test_powershell.ps1
/Applications/FreeCAD.app/Contents/Resources/bin/python -m unittest discover -s tests -p test_geometry.py -v
```

The regular Python run skips the FreeCAD tests when its Python ABI differs; run the geometry suite with FreeCAD's bundled Python as shown above.

Inspect reference files:

```sh
/Applications/FreeCAD.app/Contents/Resources/bin/python exporter/geometry_check.py --reference-dir "sample step files/Steps" --output verification/reference-geometry.json
```

Compare outputs after a working converter is available with `geometry_check.py --pairs pairs.json --output report.json`. Each JSON pair has `reference` and `actual` paths relative to the pair-list file. Missing outputs fail verification.

## Alternative engine investigation

- Your Bambu fork's `SLDPRT_SUPPORT.md` and `SLDPRTReader.hpp` identify its output as saved display tessellation. It cannot recover exact curved CAD surfaces or handle assembly instances/visibility.
- [cadmpeg's support profile](https://github.com/cadmpeg/cadmpeg/blob/main/docs/format-support.md) describes partial SolidWorks geometry and no product structure. The 0.6.0 macOS ARM64 release was checksum-verified and tried locally. Generated STEP files are retained only under `verification/cadmpeg` as failed diagnostic outputs, never under `STEP exports`.
- [CAD Exchanger SDK](https://cadexchanger.com/products/sdk/) explicitly supports reading SOLIDWORKS on macOS without a CAD application; [Lab](https://cadexchanger.com/products/gui/) offers Mac/Windows viewing and conversion. Its current SDK/API/license package must be obtained before implementation and testing. Recent reseller release notes report 2026 support; that version and hidden-component handling still require direct validation.
- [HOOPS Exchange 2026.1.1](https://docs.techsoft3d.com/hoops/exchange/release_notes/2026.1.1.html) explicitly added SOLIDWORKS 2026 support. [Setup](https://docs.techsoft3d.com/hoops/exchange/tutorials/c/environment-setup.html) requires a vendor account, SDK package and valid license. Evaluation licenses expire.

Neither alternative has been represented as a working or verified backend yet.
