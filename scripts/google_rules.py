#!/usr/bin/env python3
"""Generate and validate Google.list from v2fly domain-list-community."""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import tarfile
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "Google.list"
TESTS = ROOT / "tests" / "google-routing.json"
REPO = "v2fly/domain-list-community"
ROOT_LIST = "google"
MIN_RULES = 700

# Google brand gTLDs; any other dot-less DOMAIN-SUFFIX would capture a whole public TLD
# (open registries such as .app or .dev are deliberately excluded).
GOOGLE_TLDS = {
    "android", "chrome", "dclk", "gbiz", "gle", "gmail", "goog", "google",
    "guge", "hangout", "nexus", "youtube", "xn--flw351e", "xn--qcka1pmc",
}

# Google-owned domains missing from v2fly google; each resolved into AS15169 on 2026-10-31.
EXTRA_SUFFIXES = [
    "ampproject.com", "ampproject.net", "ampproject.org", "androidtv.com",
    "capitalg.com", "chromeexperiments.com", "crbug.com", "creativelab5.com",
    "crrev.com", "data-vocabulary.org", "deja.com", "digisfera.com",
    "digitalattackmap.com", "getmdl.io", "googlemashups.com", "googlescholar.com",
    "neverware.com", "plus.codes", "schema.org", "teachparentstech.org",
    "waveprotocol.org", "waymo.com", "zynamics.com",
]

# Non-domain rules kept from the previous blackmatrix7 Google list.
# The CIDRs are originated by AS15169; Android/Windows process rules never match on Surge.
SUPPLEMENT = [
    "IP-CIDR,74.125.0.0/16,no-resolve",
    "IP-CIDR,172.110.32.0/21,no-resolve",
    "IP-CIDR,173.194.0.0/16,no-resolve",
    "IP-CIDR,216.73.80.0/20,no-resolve",
    "IP-CIDR6,2620:120:e000::/40,no-resolve",
    "USER-AGENT,%E4%BA%91%E7%AB%AF%E7%A1%AC%E7%9B%98*",
    "USER-AGENT,*com.google.Drive*",
    "USER-AGENT,Google.Drive*",
]

TYPE_ORDER = {"DOMAIN": 0, "DOMAIN-SUFFIX": 1, "DOMAIN-KEYWORD": 2}


def fetch(url: str) -> bytes:
    headers = {"User-Agent": "reallinzc-surge-rules"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as resp:
        return resp.read()


def upstream_head() -> str:
    data = json.loads(fetch(f"https://api.github.com/repos/{REPO}/commits/master"))
    return data["sha"]


def snapshot(ref: str) -> dict[str, str]:
    """Read every data/<name> file from the upstream tarball at ref."""
    raw = fetch(f"https://codeload.github.com/{REPO}/tar.gz/{ref}")
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        for member in tar.getmembers():
            parts = member.name.split("/")
            if member.isfile() and len(parts) == 3 and parts[1] == "data":
                files[parts[2]] = tar.extractfile(member).read().decode()
    return files


def load(name: str, ref: str, cache: dict[str, str]) -> str:
    if name not in cache:
        raise SystemExit(f"upstream {ref[:12]} has no data/{name}")
    return cache[name]


def collect(name: str, ref: str, cache: dict[str, str], want: set[str] | None = None,
            seen: tuple[str, ...] = ()) -> tuple[set[tuple[str, str]], list[str]]:
    """Return (rules, skipped) for a v2fly list, following include: directives."""
    if name in seen:
        raise SystemExit(f"include cycle: {' -> '.join(seen + (name,))}")
    rules: set[tuple[str, str]] = set()
    skipped: list[str] = []
    for raw in load(name, ref, cache).splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        value, attrs = parts[0], {p[1:] for p in parts[1:] if p.startswith("@")}
        if value.startswith("include:"):
            # include:name @attr / @-attr filters the included entries.
            rules_, skipped_ = collect(value[8:], ref, cache, set(parts[1:]) or None, seen + (name,))
            rules |= rules_
            skipped += skipped_
            continue
        if want and not all((w[2:] not in attrs) if w.startswith("@-") else (w[1:] in attrs) for w in want):
            continue
        kind, _, val = value.rpartition(":")
        val = val.lower().rstrip(".")
        if kind in ("", "domain"):
            rules.add(("DOMAIN-SUFFIX", val))
        elif kind == "full":
            rules.add(("DOMAIN", val))
        elif kind == "keyword":
            rules.add(("DOMAIN-KEYWORD", val))
        else:
            skipped.append(f"{name}: {value}")
    return rules, skipped


def covered(kind: str, val: str, suffixes: set[str], keywords: set[str]) -> bool:
    if kind == "DOMAIN-KEYWORD":
        return any(k != val and k in val for k in keywords)
    if any(k in val for k in keywords):
        return True
    labels = val.split(".")
    start = 1 if kind == "DOMAIN-SUFFIX" else 0
    return any(".".join(labels[i:]) in suffixes for i in range(start, len(labels)))


def minimize(rules: set[tuple[str, str]]) -> list[tuple[str, str]]:
    suffixes = {v for k, v in rules if k == "DOMAIN-SUFFIX"}
    keywords = {v for k, v in rules if k == "DOMAIN-KEYWORD"}
    kept = [(k, v) for k, v in rules if not covered(k, v, suffixes, keywords)]
    return sorted(kept, key=lambda r: (TYPE_ORDER[r[0]], r[1]))


def render(ref: str, rules: list[tuple[str, str]], skipped: list[str]) -> str:
    counts = {k: sum(1 for r in rules if r[0] == k) for k in TYPE_ORDER}
    head = [
        "# NAME: Google",
        "# MAINTAINER: reallinzc",
        f"# SOURCE: https://github.com/{REPO}/blob/{ref}/data/{ROOT_LIST} (includes expanded)",
        f"# UPSTREAM-COMMIT: {ref}",
        "# LICENSE: v2fly MIT, see LICENSES/v2fly-MIT.txt; generated by scripts/google_rules.py",
        "# COUNTS: " + ", ".join(f"{k}={v}" for k, v in counts.items())
        + f" (incl. {len(EXTRA_SUFFIXES)} reviewed extras), SUPPLEMENT={len(SUPPLEMENT)}",
        "# Rules contain no policy; use RULE-SET,.../Google.list,Google,extended-matching,no-resolve",
    ]
    if skipped:
        head.append("# SKIPPED (no Surge equivalent): " + "; ".join(sorted(skipped)))
    body = [f"{k},{v}" for k, v in rules]
    supplement = ["", "# Supplement: AS15169 CIDRs and Google Drive user agents", *SUPPLEMENT]
    return "\n".join(head + [""] + body + supplement) + "\n"


def parse_list(text: str) -> list[tuple[str, str]]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            kind, val = line.split(",")[:2]
            out.append((kind, val))
    return out


def matches(rules: list[tuple[str, str]], host: str) -> bool:
    for kind, val in rules:
        if kind == "DOMAIN" and host == val:
            return True
        if kind == "DOMAIN-SUFFIX" and (host == val or host.endswith("." + val)):
            return True
        if kind == "DOMAIN-KEYWORD" and val in host:
            return True
    return False


def validate(text: str) -> list[str]:
    errors = []
    rules = parse_list(text)
    domain_rules = [r for r in rules if r[0] in TYPE_ORDER]
    if len(domain_rules) < MIN_RULES:
        errors.append(f"only {len(domain_rules)} domain rules (< {MIN_RULES})")
    for kind, val in domain_rules:
        if kind == "DOMAIN-SUFFIX" and "." not in val and val not in GOOGLE_TLDS:
            errors.append(f"bare TLD suffix outside Google gTLD allowlist: {val}")
        if not re.fullmatch(r"[a-z0-9.-]+", val) or val.startswith(".") or ".." in val:
            errors.append(f"malformed value: {kind},{val}")
    if len(set(rules)) != len(rules):
        errors.append("duplicate rules")
    cases = json.loads(TESTS.read_text())
    for host in cases["match"]:
        if not matches(domain_rules, host):
            errors.append(f"expected match: {host}")
    for host in cases["no_match"]:
        if matches(domain_rules, host):
            errors.append(f"unexpected match: {host}")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update", action="store_true",
                    help="regenerate from upstream master; rewrite only when rules change")
    args = ap.parse_args()

    current = OUTPUT.read_text() if OUTPUT.exists() else ""
    pinned = re.search(r"^# UPSTREAM-COMMIT: ([0-9a-f]{40})$", current, re.M)
    if args.update or not pinned:
        ref = upstream_head()
    else:
        ref = pinned.group(1)

    rules, skipped = collect(ROOT_LIST, ref, snapshot(ref))
    rules |= {("DOMAIN-SUFFIX", d) for d in EXTRA_SUFFIXES}
    text = render(ref, minimize(rules), skipped)
    errors = validate(text)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    strip = lambda s: [l for l in s.splitlines() if not l.startswith(("# SOURCE:", "# UPSTREAM-COMMIT:"))]
    if args.update:
        if strip(text) == strip(current):
            print(f"Google.list unchanged at {ref[:12]}")
        else:
            OUTPUT.write_text(text)
            print(f"Google.list regenerated at {ref[:12]}")
        return 0
    if text != current:
        print(f"Google.list differs from regeneration at {ref[:12]}; run --update", file=sys.stderr)
        return 1
    print(f"Google.list matches {ref[:12]}; {len(parse_list(text))} rules validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
