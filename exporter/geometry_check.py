"""Measure and compare STEP solids using FreeCAD's OpenCascade B-rep kernel.

Run with the Python bundled in FreeCAD, with its lib directory on sys.path.
This does not read SLDPRT/SLDASM and is not a conversion engine.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys


def load_kernel():
    mac_lib = Path('/Applications/FreeCAD.app/Contents/Resources/lib')
    if mac_lib.is_dir():
        sys.path.insert(0, str(mac_lib))
    import FreeCAD
    import Part
    return FreeCAD, Part


def bounds(shape):
    box = shape.BoundBox
    return [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax]


def metrics(shape):
    return {'valid': bool(shape.isValid()), 'solids': len(shape.Solids),
            'shells': len(shape.Shells), 'faces': len(shape.Faces),
            'volume_mm3': shape.Volume, 'area_mm2': shape.Area,
            'bounds_mm': bounds(shape)}


def close_measure(a, b, absolute, relative=1e-6):
    return abs(a-b) <= max(absolute, relative * max(abs(a), abs(b)))


def compare_shapes(reference, actual, length_tol=1e-4, volume_rel_tol=1e-6):
    """Match solids one-to-one; verify positions, areas and B-rep differences.

    Volume/area/bounds alone do not prove shape equality. Bidirectional solid
    subtraction detects moved holes, changed topology and internal differences.
    Assembly instance multiplicity is retained, including identical instances.
    """
    expected_metrics, actual_metrics = metrics(reference), metrics(actual)
    result = {'reference': expected_metrics, 'actual': actual_metrics,
              'length_tolerance_mm': length_tol, 'volume_relative_tolerance': volume_rel_tol,
              'passed': False, 'solid_checks': []}
    if not expected_metrics['valid'] or not actual_metrics['valid']:
        result['reason'] = 'Invalid B-rep in reference or actual output.'
        return result
    if not reference.Solids or not actual.Solids:
        result['reason'] = 'Solid comparison unavailable for surface-only or empty geometry.'
        return result
    if len(reference.Solids) != len(actual.Solids):
        result['reason'] = 'Solid/instance count differs.'
        return result
    # A mixed model needs surface comparison too: do not silently ignore surfaces.
    if sum(len(s.Faces) for s in reference.Solids) != len(reference.Faces) or sum(len(s.Faces) for s in actual.Solids) != len(actual.Faces):
        result['reason'] = 'Mixed solid/surface model requires additional surface verification.'
        return result
    remaining = list(enumerate(actual.Solids))
    for expected_index, expected in enumerate(reference.Solids):
        matched = None
        for position, (actual_index, candidate) in enumerate(remaining):
            if not all(abs(a-b) <= length_tol for a,b in zip(bounds(expected), bounds(candidate))):
                continue
            if not close_measure(expected.Volume, candidate.Volume, 1e-6, volume_rel_tol):
                continue
            if not close_measure(expected.Area, candidate.Area, 1e-6):
                continue
            try:
                removed = expected.cut(candidate)
                added = candidate.cut(expected)
                if not removed.isValid() or not added.isValid():
                    continue
                missing_volume, extra_volume = abs(removed.Volume), abs(added.Volume)
                tolerance = max(1e-6, volume_rel_tol * max(abs(expected.Volume), abs(candidate.Volume)))
                if missing_volume <= tolerance and extra_volume <= tolerance:
                    matched = position
                    result['solid_checks'].append({'reference_index': expected_index,
                        'actual_index': actual_index, 'missing_volume_mm3': missing_volume,
                        'extra_volume_mm3': extra_volume, 'allowed_difference_mm3': tolerance})
                    break
            except Exception:
                continue
        if matched is None:
            result['reason'] = f'No geometrically matching output solid for reference solid {expected_index}.'
            return result
        remaining.pop(matched)
    result['passed'] = True
    result['reason'] = 'All solids match within tolerance, including positions and instance counts.'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-dir', type=Path)
    parser.add_argument('--pairs', type=Path, help='JSON list of {reference, actual} paths, relative to this file')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    FreeCAD, Part = load_kernel()
    report = {'kernel': 'FreeCAD/OpenCascade', 'freecad_version': FreeCAD.Version(),
              'reference_inspections': [], 'comparisons': []}
    if args.reference_dir:
        for path in sorted(args.reference_dir.rglob('*')):
            if path.suffix.lower() not in {'.step', '.stp'}:
                continue
            try:
                row = {'file': str(path), **metrics(Part.read(str(path)))}
            except Exception as exc:
                row = {'file': str(path), 'valid': False, 'error': str(exc)}
            report['reference_inspections'].append(row)
            print(f"Inspected {path.name}: {row.get('solids', '?')} solids, valid={row['valid']}", flush=True)
    if args.pairs:
        pairs = json.loads(args.pairs.read_text())
        for pair in pairs:
            paths = {k: (args.pairs.parent / pair[k]).resolve() for k in ('reference', 'actual')}
            row = {k+'_file': str(v) for k,v in paths.items()}
            if not paths['actual'].is_file():
                row.update(passed=False, reason='New export missing; conversion has not been verified.')
            else:
                try:
                    row.update(compare_shapes(Part.read(str(paths['reference'])), Part.read(str(paths['actual']))))
                except Exception as exc:
                    row.update(passed=False, reason=str(exc))
            report['comparisons'].append(row)
            print(f"Compared {paths['actual'].name}: {row['passed']} — {row['reason']}", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    return 1 if any(not r['passed'] for r in report['comparisons']) or any(not r['valid'] for r in report['reference_inspections']) else 0

if __name__ == '__main__':
    sys.exit(main())
