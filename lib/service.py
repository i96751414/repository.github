import logging
import os
import threading
from xml.etree import ElementTree

import xbmc

from lib.entries import ENTRIES_PATH
from lib.httpserver import ThreadedHTTPServer, ServerHandler
from lib.kodi import ADDON_PATH, get_repository_port, set_logger
from lib.routes import route_get_addons, route_get_addons_md5, route_get_assets, route_update, repository

# Register routes
ServerHandler.add_get_route("/addons.xml", route_get_addons)
ServerHandler.add_get_route("/addons.xml.md5", route_get_addons_md5)
ServerHandler.add_get_route("/{w}/{p}", route_get_assets)
ServerHandler.add_get_route("/update", route_update)


def update_repository_port(port, xml_path=os.path.join(ADDON_PATH, "addon.xml")):
    base_url = "http://127.0.0.1:{}/".format(port)
    tree = ElementTree.parse(xml_path)
    tree.find("extension[@point='xbmc.addon.repository']/info").text = base_url + "addons.xml"
    tree.find("extension[@point='xbmc.addon.repository']/checksum").text = base_url + "addons.xml.md5"
    tree.find("extension[@point='xbmc.addon.repository']/datadir").text = base_url
    tree.write(xml_path, encoding="UTF-8", xml_declaration=True)


class ServiceMonitor(xbmc.Monitor):
    def __init__(self):
        super(ServiceMonitor, self).__init__()
        self._port = get_repository_port()

    def onSettingsChanged(self):
        port = get_repository_port()
        if port != self._port:
            update_repository_port(port)
            self._port = port


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
    set_logger()
    repository.files = [os.path.join(ADDON_PATH, "resources", "repository.json"), ENTRIES_PATH]
    repository.update()
    monitor = ServiceMonitor()
    server = HTTPServerRunner(monitor, get_repository_port())
    server.start()
    monitor.waitForAbort()
    server.stop()
    server.join()
