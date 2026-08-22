## 2025-02-17 - SSRF Bypass via IPv4-Mapped IPv6 Literals
**Vulnerability:** The SSRF protection logic checked for `is_link_local` and `is_unspecified` on regular IP objects, but only checked `is_link_local` on IPv4-mapped IPv6 objects. This allowed bypassing SSRF restrictions using mapped literals like `::ffff:0.0.0.0`.
**Learning:** Any security checks applied to the primary IP object (e.g., `is_unspecified`, `is_link_local`) must be identically mirrored on the `ipv4_mapped` object to prevent bypasses using IPv4-mapped IPv6 literals.
**Prevention:** Ensure that all checks (like `is_unspecified`) are consistently applied to both the primary IP object and its mapped equivalent when dealing with `ipaddress` objects for SSRF defense.
