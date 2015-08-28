from dscan.common.async import request_url, REQUEST_DEFAULTS
from dscan.plugins.internal.async_scan import _identify_url_file, identify_lines, \
    identify_line, identify_url
from dscan import tests
from mock import patch
from twisted.internet.defer import Deferred, succeed, fail
from twisted.internet import reactor
from twisted.internet import ssl
from twisted.trial.unittest import TestCase
from twisted.web.error import PageRedirect, Error
from twisted.web import client
import dscan
import dscan.common.plugins_util as pu
import os


ASYNC = 'dscan.common.async.'
ASYNC_SCAN = 'dscan.plugins.internal.async_scan.'

def f():
    """
    Returns a failed deferrer.
    """
    return fail(Exception('Failed'))

def s():
    """
    Returns a successful deferrer.
    """
    return succeed('')

class AsyncTests(TestCase):
    timeout = 3
    prev_cwd = None

    base_url = 'http://wiojqiowdjqoiwdjoqiwjdoqiwjfoqiwjfqowijf.com/'

    lines = ['http://adhwuiaihduhaknbacnckajcwnncwkakncw.com/\n',
            'http://adhwuiaihduhaknbacnckajcwnncwkakncx.com/\n',
            'http://adhwuiaihduhaknbacnckajcwnncwkakncy.com/\n']

    def setUp(self):
        self.prev_cwd = os.getcwd()
        # http://comments.gmane.org/gmane.comp.python.twisted/18676
        os.chdir(os.path.dirname(dscan.PWD[:-1]))

    def tearDown(self):
        os.chdir(self.prev_cwd)

    def test_lines_get_read(self):
        d = Deferred()
        def side_effect(lines):
            if len(lines) == 3:
                d.callback(lines)
            else:
                d.errback(lines)

            return d

        with patch(ASYNC_SCAN + 'identify_lines', side_effect=side_effect) as il:
            _identify_url_file(tests.VALID_FILE)

        return d

    @patch(ASYNC_SCAN + 'identify_line', autospec=True)
    def test_calls_identify_line(self, il):
        dl = identify_lines(self.lines)
        calls = il.call_args_list
        self.assertEquals(len(calls), len(self.lines))
        for i, comb_args in enumerate(calls):
            args, kwargs = comb_args
            self.assertEquals(args[0], self.lines[i])

    @patch(ASYNC_SCAN + 'error_line', autospec=True)
    def test_calls_identify_line_errback(self, el):
        ret = [f(), f(), s()]
        with patch(ASYNC_SCAN + 'identify_line', side_effect=ret) as il:
            dl = identify_lines(self.lines)
            calls = el.call_args_list
            self.assertEquals(len(calls), len(self.lines) - 1)
            for i, comb_args in enumerate(calls):
                args, kwargs = comb_args
                self.assertEquals(args[0],self.lines[i])

    @patch(ASYNC_SCAN + 'request_url', autospec=True)
    def test_identify_strips_url(self, ru):
        stripped = self.lines[0].strip()
        identify_line(self.lines[0])

        args, kwargs = ru.call_args
        self.assertEquals(ru.call_count, 1)
        self.assertEquals(args[0], stripped)

    @patch(ASYNC_SCAN + 'request_url', autospec=True)
    def test_identify_strips_url(self, ru):
        stripped = self.lines[0].strip()
        identify_line(self.lines[0])

        args, kwargs = ru.call_args
        self.assertEquals(ru.call_count, 1)
        self.assertEquals(args[0], stripped)

    @patch(ASYNC_SCAN + 'request_url', autospec=True)
    def test_identify_accepts_space_separated_hosts(self, ru):
        file_ip = open(tests.VALID_FILE_IP)
        for i, line in enumerate(file_ip):
            if i < 2:
                expected_url, expected_host = ('http://192.168.1.1/',
                        'example.com')
            elif i == 2:
                expected_url, expected_host = ('http://192.168.1.2/drupal/',
                        'example.com')

            identify_line(line)

            args, kwargs = ru.call_args_list[-1]
            self.assertEquals(args[0], expected_url)
            self.assertEquals(args[1], expected_host)

    @patch(ASYNC + 'reactor', autospec=True)
    def test_request_url_http(self, r):
        url = 'http://google.com/'
        host = None

        request_url(url, host)
        ct = r.connectTCP

        self.assertEquals(ct.call_count, 1)
        args, kwargs = ct.call_args
        self.assertEquals(args[0], 'google.com')
        self.assertEquals(args[1], 80)
        self.assertTrue(isinstance(args[2], client.HTTPClientFactory))

    @patch(ASYNC + 'reactor', autospec=True)
    def test_request_url_ssl(self, r):
        url = 'https://google.com/'
        host = None

        request_url(url, host)
        cs = r.connectSSL

        self.assertEquals(cs.call_count, 1)
        args, kwargs = cs.call_args
        self.assertEquals(args[0], 'google.com')
        self.assertEquals(args[1], 443)
        self.assertTrue(isinstance(args[2], client.HTTPClientFactory))
        self.assertTrue(isinstance(args[3], ssl.ClientContextFactory))


    @patch(ASYNC + 'client.HTTPClientFactory')
    @patch(ASYNC + 'reactor', autospec=True)
    def test_request_host_header(self, r, hcf):
        url = 'http://203.97.26.37/'
        host = 'google.com'
        url_with_host = 'http://google.com/'

        request_url(url, host)
        request_url(url_with_host, None)

        ct = r.connectTCP.call_args_list

        self.assertEquals(hcf.call_count, 2)
        args, kwargs = hcf.call_args_list[0]
        self.assertEquals(args[0], url)
        self.assertEquals(kwargs['headers']['Host'], host)
        self.assertEquals(ct[0][0][0], '203.97.26.37')

        args, kwargs = hcf.call_args_list[1]
        self.assertEquals(args[0], url_with_host)
        self.assertEquals(kwargs['headers']['Host'], host)
        self.assertEquals(ct[1][0][0], 'google.com')

    @patch(ASYNC + 'client.HTTPClientFactory')
    @patch(ASYNC + 'reactor', autospec=True)
    def test_request_defaults(self, r, hcf):
        url = 'http://google.com/'
        host = None
        defaults = REQUEST_DEFAULTS

        request_url(url, host)

        self.assertEquals(hcf.call_count, 1)
        args, kwargs = hcf.call_args

        for key in defaults:
            self.assertEquals(kwargs[key], defaults[key])

    def test_request_redirect_follow(self):
        redirect_url = 'http://urlb.com/'
        r = PageRedirect('redirect')
        r.location = redirect_url

        with patch(ASYNC_SCAN + 'request_url', autospec=True, side_effect=r) as ru:
            with patch(ASYNC_SCAN + 'identify_url', autospec=True) as iu:
                identify_line(self.lines[0])

                self.assertEquals(iu.call_count, 1)
                args, kwargs = iu.call_args

                self.assertEquals(args[0], redirect_url)

    def test_request_redirect_follow_query_string(self):
        redirect_url = 'http://urlb.com/?aa=a'
        r = PageRedirect('redirect')
        r.location = redirect_url

        with patch(ASYNC_SCAN + 'request_url', autospec=True, side_effect=r) as ru:
            with patch(ASYNC_SCAN + 'identify_url', autospec=True) as iu:
                identify_line(self.lines[0])

                args, kwargs = iu.call_args

                self.assertEquals(args[0], 'http://urlb.com/')

    def test_identify_calls_all_rfu(self):
        rfu = pu.get_rfu()
        with patch(ASYNC_SCAN + 'download_url', autospec=True) as du:
            identify_url(self.base_url, None)

            self.assertEquals(du.call_count, len(rfu))
            for i, call in enumerate(du.call_args_list):
                args, kwargs = call
                self.assertEquals(args[0], self.base_url + rfu[i])
                self.assertTrue(args[2].endswith(rfu[i]))

