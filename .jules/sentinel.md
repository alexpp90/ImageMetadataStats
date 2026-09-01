## 2025-02-28 - Incomplete SSRF Protection mapped.is_unspecified

**Vulnerability:** The SSRF protection logic checked `is_link_local` and `is_unspecified` on the primary IP object, but only checked `is_link_local` on the `ipv4_mapped` object. This asymmetric check could allow IPv4-mapped IPv6 literals to bypass the `is_unspecified` check.
**Learning:** Any security constraint placed on a primary IP address object must be symmetrically applied to its `ipv4_mapped` counterpart to prevent bypasses.
**Prevention:** Ensure that if `is_unspecified` (or any other check) is evaluated for the main IP object, the identical check is also enforced on the `ipv4_mapped` object if it exists.
