#!/usr/bin/env python3
"""Validate maintained AI lists; refresh only the official voice-IP snapshot."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOICE_URL = "https://openai.com/chatgpt-voice.json"
VOICE_SOURCE = ROOT / "sources/chatgpt-voice.json"


def voice_rules(data: dict) -> str:
    networks = set()
    for entry in data["prefixes"]:
        for key, value in entry.items():
            if key not in ("ipv4Prefix", "ipv6Prefix"):
                raise ValueError(f"unexpected voice prefix field: {key}")
            network = ipaddress.ip_network(value, strict=True)
            if not network.is_global:
                raise ValueError(f"non-public voice prefix: {network}")
            networks.add(network)
    if not networks:
        raise ValueError("empty official voice prefix list")
    lines = [
        "# NAME: AI-IP",
        "# MAINTAINER: reallinzc",
        f"# SOURCE: {VOICE_URL}",
        f"# SOURCE-UPDATED: {data['creationTime']}",
        "# Generated from sources/chatgpt-voice.json by scripts/ai_rules.py.",
        "# ChatGPT real-time voice; keep after domain rules, with no-resolve.",
        "",
    ]
    for network in sorted(networks, key=lambda n: (n.version, int(n.network_address), n.prefixlen)):
        kind = "IP-CIDR" if network.version == 4 else "IP-CIDR6"
        lines.append(f"{kind},{network},no-resolve")
    return "\n".join(lines) + "\n"


def read_rules(name: str) -> list[tuple[str, str]]:
    rules = []
    for number, line in enumerate((ROOT / name).read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",")
        kind, value = parts[:2] if len(parts) >= 2 else ("", "")
        if name == "AI-IP.list":
            if kind not in ("IP-CIDR", "IP-CIDR6") or parts[2:] != ["no-resolve"]:
                raise ValueError(f"{name}:{number}: invalid IP rule")
            network = ipaddress.ip_network(value, strict=True)
            if network.version != (4 if kind == "IP-CIDR" else 6) or not network.is_global:
                raise ValueError(f"{name}:{number}: invalid address family/range")
        else:
            if len(parts) != 2 or kind not in ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "URL-REGEX"):
                raise ValueError(f"{name}:{number}: unsupported rule or embedded policy")
            if kind == "URL-REGEX":
                re.compile(value)
            elif not re.fullmatch(r"[a-z0-9.-]+", value):
                raise ValueError(f"{name}:{number}: invalid domain")
        if (kind, value) in rules:
            raise ValueError(f"{name}:{number}: duplicate rule")
        rules.append((kind, value))
    if not rules:
        raise ValueError(f"empty rule set: {name}")
    return rules


def matches(host: str, rules: list[tuple[str, str]]) -> bool:
    for kind, value in rules:
        if kind == "DOMAIN" and host == value:
            return True
        if kind == "DOMAIN-SUFFIX" and (host == value or host.endswith("." + value)):
            return True
        if kind == "DOMAIN-KEYWORD" and value in host:
            return True
        if kind in ("IP-CIDR", "IP-CIDR6"):
            try:
                if ipaddress.ip_address(host) in ipaddress.ip_network(value):
                    return True
            except ValueError:
                pass
    return False


def check() -> None:
    expected = voice_rules(json.loads(VOICE_SOURCE.read_text()))
    if (ROOT / "AI-IP.list").read_text() != expected:
        raise ValueError("AI-IP.list differs from its source; run scripts/ai_rules.py --render-voice")
    lists = {name: read_rules(name) for name in ("AI.list", "AppleIntelligence.list", "AI-IP.list")}
    rules = [rule for group in lists.values() for rule in group]
    cases = json.loads((ROOT / "tests/ai-routing.json").read_text())
    for case in cases:
        if matches(case["host"], rules) != case["ai"]:
            raise ValueError(f"routing scope changed for {case['host']}")
    print(", ".join(f"{name}: {len(rows)} rules" for name, rows in lists.items()))
    print(f"Validated syntax, duplicate entries, official voice snapshot and {len(cases)} routing cases")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--render-voice", action="store_true", help="render the checked-in official snapshot")
    mode.add_argument("--refresh-voice", action="store_true", help="download the official snapshot and render it for review")
    args = parser.parse_args()
    if args.refresh_voice:
        request = urllib.request.Request(VOICE_URL, headers={"User-Agent": "reallinzc-Surge-AI/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
        rendered = voice_rules(data)
        VOICE_SOURCE.write_text(json.dumps(data, indent=2) + "\n")
        (ROOT / "AI-IP.list").write_text(rendered)
    elif args.render_voice:
        (ROOT / "AI-IP.list").write_text(voice_rules(json.loads(VOICE_SOURCE.read_text())))
    check()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
