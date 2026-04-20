"""High-level methodology phases (PTES-style) for local planning hints."""

PHASES: list[dict[str, str | list[str]]] = [
    {
        "id": "pre_engagement",
        "title": "Pre-engagement & scope",
        "hints": [
            "Confirm written authorization and RoE.",
            "Lock targets in config/scope.yaml (hosts, CIDRs, URL prefixes).",
        ],
    },
    {
        "id": "recon_passive",
        "title": "Passive / light recon",
        "hints": [
            "whois, DNS (dig/host), certificate transparency if available.",
            "Keep traffic minimal until scope confirms active probing is allowed.",
        ],
    },
    {
        "id": "recon_active",
        "title": "Active mapping",
        "hints": [
            "nmap top ports, service fingerprint; curl/http probing on allowed URLs.",
        ],
    },
    {
        "id": "modeling",
        "title": "Attack surface modeling",
        "hints": [
            "List entry points: auth, uploads, APIs, admin paths.",
            "Map trust boundaries before deeper testing.",
        ],
    },
    {
        "id": "discovery",
        "title": "Vulnerability discovery",
        "hints": [
            "Structured tests per app profile; enable internal profile only if in scope.",
        ],
    },
    {
        "id": "validation",
        "title": "Controlled validation",
        "hints": [
            "Prove impact with least-destructive PoC; log evidence under output/.",
        ],
    },
    {
        "id": "reporting",
        "title": "Reporting & retest",
        "hints": [
            "Export findings with repro steps; re-run xjf exec for retest diffs.",
        ],
    },
]
