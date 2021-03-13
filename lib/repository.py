import json
import logging
import re
from collections import namedtuple, OrderedDict
from hashlib import md5
from xml.etree import ElementTree  # nosec

try:
    from urllib import request as ul
except ImportError:
    # noinspection PyUnresolvedReferences
    import urllib2 as ul

from concurrent.futures import ThreadPoolExecutor

from lib.cache import cached
from lib.kodi import string_types
from lib.os_platform import PLATFORM, get_platform_arch

ADDON = namedtuple("ADDON", "id username branch assets asset_prefix repository")

GITHUB_CONTENT_URL = "https://raw.githubusercontent.com/{username}/{repository}/{branch}"
GITHUB_RELEASES_URL = "https://api.github.com/repos/{username}/{repository}/releases"
GITHUB_LATEST_RELEASE_URL = GITHUB_RELEASES_URL + "/latest"
GITHUB_RELEASE_URL = GITHUB_RELEASES_URL + "/{release}"
GITHUB_ZIP_URL = "https://github.com/{username}/{repository}/archive/{branch}.zip"

ENTRY_SCHEMA = {
    "required": ["id", "username"],
    "properties": {
        "id": {"type": string_types},
        "username": {"type": string_types},
        "branch": {"type": string_types},
        "assets": {"type": dict},
        "asset_prefix": {"type": string_types},
        "repository": {"type": string_types},
        "platforms": {"type": list}
    }
}


class InvalidSchemaError(Exception):
    pass


def validate_entry_schema(entry):
    if not isinstance(entry, dict):
        raise InvalidSchemaError("Expecting dictionary for entry")
    for key in ENTRY_SCHEMA["required"]:
        if key not in entry:
            raise InvalidSchemaError("Key '{}' is required".format(key))
    for key, value in entry.items():
        if key not in ENTRY_SCHEMA["properties"]:
            raise InvalidSchemaError("Key '{}' is not valid".format(key))
        value_type = ENTRY_SCHEMA["properties"][key]["type"]
        if not isinstance(value, value_type):
            raise InvalidSchemaError("Expected type {} for '{}'".format(value_type.__name__, key))
        if value_type is dict:
            for k, v in value.items():
                if not (isinstance(k, string_types) and isinstance(v, string_types)):
                    raise InvalidSchemaError("Expected dict[str, str] for '{}'".format(key))
        elif value_type is list:
            for v in value:
                if not isinstance(v, string_types):
                    raise InvalidSchemaError("Expected list[str] for '{}'".format(key))


def validate_json_schema(data):
    if not isinstance(data, (list, tuple)):
        raise InvalidSchemaError("Expecting list/tuple for data")
    for entry in data:
        validate_entry_schema(entry)


def get_request(url, **kwargs):
    return ul.urlopen(url, **kwargs).read()


class Repository(object):
    def __init__(self, **kwargs):
        self.files = kwargs.get("files", [])
        self.urls = kwargs.get("urls", [])
        self._max_threads = kwargs.get("max_threads", 5)
        self._platform = get_platform_arch()
        self._addons = OrderedDict()
        self.update()

    def update(self, clear=False):
        if clear:
            self._addons.clear()
        for u in self.urls:
            self._load_url(u)
        for f in self.files:
            self._load_file(f)

    def _load_file(self, path):
        with open(path) as f:
            self._load_data(json.load(f))

    def _load_url(self, url):
        self._load_data(json.loads(get_request(url)))

    def _load_data(self, data):
        for addon_data in data:
            addon_id = addon_data["id"]
            platforms = addon_data.get("platforms")

            if platforms and self._platform not in platforms:
                logging.debug("Skipping addon %s as it does not support platform %s", addon_id, self._platform)
                continue

            self._addons[addon_id] = ADDON(
                id=addon_id, username=addon_data["username"], branch=addon_data.get("branch"),
                assets=addon_data.get("assets", {}), asset_prefix=addon_data.get("asset_prefix", ""),
                repository=addon_data.get("repository", addon_id))

    def clear_cache(self):
        self.get_addons_xml.cache_clear()
        self.get_latest_release.cache_clear()

    @cached(seconds=60 * 60)
    def get_latest_release(self, username, repository, default="master"):
        data = json.loads(get_request(GITHUB_LATEST_RELEASE_URL.format(username=username, repository=repository)))
        try:
            return data["tag_name"]
        except KeyError:
            return default

    def _get_addon_branch(self, addon):
        return addon.branch or self.get_latest_release(addon.username, addon.repository)

    def _get_addon_xml(self, addon):
        try:
            addon_xml_url = addon.assets["addon.xml"]
        except KeyError:
            addon_xml_url = GITHUB_CONTENT_URL.format(
                username=addon.username, repository=addon.repository,
                branch=self._get_addon_branch(addon)) + "/addon.xml"

        try:
            return ElementTree.fromstring(get_request(addon_xml_url))
        except Exception as e:
            logging.error("failed getting '%s': %s", addon.id, e, exc_info=True)
            return None

    @cached(seconds=60 * 60)
    def get_addons_xml(self):
        root = ElementTree.Element("addons")
        num_threads = min(self._max_threads, len(self._addons))
        if num_threads <= 1:
            results = [self._get_addon_xml(a) for a in self._addons.values()]
        else:
            with ThreadPoolExecutor(num_threads) as pool:
                results = list(pool.map(self._get_addon_xml, self._addons.values()))

        for result in results:
            if result is not None:
                root.append(result)

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
                   "branch": self._get_addon_branch(addon), "system": PLATFORM.system, "arch": PLATFORM.arch}
        match = re.match(addon_id + r"-(.+?)\.zip$", asset)
        if match:
            formats["version"] = match.group(1)
            asset = "zip"
            default_asset_url = GITHUB_ZIP_URL
        else:
            default_asset_url = GITHUB_CONTENT_URL + "/" + addon.asset_prefix + asset

        return addon.assets.get(asset, default_asset_url).format(**formats)
