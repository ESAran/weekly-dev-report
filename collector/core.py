import fnmatch
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('America/Sao_Paulo')
IGNORED_DIRS = {'node_modules', 'vendor', '.venv', 'venv', 'dist', 'build', 'coverage', '__pycache__', '.next', '.nuxt', 'Pods', '.git'}
LOCKFILES = {'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'poetry.lock', 'uv.lock', 'Cargo.lock', 'Gemfile.lock', 'composer.lock', 'Pipfile.lock', 'bun.lock', 'bun.lockb'}
BINARY_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.ico', '.pdf', '.zip', '.gz', '.7z', '.woff', '.woff2', '.ttf', '.mp3', '.mp4', '.mov', '.exe', '.dll', '.so', '.pyc', '.class', '.jar', '.xlsx', '.docx', '.pptx'}


def parse_time(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZONE)
    return parsed


def period(start=None, end=None):
    finish = parse_time(end) if end else datetime.now(ZONE)
    local = finish.astimezone(ZONE)
    begin = parse_time(start) if start else (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    if begin > finish:
        raise ValueError('Start must not be after end.')
    return begin, finish


def in_period(commit, start, end):
    return start <= parse_time(commit['committed_at']) <= end


def normalize_commit(platform, raw):
    if platform == 'github':
        meta = raw['commit']
        return {'sha': raw['sha'], 'author_email': meta['author'].get('email', ''),
                'author_name': meta['author'].get('name', ''), 'author_login': (raw.get('author') or {}).get('login'),
                'author_id': (raw.get('author') or {}).get('id'), 'authored_at': meta['author']['date'],
                'committed_at': meta['committer']['date'], 'message': meta['message'],
                'parents': [p['sha'] for p in raw.get('parents', [])], 'url': raw.get('html_url')}
    return {'sha': raw['id'], 'author_email': raw.get('author_email', ''), 'author_name': raw.get('author_name', ''),
            'author_login': None, 'author_id': None, 'authored_at': raw['authored_date'],
            'committed_at': raw['committed_date'], 'message': raw['message'],
            'parents': raw.get('parent_ids', []), 'url': raw.get('web_url')}


def attribution(commit, identity):
    if commit.get('author_id') is not None and str(commit['author_id']) == str(identity.get('id')):
        return 'authenticated-account-id'
    if commit.get('author_login') and commit['author_login'].casefold() == identity.get('login', '').casefold():
        return 'authenticated-account-login'
    email = commit.get('author_email', '').casefold().strip()
    if email and email in {e.casefold().strip() for e in identity.get('emails', [])}:
        return 'authorized-email'
    return None


def file_reason(path, patch='', extra_patterns=()):
    components = path.replace('\\', '/').split('/')
    name = components[-1]
    if name == '.DS_Store' or ('.obsidian' in components and fnmatch.fnmatch(name, 'workspace*.json')):
        return 'automatic-editor-state'
    if any(part in IGNORED_DIRS for part in components[:-1]):
        return 'dependency-or-generated-directory'
    if name in LOCKFILES:
        return 'lockfile'
    if any(name.lower().endswith(ext) for ext in BINARY_EXTENSIONS) or 'Binary files ' in patch:
        return 'binary'
    if re.search(r'\.(min\.(js|css)|map|generated\.[^.]+)$', name, re.I):
        return 'generated-file'
    if any(fnmatch.fnmatch(path, pattern) for pattern in extra_patterns):
        return 'configured-exclusion'
    return None


def is_submodule(file, patch):
    if any(str(file.get(key, '')) == '160000' for key in ('a_mode', 'b_mode', 'old_mode', 'new_mode', 'mode')):
        return True
    # GitHub may omit the gitlink mode. Require every changed line to be a pointer.
    changed = [line[1:] for line in patch.splitlines() if line.startswith(('+', '-')) and not line.startswith(('+++ ', '--- '))]
    return bool(changed) and all(re.fullmatch(r'Subproject commit [0-9a-f]{40,64}(?:-dirty)?', line) for line in changed)


def diff_counts(patch):
    # Only count inside hunks: +++/--- filenames are metadata, but code lines
    # beginning with repeated + or - inside a hunk are real changes.
    added = removed = 0
    inside = False
    for line in patch.splitlines():
        if line.startswith('@@'):
            inside = True
        elif line.startswith(('diff --git ', '--- ', '+++ ')) and not inside:
            continue
        elif inside and line.startswith('+'):
            added += 1
        elif inside and line.startswith('-'):
            removed += 1
    return added, removed


def measure(commit, files, stats, platform, patterns=(), initial_threshold=10000):
    included = {'added': 0, 'removed': 0}
    excluded = {'added': 0, 'removed': 0}
    parsed_total = {'added': 0, 'removed': 0}
    classified, warnings = [], []
    merge = len(commit['parents']) > 1
    large_initial = not commit['parents'] and (stats.get('additions', 0) + stats.get('deletions', 0)) >= initial_threshold
    for file in files:
        path = file.get('filename') or file.get('new_path') or file.get('old_path')
        patch = file.get('patch', file.get('diff', '')) or ''
        if platform == 'github':
            added, removed = file.get('additions', 0), file.get('deletions', 0)
        else:
            added, removed = diff_counts(patch)
        if file.get('too_large') or file.get('collapsed'):
            warnings.append('diff-truncated-or-collapsed')
        reason = 'merge-integration' if merge else 'large-initial-import' if large_initial else 'submodule-pointer' if is_submodule(file, patch) else file_reason(path, patch, patterns)
        # Unknown/truncated deltas cannot silently become confirmed zeros.
        if not patch and not reason and (added + removed > 0 or platform == 'gitlab'):
            warnings.append('patch-not-available')
        target = excluded if reason else included
        target['added'] += added
        target['removed'] += removed
        parsed_total['added'] += added
        parsed_total['removed'] += removed
        classified.append({'path': path, 'previous_path': file.get('previous_filename', file.get('old_path')),
                           'added': added, 'removed': removed, 'excluded_reason': reason,
                           'patch_available': bool(patch), 'evidence_patch': patch[:12000]})
    complete = parsed_total == {'added': stats.get('additions'), 'removed': stats.get('deletions')}
    if not complete:
        warnings.append('file-totals-do-not-match-commit-stats')
    return {'included': included, 'excluded': excluded, 'raw': stats, 'files': classified,
            'complete': complete and not any(w in warnings for w in ('diff-truncated-or-collapsed', 'patch-not-available')),
            'warnings': sorted(set(warnings)), 'merge': merge, 'large_initial': large_initial}


def evidence_summary(commits, reviews):
    """Conservative extractive fallback; no unsupported functional claims."""
    candidates = []
    for commit in commits:
        if commit.get('measurement', {}).get('merge'):
            continue
        subject = commit['message'].splitlines()[0].strip()
        subject = re.sub(r'^(feat|fix|chore|docs|refactor|test|style|build|ci|perf)(\([^)]*\))?!?:\s*', '', subject, flags=re.I)
        if len(subject) >= 12 and subject.casefold() not in {'initial commit', 'primeiro commit'}:
            candidates.append((subject, 'commit:' + commit['sha']))
    for review in reviews:
        if review.get('owned') and review.get('title'):
            candidates.append((review['title'], review['evidence_id']))
    selected, seen = [], set()
    for text, reference in candidates:
        if text.casefold() not in seen:
            selected.append((text[:140].rstrip(), reference))
            seen.add(text.casefold())
        if len(selected) == 2:
            break
    if not selected:
        return {'text': 'Atividade registrada em commits; as evidências disponíveis não descrevem a finalidade das alterações.', 'evidence': ['commit:' + c['sha'] for c in commits[:2]], 'method': 'extractive'}
    return {'text': 'Alterações registradas: ' + '; '.join(t.rstrip('.') for t, _ in selected) + '.',
            'evidence': [ref for _, ref in selected], 'method': 'extractive'}
