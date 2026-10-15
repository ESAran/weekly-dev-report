"""Collect real activity through the Codex bridge; never writes to repositories."""
import argparse
import json
import subprocess
from copy import deepcopy
from datetime import timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl, quote

from .bridge import Bridge, unwrap, write_private
from .core import ZONE, period, in_period, attribution, normalize_commit, measure, evidence_summary, parse_time

ROOT = Path(__file__).resolve().parents[1]


def gh(path, **parameters):
    return ('github_fetch', {'url': 'https://api.github.com/repos/' + path + ('?' + urlencode(parameters) if parameters else '')})


def page_call(tool, arguments, page):
    arguments = deepcopy(arguments)
    if tool == 'github_fetch':
        parsed = urlsplit(arguments['url'])
        params = dict(parse_qsl(parsed.query))
        params.update(per_page=100, page=page)
        arguments['url'] = urlunsplit(parsed._replace(query=urlencode(params)))
    elif tool == 'github_list_repositories':
        arguments.update(page_size=100, page_offset=(page - 1) * 100)
    else:
        arguments.update(per_page=100, page=page)
    return tool, arguments


def pages(bridge, specs, field=None, updated_since=None, max_pages=100):
    """Paginate independently. Errors retain earlier pages and mark coverage."""
    result = {key: [] for key in specs}
    metadata, errors = {}, {}
    pending = {key: 1 for key in specs}
    while pending:
        keys = list(pending)
        calls = [page_call(*specs[key], pending[key]) for key in keys]
        for key, value in zip(keys, bridge.many(calls)):
            if value.get('error'):
                errors[key] = value['error']
                del pending[key]
                continue
            raw = unwrap(value['result'])
            metadata.setdefault(key, raw)
            items = raw.get(field, []) if field else raw
            if not isinstance(items, list):
                errors[key] = 'Unexpected connector response; expected an array.'
                del pending[key]
                continue
            result[key].extend(items)
            if len(items) < 100 or (updated_since and items and parse_time(items[-1]['updated_at']) < updated_since):
                del pending[key]
            elif pending[key] >= max_pages:
                errors[key] = 'Pagination limit reached; coverage is partial.'
                del pending[key]
            else:
                pending[key] += 1
    return result, errors, metadata


def git_email():
    try:
        proc = subprocess.run(['git', 'config', '--get', 'user.email'], capture_output=True, text=True)
    except FileNotFoundError:
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


class Collector:
    def __init__(self, bridge, start, end, config=None):
        self.bridge, self.start, self.end = bridge, start, end
        self.config = config or {}
        self.since, self.until = [date.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z') for date in (start, end)]
        self.sources = {name: {'status': 'complete', 'note': '', 'issues': [], 'repositories': 0} for name in ('github', 'gitlab')}
        self.identities, self.repos, self.commits, self.reviews, self.rejected = {}, {}, {}, {}, []
        self.duplicates = 0

    def issue(self, platform, stage, details):
        self.sources[platform]['status'] = 'partial'
        self.sources[platform]['issues'].append({'stage': stage, 'details': str(details)[:1500]})

    def discover(self):
        identities = self.bridge.many([('github_get_profile', {}), ('gitlab_get_current_user', {})])
        local_email = git_email()
        for platform, response in zip(('github', 'gitlab'), identities):
            if response.get('error'):
                self.sources[platform].update(status='unavailable', note='Conexão indisponível nesta coleta.')
                continue
            profile = unwrap(response['result'])
            emails = set(self.config.get('identities', {}).get(platform, {}).get('emails', []))
            emails.update(e for e in (profile.get('email'), profile.get('commit_email'), profile.get('public_email'), local_email) if e)
            login = profile.get('nickname') or profile.get('login') or profile.get('username')
            if platform == 'github':
                emails.add(f'{profile["id"]}+{login}@users.noreply.github.com')
                emails.add(f'{login}@users.noreply.github.com')
            self.identities[platform] = {'id': profile['id'], 'login': login, 'emails': sorted(emails), 'local_git_email': local_email}
        if 'github' in self.identities:
            listed, errors, _ = pages(self.bridge, {'repos': ('github_list_repositories', {})}, field='repositories')
            for error in errors.values():
                self.issue('github', 'repository-discovery', error)
            for repo in listed['repos']:
                key = 'github:' + str(repo['id'])
                self.repos[key] = {'id': key, 'remote_id': repo['id'], 'path': repo['repository_full_name'], 'name': repo['name'],
                                   'platform': 'github', 'visibility': repo.get('visibility', 'unknown'), 'branches': [], 'empty': False}
        if 'gitlab' in self.identities:
            listed, errors, _ = pages(self.bridge, {'repos': ('gitlab_list_projects', {'membership': True, 'simple': True})})
            for error in errors.values():
                self.issue('gitlab', 'repository-discovery', error)
            for repo in listed['repos']:
                key = 'gitlab:' + str(repo['id'])
                self.repos[key] = {'id': key, 'remote_id': repo['id'], 'path': repo['path_with_namespace'], 'name': repo['name'],
                                   'platform': 'gitlab', 'visibility': repo.get('visibility', 'unknown'), 'branches': ['all reachable refs'], 'empty': False}
        for platform in self.identities:
            self.sources[platform]['repositories'] = sum(r['platform'] == platform for r in self.repos.values())

    def add_commits(self, repository, raw_commits, reference):
        platform = self.repos[repository]['platform']
        for raw in raw_commits:
            commit = normalize_commit(platform, raw)
            if not in_period(commit, self.start, self.end):
                continue
            proof = attribution(commit, self.identities[platform])
            if not proof:
                self.rejected.append({'repository': repository, 'sha': commit['sha'], 'reason': 'unmatched-author', 'author_email': commit['author_email'], 'author_name': commit['author_name']})
                continue
            key = (repository, commit['sha'])
            if key in self.commits:
                self.duplicates += 1
                self.commits[key]['found_in'] = sorted(set(self.commits[key]['found_in'] + [reference]))
            else:
                commit.update(repository=repository, attribution=proof, found_in=[reference])
                self.commits[key] = commit

    def histories(self):
        specs = {key: gh(repo['path'] + '/branches') for key, repo in self.repos.items() if repo['platform'] == 'github'}
        branches, errors, _ = pages(self.bridge, specs)
        for key, error in errors.items():
            if 'empty' in error.lower():
                self.repos[key]['empty'] = True
            else:
                self.issue('github', 'branches:' + key, error)
        specs = {}
        origins = {}
        for key, repo in self.repos.items():
            if repo['platform'] == 'github':
                repo['branches'] = [branch['name'] for branch in branches[key]]
                for branch in branches[key]:
                    request_id = key + ':' + branch['name']
                    # Freeze branch heads to their SHAs at the start of collection.
                    specs[request_id] = gh(repo['path'] + '/commits', sha=branch['commit']['sha'], since=self.since, until=self.until)
                    origins[request_id] = (key, branch['name'])
            else:
                specs[key] = ('gitlab_list_commits', {'project_id': repo['remote_id'], 'all': True, 'since': self.since, 'until': self.until, 'with_stats': True})
                origins[key] = (key, 'all reachable refs')
        histories, errors, _ = pages(self.bridge, specs)
        for request_id, error in errors.items():
            key, _ = origins[request_id]
            self.issue(self.repos[key]['platform'], 'commits:' + key, error)
        for request_id, commits in histories.items():
            repository, reference = origins[request_id]
            self.add_commits(repository, commits, reference)

    def review_evidence(self):
        # All recently updated reviews in authorized repositories, regardless of author.
        specs = {}
        for key, repo in self.repos.items():
            if repo['empty']:
                continue
            if repo['platform'] == 'github':
                specs[key] = gh(repo['path'] + '/pulls', state='all', sort='updated', direction='desc')
            else:
                specs[key] = ('gitlab_list_project_merge_requests', {'project_id': repo['remote_id'], 'scope': 'all', 'state': 'all', 'updated_after': self.since, 'order_by': 'updated_at', 'sort': 'desc'})
        listed, errors, _ = pages(self.bridge, specs, updated_since=self.start)
        for key, error in errors.items():
            self.issue(self.repos[key]['platform'], 'review-discovery:' + key, error)
        candidates, commit_queries = {}, {}
        for key, raw_reviews in listed.items():
            repo = self.repos[key]
            platform = repo['platform']
            for raw in raw_reviews:
                # Reviews updated after the cutoff may contain later metadata. Keep
                # only objects created by cutoff, and label metadata as collected now.
                if parse_time(raw['updated_at']) < self.start or parse_time(raw['created_at']) > self.end:
                    continue
                number = raw.get('number', raw.get('iid'))
                rid = f'{key}:{number}'
                user = raw.get('user', raw.get('author', {}))
                owned = str(user.get('id')) == str(self.identities[platform]['id'])
                review = {'repository': key, 'number': number, 'title': raw['title'], 'description': raw.get('body', raw.get('description')) or '',
                          'url': raw.get('html_url', raw.get('web_url')), 'state': raw['state'], 'owned': owned,
                          'created_at': raw['created_at'], 'updated_at': raw['updated_at'], 'merged_at': raw.get('merged_at'),
                          'evidence_id': ('pr:' if platform == 'github' else 'mr:') + rid,
                          'merge_commit_sha': raw.get('merge_commit_sha'), 'squash_commit_sha': raw.get('squash_commit_sha')}
                candidates[rid] = review
                commit_queries[rid] = gh(repo['path'] + f'/pulls/{number}/commits') if platform == 'github' else ('gitlab_list_merge_request_commits', {'project_id': repo['remote_id'], 'merge_request_iid': number})
        review_commits, errors, _ = pages(self.bridge, commit_queries)
        for rid, error in errors.items():
            self.issue(self.repos[candidates[rid]['repository']]['platform'], 'review-commits:' + rid, error)
        for rid, raw_commits in review_commits.items():
            review = candidates[rid]
            key = review['repository']
            self.add_commits(key, raw_commits, review['evidence_id'])
            shas = [r.get('sha', r.get('id')) for r in raw_commits]
            review['commit_shas'] = shas
            relevant = [sha for sha in shas if (key, sha) in self.commits]
            if relevant or review['owned']:
                review['own_commit_shas'] = relevant
                self.reviews[rid] = review
            if self.repos[key]['platform'] == 'github' and len(shas) >= 250:
                self.issue('github', 'review-commits:' + rid, 'GitHub PR commit list can be limited to 250 commits.')
        # A squash aggregate is not counted in addition to its observed own commits.
        for review in self.reviews.values():
            key = review['repository']
            aggregate = review.get('squash_commit_sha')
            if not aggregate and self.repos[key]['platform'] == 'github':
                aggregate = review.get('merge_commit_sha')
            if review.get('merged_at') and aggregate not in review['commit_shas'] and aggregate and (key, aggregate) in self.commits and any(sha != aggregate and (key, sha) in self.commits for sha in review['commit_shas']):
                commit = self.commits[(key, aggregate)]
                if len(commit['parents']) <= 1:
                    commit['aggregate_of_review'] = review['evidence_id']

    def details(self):
        github = {key: gh(self.repos[key[0]]['path'] + '/commits/' + key[1]) for key in self.commits if self.repos[key[0]]['platform'] == 'github'}
        files, errors, metadata = pages(self.bridge, github, field='files', max_pages=30)
        for key, error in errors.items():
            self.issue('github', 'commit-detail:' + key[1], error)
        gl_keys = [key for key in self.commits if self.repos[key[0]]['platform'] == 'gitlab']
        calls = [('gitlab_get_commit', {'project_id': self.repos[key[0]]['remote_id'], 'sha': key[1], 'stats': True}) for key in gl_keys]
        for key, response in zip(gl_keys, self.bridge.many(calls)):
            if response.get('error'):
                errors[key] = response['error']
                self.issue('gitlab', 'commit-detail:' + key[1], response['error'])
            else:
                metadata[key] = unwrap(response['result'])
        gl_files, gl_errors, _ = pages(self.bridge, {key: ('gitlab_list_commit_diff', {'project_id': self.repos[key[0]]['remote_id'], 'commit_sha': key[1]}) for key in gl_keys})
        files.update(gl_files)
        errors.update(gl_errors)
        for key, error in gl_errors.items():
            self.issue('gitlab', 'commit-diff:' + key[1], error)
        for key, commit in self.commits.items():
            platform = self.repos[key[0]]['platform']
            stats = metadata.get(key, {}).get('stats')
            if stats is None:
                commit['measurement'] = None
                commit['measurement_error'] = 'Commit stats unavailable; excluded from observed dashboard metrics.'
                self.issue(platform, 'missing-stats:' + key[1], commit['measurement_error'])
                continue
            measured = measure(commit, files.get(key, []), stats, platform,
                               self.config.get('exclude_patterns', []), self.config.get('initial_import_threshold', 10000))
            if commit.get('aggregate_of_review'):
                measured['excluded']['added'] += measured['included']['added']
                measured['excluded']['removed'] += measured['included']['removed']
                measured['included'] = {'added': 0, 'removed': 0}
                measured['excluded_aggregate'] = True
            commit['measurement'] = measured
            if not measured['complete'] or key in errors:
                self.issue(platform, 'incomplete-diff:' + key[1], ', '.join(measured['warnings']) or errors.get(key))

    def result(self):
        for platform, source in self.sources.items():
            if source['status'] == 'unavailable':
                continue
            n = source['repositories']
            source['note'] = f'{n} repositórios autorizados; branches e revisões consultadas. Volume filtrado de alterações.'
            if source['status'] == 'partial':
                source['note'] = 'Parte dos dados não pôde ser confirmada; métricas limitadas às alterações verificáveis. Consulte a auditoria privada.'
        return {'schemaVersion': 1, 'collectedAt': self.end.isoformat(), 'period': {'start': self.start.isoformat(), 'end': self.end.isoformat(), 'timezone': 'America/Sao_Paulo', 'timestampBasis': 'committed_at'},
                'identities': self.identities, 'sources': self.sources, 'repositories': list(self.repos.values()),
                'commits': sorted(self.commits.values(), key=lambda c: (c['repository'], c['committed_at'], c['sha'])),
                'reviews': list(self.reviews.values()), 'rejectedCandidates': self.rejected, 'duplicateOccurrencesRemoved': self.duplicates,
                'criteria': {'metric': 'filtered-added-plus-removed', 'mergeLines': 'excluded', 'submodulePointers': 'excluded', 'squashAggregates': 'excluded-when-original-commits-observed', 'initialImportThreshold': self.config.get('initial_import_threshold', 10000), 'customExclusions': self.config.get('exclude_patterns', [])}}


def build_dashboard(audit, summaries=None):
    projects, evidence = [], {}
    for repo in audit['repositories']:
        commits = [c for c in audit['commits'] if c['repository'] == repo['id'] and c.get('measurement') is not None and not c['measurement'].get('excluded_aggregate')]
        if not commits:
            continue
        reviews = [r for r in audit['reviews'] if r['repository'] == repo['id']]
        digest = evidence_summary(commits, reviews)
        if summaries and repo['id'] in summaries:
            digest = summaries[repo['id']]
            valid = {'commit:' + c['sha'] for c in commits} | {r['evidence_id'] for r in reviews}
            if not digest.get('evidence') or not set(digest['evidence']).issubset(valid):
                raise ValueError('Summary references evidence not present in the collection.')
            if not isinstance(digest.get('text'), str) or not digest['text'].strip() or len(digest['text']) > 360:
                raise ValueError('Summary must contain 1–360 characters.')
        evidence[repo['id']] = digest
        projects.append({'id': repo['id'], 'name': repo['name'], 'platform': repo['platform'], 'commits': len(commits),
                         'added': sum(c['measurement']['included']['added'] for c in commits),
                         'removed': sum(c['measurement']['included']['removed'] for c in commits), 'summary': digest['text']})
    projects.sort(key=lambda p: (-p['added'] - p['removed'], p['id']))
    for i, project in enumerate(projects):
        project.update(color=['blue', 'purple', 'green', 'orange'][i % 4], icon=['cube', 'monitor', 'phone', 'globe'][i % 4])
    data = {'schemaVersion': 1, 'demo': False, 'activityMetric': 'changedLines',
            'week': {key: parse_time(audit['period'][key]).astimezone(ZONE).date().isoformat() for key in ('start', 'end')},
            'sources': {key: {k: value[k] for k in ('status', 'note')} for key, value in audit['sources'].items()},
            'projects': projects, 'collection': {'period': audit['period'], 'metric': audit['criteria'], 'summaryEvidence': evidence}}
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--start')
    parser.add_argument('--end')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--from-audit', type=Path)
    parser.add_argument('--summaries', type=Path)
    parser.add_argument('--export', action='store_true')
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    if destination == ROOT or ROOT in destination.parents:
        parser.error('Real data must be stored outside the publishable template directory.')
    if args.from_audit:
        audit = json.loads(args.from_audit.read_text())
    else:
        if not args.bridge:
            parser.error('--bridge is required for live collection.')
        if args.bridge.resolve() == ROOT or ROOT in args.bridge.resolve().parents:
            parser.error('Connector cache must be outside the publishable template.')
        start, end = period(args.start, args.end)
        config = json.loads(args.config.read_text()) if args.config else {}
        bridge = Bridge(args.bridge)
        run = {'start': start.isoformat(), 'end': end.isoformat()}
        manifest = bridge.directory / 'run.json'
        if manifest.exists() and json.loads(manifest.read_text()) != run:
            parser.error('This bridge belongs to another interval. Use a new private bridge directory, or resume with its exact --start and --end.')
        write_private(manifest, run)
        collector = Collector(bridge, start, end, config)
        print('Discovering identities and authorized repositories', flush=True)
        collector.discover()
        print('Reading branch histories', flush=True)
        collector.histories()
        print('Reading pull/merge request evidence', flush=True)
        collector.review_evidence()
        print('Measuring unique commits and file changes', flush=True)
        collector.details()
        audit = collector.result()
    summaries = json.loads(args.summaries.read_text()) if args.summaries else None
    data = build_dashboard(audit, summaries)
    write_private(destination / 'audit.json', audit)
    write_private(destination / 'report.json', data)
    print(json.dumps({'projects': len(data['projects']), 'commits': sum(p['commits'] for p in data['projects']), 'added': sum(p['added'] for p in data['projects']), 'removed': sum(p['removed'] for p in data['projects']), 'sources': {k: v['status'] for k, v in data['sources'].items()}}), flush=True)
    if args.export:
        subprocess.run(['node', str(ROOT / 'scripts/export.mjs'), '--input', str(destination / 'report.json'), '--output', str(destination / 'report.png')], cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
