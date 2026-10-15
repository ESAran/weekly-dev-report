import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from collector.bridge import validate_call
from collector.collect import Collector, build_dashboard, pages
from collector.core import period, normalize_commit, attribution, measure, diff_counts, evidence_summary, file_reason


def commit(sha='abc', email='dev@example.test', parents=None):
    return {'sha': sha, 'author_email': email, 'author_name': 'Developer', 'author_login': 'developer', 'author_id': 10,
            'authored_at': '2026-10-12T03:00:00Z', 'committed_at': '2026-10-12T03:00:00Z',
            'message': 'fix: Corrige validação do formulário', 'parents': ['parent'] if parents is None else parents, 'url': 'https://example.test/commit/' + sha}


class CollectorTests(unittest.TestCase):
    def test_sao_paulo_week_boundary(self):
        start, end = period(end='2026-10-15T16:00:00-03:00')
        self.assertEqual(start.isoformat(), '2026-10-12T00:00:00-03:00')
        self.assertEqual(start.utcoffset().total_seconds(), -10800)
        self.assertRaises(ValueError, period, '2026-10-16', '2026-10-15')

    def test_author_not_committer_or_display_name(self):
        identity = {'id': 10, 'login': 'developer', 'emails': ['other@example.test']}
        self.assertEqual(attribution(commit(), identity), 'authenticated-account-id')
        c = commit(); c.update(author_id=12, author_login='someone-else')
        self.assertIsNone(attribution(c, identity))
        c['author_email'] = 'OTHER@example.test'
        self.assertEqual(attribution(c, identity), 'authorized-email')

    def test_generated_lock_binary_merge_initial_import(self):
        files = [
            {'filename': 'src/main.py', 'additions': 3, 'deletions': 1, 'patch': '@@ -1 +1 @@\n-old\n+new\n+next\n+last'},
            {'filename': 'package-lock.json', 'additions': 100, 'deletions': 10},
            {'filename': 'vendor/lib.js', 'additions': 40, 'deletions': 0},
            {'filename': 'logo.png', 'additions': 0, 'deletions': 0},
        ]
        stats = {'additions': 143, 'deletions': 11}
        m = measure(commit(), files, stats, 'github')
        self.assertEqual(m['included'], {'added': 3, 'removed': 1})
        self.assertEqual(m['excluded'], {'added': 140, 'removed': 10})
        self.assertTrue(m['complete'])
        self.assertEqual(measure(commit(parents=['a', 'b']), files, stats, 'github')['included']['added'], 0)
        self.assertTrue(measure(commit(parents=[]), files, stats, 'github', initial_threshold=100)['large_initial'])

    def test_truncated_diff_is_partial_not_confirmed_zero(self):
        m = measure(commit(), [{'new_path': 'main.py', 'diff': '', 'too_large': True}], {'additions': 50, 'deletions': 2}, 'gitlab')
        self.assertFalse(m['complete'])
        self.assertIn('file-totals-do-not-match-commit-stats', m['warnings'])

    def test_automatic_editor_state_is_excluded(self):
        self.assertEqual(file_reason('.obsidian/workspace.json'), 'automatic-editor-state')
        self.assertEqual(file_reason('.DS_Store'), 'automatic-editor-state')
        self.assertIsNone(file_reason('.obsidian/appearance.json'))

    def test_diff_hunk_metadata_and_code_starting_with_pluses(self):
        self.assertEqual(diff_counts('--- a/file\n+++ b/file\n@@ -1 +1 @@\n---code\n+++code'), (1, 1))

    def test_dedup_across_branches_and_pr(self):
        start, end = period(end='2026-10-15T16:00:00-03:00')
        c = Collector(Mock(), start, end)
        c.repos['gitlab:1'] = {'platform': 'gitlab'}
        c.identities['gitlab'] = {'emails': ['dev@example.test']}
        raw = {'id': 'abc', 'author_email': 'dev@example.test', 'author_name': 'Developer', 'authored_date': '2026-10-12T03:00:00Z', 'committed_date': '2026-10-12T03:00:00Z', 'message': 'Fix form', 'parent_ids': ['p']}
        for ref in ('main', 'feature', 'mr:1'):
            c.add_commits('gitlab:1', [raw], ref)
        self.assertEqual(len(c.commits), 1)
        self.assertEqual(c.duplicates, 2)
        self.assertEqual(len(c.commits[('gitlab:1', 'abc')]['found_in']), 3)
        raw['id'] = 'outside'; raw['committed_date'] = '2026-10-12T02:59:59Z'
        c.add_commits('gitlab:1', [raw], 'main')
        self.assertEqual(len(c.commits), 1)

    def test_submodules_exclude_pointers_but_keep_configuration(self):
        diff = '@@ -1 +1 @@\n-Subproject commit ' + 'a' * 40 + '\n+Subproject commit ' + 'b' * 40
        for platform, files in (
            ('github', [{'filename': 'modules/lib', 'patch': diff, 'additions': 1, 'deletions': 1}]),
            ('gitlab', [{'new_path': 'modules/lib', 'diff': diff, 'a_mode': '160000', 'b_mode': '160000'}]),
        ):
            m = measure(commit(), files, {'additions': 1, 'deletions': 1}, platform)
            self.assertEqual(m['included'], {'added': 0, 'removed': 0})
            self.assertEqual(m['excluded'], {'added': 1, 'removed': 1})
            self.assertEqual(m['files'][0]['excluded_reason'], 'submodule-pointer')
            self.assertTrue(m['complete'])
        self.assertIsNone(file_reason('.gitmodules', '+url = https://example.test/lib'))
        m = measure(commit(), [{'filename': '.gitmodules', 'additions': 1, 'deletions': 0,
                               'patch': '@@ -0,0 +1 @@\n+url = https://example.test/lib'}],
                    {'additions': 1, 'deletions': 0}, 'github')
        self.assertEqual(m['included']['added'], 1)

    def test_merge_commit_counts_once_without_integration_lines(self):
        c = commit(parents=['a', 'b'])
        c['repository'] = 'github:1'
        c['measurement'] = measure(c, [{'filename': 'main.py', 'additions': 4, 'deletions': 1, 'patch': '@@ -1 +1 @@\n-old\n+new'}],
                                   {'additions': 4, 'deletions': 1}, 'github')
        audit = {'repositories': [{'id': 'github:1', 'name': 'Example', 'platform': 'github'}], 'commits': [c], 'reviews': [],
                 'period': {'start': '2026-10-12', 'end': '2026-10-15'}, 'criteria': {},
                 'sources': {p: {'status': 'complete', 'note': ''} for p in ('github', 'gitlab')}}
        project = build_dashboard(audit)['projects'][0]
        self.assertEqual((project['commits'], project['added'], project['removed']), (1, 0, 0))

    def test_squash_exclusion_does_not_remove_fast_forward_original(self):
        for aggregate, originals, merged, excluded in [('squash', ['a', 'b'], True, True),
                                                       ('b', ['a', 'b'], True, False),
                                                       ('squash', ['a', 'b'], False, False)]:
            with self.subTest(aggregate=aggregate, merged=merged):
                start, end = period(end='2026-10-15T16:00:00-03:00')
                c = Collector(Mock(), start, end)
                c.repos['gitlab:1'] = {'platform': 'gitlab', 'empty': False, 'remote_id': 1}
                c.identities['gitlab'] = {'id': 10, 'emails': ['dev@example.test']}
                c.commits[('gitlab:1', aggregate)] = commit(sha=aggregate)
                review = {'iid': 1, 'author': {'id': 10}, 'title': 'Fix validation', 'state': 'merged' if merged else 'opened',
                          'created_at': '2026-10-12T03:00:00Z', 'updated_at': '2026-10-13T03:00:00Z',
                          'merged_at': '2026-10-13T03:00:00Z' if merged else None, 'squash_commit_sha': aggregate}
                raw = [{'id': sha, 'author_email': 'dev@example.test', 'authored_date': '2026-10-12T03:00:00Z',
                        'committed_date': '2026-10-12T03:00:00Z', 'message': 'Fix validation', 'parent_ids': ['parent']} for sha in originals]
                c.commits[('gitlab:1', aggregate)]['found_in'] = []
                with patch('collector.collect.pages', side_effect=[({'gitlab:1': [review]}, {}, {}), ({'gitlab:1:1': raw}, {}, {})]):
                    c.review_evidence()
                self.assertEqual('aggregate_of_review' in c.commits[('gitlab:1', aggregate)], excluded)

    def test_pagination_and_partial_error(self):
        bridge = Mock()
        bridge.many.side_effect = [[{'result': {'data': list(range(100))}}], [{'error': 'Rate limited'}]]
        data, errors, _ = pages(bridge, {'r': ('gitlab_list_commits', {'project_id': 1})})
        self.assertEqual(len(data['r']), 100)
        self.assertIn('r', errors)
        self.assertEqual(bridge.many.call_args.args[0][0][1]['page'], 2)

    def test_bridge_rejects_writes_and_external_hosts(self):
        self.assertRaises(ValueError, validate_call, {'tool': 'github_create_commit', 'arguments': {}})
        self.assertRaises(ValueError, validate_call, {'tool': 'github_fetch', 'arguments': {'url': 'https://evil.example/repos/a/b'}})
        validate_call({'tool': 'github_fetch', 'arguments': {'url': 'https://api.github.com/repos/example/repo/commits'}})

    def test_empty_sources_preserve_unknown_status(self):
        audit = {'repositories': [], 'commits': [], 'reviews': [], 'period': {'start': '2026-10-12T00:00:00-03:00', 'end': '2026-10-15T16:00:00-03:00'},
                 'criteria': {}, 'sources': {'github': {'status': 'unavailable', 'note': 'Disconnected'}, 'gitlab': {'status': 'complete', 'note': 'Checked'}}}
        data = build_dashboard(audit)
        self.assertFalse(data['demo'])
        self.assertEqual(data['projects'], [])
        self.assertEqual(data['sources']['github']['status'], 'unavailable')

    def test_summary_keeps_evidence(self):
        digest = evidence_summary([commit()], [])
        self.assertIn('Corrige validação do formulário', digest['text'])
        self.assertEqual(digest['evidence'], ['commit:abc'])


if __name__ == '__main__':
    unittest.main()
