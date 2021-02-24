import os

from lib.entries import ENTRIES_PATH
from lib.httpserver import ServerHandler, add_get_route  # pylint: disable=unused-import
from lib.kodi import ADDON_PATH
from lib.repository import Repository

repository = Repository(files=(os.path.join(ADDON_PATH, "resources", "repository.json"), ENTRIES_PATH))


@add_get_route("/addons.xml")
def route_get_addons(ctx):
    # type: (ServerHandler) -> None
    xml = repository.get_addons_xml()
    ctx.send_response(200)
    ctx.send_header("Content-Type", "application/xml")
    ctx.send_header("Content-Length", str(len(xml)))
    ctx.end_headers()
    ctx.wfile.write(xml)


@add_get_route("/addons.xml.md5")
def route_get_addons_md5(ctx):
    # type: (ServerHandler) -> None
    hash_md5 = repository.get_addons_xml_md5()
    ctx.send_response(200)
    ctx.send_header("Content-Type", "text/plain")
    ctx.send_header("Content-Length", str(len(hash_md5)))
    ctx.end_headers()
    ctx.wfile.write(hash_md5)


@add_get_route("/{w}/{p}")
def route_get_assets(ctx, addon_id, asset):
    # type: (ServerHandler, str, str) -> None
    url = repository.get_asset_url(addon_id, asset)
    if url is None:
        ctx.send_response(404)
    else:
        ctx.send_response(301)
        ctx.send_header("Location", url)
    ctx.end_headers()


@add_get_route("/update")
def route_update(ctx):
    # type: (ServerHandler) -> None
    repository.update()
    repository.clear_cache()
    ctx.send_response(200)
    ctx.end_headers()
