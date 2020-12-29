# Kodi GitHub virtual repository

This add-on creates a virtual repository for Kodi. This way, one does not need to use a GitHub repository for storing add-ons zips when all that information is already accessible from each add-on repository.

It works by setting a HTTP server which has the following endpoints:

|Endpoint|Description|
|--------|-----------|
|http://127.0.0.1:{port}/addons.xml|Main xml file containing all add-ons information|
|http://127.0.0.1:{port}/addons.xml.md5|Checksum of the main xml file|
|http://127.0.0.1:{port}/{addon_id}/{asset_path}|Endpoint for serving add-ons assets/zips|
|http://127.0.0.1:{port}/update|Endpoint for updating repository entries and clearing caches|

##  Add-on entries

In order to know which repositories to proxy, the virtual repository needs to be provided with a _list of add-on entries_.
An example can be found [here](https://raw.githubusercontent.com/i96751414/repository.github/master/resources/repository.json).
Each entry must follow the following schema:

|Property|Required|Description|
|--------|--------|-----------|
|id|true|Add-on id.|
|username|true|GitHub repository username.|
|branch|false|GitHub repository branch. If not defined, it will be the commit of the latest release or, in case there are no releases, master branch.|
|assets|false|Dictionary containing string/string key-value pairs, where the key corresponds to the relative asset location and the value corresponds to the real asset location. One can also set "zip" asset, which is a special case for the add-on zip. If an asset is not defined, its location will be automatically evaluated.<br>Note: assets are treated as "new style" format strings with the following keywords - _id_, _username_, _repository_, _branch_, _system_ and _arch_.|
|asset_prefix|false|Prefix to use on the real asset location when it is automatically evaluated.|
|repository|false|GitHub repository name. If not set, it is assumed to be the same as the add-on id.|
