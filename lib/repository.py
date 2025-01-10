import json
import logging
from collections import namedtuple, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from hashlib import md5
from xml.etree import ElementTree  # nosec

from lib.cache import LoadingCache
from lib.github import GitHubRepositoryApi, GitHubApiError
from lib.utils import string_types, is_http_like, request

Addon = namedtuple("Addon", ("id", "username", "branch", "assets", "asset_prefix", "repository", "platforms"))
EntrySchema = namedtuple("EntrySchema", ("required", "validators"))


class InvalidSchemaError(Exception):
    pass


class AddonNotFound(Exception):
    pass


def validate_string(key, value):
    if not isinstance(value, string_types):
        raise InvalidSchemaError("Expected str for '{}'".format(key))


def validate_string_map(key, value):
    if not (isinstance(value, dict)
            and all(isinstance(k, string_types) and isinstance(v, string_types) for k, v in value.items())):
        raise InvalidSchemaError("Expected dict[str, str] for '{}'".format(key))


def validate_string_list(key, value):
    if not (isinstance(value, list) and all(isinstance(v, string_types) for v in value)):
        raise InvalidSchemaError("Expected list[str] for '{}'".format(key))


_entry_schema = EntrySchema(required=("id", "username"), validators=dict(
    id=validate_string,
    username=validate_string,
    branch=validate_string,
    assets=validate_string_map,
    asset_prefix=validate_string,
    repository=validate_string,
    platforms=validate_string_list,
))


def validate_entry_schema(entry):
    if not isinstance(entry, dict):
        raise InvalidSchemaError("Expecting dictionary for entry")
    for key in _entry_schema.required:
        if key not in entry:
            raise InvalidSchemaError("Key '{}' is required".format(key))
    for key, value in entry.items():
        validator = _entry_schema.validators.get(key)
        if not validator:
            raise InvalidSchemaError("Key '{}' is not valid".format(key))
        validator(key, value)


def validate_schema(data):
    if not isinstance(data, (list, tuple)):
        raise InvalidSchemaError("Expecting list/tuple for data")
    for entry in data:
        validate_entry_schema(entry)


def remove_prefix(text, prefix):
    return text[len(prefix):] if text.startswith(prefix) else text


class Repository(object):
    ZIP_EXTENSION = ".zip"
    VERSION_SEPARATOR = "-"

    def __init__(self, files=(), urls=(), max_threads=5, platform=None, cache_ttl=60 * 60, default_branch="main"):
        self.files = files
        self.urls = urls
        self._max_threads = max_threads
        self._default_branch = default_branch
        self._addons = OrderedDict()

        if platform is None:
            from lib.platform.core import PLATFORM
            self._platform = PLATFORM
        else:
            self._platform = platform

        self._addons_xml_cache = LoadingCache(self._get_addons_xml, cache_ttl)
        self._fallback_ref_cache = LoadingCache(self._get_fallback_ref, cache_ttl)
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
        with request(url) as r:
            r.raise_for_status()
            self._load_data(r.json())

    def _load_data(self, data):
        platform_name = self._platform.name()
        for addon_data in data:
            addon_id = addon_data["id"]
            platforms = addon_data.get("platforms")

            if platforms and platform_name not in platforms:
                logging.debug("Skipping addon %s as it does not support platform %s", addon_id, platform_name)
                continue

            self._addons[addon_id] = Addon(
                id=addon_id, username=addon_data["username"], branch=addon_data.get("branch"),
                assets=addon_data.get("assets", {}), asset_prefix=addon_data.get("asset_prefix", ""),
                repository=addon_data.get("repository", addon_id), platforms=platforms)

    def clear_cache(self):
        self._addons_xml_cache.clear()
        self._fallback_ref_cache.clear()

    def _get_addon_xml(self, addon):
        with self._get_asset(addon, "addon.xml") as r:
            r.raise_for_status()
            addon_xml = r.content

        try:
            return ElementTree.fromstring(addon_xml)
        except Exception as e:
            logging.error("Failed getting '%s' addon XML: %s", addon.id, e, exc_info=True)
            return None

    def _get_addons_xml(self):
        root = ElementTree.Element("addons")
        num_threads = min(self._max_threads, len(self._addons))
        if num_threads <= 1:
            results = map(self._get_addon_xml, self._addons.values())
        else:
            with ThreadPoolExecutor(num_threads) as pool:
                futures = [pool.submit(self._get_addon_xml, addon) for addon in self._addons.values()]
                results = map(lambda f: f.result(), futures)

        for result in results:
            if result is not None:
                root.append(result)

        return ElementTree.tostring(root, encoding="utf-8", method="xml")

    def get_addons_xml(self):
        return self._addons_xml_cache.get()

    def get_addons_xml_md5(self):
        m = md5()
        m.update(self.get_addons_xml())
        return m.hexdigest().encode("utf-8")

    def get_asset(self, addon_id, asset):
        addon = self._addons.get(addon_id)
        if addon is None:
            raise AddonNotFound("No such addon: {}".format(addon_id))
        return self._get_asset(addon, asset)

    def _get_asset(self, addon, asset):
        repo = GitHubRepositoryApi(addon.username, addon.repository)
        branch = addon.branch or self._fallback_ref_cache.get(repo)
        formats = dict(
            id=addon.id, username=addon.username, repository=addon.repository,
            branch=branch, system=self._platform.system, arch=self._platform.arch)

        is_zip = asset.startswith(addon.id + self.VERSION_SEPARATOR) and asset.endswith(self.ZIP_EXTENSION)
        if is_zip:
            formats["version"] = asset[len(addon.id) + len(self.VERSION_SEPARATOR):-len(self.ZIP_EXTENSION)]
            asset = "zip"

        try:
            asset_path = addon.assets[asset].format(**formats)
        except KeyError:
            if is_zip:
                # TODO: check tags first before falling back to latest repo ZIP
                response = repo.get_zip(branch)
            else:
                response = repo.get_contents(addon.asset_prefix.format(**formats) + asset, branch)
        else:
            # TODO: add support for release assets for private repos
            if is_http_like(asset_path):
                response = request(asset_path)
            else:
                response = repo.get_contents(asset_path, branch)

        return response

    def _get_fallback_ref(self, repo):
        try:
            return repo.get_latest_release().tag_name
        except GitHubApiError:
            pass

        try:
            for tag in reversed(repo.get_refs_tags()):
                # TODO: return conditionally based on tag selector
                return remove_prefix(tag.ref, "refs/tags/")
        except GitHubApiError:
            pass

        try:
            return repo.get_repository_info().default_branch
        except GitHubApiError:
            pass

        return self._default_branch
