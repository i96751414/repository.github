import os

from lib.entries import ENTRIES_PATH
from lib.httpserver import ServerHandler, add_get_route  # pylint: disable=unused-import
from lib.kodi import ADDON_PATH
from lib.repository import Repository

repository = Repository(files=(os.path.join(ADDON_PATH, "resources", "repository.json"), ENTRIES_PATH))


@add_get_route("/addons.xml")
def route_get_addons(ctx):
    # type: (ServerHandler) -> None
    ctx.send_response_with_data(repository.get_addons_xml(), "application/xml")


@add_get_route("/addons.xml.md5")
def route_get_addons_md5(ctx):
    # type: (ServerHandler) -> None
    ctx.send_response_with_data(repository.get_addons_xml_md5(), "text/plain")


@add_get_route("/{w}/{p}")
def route_get_assets(ctx, addon_id, asset):
    # type: (ServerHandler, str, str) -> None
    url = repository.get_asset_url(addon_id, asset)
    if url is None:
        ctx.send_response_and_end(404)
    else:
        ctx.send_redirect(url)


@add_get_route("/update")
def route_update(ctx):
    # type: (ServerHandler) -> None
    repository.update()
    repository.clear_cache()
    ctx.send_response_and_end(200)
