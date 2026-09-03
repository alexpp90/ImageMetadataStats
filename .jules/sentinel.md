## 2024-05-24 - SSRF bypass via IPv4-mapped IPv6 literals
**Vulnerability:** A bypass in the SSRF protection logic when parsing `ipaddress` objects. The application checks for `is_link_local` and `is_unspecified` on the primary IP object, but only checked `is_link_local` on the `ipv4_mapped` object. This meant an IPv4-mapped IPv6 literal pointing to an unspecified address like `::ffff:0.0.0.0` bypassed the `is_unspecified` block, leading to an SSRF bypass.
**Learning:** Security checks applied to `ipaddress` objects must be fully mirrored onto any `ipv4_mapped` version of the address to prevent bypasses. Asymmetric checks can open up vulnerabilities.
**Prevention:** Always verify that all checks applied to an IP object are identically applied to its mapped counterpart.
