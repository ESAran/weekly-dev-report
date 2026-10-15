"""File-based request/reply bridge to the authenticated Codex connectors.

No token leaves Codex. Run only inside a private directory outside the template.
Only the tools below and GET repository resources are permitted.
"""
import hashlib
import json
import os
import time
from pathlib import Path
from urllib.parse import urlsplit

ALLOWLIST = {
    'github_get_profile', 'github_list_repositories', 'github_fetch',
    'gitlab_get_current_user', 'gitlab_list_projects', 'gitlab_list_commits',
    'gitlab_get_commit', 'gitlab_list_commit_diff',
    'gitlab_list_project_merge_requests', 'gitlab_list_merge_request_commits',
}


def write_private(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + '.tmp')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def validate_call(call):
    if call['tool'] not in ALLOWLIST:
        raise ValueError('Connector operation not on the read-only allowlist.')
    if call['tool'] == 'github_fetch':
        parsed = urlsplit(call['arguments']['url'])
        if parsed.scheme != 'https' or parsed.netloc != 'api.github.com' or not parsed.path.startswith('/repos/'):
            raise ValueError('Only GitHub repository GET endpoints are allowed.')


def call_id(tool, arguments):
    return hashlib.sha256(json.dumps([tool, arguments], sort_keys=True).encode()).hexdigest()


def unwrap(result):
    if isinstance(result, dict) and 'content' in result and isinstance(result['content'], str):
        return json.loads(result['content'])
    if isinstance(result, dict) and 'data' in result:
        return result['data']
    return result


class ConnectorError(RuntimeError):
    pass


class Bridge:
    def __init__(self, directory, timeout=900):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        self.cache = self.directory / 'cache'
        self.cache.mkdir(exist_ok=True, mode=0o700)
        self.timeout = timeout
        self.calls = 0
        self.lock = open(self.directory / '.collector.lock', 'a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                self.lock.write(b'0')
                self.lock.flush()
                self.lock.seek(0)
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.lock.close()
            raise RuntimeError('Another collector is using this bridge directory.') from error

    def many(self, calls):
        requests, values = [], {}
        for tool, arguments in calls:
            request = {'id': call_id(tool, arguments), 'tool': tool, 'arguments': arguments}
            validate_call(request)
            cached = self.cache / (request['id'] + '.json')
            if cached.exists():
                values[request['id']] = json.loads(cached.read_text())
            elif request not in requests:
                requests.append(request)
        if requests:
            batch = hashlib.sha256(''.join(r['id'] for r in requests).encode()).hexdigest()
            response_path = self.directory / ('response-' + batch + '.json')
            write_private(self.directory / 'request.json', {'batch': batch, 'requests': requests})
            print(f'Connector batch: {len(requests)} read requests', flush=True)
            started = time.monotonic()
            while not response_path.exists():
                if time.monotonic() - started > self.timeout:
                    raise TimeoutError('Codex bridge timed out; resume with the same private bridge directory.')
                time.sleep(.25)
            responses = json.loads(response_path.read_text())
            if responses.get('batch') != batch:
                raise ConnectorError('Unexpected bridge batch.')
            for item in responses['responses']:
                if item['id'] not in {r['id'] for r in requests}:
                    raise ConnectorError('Unexpected bridge response.')
                values[item['id']] = item
                # Successful responses only: failed requests can be retried.
                if not item.get('error'):
                    write_private(self.cache / (item['id'] + '.json'), item)
            self.calls += len(requests)
            (self.directory / 'request.json').unlink(missing_ok=True)
            response_path.unlink(missing_ok=True)
        return [values.get(call_id(tool, arguments), {'error': 'Missing connector response'}) for tool, arguments in calls]

    def one(self, tool, **arguments):
        value = self.many([(tool, arguments)])[0]
        if value.get('error'):
            raise ConnectorError(value['error'])
        return unwrap(value['result'])
