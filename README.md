# Kodi GitHub virtual repository

This add-on creates a virtual repository for Kodi. This way, one does not need to use a GitHub repository for storing add-ons zips when all that information is already accessible from each add-on repository.

It works by setting a HTTP server which has the following endpoints:

|Endpoint|Description|
|--------|-----------|
|http://127.0.0.1:{port}/addons.xml|Main xml file containing all add-ons information|
|http://127.0.0.1:{port}/addons.xml.md5|Checksum of the main xml file|
|http://127.0.0.1:{port}/{addon_id}/{asset_path}|Endpoint for serving add-ons assets/zips|
