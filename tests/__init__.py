import os
import shutil
import requests
import unittest
from orderedattrdict import AttrDict
from . import server
from gramex import conf
from gramex.http import OK
from gramex.services import info

tempfiles = AttrDict()
folder = os.path.dirname(os.path.abspath(__file__))


def setUp():
    # Remove uploads folder before Gramex locks .meta.h5
    # This may fail on Python 2.7 on Windows due to unicode characters.
    # Delete tests/uploads/ manually in that case
    upload_path = os.path.join(folder, 'uploads')
    if os.path.exists(upload_path):
        shutil.rmtree(upload_path)
    server.start_gramex()


def tearDown():
    server.stop_gramex()

    for filename in tempfiles.values():
        if os.path.exists(filename):
            os.unlink(filename)


class TestGramex(unittest.TestCase):
    '''Base class to test Gramex running as a subprocess'''

    def get(self, url, session=None, method='get', timeout=10, **kwargs):
        req = session or requests
        return getattr(req, method)(server.base_url + url, timeout=timeout, **kwargs)

    def check(self, url, data=None, path=None, code=200, text=None, no_text=None,
              headers=None, session=None, method='get', timeout=10):
        r = self.get(url, session=session, data=data, method=method, timeout=timeout)
        self.assertEqual(r.status_code, code, '%s: code %d != %d' % (url, r.status_code, code))
        if text is not None:
            self.assertIn(text, r.text, '%s: %s not in %s' % (url, text, r.text))
        if no_text is not None:
            self.assertNotIn(text, r.text, '%s: %s should not be in %s' % (url, text, r.text))
        if path is not None:
            with (server.info.folder / path).open('rb') as file:
                self.assertEqual(r.content, file.read(), '%s != %s' % (url, path))
        if headers is not None:
            for header, value in headers.items():
                if value is None or value is False:
                    self.assertFalse(header in r.headers,
                                     '%s: should not have header %s' % (url, header))
                elif value is True:
                    self.assertTrue(header in r.headers,
                                    '%s: should have header %s' % (url, header))
                else:
                    actual = r.headers[header]
                    self.assertEqual(actual, value,
                                     '%s: header %s = %s != %s' % (url, header, actual, value))
        return r


class TestSchedule(TestGramex):

    def test_schedule(self):
        # Run this test as soon as Gramex starts to check if schedule has run.
        self.assertIn('schedule-key', info, 'Schedule was run at startup')
        self.check('/', code=OK)

        # This tests that long running threads run in parallel. We run
        # utils.slow_count every 10ms for kwargs.count seconds. If this test
        # fails, increase schedule.schedule-startup-slow.kwargs.count. It may be
        # due to slow startup.
        max_count = conf.schedule['schedule-startup-slow'].kwargs.count - 1
        self.assertTrue(0 < info['schedule-count'] < max_count, 'Schedule still running')
