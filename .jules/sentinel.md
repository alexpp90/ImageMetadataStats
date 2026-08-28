## 2024-05-18 - [Fix SSRF bypass via IPv4-mapped IPv6 literals]
**Vulnerability:** The SSRF block list checked `is_unspecified` on main IPs, but only checked `is_link_local` on `ipv4_mapped` IPs, enabling SSRF via mapped unspecified IPs like `::ffff:0.0.0.0`.
**Learning:** Security checks on IP addresses must be applied symmetrically. If an IP property (like `is_unspecified`) is blocked, the same property must be blocked on its `ipv4_mapped` version if it exists.
**Prevention:** Always mirror the exact same `is_link_local`, `is_loopback`, `is_unspecified`, and `is_private` block lists against the `.ipv4_mapped` object to prevent IPv6 bypasses.
