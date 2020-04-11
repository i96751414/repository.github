import json
import logging
import re
from collections import namedtuple, OrderedDict
from hashlib import md5
from multiprocessing.pool import ThreadPool
from xml.etree import ElementTree

import requests

from lib.cache import cached
from lib.os_platform import PLATFORM

ADDON = namedtuple("ADDON", "id username branch assets asset_prefix repository")

GITHUB_CONTENT_URL = "https://raw.githubusercontent.com/{username}/{repository}/{branch}"
GITHUB_RELEASES_URL = "https://api.github.com/repos/{username}/{repository}/releases"
GITHUB_LATEST_RELEASE_URL = GITHUB_RELEASES_URL + "/latest"
GITHUB_RELEASE_URL = GITHUB_RELEASES_URL + "/{release}"
GITHUB_ZIP_URL = "https://github.com/{username}/{repository}/archive/{branch}.zip"


@cached(seconds=60 * 60)
def get_latest_release(username, repository, default="master"):
    r = requests.get(GITHUB_LATEST_RELEASE_URL.format(username=username, repository=repository))
    try:
        return r.json()["target_commitish"]
    except KeyError:
        return default


class Repository(object):
    def __init__(self, max_threads=5):
        self._addons = OrderedDict()
        self._max_threads = max_threads

    def load_file(self, path):
        with open(path) as f:
            self.load_data(json.load(f))

    def load_data(self, data):
        # Required: id, username
        # Optional: branch, assets, asset_prefix, repository
        for addon_data in data:
            addon_id = addon_data["id"]
            self._addons[addon_id] = ADDON(
                id=addon_id, username=addon_data["username"], branch=addon_data.get("branch"),
                assets=addon_data.get("assets", {}), asset_prefix=addon_data.get("asset_prefix", ""),
                repository=addon_data.get("repository", addon_id))

    @staticmethod
    def _get_addon_xml(addon):
        try:
            addon_xml_url = addon.assets["addon.xml"]
        except KeyError:
            addon_xml_url = GITHUB_CONTENT_URL.format(
                username=addon.username, repository=addon.repository,
                branch=addon.branch or get_latest_release(addon.username, addon.repository),
            ) + "/addon.xml"

        try:
            return ElementTree.fromstring(requests.get(addon_xml_url).content)
        except Exception as e:
            logging.error(e, exc_info=True)
            return None

    @cached(seconds=60 * 60)
    def get_addons_xml(self):
        pool = ThreadPool(self._max_threads)
        results = pool.map(self._get_addon_xml, self._addons.values())
        root = ElementTree.Element("addons")
        for result in results:
            if result is not None:
                root.append(result)

        pool.close()
        pool.join()
        return ElementTree.tostring(root, encoding="utf-8", method="xml")

    def get_addons_xml_md5(self):
        m = md5()
        m.update(self.get_addons_xml())
        return m.hexdigest().encode("utf-8")

    def get_asset_url(self, addon_id, asset):
        addon = self._addons.get(addon_id)
        if addon is None:
            return None
        formats = {"id": addon.id, "username": addon.username, "repository": addon.repository,
                   "branch": addon.branch or get_latest_release(addon.username, addon.repository),
                   "system": PLATFORM.system, "arch": PLATFORM.arch}
        match = re.match(addon_id + r"-(.+?)\.zip$", asset)
        if match:
            formats["version"] = match.group(1)
            asset = "zip"
            default_asset_url = GITHUB_ZIP_URL
        else:
            default_asset_url = GITHUB_CONTENT_URL + "/" + addon.asset_prefix + asset

        return addon.assets.get(asset, default_asset_url).format(**formats)
