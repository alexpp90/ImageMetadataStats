## 2024-05-15 - Missing SSRF Check for IPv4-mapped IPv6 Literals
**Vulnerability:** The SSRF protection logic in `_is_forbidden_ip` checked `is_link_local` and `is_unspecified` for regular IP objects, but only checked `is_link_local` for IPv4-mapped IPv6 objects.
**Learning:** Security checks must be applied symmetrically. If a condition is checked on the primary IP object, it must also be verified on the mapped IP object to prevent bypasses using formats like `::ffff:0.0.0.0`.
**Prevention:** When validating IP addresses, always ensure all security conditions are uniformly enforced on both the raw IP and any mapped representations (like `ipv4_mapped`).
