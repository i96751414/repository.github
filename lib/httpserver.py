# -*- coding: utf-8 -*-

import logging
import re

try:
    import urlparse
    from SocketServer import ThreadingMixIn
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    import urllib.parse as urlparse
    from socketserver import ThreadingMixIn
    from http.server import BaseHTTPRequestHandler, HTTPServer

_patterns = (
    (re.escape("{w}"), "([^/]+)"),
    (re.escape("{p}"), "(.+)"),
)


def _generate_pattern(s):
    pattern = re.escape(s)
    for p in _patterns:
        pattern = pattern.replace(*p)
    return re.compile(pattern + "$")


class ServerHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    get_routes = []

    @classmethod
    def add_get_route(cls, pattern, handle):
        cls.get_routes.append((_generate_pattern(pattern), handle))

    # noinspection PyPep8Naming
    def do_GET(self):
        self._handle_request(self.get_routes)

    def _handle_request(self, routes):
        try:
            self.url = urlparse.urlsplit(self.path)
            self.request = dict(urlparse.parse_qsl(self.url.query))
            for pattern, handler in routes:
                match = pattern.match(self.url.path)
                if match:
                    handler(self, *match.groups())
                    break
            else:
                self.send_response(404)
                self.end_headers()
        except Exception as e:
            logging.error(e, exc_info=True)
            self.send_response(500)
            self.end_headers()

    def log_message(self, fmt, *args):
        logging.debug(fmt, *args)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """
    Handle requests in a separate thread.
    """
    daemon_threads = True


def threaded_http_server(host, port):
    return ThreadedHTTPServer((host, port), ServerHandler)


def add_get_route(pattern):
    def wrapper(func):
        ServerHandler.add_get_route(pattern, func)
        return func

    return wrapper
