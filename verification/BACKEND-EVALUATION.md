# Free standalone backend evaluation — 2026-09-25

**No tested free standalone backend meets the complete task.** This is a conclusion about the implementations inspected and tested, not proof that every possible converter is unsuitable.

## Bambu fork

Inspected the user's adjacent `bambu fork/BambuStudio` project, specifically:

- `SLDPRT_SUPPORT.md`
- `src/libslic3r/Format/SLDPRTReader.hpp`
- `src/libslic3r/Format/SLDPRTReader.cpp`
- `src/libslic3r/Format/SLDPRT.cpp`

The reader inflates `Contents/DisplayLists` and returns floating-point vertices and triangle indices. It imports saved display tessellation, whose curve resolution is determined when SolidWorks saves the source. Its own support documentation explicitly excludes assemblies and exact Parasolid surfaces. This explains its cross-platform import capability, but it cannot provide equivalent exact STEP geometry or assembly occurrence/visibility handling. No changes were made to the Bambu project.

## cadmpeg 0.6.0

Downloaded the official macOS ARM64 release and checked its published SHA-256:

`6731f9da45572430311346777c87d9f2143a4156aad30b884571b98b2c615f1a`

Release: <https://github.com/cadmpeg/cadmpeg/releases/tag/v0.6.0>

Support profile: <https://github.com/cadmpeg/cadmpeg/blob/main/docs/format-support.md>

Executed the normal `convert SOURCE -o OUTPUT --report REPORT` command locally, without `--allow-errors` or `--allow-empty`, on three supplied parts and one assembly. Geometry was then read and compared with the existing FreeCAD/OpenCascade checker.

| Input | Result |
| --- | --- |
| Throttle coupling.SLDPRT | Command returned success, but output B-rep is invalid: 5 faces versus 75 in the valid reference. Volume also differs. |
| throttle mount.SLDPRT | Command returned success, but output B-rep is invalid and contains zero solids; reference contains one valid solid. |
| Actuator Base.SLDPRT | Converter refused export after four internal reference errors. No STEP written. |
| New/Tolomatic + plate.SLDASM | Command returned success through its part decoder, but output has one solid and 11 faces versus 15 solids and 4,282 faces in the reference. Assembly product structure is unsupported. The reference also fails B-rep validity, so it cannot establish an exact match even with a complete output. |

**Zero of four trial inputs passed verification.** A process exit code of zero was not sufficient evidence of accurate conversion. The logs explicitly record omitted geometry/topology in some nominally successful exports. The three diagnostic STEP files stay under `verification/cadmpeg`, outside the deliverable exports and the distribution ZIP.

Evidence: `cadmpeg/summary.json`, `cadmpeg/*.log`, `cadmpeg/*.report.json`, `cadmpeg/pairs.json`, and `cadmpeg/geometry-comparison.json`.

## Selected fallback

Retain the existing SOLIDWORKS backend and obtain access to a compatible Windows installation. The current local 2025 installation rejects the supplied files as future-version documents. A compatible installation is an outstanding external dependency, and successful native export, output/reference geometry checks, and hidden-component integration checks remain unfinished.

No CAD files were uploaded to an external service. No commercial license was purchased and no accounts were created.
