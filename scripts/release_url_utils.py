from __future__ import annotations

import urllib.parse


def is_github_release_api_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "api.github.com":
        return False
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) == 5 and parts[0] == "repos" and parts[3] == "releases" and parts[4] == "latest":
        return True
    return len(parts) == 6 and parts[0] == "repos" and parts[3] == "releases" and parts[4] == "tags"
