import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('geometry_check', Path(__file__).parents[1] / 'exporter/geometry_check.py')
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)

class GeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform == 'darwin' and sys.version_info[:2] != (3, 11):
            raise unittest.SkipTest('Run using the Python bundled with the installed FreeCAD (3.11).')
        try:
            cls.FreeCAD, cls.Part = geometry.load_kernel()
        except ImportError:
            raise unittest.SkipTest('FreeCAD geometry kernel is required.')

    def test_step_roundtrip_preserves_box(self):
        box = self.Part.makeBox(12.3, 27.4, 9.5)
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'box.step')
            box.exportStep(path)
            actual = self.Part.read(path)
        self.assertTrue(geometry.compare_shapes(box, actual)['passed'])

    def test_scaled_box_is_rejected(self):
        self.assertFalse(geometry.compare_shapes(self.Part.makeBox(10,20,30), self.Part.makeBox(10,20,31))['passed'])

    def test_displaced_instance_is_rejected(self):
        box = self.Part.makeBox(10,20,30)
        moved = box.copy()
        moved.translate(self.FreeCAD.Vector(1,0,0))
        self.assertFalse(geometry.compare_shapes(box,moved)['passed'])

    def test_missing_duplicate_instance_is_rejected(self):
        box = self.Part.makeBox(10,20,30)
        compound = self.Part.makeCompound([box,box.copy()])
        self.assertFalse(geometry.compare_shapes(compound,box)['passed'])

    def test_reordered_solids_still_match(self):
        a = self.Part.makeBox(10,20,30)
        b = self.Part.makeBox(4,5,6)
        b.translate(self.FreeCAD.Vector(50,0,0))
        self.assertTrue(geometry.compare_shapes(self.Part.makeCompound([a,b]),self.Part.makeCompound([b,a]))['passed'])

    def test_equal_volume_and_bounds_but_moved_hole_is_rejected(self):
        box = self.Part.makeBox(40,20,10)
        hole_a = self.Part.makeCylinder(2,10,self.FreeCAD.Vector(10,10,0))
        hole_b = self.Part.makeCylinder(2,10,self.FreeCAD.Vector(30,10,0))
        a,b = box.cut(hole_a),box.cut(hole_b)
        self.assertAlmostEqual(a.Volume,b.Volume)
        self.assertEqual(geometry.bounds(a),geometry.bounds(b))
        self.assertFalse(geometry.compare_shapes(a,b)['passed'])
