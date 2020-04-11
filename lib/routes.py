import os

from lib.httpserver import ServerHandler
from lib.repository import Repository

repository = Repository()
repository.load_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resources", "repository.json"))


def route_get_addons(ctx):
    # type: (ServerHandler) -> None
    xml = repository.get_addons_xml()
    ctx.send_response(200)
    ctx.send_header("Content-Type", "application/xml")
    ctx.send_header('Content-Length', len(xml))
    ctx.end_headers()
    ctx.wfile.write(xml)


def route_get_addons_md5(ctx):
    # type: (ServerHandler) -> None
    hash_md5 = repository.get_addons_xml_md5()
    ctx.send_response(200)
    ctx.send_header("Content-Type", "text/plain")
    ctx.send_header('Content-Length', len(hash_md5))
    ctx.end_headers()
    ctx.wfile.write(hash_md5)


def route_get_assets(ctx, addon_id, asset):
    # type: (ServerHandler, str, str) -> None
    url = repository.get_asset_url(addon_id, asset)
    if url is None:
        ctx.send_response(404)
    else:
        ctx.send_response(301)
        ctx.send_header("Location", url)
    ctx.end_headers()
