from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from ipaddress import IPv4Network, IPv6Network
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

_IPNetwork = IPv4Network | IPv6Network


@dataclass
class Scope:
    allowed_hosts: list[str]
    allowed_cidrs: list[_IPNetwork]
    allowed_url_prefixes: list[str]
    excluded_hosts: list[str]
    max_requests_per_second: int
    profiles: dict[str, bool]
    source_path: Path | None = None

    @classmethod
    def load(cls, path: Path) -> Scope:
        data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        cidrs_raw = data.get("allowed_cidrs") or []
        nets: list[_IPNetwork] = []
        for c in cidrs_raw:
            nets.append(ipaddress.ip_network(str(c), strict=False))
        return cls(
            allowed_hosts=[str(h).lower().strip(".") for h in (data.get("allowed_hosts") or [])],
            allowed_cidrs=nets,
            allowed_url_prefixes=list(data.get("allowed_url_prefixes") or []),
            excluded_hosts=[str(h).lower().strip(".") for h in (data.get("excluded_hosts") or [])],
            max_requests_per_second=int(data.get("max_requests_per_second") or 10),
            profiles=dict(data.get("profiles") or {}),
            source_path=path,
        )

    def profile_enabled(self, name: str) -> bool:
        return bool(self.profiles.get(name, False))

    def _excluded(self, host: str) -> bool:
        h = host.lower().strip(".")
        for ex in self.excluded_hosts:
            ex = ex.strip(".")
            if h == ex or h.endswith("." + ex):
                return True
        return False

    def host_allowed(self, host: str) -> bool:
        if self._excluded(host):
            return False
        h = host.lower().strip(".")
        for ah in self.allowed_hosts:
            base = ah.strip(".")
            if h == base or h.endswith("." + base):
                return True
        return False

    def ip_allowed(self, ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if self._excluded(str(addr)):
            return False
        return any(addr in net for net in self.allowed_cidrs)

    def url_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        if not parsed.hostname:
            return False
        if self._excluded(parsed.hostname):
            return False

        norm = url.split("?", 1)[0]

        if self.allowed_url_prefixes:
            for prefix in self.allowed_url_prefixes:
                pref_p = urlparse(prefix)
                if not pref_p.hostname:
                    continue
                p_base = prefix.split("?", 1)[0].rstrip("/")
                n = norm.rstrip("/")
                if not (n == p_base or n.startswith(p_base + "/")):
                    continue
                if pref_p.scheme and parsed.scheme != pref_p.scheme:
                    continue
                if parsed.hostname.lower() != pref_p.hostname.lower():
                    continue

                def _port(u: Any) -> int:
                    scheme = u.scheme or "http"
                    return u.port or (443 if scheme == "https" else 80)

                if _port(parsed) != _port(pref_p):
                    continue
                return True
            return False

        return bool(self.host_allowed(parsed.hostname) or self.ip_allowed(parsed.hostname))

    def validate_target(self, target: str) -> None:
        """Raise ValueError if target (host, IP, or URL) is out of scope."""
        t = target.strip()
        if not t:
            raise ValueError("empty target")
        if "://" in t:
            if not self.url_allowed(t):
                raise ValueError(f"URL not allowed by scope: {t}")
            return
        try:
            ipaddress.ip_address(t)
            if not self.ip_allowed(t):
                raise ValueError(f"IP not in allowed_cidrs: {t}")
            return
        except ValueError:
            pass
        if self.host_allowed(t):
            return
        raise ValueError(f"Host not in allowed_hosts: {t}")


def load_scope_from_env(config_dir: Path) -> Scope:
    path = config_dir / "scope.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Missing scope file: {path}")
    return Scope.load(path)
