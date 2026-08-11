## 2024-05-20 - Incomplete SSRF protection via IPv4-mapped IPv6 literals
**Vulnerability:** The `is_forbidden_ip` check within `ollama.py` and `aesthetic_settings.py` checked `ip_obj.ipv4_mapped.is_link_local` to block cloud metadata IPs, but missed `ip_obj.ipv4_mapped.is_unspecified`. This allowed SSRF attacks on localhost via `::ffff:0.0.0.0`.
**Learning:** Security checks on an `ipaddress` object's primary IP must be identically mirrored on its `ipv4_mapped` counterpart to prevent bypasses utilizing mapped literals.
**Prevention:** Ensure that anytime `ipv4_mapped` is extracted from an `ipaddress` object, all corresponding flag checks (e.g. `is_unspecified`, `is_link_local`) applied to the main IP are consistently evaluated against the mapped IP.
