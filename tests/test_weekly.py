import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from collector.collect import ROOT
from collector.weekly import generate, outside_template, run_lock


class WeeklyTests(unittest.TestCase):
    def test_private_directories_must_be_outside_template(self):
        for path in (ROOT, ROOT / 'reports'):
            with self.assertRaises(ValueError):
                outside_template(path)

    def test_parallel_run_is_rejected_and_lock_is_released(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            with run_lock(state):
                with self.assertRaises(RuntimeError):
                    with run_lock(state):
                        pass
            with run_lock(state):
                pass

    def test_missing_integrations_do_not_produce_zero_report_and_clean_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            audit = {'repositories': [], 'commits': [], 'reviews': [], 'criteria': {},
                     'period': {'start': '2026-10-12', 'end': '2026-10-16'},
                     'sources': {p: {'status': 'unavailable', 'note': 'Disconnected'} for p in ('github', 'gitlab')}}
            with patch('collector.weekly.Collector') as collector, contextlib.redirect_stdout(io.StringIO()):
                collector.return_value.result.return_value = audit
                with self.assertRaisesRegex(RuntimeError, 'Both integrations'):
                    generate(output_dir=root / 'out', state_dir=root / 'state')
            self.assertEqual(list((root / 'state').iterdir()), [root / 'state/.weekly.lock'])
            self.assertFalse((root / 'out').exists())

    def test_export_failure_cleans_intermediates_and_never_installs_packages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch('collector.weekly.subprocess.run', return_value=Mock(returncode=1, stderr='private browser detail')) as run:
                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaisesRegex(RuntimeError, 'PNG export failed'):
                        generate(output_dir=root / 'out', state_dir=root / 'state', demo=True)
                arguments = run.call_args.args[0]
                self.assertEqual(Path(arguments[0]).name, 'node')
                self.assertEqual(arguments[-2:], ['--channel', 'chrome'])
                self.assertNotIn('install', arguments)
            self.assertEqual(list((root / 'state').iterdir()), [root / 'state/.weekly.lock'])
            self.assertFalse((root / 'out').exists())
