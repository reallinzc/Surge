#!/usr/bin/env python3
"""Generate and validate the regional Telegram Surge rule sets."""

from __future__ import annotations

import argparse
import ipaddress
import re
import sys
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CIDR_URL = "https://core.telegram.org/resources/cidr.txt"
PROXY_CONFIG_URL = "https://core.telegram.org/getProxyConfig"

REGIONS = {
    "Americas": {
        "file": "TelegramDC-Americas.list",
        "desc": "Telegram DC1/DC3 address space routed through the Japan T1 Smart group",
        "asns": (59930,),
        "cidrs": (
            "91.108.12.0/22",
            "149.154.172.0/22",
            "2a0a:f280::/32",
        ),
        "note": "149.154.160.0/20 is intentionally split by live regional route evidence.",
    },
    "Europe": {
        "file": "TelegramDC-Europe.list",
        "desc": "Telegram DC2/DC4/DC203 address space routed through the Hong Kong T1 Smart group",
        "asns": (44907, 211157),
        "cidrs": (
            "91.105.192.0/23",
            "91.108.4.0/22",
            "91.108.8.0/22",
            "91.108.20.0/22",
            "149.154.160.0/21",
            "185.76.151.0/24",
            "2001:b28:f23c::/48",
            "2001:b28:f23d::/48",
            "2001:67c:4e8::/48",
        ),
        "note": "AS62041 is omitted because its 149.154.160.0/20 is split across regions.",
    },
    "Singapore": {
        "file": "TelegramDC-Singapore.list",
        "desc": "Telegram DC5 address space routed through the Singapore V.PS node",
        "asns": (62014,),
        "cidrs": (
            "91.108.16.0/22",
            "91.108.56.0/22",
            "149.154.168.0/22",
            "2001:b28:f23f::/48",
        ),
        "note": "149.154.168.0/22 is split from AS62041 by live Singapore route evidence.",
    },
}

DC_REGION = {
    1: "Americas",
    2: "Europe",
    3: "Americas",
    4: "Europe",
    5: "Singapore",
    203: "Europe",
}


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "reallinzc-Surge-rule-validator/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8")


def network_map() -> dict[str, tuple[ipaddress._BaseNetwork, ...]]:
    return {
        region: tuple(ipaddress.ip_network(cidr) for cidr in config["cidrs"])
        for region, config in REGIONS.items()
    }


def parse_official_networks(text: str) -> tuple[ipaddress._BaseNetwork, ...]:
    return tuple(
        ipaddress.ip_network(line.strip())
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def collapsed(networks: tuple[ipaddress._BaseNetwork, ...], version: int) -> tuple[str, ...]:
    selected = (network for network in networks if network.version == version)
    return tuple(str(network) for network in ipaddress.collapse_addresses(selected))


def validate_partition(official: tuple[ipaddress._BaseNetwork, ...]) -> None:
    by_region = network_map()
    region_names = tuple(by_region)
    for index, left_name in enumerate(region_names):
        for right_name in region_names[index + 1 :]:
            for left in by_region[left_name]:
                for right in by_region[right_name]:
                    if left.version == right.version and left.overlaps(right):
                        raise ValueError(f"overlap: {left_name} {left} and {right_name} {right}")

    regional = tuple(network for networks in by_region.values() for network in networks)
    for version in (4, 6):
        expected = collapsed(official, version)
        actual = collapsed(regional, version)
        if actual != expected:
            raise ValueError(
                f"official IPv{version} coverage changed: expected {expected}, regional rules have {actual}"
            )


def validate_proxy_config(text: str) -> None:
    by_region = network_map()
    matches = re.findall(r"proxy_for\s+(-?\d+)\s+([0-9a-fA-F:.]+):\d+;", text)
    if not matches:
        raise ValueError("no proxy_for endpoints found")

    for raw_dc, raw_ip in matches:
        dc = abs(int(raw_dc))
        expected_region = DC_REGION.get(dc)
        if expected_region is None:
            raise ValueError(f"unmapped Telegram DC: {dc}")
        address = ipaddress.ip_address(raw_ip)
        owners = [
            region
            for region, networks in by_region.items()
            if any(address in network for network in networks)
        ]
        if owners != [expected_region]:
            raise ValueError(
                f"DC{dc} endpoint {address} belongs to {owners or ['no region']}, expected {expected_region}"
            )


def render(region: str, config: dict[str, object]) -> str:
    lines = [
        f"# NAME: TelegramDC-{region}",
        f"# DESC: {config['desc']}",
        f"# SOURCE: {CIDR_URL}",
        f"# DC-ENDPOINTS: {PROXY_CONFIG_URL}",
        "# REGION-REFERENCE: https://raw.githubusercontent.com/Repcz/Tool/X/Surge/Custom/Telegram.list",
        f"# NOTE: {config['note']}",
        "",
    ]
    lines.extend(f"IP-ASN,{asn},no-resolve" for asn in config["asns"])
    for cidr in config["cidrs"]:
        kind = "IP-CIDR6" if ":" in cidr else "IP-CIDR"
        lines.append(f"{kind},{cidr},no-resolve")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate live sources and committed files")
    args = parser.parse_args()

    official = parse_official_networks(fetch_text(CIDR_URL))
    validate_partition(official)
    validate_proxy_config(fetch_text(PROXY_CONFIG_URL))

    changed = []
    for region, config in REGIONS.items():
        path = ROOT / str(config["file"])
        expected = render(region, config)
        current = path.read_text() if path.exists() else None
        if current == expected:
            continue
        changed.append(path.name)
        if not args.check:
            path.write_text(expected)

    if args.check and changed:
        print("outdated generated files: " + ", ".join(changed), file=sys.stderr)
        return 1

    action = "validated" if args.check else "generated"
    print(f"{action}: full official CIDR coverage, no overlaps, current DC endpoints correctly mapped")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
