import logging
import threading

import xbmc

from lib.httpserver import ThreadedHTTPServer, ServerHandler
from lib.kodi import get_repository_port, set_logger
from lib.routes import route_get_addons, route_get_addons_md5, route_get_assets

# Register routes
ServerHandler.add_get_route("/addons.xml", route_get_addons)
ServerHandler.add_get_route("/addons.xml.md5", route_get_addons_md5)
ServerHandler.add_get_route("/{w}/{p}", route_get_assets)


class ServiceMonitor(xbmc.Monitor):
    pass


class HTTPServerRunner(threading.Thread):
    def __init__(self, monitor, port):
        self._monitor = monitor
        self._port = port
        self._server = None
        super(HTTPServerRunner, self).__init__()

    def run(self):
        self._server = ThreadedHTTPServer(("", self._port), ServerHandler)
        self._server.daemon_threads = True

        logging.debug("Server started at port {}".format(self._port))

        self._server.serve_until_shutdown(self._monitor.abortRequested)
        self._server.server_close()

    def stop(self):
        if self._server is not None:
            self._server.shutdown_server()


def run():
    set_logger(level=logging.INFO)
    monitor = ServiceMonitor()
    server = HTTPServerRunner(monitor, get_repository_port())
    server.start()
    monitor.waitForAbort()
    server.stop()
    server.join()
