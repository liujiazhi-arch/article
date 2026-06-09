from __future__ import annotations

from release_url_utils import is_github_release_api_url


def test_github_release_api_url_accepts_latest_and_tag_endpoints_only():
    assert is_github_release_api_url("https://api.github.com/repos/example/article/releases/latest") is True
    assert is_github_release_api_url("https://api.github.com/repos/example/article/releases/tags/v0.1.0") is True

    assert is_github_release_api_url("http://api.github.com/repos/example/article/releases/latest") is False
    assert is_github_release_api_url("https://github.com/example/article/releases/latest") is False
    assert is_github_release_api_url("https://api.github.com/repos/example/article/releases") is False
