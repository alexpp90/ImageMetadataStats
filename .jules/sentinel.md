## 2024-08-24 - SSRF Bypass via IPv4-mapped IPv6 literals
**Vulnerability:** The application was vulnerable to Server-Side Request Forgery (SSRF) bypasses because it checked the primary IP object for \`is_unspecified\` but failed to perform the identical check on \`ipv4_mapped\` objects.
**Learning:** Security checks applied to the primary IP object (e.g., \`is_unspecified\`, \`is_link_local\`) must be identically mirrored on the \`ipv4_mapped\` object to prevent bypasses using IPv4-mapped IPv6 literals (e.g., \`::ffff:0.0.0.0\`).
**Prevention:** Always verify \`ipv4_mapped\` checks when dealing with IP validation and ensure asymmetric validation does not introduce logical inconsistencies.
