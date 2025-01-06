import os
import logging

from lib.httpserver import threaded_http_server
from lib.platform.os_platform import get_platform
from lib.repository import Repository
from lib.routes import add_repository_routes


def run(port):
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
    add_repository_routes(Repository(
        files=(os.path.join(os.path.dirname(__file__), "resources", "repository.json"),),
        platform=get_platform()))

    server = threaded_http_server("", port)
    logging.debug("Server started at port %d", port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        logging.debug("Closing server")
        server.server_close()


if __name__ == "__main__":
    run(8080)
