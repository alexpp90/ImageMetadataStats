## 2026-08-29 - SSRF Bypass via IPv4-mapped IPv6 Unspecified Addresses
**Vulnerability:** The SSRF protection functions allowed `::ffff:0.0.0.0` bypassing the `is_unspecified` check. Although `ip_obj.is_unspecified` on `::ffff:0.0.0.0` evaluates to `True`, a symmetric check for `mapped.is_unspecified` was missing from the `ipv4_mapped` branch which is an inconsistency.
**Learning:** When validating IP addresses for SSRF protection via Python's `ipaddress` module, any security checks applied to the primary IP object (e.g., `is_unspecified`, `is_link_local`) must be identically mirrored on the `ipv4_mapped` object to prevent bypasses using IPv4-mapped IPv6 literals.
**Prevention:** Ensure symmetric application of IP checks on both the primary IP object and any associated mapped IP object.
