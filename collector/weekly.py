"""One local run: existing plugins -> private JSON -> installed Chrome -> PNG.

Never installs dependencies or downloads a browser. The live mode needs Codex to
service the bridge; --demo is fully offline and requires no authenticated tools.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

from .bridge import Bridge, write_private
from .collect import Collector, ROOT, build_dashboard
from .core import ZONE, period


def outside_template(path):
    path = Path(path).expanduser().resolve()
    if path == ROOT or ROOT in path.parents:
        raise ValueError('Use a private directory outside the template.')
    return path


@contextmanager
def run_lock(directory):
    # POSIX local scheduler (macOS/Linux). Keep this one small lock file so
    # concurrent processes cannot unlink/recreate different lock inodes.
    import fcntl
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / '.weekly.lock').open('a+b') as handle:
        os.chmod(handle.name, 0o600)
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('Another weekly report is already running.') from error
        yield


def emit(**values):
    print(json.dumps(values, ensure_ascii=False), flush=True)


def generate(*, output_dir, state_dir, demo=False, channel='chrome', config=None, end=None):
    destination = outside_template(output_dir)
    state = outside_template(state_dir)
    start, finish = period(end=end)
    finish = finish.astimezone(ZONE)
    node = shutil.which('node')
    if not node or not (ROOT / 'node_modules/playwright/package.json').is_file():
        raise RuntimeError('Dependencies missing. Install Node >=20 and run npm ci once in the template.')
    if channel not in ('chrome', 'chromium'):
        raise ValueError('Use chrome (installed) or chromium (already installed by Playwright).')
    with run_lock(state), tempfile.TemporaryDirectory(prefix='weekly-', dir=state) as temporary:
        work = Path(temporary)
        bridge = None
        try:
            if demo:
                data = json.loads((ROOT / 'data/demo.json').read_text(encoding='utf8'))
                observed = {'start': start.isoformat(), 'end': finish.isoformat()}
            else:
                bridge = Bridge(work / 'bridge')
                emit(stage='collection', bridge=str(bridge.directory), start=start.isoformat(), end=finish.isoformat())
                collector = Collector(bridge, start, finish, config)
                collector.discover()
                collector.histories()
                collector.review_evidence()
                collector.details()
                audit = collector.result()
                data = build_dashboard(audit)
                observed = audit['period']
                if all(source['status'] == 'unavailable' for source in data['sources'].values()):
                    raise RuntimeError('Both integrations are unavailable; no report was generated.')
            # No audit/cache or real JSON is left in the reusable template.
            write_private(work / 'report.json', data)
            emit(stage='export', sources={key: value['status'] for key, value in data['sources'].items()})
            command = [node, str(ROOT / 'scripts/export.mjs'), '--input', str(work / 'report.json'),
                       '--output', str(work / 'report.png'), '--channel', channel]
            exported = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=120)
            if exported.returncode:
                # The renderer can include private paths/content in diagnostics;
                # keep scheduler output short and avoid dumping browser logs.
                raise RuntimeError('PNG export failed. Check the installed browser and local execution permissions; no browser will be downloaded automatically.')
            image = (work / 'report.png').read_bytes()
            if image[:8] != b'\x89PNG\r\n\x1a\n' or len(image) < 24:
                raise RuntimeError('Renderer did not produce a valid PNG.')
            width, height = struct.unpack('>II', image[16:24])
            if width <= 0 or height <= 0:
                raise RuntimeError('Invalid PNG dimensions.')
            folder = destination / finish.strftime('%Y-%m-%d')
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(folder, 0o700)
            name = ('demo-' if demo else 'report-') + finish.strftime('%H%M%S%f') + '.png'
            target = folder / name
            # Exclusive creation preserves any existing report, even when the
            # same explicit cutoff is used for a repeated manual invocation.
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(descriptor, 'wb') as handle:
                    handle.write(image)
            except BaseException:
                target.unlink(missing_ok=True)
                raise
            result = {'ok': True, 'demo': demo, 'png': str(target), 'width': width, 'height': height,
                      'period': data['week'] if demo else observed,
                      'sources': {key: value['status'] for key, value in data['sources'].items()}}
            emit(**result)
            return result
        finally:
            if bridge is not None:
                bridge.lock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--state-dir', type=Path, default=Path(tempfile.gettempdir()) / 'weekly-dev-report-private')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--channel', choices=('chrome', 'chromium'), default='chrome')
    parser.add_argument('--end', help='Optional ISO cutoff; default: start of this execution.')
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding='utf8')) if args.config else None
        generate(output_dir=args.output_dir, state_dir=args.state_dir, demo=args.demo,
                 channel=args.channel, config=config, end=args.end)
    except Exception as error:
        emit(ok=False, error=str(error))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
