from lib.utils import request


class _Dict(dict):
    def __getattr__(self, name):
        return self[name]


class GitHubApiError(Exception):
    pass


class GitHubRepositoryApi(object):
    def __init__(self, username, repository):
        self._base_url = "https://api.github.com/repos/{username}/{repository}".format(
            username=username, repository=repository)

    def get_release(self, release):
        return self._request_json("/releases/{}".format(release))

    def get_latest_release(self):
        return self.get_release("latest")

    def get_zip(self, ref=None):
        return self._request("/zipball/{}".format(ref) if ref else "/zipball")

    def get_contents(self, path, ref=None):
        return self._request(
            "/contents/{}".format(path),
            params=dict(ref=ref) if ref else None,
            headers={"Accept": "application/vnd.github.raw"})

    def _request_json(self, url, **kwargs):
        with self._request(url, **kwargs) as response:
            return response.json(object_pairs_hook=_Dict)

    def _request(self, url, **kwargs):
        full_url = self._base_url + url
        response = request(full_url, **kwargs)

        if response.status_code >= 400:
            try:
                response.close()
            finally:
                raise GitHubApiError("Call to {} failed with HTTP {}".format(full_url, response.status_code))

        return response
