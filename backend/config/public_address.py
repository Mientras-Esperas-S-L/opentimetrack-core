"""The address people use to reach this installation, and everything derived from it.

An installation used to be described by six settings that had to agree with each
other and were checked by nobody: where the web app lives (for the links in the
mail), where the provider sends people back (which must match, character for
character, what was registered there), where to land them afterwards, the hosts
Django answers to, the origins the API accepts, and whether any of it is https.
Leave one out and the failure shows up far from the cause: an invitation that
opens `localhost:3000` on somebody's phone, or a sign-in that ends on a page of
raw JSON with the session tokens in it.

Now there is one: `PUBLIC_URL`, the address in the browser bar, and optionally
`PUBLIC_API_URL` when the API is served from somewhere else. The rest is derived,
each of the old settings still wins when it is set, and production refuses to
start with an address that cannot work instead of starting and failing later.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

#: Where the API is mounted. Django routes everything under it; there is no
#: setting that moves it, so an API address has to end exactly here.
API_PATH = "/api"


def clean(value: str, name: str, *, exact: bool = False) -> str:
    """An absolute http(s) address with no trailing slash, or a clear refusal.

    `exact` checks it the same way and hands it back untouched: a redirect URI
    is compared character for character with what the provider has registered,
    so its trailing slash is not ours to remove.
    """
    given = (value or "").strip()
    value = given.rstrip("/")
    if not value:
        return ""
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ImproperlyConfigured(
            f"{name} has to be a full address starting with https:// (or http://), "
            f"and it is {value!r}."
        )
    if parts.username or parts.password:
        raise ImproperlyConfigured(f"{name} cannot carry a user or a password: {value!r}.")
    if parts.query or parts.fragment:
        raise ImproperlyConfigured(f"{name} cannot carry a query or a fragment: {value!r}.")
    return given if exact else value


def origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def host(url: str) -> str:
    return urlsplit(url).hostname or ""


def api_url_for(public_url: str, public_api_url: str) -> str:
    """The API's own address: the one given, or the web's with `/api` after it."""
    if public_api_url:
        return public_api_url
    return f"{public_url}{API_PATH}" if public_url else ""


def check_for_production(*, web: str, api: str, allow_http: bool) -> None:
    """Refuse, at start-up, the addresses a production installation cannot run on."""
    if not web:
        raise ImproperlyConfigured(
            "PUBLIC_URL is required in production: the address people type to reach this "
            "installation, such as https://time.example.com. Invitation links, the return "
            "from an identity provider and the hosts this server answers to all come from it."
        )
    if urlsplit(web).path:
        raise ImproperlyConfigured(
            f"The web address cannot have a path ({web!r}): serving the installation under a "
            "path prefix is not supported. Give it its own host name, such as "
            "https://time.example.com."
        )
    if urlsplit(api).path != API_PATH:
        raise ImproperlyConfigured(
            f"The API address has to end in {API_PATH}, which is where the API is mounted, and "
            f"it is {api!r}. For an API on its own host: https://api.time.example.com{API_PATH}."
        )
    if not allow_http:
        for name, url in (("PUBLIC_URL", web), ("PUBLIC_API_URL", api)):
            if urlsplit(url).scheme != "https":
                raise ImproperlyConfigured(
                    f"{name} is {url!r}: over http, passwords and session tokens travel in the "
                    "clear. Serve it over https. Inside a private network only, "
                    "ALLOW_INSECURE_HTTP=true allows it."
                )
