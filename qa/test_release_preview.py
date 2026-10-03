import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from publish_release import GitHubAPI, publish_candidate
from release_contract import mark_published, write_candidate
from verify_release import verify_remote


class ReleasePreviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='rv-preview-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.expected = {}
        self.assets = []
        for name in ('RV-Setup.zip', 'RV-Host-Tools.zip', 'RV-Third-Party-Sources.zip', 'RV-World-Template.zip', 'SHA256SUMS.txt'):
            data = name.encode()
            (self.root / name).write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            self.assets.append({'name': name, 'digest': 'sha256:' + digest, 'size': len(data), 'state': 'uploaded'})
            if name != 'SHA256SUMS.txt':
                self.expected[name] = digest
        self.release = {'draft': False, 'prerelease': True, 'tag_name': 'v2.0.0', 'assets': self.assets}

    def verify(self, release=None, latest='v1.2.1', prerelease=True):
        documents = [release or self.release, {'tag_name': latest}]
        with patch('verify_release.urllib.request.urlopen', side_effect=[io.BytesIO(json.dumps(item).encode()) for item in documents]):
            verify_remote(self.root, 'v2.0.0', self.expected, prerelease)

    def test_preview_preserves_stable_update_target(self):
        self.verify()

    def test_preview_cannot_be_latest(self):
        with self.assertRaisesRegex(ValueError, 'replaced stable latest'):
            self.verify(latest='v2.0.0')

    def test_stable_verification_cannot_accept_preview(self):
        with self.assertRaisesRegex(ValueError, 'preview status'):
            self.verify(prerelease=False)

    def test_stable_release_must_be_latest(self):
        release = {**self.release, 'prerelease': False}
        with self.assertRaisesRegex(ValueError, 'not latest'):
            self.verify(release=release, prerelease=False)
        self.verify(release=release, latest='v2.0.0', prerelease=False)

    def test_preview_requires_exact_uploaded_asset_bytes(self):
        for field, value in (('digest', 'sha256:' + '0' * 64), ('size', 0), ('state', 'new')):
            with self.subTest(field=field):
                release = copy.deepcopy(self.release)
                release['assets'][0][field] = value
                with self.assertRaises(ValueError):
                    self.verify(release=release)

    def test_preview_rejects_draft_wrong_tag_and_extra_asset(self):
        for field, value in (('draft', True), ('tag_name', 'v2.0.1')):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.verify(release={**self.release, field: value})
        with self.assertRaisesRegex(ValueError, 'Unexpected release assets'):
            self.verify(release={**self.release, 'assets': self.assets + [self.assets[0]]})


class InterceptedGitHub:
    PREFIX = '/repos/rudyvale/rv-warfare'

    def __init__(self):
        self.releases = {}
        self.calls = []
        self.push = True
        self.by_tag_missing = True
        self.failures = {}
        self.after_write = None
        self.after_read = None

    def add(self, release):
        self.releases[release['id']] = copy.deepcopy(release)

    def writes(self, method=None):
        return [call for call in self.calls if call['method'] != 'GET' and (method is None or call['method'] == method)]

    def open(self, request, timeout):
        method = request.get_method()
        url = urllib.parse.urlsplit(request.full_url)
        if url.hostname not in ('api.github.com', 'uploads.github.com'):
            raise AssertionError('Unexpected network request: ' + request.full_url)
        path = url.path + ('?' + url.query if url.query else '')
        body = json.loads(request.data) if request.data and request.get_header('Content-type') == 'application/json' else request.data
        call = {'method': method, 'path': path, 'body': copy.deepcopy(body), 'timeout': timeout}
        self.calls.append(call)
        failure = self.failures.get((method, path))
        if failure is not None:
            raise failure
        if path == self.PREFIX and method == 'GET':
            response = {'permissions': {'push': self.push}}
        elif path.startswith(self.PREFIX + '/releases/tags/') and method == 'GET':
            tag = path.rsplit('/', 1)[1]
            matches = [release for release in self.releases.values() if release['tag_name'] == tag and not release['draft']]
            if not matches and not self.by_tag_missing:
                matches = [release for release in self.releases.values() if release['tag_name'] == tag]
            if not matches:
                raise urllib.error.HTTPError(request.full_url, 404, 'Not Found', {}, None)
            response = matches[0]
        elif path.startswith(self.PREFIX + '/releases?') and method == 'GET':
            page = int(urllib.parse.parse_qs(url.query)['page'][0])
            response = list(self.releases.values())[(page - 1) * 100:page * 100]
        elif path == self.PREFIX + '/releases' and method == 'POST':
            identifier = max(self.releases, default=400) + 1
            response = {**body, 'id': identifier, 'assets': [], 'upload_url': 'https://uploads.github.com' + self.PREFIX + '/releases/' + str(identifier) + '/assets{?name,label}', 'html_url': 'https://github.com/rudyvale/rv-warfare/releases/tag/' + body['tag_name']}
            self.add(response)
        elif url.hostname == 'uploads.github.com' and method == 'POST':
            identifier = int(url.path.split('/')[-2])
            name = urllib.parse.parse_qs(url.query)['name'][0]
            response = {'name': name, 'size': len(body), 'digest': 'sha256:' + hashlib.sha256(body).hexdigest(), 'state': 'uploaded'}
            self.releases[identifier]['assets'].append(copy.deepcopy(response))
        elif path.startswith(self.PREFIX + '/releases/'):
            identifier = int(path.rsplit('/', 1)[1])
            if identifier not in self.releases:
                raise urllib.error.HTTPError(request.full_url, 404, 'Not Found', {}, None)
            if method == 'PATCH':
                self.releases[identifier].update(body)
                if 'tag_name' not in body:
                    self.releases[identifier]['tag_name'] = 'untagged-53e6360d76793728fa2b'
            elif method != 'GET':
                raise AssertionError('Unexpected method: ' + method)
            response = self.releases[identifier]
        else:
            raise AssertionError('Unexpected request: ' + method + ' ' + path)
        if method != 'GET' and self.after_write is not None:
            self.after_write(call, response)
        if method == 'GET' and self.after_read is not None:
            self.after_read(call, response)
        return io.BytesIO(json.dumps(response).encode())


class ReleasePublisherTests(unittest.TestCase):
    COMMIT = 'b' * 40
    VERSION = '2.0.1'
    TAG = 'v2.0.1'
    NAME = 'RV Warfare 2.0.1 Preview'
    NOTES = 'Verified preview notes with the exact source and limits.'
    ID = 402702137

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='rv-publisher-api-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.assets = []
        lines = []
        for name in ('RV-Setup.zip', 'RV-Host-Tools.zip', 'RV-Third-Party-Sources.zip', 'RV-World-Template.zip'):
            data = ('exact candidate bytes ' + name).encode()
            (self.root / name).write_bytes(data)
            lines.append(hashlib.sha256(data).hexdigest() + '  ' + name)
        (self.root / 'SHA256SUMS.txt').write_text('\n'.join(lines) + '\n', encoding='ascii')
        for file in self.root.iterdir():
            data = file.read_bytes()
            self.assets.append({'name': file.name, 'size': len(data), 'digest': 'sha256:' + hashlib.sha256(data).hexdigest(), 'state': 'uploaded'})
        write_candidate(self.root, self.VERSION)
        self.github = InterceptedGitHub()
        transport = patch('publish_release.urllib.request.urlopen', side_effect=self.github.open)
        transport.start()
        self.addCleanup(transport.stop)
        output = patch('builtins.print')
        output.start()
        self.addCleanup(output.stop)
        self.api = GitHubAPI('intercepted-fixture-token')

    def draft(self, **changes):
        return {'id': self.ID, 'tag_name': self.TAG, 'target_commitish': self.COMMIT, 'name': self.NAME, 'body': self.NOTES, 'draft': True, 'prerelease': True, 'assets': copy.deepcopy(self.assets), 'upload_url': 'https://uploads.github.com' + self.github.PREFIX + '/releases/' + str(self.ID) + '/assets{?name,label}', 'html_url': 'https://github.com/rudyvale/rv-warfare/releases/tag/' + self.TAG, **changes}

    def publish(self, **options):
        return publish_candidate(self.api, 'rudyvale/rv-warfare', self.VERSION, self.COMMIT, self.root, self.NOTES, **{'publish': True, 'prerelease': True, **options})

    def assert_full_patches(self, latest='false'):
        patches = self.github.writes('PATCH')
        self.assertTrue(patches)
        for call in patches:
            self.assertEqual(set(call['body']), {'tag_name', 'target_commitish', 'name', 'body', 'draft', 'prerelease', 'make_latest'})
            self.assertEqual(call['body']['tag_name'], self.TAG)
            self.assertEqual(call['body']['target_commitish'], self.COMMIT)
            self.assertEqual(call['body']['body'], self.NOTES)
        self.assertEqual(patches[-1]['body']['make_latest'], latest)

    def test_by_tag_404_resumes_existing_draft_without_creating_release(self):
        self.github.add(self.draft())
        result = self.publish()
        self.assertEqual(result['id'], self.ID)
        self.assertFalse(result['draft'])
        self.assertEqual(self.github.writes('POST'), [])
        self.assert_full_patches()
        self.assertEqual(len(self.github.releases), 1)
        self.assertEqual(json.loads((self.root / '.release-upload.json').read_text())['releaseId'], self.ID)

    def test_known_id_recovers_untagged_alias_and_restores_all_metadata(self):
        self.github.add(self.draft(tag_name='untagged-53e6360d76793728fa2b', body='Earlier draft notes'))
        result = self.publish(known_id=self.ID)
        self.assertEqual(result['tag_name'], self.TAG)
        self.assertEqual(result['body'], self.NOTES)
        self.assertEqual(self.github.writes('POST'), [])
        self.assert_full_patches()

    def test_unique_alias_can_be_recovered_from_exact_source_name_and_notes(self):
        self.github.add(self.draft(tag_name='untagged-53e6360d76793728fa2b'))
        self.assertEqual(self.publish()['id'], self.ID)
        self.assertEqual(self.github.writes('POST'), [])

    def test_unidentified_alias_with_other_notes_is_not_mutated(self):
        self.github.add(self.draft(tag_name='untagged-53e6360d76793728fa2b', body='Unrelated notes'))
        with self.assertRaisesRegex(ValueError, 'tag differs'):
            self.publish()
        self.assertEqual(self.github.writes(), [])

    def test_full_patch_avoids_the_observed_partial_patch_tag_alias_hazard(self):
        self.github.add(self.draft(body='Earlier notes'))
        self.assertEqual(self.publish()['tag_name'], self.TAG)
        self.assert_full_patches()
        self.assertEqual(self.github.releases[self.ID]['tag_name'], self.TAG)

    def test_post_patch_reread_catches_metadata_drift_before_upload_or_publish(self):
        self.github.add(self.draft())
        def mutate(call, response):
            if call['method'] == 'GET' and self.github.writes('PATCH') and isinstance(response, dict) and response.get('id') == self.ID:
                response['tag_name'] = 'untagged-bad-metadata'
        self.github.after_read = mutate
        with self.assertRaisesRegex(ValueError, 'tag differs'):
            self.publish()
        self.assertEqual(len(self.github.writes('PATCH')), 1)
        self.assertEqual(self.github.writes('POST'), [])
        self.assertTrue(self.github.releases[self.ID]['draft'])

    def test_partial_upload_resumes_only_missing_exact_assets(self):
        self.github.add(self.draft(assets=self.assets[:2]))
        result = self.publish()
        uploaded = [urllib.parse.parse_qs(urllib.parse.urlsplit(call['path']).query)['name'][0] for call in self.github.writes('POST')]
        self.assertEqual(set(uploaded), {asset['name'] for asset in self.assets[2:]})
        self.assertEqual(len(uploaded), 3)
        self.assertEqual({asset['name']: asset['digest'] for asset in result['assets']}, {asset['name']: asset['digest'] for asset in self.assets})

    def test_new_candidate_creates_only_one_draft_after_complete_discovery(self):
        result = self.publish(publish=False)
        creates = [call for call in self.github.writes('POST') if call['path'] == self.github.PREFIX + '/releases']
        self.assertEqual(len(creates), 1)
        self.assertTrue(result['draft'])
        first_write = next(index for index, call in enumerate(self.github.calls) if call['method'] != 'GET')
        self.assertTrue(any('/releases?per_page=' in call['path'] for call in self.github.calls[:first_write]))
        self.assertEqual(creates[0]['body']['make_latest'], 'false')

    def test_pagination_finds_draft_beyond_first_page(self):
        for identifier in range(1, 101):
            self.github.add(self.draft(id=identifier, tag_name='v0.' + str(identifier) + '.0', name='Older release ' + str(identifier), draft=False))
        self.github.add(self.draft())
        self.assertEqual(self.publish()['id'], self.ID)
        self.assertTrue(any(call['path'].endswith('page=2') for call in self.github.calls))
        self.assertEqual(self.github.writes('POST'), [])

    def test_duplicate_matching_drafts_are_refused_even_with_known_id(self):
        self.github.add(self.draft())
        self.github.add(self.draft(id=self.ID + 1, tag_name='untagged-duplicate'))
        with self.assertRaisesRegex(ValueError, 'Multiple releases'):
            self.publish(known_id=self.ID)
        self.assertEqual(self.github.writes(), [])

    def test_published_and_draft_duplicate_are_refused(self):
        self.github.add(self.draft(draft=False))
        self.github.add(self.draft(id=self.ID + 1))
        with self.assertRaisesRegex(ValueError, 'Multiple releases'):
            self.publish()
        self.assertEqual(self.github.writes(), [])

    def test_unexpected_target_mode_tag_name_and_status_are_refused(self):
        cases = ({'target_commitish': 'main'}, {'prerelease': False}, {'tag_name': 'v2.0.2'}, {'name': 'Another project'}, {'draft': 'true'})
        for changes in cases:
            with self.subTest(changes=changes):
                self.github.releases.clear()
                self.github.calls.clear()
                self.github.add(self.draft(**changes))
                with self.assertRaises(ValueError):
                    self.publish(known_id=self.ID)
                self.assertEqual(self.github.writes(), [])

    def test_unexpected_duplicate_and_corrupt_assets_are_refused_before_any_write(self):
        bad = copy.deepcopy(self.assets[0])
        bad['digest'] = 'sha256:' + '0' * 64
        pending = {**self.assets[0], 'state': 'new'}
        wrong_size = {**self.assets[0], 'size': True}
        cases = (self.assets + [{'name': 'secret.zip'}], self.assets + [self.assets[0]], [bad] + self.assets[1:], [pending] + self.assets[1:], [wrong_size] + self.assets[1:])
        for assets in cases:
            with self.subTest(assets=assets):
                self.github.releases.clear()
                self.github.calls.clear()
                self.github.add(self.draft(assets=assets))
                with self.assertRaises(ValueError):
                    self.publish()
                self.assertEqual(self.github.writes(), [])

    def test_known_missing_id_never_creates_a_replacement(self):
        with self.assertRaisesRegex(RuntimeError, 'HTTP 404'):
            self.publish(known_id=self.ID)
        self.assertEqual(self.github.writes(), [])

    def test_without_push_access_404_cannot_be_treated_as_no_draft(self):
        self.github.push = False
        with self.assertRaisesRegex(ValueError, 'Push access'):
            self.publish()
        self.assertEqual(self.github.writes(), [])

    def test_tag_list_and_id_read_timeout_never_create_or_patch(self):
        for path in (self.github.PREFIX + '/releases/tags/' + self.TAG, self.github.PREFIX + '/releases?per_page=100&page=1', self.github.PREFIX + '/releases/' + str(self.ID)):
            with self.subTest(path=path):
                self.github.calls.clear()
                self.github.failures = {('GET', path): TimeoutError('intercepted read timeout')}
                with self.assertRaises(TimeoutError):
                    self.publish(known_id=self.ID)
                self.assertEqual(self.github.writes(), [])

    def test_listing_http_404_403_and_503_do_not_create_a_draft(self):
        path = self.github.PREFIX + '/releases?per_page=100&page=1'
        for status in (404, 403, 503):
            with self.subTest(status=status):
                self.github.calls.clear()
                self.github.failures = {('GET', path): urllib.error.HTTPError('https://api.github.com' + path, status, 'Intercepted failure', {}, None)}
                with self.assertRaisesRegex(RuntimeError, 'HTTP ' + str(status)):
                    self.publish()
                self.assertEqual(self.github.writes(), [])

    def test_creation_timeout_after_server_acceptance_resumes_same_id(self):
        def fail(call, response):
            if call['path'] == self.github.PREFIX + '/releases':
                raise TimeoutError('response lost after creating the draft')
        self.github.after_write = fail
        with self.assertRaises(TimeoutError):
            self.publish()
        state = json.loads((self.root / '.release-upload.json').read_text())
        self.assertIsNone(state['releaseId'])
        self.assertEqual(len(self.github.releases), 1)
        identifier = next(iter(self.github.releases))
        self.github.after_write = None
        self.assertEqual(self.publish()['id'], identifier)
        creates = [call for call in self.github.writes('POST') if call['path'] == self.github.PREFIX + '/releases']
        self.assertEqual(len(creates), 1)

    def test_creation_timeout_without_visible_outcome_refuses_second_create(self):
        path = self.github.PREFIX + '/releases'
        self.github.failures[('POST', path)] = TimeoutError('uncertain create')
        with self.assertRaises(TimeoutError):
            self.publish()
        self.github.failures.clear()
        with self.assertRaisesRegex(ValueError, 'outcome is uncertain'):
            self.publish()
        self.assertEqual(len(self.github.writes('POST')), 1)

    def test_upload_timeout_after_acceptance_resumes_without_duplicate_asset(self):
        self.github.add(self.draft(assets=self.assets[:2]))
        def fail(call, response):
            if '/assets?name=' in call['path']:
                raise TimeoutError('upload response lost')
        self.github.after_write = fail
        with self.assertRaises(TimeoutError):
            self.publish()
        self.github.after_write = None
        result = self.publish()
        self.assertEqual(len(result['assets']), 5)
        uploads = [call['path'] for call in self.github.writes('POST')]
        self.assertEqual(len(uploads), 3)
        self.assertEqual(len(set(uploads)), 3)

    def test_publish_timeout_after_acceptance_only_verifies_published_release_on_retry(self):
        self.github.add(self.draft())
        def fail(call, response):
            if call['method'] == 'PATCH' and call['body']['draft'] is False:
                raise TimeoutError('publish response lost')
        self.github.after_write = fail
        with self.assertRaises(TimeoutError):
            self.publish()
        self.assertFalse(self.github.releases[self.ID]['draft'])
        writes = len(self.github.writes())
        self.github.after_write = None
        self.assertFalse(self.publish()['draft'])
        self.assertEqual(len(self.github.writes()), writes)

    def test_published_exact_release_is_read_only_and_incomplete_release_is_refused(self):
        self.github.add(self.draft(draft=False))
        self.assertFalse(self.publish()['draft'])
        self.assertEqual(self.github.writes(), [])
        self.github.releases[self.ID]['assets'].pop()
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.publish()
        self.assertEqual(self.github.writes(), [])

    def test_published_candidate_cannot_recreate_missing_or_reverted_release(self):
        mark_published(self.root, self.VERSION, self.COMMIT, 'https://github.com/rudyvale/rv-warfare/releases/tag/' + self.TAG)
        with self.assertRaisesRegex(ValueError, 'Published candidate state'):
            self.publish()
        self.github.add(self.draft())
        with self.assertRaisesRegex(ValueError, 'Published candidate state'):
            self.publish()
        self.assertEqual(self.github.writes(), [])

    def test_stable_publication_explicitly_selects_latest(self):
        self.github.add(self.draft(name='RV Warfare ' + self.VERSION, prerelease=False))
        result = self.publish(prerelease=False)
        patches = self.github.writes('PATCH')
        self.assertFalse(result['prerelease'])
        self.assertEqual(patches[0]['body']['make_latest'], 'false')
        self.assertEqual(patches[-1]['body']['make_latest'], 'true')
        self.assertEqual(set(patches[-1]['body']), {'tag_name', 'target_commitish', 'name', 'body', 'draft', 'prerelease', 'make_latest'})

    def test_invalid_successful_by_tag_response_cannot_create_another_release(self):
        self.github.add(self.draft(draft=False))
        def mutate(call, response):
            if '/releases/tags/' in call['path']:
                response['tag_name'] = 'v2.0.2'
                response['name'] = 'Unrelated release'
        self.github.after_read = mutate
        with self.assertRaisesRegex(ValueError, 'tag differs'):
            self.publish()
        self.assertEqual(self.github.writes(), [])

    def test_conflicting_upload_receipt_is_refused_before_network_access(self):
        self.github.add(self.draft())
        self.publish(publish=False)
        state_path = self.root / '.release-upload.json'
        state = json.loads(state_path.read_text())
        state['commit'] = 'a' * 40
        state_path.write_text(json.dumps(state))
        self.github.calls.clear()
        with self.assertRaisesRegex(ValueError, 'another candidate'):
            self.publish()
        self.assertEqual(self.github.calls, [])

    def test_saved_id_disagreement_and_missing_saved_id_never_create_replacement(self):
        self.github.add(self.draft())
        self.publish(publish=False)
        self.github.calls.clear()
        with self.assertRaisesRegex(ValueError, 'differs from the upload receipt'):
            self.publish(known_id=self.ID + 1)
        self.assertEqual(self.github.calls, [])
        self.github.releases.clear()
        with self.assertRaisesRegex(RuntimeError, 'HTTP 404'):
            self.publish()
        self.assertEqual(self.github.writes(), [])

    def test_metadata_patch_response_cannot_silently_publish_or_change_source(self):
        self.github.add(self.draft())
        def mutate(call, response):
            if call['method'] == 'PATCH':
                response['target_commitish'] = 'a' * 40
        self.github.after_write = mutate
        with self.assertRaisesRegex(ValueError, 'target differs'):
            self.publish()
        self.assertTrue(self.github.releases[self.ID]['draft'])
        self.assertEqual(len(self.github.writes()), 1)

    def test_missing_final_tag_read_can_be_retried_without_mutating_published_release(self):
        self.github.add(self.draft())
        path = self.github.PREFIX + '/releases/tags/' + self.TAG
        def fail(call, response):
            if call['method'] == 'PATCH' and call['body']['draft'] is False:
                self.github.failures[('GET', path)] = urllib.error.HTTPError('https://api.github.com' + path, 404, 'Tag not visible yet', {}, None)
        self.github.after_write = fail
        with self.assertRaisesRegex(RuntimeError, 'HTTP 404'):
            self.publish()
        writes = len(self.github.writes())
        self.github.after_write = None
        self.github.failures.clear()
        self.assertFalse(self.publish()['draft'])
        self.assertEqual(len(self.github.writes()), writes)

    def test_concurrent_create_intent_is_not_overwritten(self):
        import publish_release
        original = publish_release.save_upload_state
        def race(path, identity, identifier=None, create=False):
            if create:
                original(path, identity, create=True)
            return original(path, identity, identifier, create=create)
        with patch('publish_release.save_upload_state', side_effect=race):
            with self.assertRaises(FileExistsError):
                self.publish()
        self.assertEqual(self.github.writes(), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
