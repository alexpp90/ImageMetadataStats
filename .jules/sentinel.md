## 2024-05-24 - SSRF bypass via IPv4-mapped IPv6 for unspecified IPs
**Vulnerability:** The application had an SSRF vulnerability where unspecified IPs (0.0.0.0) could be bypassed using IPv4-mapped IPv6 literals like `::ffff:0.0.0.0`.
**Learning:** When protecting against SSRF, any security checks applied to the primary IP object must be identically mirrored on the `ipv4_mapped` object to prevent bypasses. In this case, `is_unspecified` was checked on the primary object but not on the mapped object.
**Prevention:** Always mirror the checks on the mapped IP object. E.g. `mapped = getattr(ip_obj, "ipv4_mapped", None)` and then check `mapped.is_unspecified` and `mapped.is_link_local`.
