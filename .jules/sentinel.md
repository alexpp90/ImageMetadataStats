## 2024-05-18 - SSRF Bypass via IPv4-Mapped IPv6
**Vulnerability:** The SSRF protection in `is_forbidden_ip` failed to check `is_unspecified` on `ipv4_mapped` IPs, allowing `::ffff:0.0.0.0` to bypass the filter.
**Learning:** When validating IP addresses for SSRF, any security checks applied to the primary `ipaddress.ip_address` object must be identically mirrored on its `ipv4_mapped` representation.
**Prevention:** Always apply the exact same checks (e.g. `is_link_local`, `is_unspecified`) to both the main IP object and its `ipv4_mapped` version if it exists.
