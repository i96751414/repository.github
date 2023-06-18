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


class ServerHandler(BaseHTTPRequestHandler):
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
            logging.error(e, exc_info=True)
            self.send_response_and_end(500)

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
