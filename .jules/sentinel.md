## 2025-05-24 - Unsafe SSRF Mitigation in Ollama Tool
**Vulnerability:** Incomplete SSRF protection via `ipaddress` for IPv4-mapped IPv6 literals.
**Learning:** `ipaddress.is_loopback` needs to be checked on `ip_obj.ipv4_mapped` exactly as it's checked (or not checked) on `ip_obj`. In `ollama.py`, `is_forbidden_ip` checks `ip_obj.is_link_local` and `ip_obj.is_unspecified`, and attempts to check `ipv4_mapped.is_link_local`, but misses `ipv4_mapped.is_unspecified`. This inconsistency allows bypass via IPv4-mapped IPv6 literals like `::ffff:0.0.0.0`.
**Prevention:** Always mirror the exact same security checks (unspecified, link_local, etc.) across both the primary `ip_obj` and its `ipv4_mapped` counterpart.
