import copy
import unittest

import cloud_sync as sync


def cloud(words=455125):
    counts = dict.fromkeys(sync.FIELDS, 0)
    counts['words'] = words
    return {'protocol': 2, 'global': counts.copy(), 'device_count': 1,
            'devices': [dict(counts, device_id='desktop', device_name='Desktop', revision=7)]}


class CloudSyncTests(unittest.TestCase):
    def test_cloud_percentage_basis_and_offline_local(self):
        cache = {'endpoint': 'https://one.test', 'totals': cloud()}
        self.assertEqual(sync.progress_words(200000, True, 'https://one.test', cache), 455125)
        self.assertEqual(sync.progress_words(200000, False, '', cache), 200000)
        self.assertIsNone(sync.progress_words(200000, True, 'https://two.test', cache))
        self.assertIsNone(sync.progress_words(200000, True, 'https://one.test', None))

    def test_revision_and_local_cumulative_payload(self):
        totals = dict.fromkeys(sync.FIELDS, 20)
        payload = sync.make_payload(('desktop', 'Desktop'), totals, cloud())
        self.assertEqual(payload['expected_revision'], 7)
        self.assertEqual(payload['totals'], totals)
        self.assertNotIn('days', payload)
        self.assertEqual(sync.make_payload(('new', 'Desktop'), totals, cloud())['expected_revision'], 0)

    def test_old_worker_rejected_before_upload(self):
        old = cloud(); old.pop('protocol')
        with self.assertRaisesRegex(ValueError, 'Update your cloud Worker'):
            sync.make_payload(('desktop', 'Desktop'), old['global'], old)

    def test_bad_response_does_not_replace_good_progress(self):
        invalid = cloud(); invalid['global']['words'] = 123
        with self.assertRaises(ValueError): sync.validate_cloud(invalid)
        self.assertIsNone(sync.progress_words(10, True, 'one', {'endpoint': 'one', 'totals': invalid}))
        for value in [True, -1, 2**53, 0.5, '10']:
            bad = cloud(); bad['devices'][0]['words'] = value
            with self.assertRaises(ValueError): sync.validate_cloud(bad)
        duplicate = cloud(); duplicate['devices'] *= 2
        with self.assertRaises(ValueError): sync.validate_cloud(duplicate)


if __name__ == '__main__': unittest.main()
