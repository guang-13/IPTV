"""Outbound URL admission control.

Every URL this project fetches comes either from the operator (local files) or
from third-party playlists and EPG feeds.  A malicious list must not be able to
turn the updater into an internal-network scanner or a cloud-metadata reader, so
outbound requests are checked against a scheme allowlist and against
private / loopback / link-local / reserved address space.

The DNS answer is validated before the request; a resolver that changes its
answer between the check and the connection (DNS rebinding) is out of scope for
this module and should be handled by network egress policy.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

ALLOWED_SCHEMES = frozenset({"http", "https"})

# Hostnames and addresses that only exist to serve cloud credentials.
BLOCKED_HOSTNAMES = frozenset(
    {
        "metadata",
        "metadata.google.internal",
        "metadata.goog",
        "instance-data",
        "instance-data.ec2.internal",
    }
)
METADATA_ADDRESSES = frozenset(
    {
        ipaddress.ip_address("169.254.169.254"),
        ipaddress.ip_address("169.254.170.2"),
        ipaddress.ip_address("100.100.100.200"),
        ipaddress.ip_address("fd00:ec2::254"),
    }
)


class UnsafeUrlError(ValueError):
    """Raised when a URL must not be requested."""


def _parse_address(value):
    try:
        return ipaddress.ip_address(str(value).strip("[]"))
    except ValueError:
        return None


def _resolve(host, port, resolver):
    try:
        infos = resolver(host, port, type=socket.SOCK_STREAM)
    except OSError:
        # An unresolvable host cannot reach internal space; the request layer
        # reports the failure itself.
        return []
    return [info[4][0] for info in infos]


def _address_allowed(address) -> bool:
    if address in METADATA_ADDRESSES:
        return False
    # ``is_global`` is the cheapest correct summary: it excludes private,
    # loopback, link-local, shared, reserved, multicast and unspecified space.
    return address.is_global


def check_url(url, *, allow_private=False, allow_file=False, resolver=socket.getaddrinfo):
    """Validate an outbound URL and return it unchanged when it is safe.

    ``allow_private`` keeps LAN-only deployments working; ``allow_file`` is for
    the local media feature.  Both are opt-in configuration switches.
    """
    text = str(url or "").strip()
    if not text:
        raise UnsafeUrlError("URL 为空")

    scheme = text.split(":", 1)[0].strip().lower()
    if scheme == "file":
        if allow_file:
            return text
        raise UnsafeUrlError("不允许抓取本地文件 URL")
    if scheme not in ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"不支持的协议：{scheme or '空'}")

    parsed = urlsplit(text)
    host = (parsed.hostname or "").lower()
    if not host:
        raise UnsafeUrlError("URL 缺少主机名")
    if host in BLOCKED_HOSTNAMES:
        raise UnsafeUrlError("禁止访问云元数据地址")
    if allow_private:
        return text

    literal = _parse_address(host)
    if literal is not None:
        addresses = [literal]
    else:
        default_port = 443 if scheme == "https" else 80
        addresses = [
            address
            for address in (
                _parse_address(item)
                for item in _resolve(host, parsed.port or default_port, resolver)
            )
            if address is not None
        ]
    if not addresses:
        # Unresolvable: nothing to pin, so leave the failure to the caller.
        return text
    for address in addresses:
        if not _address_allowed(address):
            raise UnsafeUrlError(f"禁止访问内网或保留地址：{address}")
    return text


def is_safe_url(url, *, allow_private=False, allow_file=False, resolver=socket.getaddrinfo) -> bool:
    """Boolean wrapper for call sites that skip an item instead of failing."""
    try:
        check_url(
            url,
            allow_private=allow_private,
            allow_file=allow_file,
            resolver=resolver,
        )
        return True
    except UnsafeUrlError:
        return False
