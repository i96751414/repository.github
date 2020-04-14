import json
import os
import sys
from zipfile import ZipFile

import requests
import xbmcgui

from lib.kodi import ADDON_DATA, ADDON_NAME, translate, notification, get_repository_port, str_to_unicode
from lib.repository import validate_json_schema

if not os.path.exists(ADDON_DATA):
    os.makedirs(ADDON_DATA)

ENTRIES_PATH = os.path.join(ADDON_DATA, "entries.json")
if not os.path.exists(ENTRIES_PATH):
    with open(ENTRIES_PATH, "w") as _f:
        _f.write("[]")


class Entries(object):
    def __init__(self, path=ENTRIES_PATH):
        self._path = path
        self._data = []
        self._ids = []
        if os.path.exists(self._path):
            self.load()

    def clear(self):
        self._data = []
        self._ids = []

    def length(self):
        return len(self._ids)

    @property
    def ids(self):
        return list(self._ids)

    def remove(self, index):
        self._data.pop(index)
        self._ids.pop(index)

    def load(self):
        with open(self._path) as f:
            self._data = json.load(f)
        self._ids = [addon["id"] for addon in self._data]

    def save(self):
        with open(self._path, "w") as f:
            json.dump(self._data, f)

    def add_entries_from_file(self, path):
        if path.endswith(".zip"):
            with ZipFile(path) as zip_file:
                for name in zip_file.namelist():
                    if name.endswith(".json"):
                        self._add_entries_from_data(json.loads(zip_file.read(name)))
        elif path.endswith(".json"):
            with open(path) as f:
                self._add_entries_from_data(json.load(f))
        else:
            raise ValueError("Unknown file extension. Supported extensions are .json and .zip")

    def _add_entries_from_data(self, data):
        validate_json_schema(data)
        for entry in data:
            addon_id = entry["id"]
            try:
                index = self._ids.index(addon_id)
                self._data[index] = entry
            except ValueError:
                self._data.append(entry)
                self._ids.append(addon_id)


def update_repository():
    requests.get("http://127.0.0.1:{}/update".format(get_repository_port()), timeout=2)


def import_entries():
    path = str_to_unicode(xbmcgui.Dialog().browse(1, translate(30002), "files", ".json|.zip"))
    if path:
        entries = Entries()
        entries.add_entries_from_file(path)
        entries.save()
        update_repository()
        notification(translate(30007))


def delete_entries():
    entries = Entries()
    if entries.length() == 0:
        notification(translate(30005))
    else:
        selected = xbmcgui.Dialog().multiselect(translate(30003), entries.ids)
        if selected:
            for index in selected:
                entries.remove(index)
            entries.save()
            update_repository()
            notification(translate(30006))


def clear_entries():
    entries = Entries()
    if entries.length() == 0:
        notification(translate(30005))
    else:
        entries.clear()
        entries.save()
        update_repository()
        notification(translate(30006))


def run():
    if len(sys.argv) == 2:
        method = sys.argv[1]
        if method == "import_entries":
            import_entries()
        elif method == "delete_entries":
            delete_entries()
        elif method == "clear_entries":
            clear_entries()
        else:
            raise NotImplementedError("Unknown method '{}'".format(method))
    else:
        selected = xbmcgui.Dialog().select(ADDON_NAME, [translate(30002), translate(30003), translate(30004)])
        if selected == 0:
            import_entries()
        elif selected == 1:
            delete_entries()
        elif selected == 2:
            clear_entries()