import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('parallels', Path(__file__).parents[1] / 'exporter/parallels.py')
parallels = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parallels)

class ParallelsTests(unittest.TestCase):
    def test_path_with_spaces_and_apostrophes(self):
        home = Path('/Users/example')
        path = home / "Desktop/My CAD's models"
        self.assertEqual(parallels.windows_path(path, home), "\\\\Mac\\Home\\Desktop\\My CAD's models")
        self.assertEqual(parallels.ps_literal("x'y"), "'x''y'")

    def test_encoding_preserves_literal_script(self):
        script = "& 'C:\\My models\\convert.ps1' -Root 'C:\\CAD'"
        self.assertEqual(base64.b64decode(parallels.encoded_command(script)).decode('utf-16-le'), script)

    def test_auto_selects_single_windows_vm(self):
        vm = {'name':'Windows 11', 'uuid':'one'}
        self.assertEqual(parallels.select_vm({}, [vm, {'name':'Ubuntu', 'uuid':'two'}]), vm)

    def test_ambiguous_vms_do_not_choose_arbitrarily(self):
        with self.assertRaisesRegex(RuntimeError, 'identify one'):
            parallels.select_vm({}, [{'name':'Windows 10','uuid':'one'}, {'name':'Windows 11','uuid':'two'}])

    def test_explicit_vm(self):
        vm = {'name':'CAD machine', 'uuid':'one'}
        self.assertEqual(parallels.select_vm({'vm':'CAD machine'}, [vm]), vm)
