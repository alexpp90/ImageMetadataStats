## 2024-05-18 - SSRF Bypass via IPv4-mapped IPv6 Unspecified Address
**Vulnerability:** The SSRF protection in local network IP checks only evaluated `is_link_local` on the `ipv4_mapped` object for IPv6 literals (e.g. `::ffff:0.0.0.0`), bypassing the `is_unspecified` check applied to standard IPv4 objects.
**Learning:** Asymmetric security checks between primary IP objects and their `ipv4_mapped` equivalents can introduce logical bypasses.
**Prevention:** Ensure that any security checks applied to the primary IP object (like `is_unspecified`, `is_link_local`) are identically mirrored on the `ipv4_mapped` object to prevent bypasses using IPv4-mapped IPv6 literals.
