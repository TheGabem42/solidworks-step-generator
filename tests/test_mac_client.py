import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('mac_client', Path(__file__).parents[1] / 'exporter/mac_client.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)

class ClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def put(self, name, data='model'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)
        return path

    def test_three_dropped_files_ignore_reference_fixtures_and_queue(self):
        self.put('A.SLDPRT'); self.put('B.SLDPRT'); self.put('Assembly.SLDASM')
        self.put('sample step files/reference.SLDPRT')
        self.put('.step-export-queue/job/duplicate.SLDPRT')
        found = {p.name for p in client.models(self.root)}
        self.assertEqual(found, {'A.SLDPRT', 'B.SLDPRT', 'Assembly.SLDASM'})
        self.assertIsNone(client.configured_queue(self.root))

    def test_discovery_and_package(self):
        self.put('A.SLDPRT'); self.put('A.SLDASM'); self.put('Old/A.sldprt')
        self.put('STEP exports/ignored.sldprt'); self.put('~$locked.SLDPRT')
        self.put('drawing.slddrw'); self.put('reference.step')
        (self.root / 'linked.sldprt').symlink_to(self.root / 'A.SLDPRT')
        target = self.root / 'input.zip'
        self.assertEqual(client.make_package(self.root, target), 3)
        with zipfile.ZipFile(target) as archive:
            self.assertEqual(set(archive.namelist()), {'A.SLDPRT', 'A.SLDASM', 'Old/A.sldprt'})

    def test_failed_export_preserves_previous_good_file(self):
        self.put('STEP exports/A.SLDPRT.step', 'old-good')
        self.put('job/result/B.SLDASM.step', 'new-assembly')
        rows = [{'source':'A.SLDPRT','status':'failed'}, {'source':'B.SLDASM','status':'exported'}]
        self.put('job/result/export-report.json', json.dumps(rows))
        client.import_results(self.root / 'job', self.root)
        self.assertEqual((self.root / 'STEP exports/A.SLDPRT.step').read_text(), 'old-good')
        self.assertEqual((self.root / 'STEP exports/B.SLDASM.step').read_text(), 'new-assembly')

    def test_interrupted_worker_does_not_claim_all_files_exported(self):
        self.put('job/manifest.json', json.dumps(['A.SLDPRT', 'B.SLDASM']))
        self.put('job/result/A.SLDPRT.step', 'good')
        self.put('job/result/export-report.json', json.dumps([{'source':'A.SLDPRT','status':'exported'}]))
        rows = client.import_results(self.root / 'job', self.root)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]['status'], 'failed')
        self.assertEqual(rows[1]['source'], 'B.SLDASM')

    def test_traversal_report_rejected(self):
        self.put('job/result/export-report.json', json.dumps([{'source':'../outside.SLDPRT','status':'exported'}]))
        with self.assertRaisesRegex(RuntimeError, 'invalid source'):
            client.import_results(self.root / 'job', self.root)

    def test_empty_folder_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'No SLDPRT'):
            client.make_package(self.root, self.root / 'input.zip')

    def test_missing_worker_report_is_failure(self):
        self.put('job/worker.log', 'SolidWorks unavailable')
        with self.assertRaisesRegex(RuntimeError, 'SolidWorks unavailable'):
            client.import_results(self.root / 'job', self.root)

if __name__ == '__main__':
    unittest.main()
