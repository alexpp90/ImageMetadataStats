## 2025-05-20 - Asymmetric SSRF IP validation bypass
**Vulnerability:** The SSRF protection functions failed to identically mirror all security checks to the IPv4-mapped IP object (`ipv4_mapped`).
**Learning:** Python's `ipaddress` module parses mapped addresses separately. Thus, checking `is_unspecified` on the primary IP object doesn't block mapped IP equivalent `::ffff:0.0.0.0` if `is_unspecified` isn't also enforced on the `ipv4_mapped` object.
**Prevention:** Always perfectly mirror ALL security attribute assertions on the primary IP object over to the `ipv4_mapped` object, to prevent bypasses utilizing IPv4-mapped IPv6 literals.
