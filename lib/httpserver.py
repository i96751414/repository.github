# -*- coding: utf-8 -*-

import logging
import re
import socket
import threading
import time
from shutil import copyfileobj

try:
    import urlparse
    from SocketServer import ThreadingMixIn
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    import urllib.parse as urlparse
    from socketserver import ThreadingMixIn
    from http.server import BaseHTTPRequestHandler, HTTPServer

from lib.utils import str_to_bytes


class HTTPRequestHandler(BaseHTTPRequestHandler, object):
    protocol_version = "HTTP/1.1"
    get_routes = []

    url_clean_regex = ((re.compile(r"\\"), "/"), (re.compile(r"/{2,}"), "/"))
    url_placeholders_patterns = ((re.escape("{w}"), "([^/]+)"), (re.escape("{p}"), "(.+)"))

    @classmethod
    def add_get_route(cls, pattern, handle):
        cls.get_routes.append((cls.generate_pattern(pattern), handle))

    @classmethod
    def generate_pattern(cls, s):
        pattern = s
        for regex, repl in cls.url_clean_regex:
            pattern = regex.sub(repl, pattern)
        pattern = re.escape(pattern)
        for p in cls.url_placeholders_patterns:
            pattern = pattern.replace(*p)
        return re.compile(pattern + "$")

    # noinspection PyPep8Naming
    def do_GET(self):
        self._handle_request(self.get_routes)

    def _handle_request(self, routes):
        self._response_started = False
        try:
            self.url = urlparse.urlparse(self.path)
            self.query = dict(urlparse.parse_qsl(self.url.query))

            self.url_path = self.url.path
            for r, s in self.url_clean_regex:
                self.url_path = r.sub(s, self.url_path)

            for pattern, handler in routes:
                match = pattern.match(self.url_path)
                if match:
                    handler(self, *match.groups())
                    break
            else:
                self.send_response_and_end(404)
        except Exception as e:
            if self._response_started:
                raise e
            else:
                logging.error(e, exc_info=True)
                self.send_response_and_end(500)

    def send_response(self, *args, **kwargs):
        # noinspection PyAttributeOutsideInit
        self._response_started = True
        super(HTTPRequestHandler, self).send_response(*args, **kwargs)

    def log_message(self, fmt, *args):
        logging.debug(fmt, *args)

    def send_response_with_data(self, data, content_type, code=200):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_response_and_end(self, code, message=None):
        self.send_response(code, message=message)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def send_redirect(self, url, code=301):
        self.send_response(code)
        self.send_header("Location", url)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def send_file_contents(self, fp, code, length=None, content_type=None,
                           content_disposition=None, chunked=True):
        self.send_response(code)

        if content_type:
            self.send_header("Content-Type", content_type)
        if content_disposition:
            self.send_header("Content-Disposition", content_disposition)
        if length:
            self.send_header("Content-Length", length)
            chunked = False
        else:
            if chunked:
                self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Connection", "close")

        self.end_headers()

        if chunked:
            self._send_chunked(fp)
        else:
            copyfileobj(fp, self.wfile)

    def _send_chunked(self, fp, chunk_size=16 * 1024):
        while True:
            buf = fp.read(chunk_size)
            if not buf:
                self.wfile.write(b"0\r\n\r\n")
                break
            self.wfile.write(str_to_bytes(format(len(buf), "x")))
            self.wfile.write(b"\r\n")
            self.wfile.write(buf)
            self.wfile.write(b"\r\n")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Keep normal HTTP behavior; wake accepted sockets only on close."""
    daemon_threads = True
    shutdown_grace_seconds = 3.0

    def __init__(self, *args, **kwargs):
        self._connection_condition = threading.Condition()
        self._connections = set()
        self._closing = False
        super(ThreadedHTTPServer, self).__init__(*args, **kwargs)

    def get_request(self):
        request, address = super(ThreadedHTTPServer, self).get_request()
        with self._connection_condition:
            if self._closing:
                request.close()
                raise OSError("HTTP server is closing")
            self._connections.add(request)
        return request, address

    def shutdown_request(self, request):
        # Serialize descriptor teardown with server_close() to avoid racing
        # socket shutdown against another thread closing/reusing the fd.
        with self._connection_condition:
            try:
                super(ThreadedHTTPServer, self).shutdown_request(request)
            finally:
                self._connections.discard(request)
                self._connection_condition.notify_all()

    def server_close(self):
        # The service calls this after serve_forever() has stopped. No changes
        # to connection timeouts, response headers or keep-alive while running.
        with self._connection_condition:
            self._closing = True
        super(ThreadedHTTPServer, self).server_close()
        with self._connection_condition:
            for request in tuple(self._connections):
                try:
                    request.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass  # Already disconnected.
            deadline = time.monotonic() + self.shutdown_grace_seconds
            while self._connections:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    logging.warning(
                        "HTTP shutdown: %d handler(s) still executing outside "
                        "the local socket read/write", len(self._connections))
                    break
                self._connection_condition.wait(remaining)

def threaded_http_server(host, port):
    return ThreadedHTTPServer((host, port), HTTPRequestHandler)


def add_get_route(pattern):
    def wrapper(func):
        HTTPRequestHandler.add_get_route(pattern, func)
        return func

    return wrapper
