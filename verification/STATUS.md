# Verification status — 2026-09-25

**The requested end state is not yet achieved.** The launchers no longer ask for folders, but successful conversion and geometric accuracy of the supplied native models remain unverified.

| Requirement | Evidence | Status |
|---|---|---|
| Drop up to three files beside launcher; use that folder | Python three-file discovery test; executed PowerShell three-file inventory; launcher paths derived from their own locations | Folder handling passes |
| Outputs in local STEP exports | Implementation and result-copy tests | Conversion path not yet successful on native inputs |
| Windows and Mac launch | PowerShell compiled C# against installed interfaces; Mac invoked it in Parallels | Invocation works; conversion is version-blocked |
| Convert supplied native files | Native run report: all 26 return swFutureVersion / 8192 on installed SW 33.4.1 | Blocked by installed reader version |
| Accurate exported geometry | Six geometry comparator tests pass; 12 reference files inspected | No new native exports available to compare |
| Hidden assembly components excluded, parts exported independently | C# implementation; no successful native assembly integration fixture | Unverified |
| Preserve originals | Before/after SHA-256 for 38 native and reference files | Pass |

The failed experimental STEP-to-native fixture import returned COM E_FAIL and produced no native fixture files. It is not counted as a passing test. The old PowerShell visibility mocks were removed when the implementation changed to typed C#; their previous pass is not current evidence.

Artifacts:

- `python-tests.log`: 12 passing workflow tests; FreeCAD class skipped in incompatible system Python.
- `geometry-tests.log`: the six FreeCAD tests run separately and passed.
- `powershell-tests.log`: syntax and three-file inventory pass.
- `native-export-report.json`: per-source errors from the actual SolidWorks run.
- `native-export-run.log`: raw native run output.
- `reference-geometry.json`: reference metrics and validity flags.
- `source-integrity.json`: unchanged original files.

`Tolomatic + plate.STEP` has 15 solids and fails FreeCAD/OpenCascade's B-rep validity test. The remaining 11 references pass that kernel's validity check. This describes the reference inputs, not newly generated output accuracy.

The user's Bambu fork was inspected: it reads saved display triangles and explicitly excludes assemblies and exact surfaces. cadmpeg 0.6.0 was also tried locally on three supplied parts and one assembly. It wrote three diagnostic STEP files and refused one input; none passed geometric verification. See `BACKEND-EVALUATION.md` and `cadmpeg/geometry-comparison.json`. These failed trial outputs are not deliverable exports.

The selected fallback remains compatible SOLIDWORKS on Windows, accessible directly, through Parallels, or through the shared-folder worker. `../SETUP.md` documents setup. No commercial translator license has been obtained, no account has been created, and no files have been uploaded to an online converter.
