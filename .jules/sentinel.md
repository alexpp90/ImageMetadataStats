## 2024-05-24 - SSRF bypass via IPv4-mapped IPv6 literals
**Vulnerability:** The code blocked link-local and unspecified IP addresses for IPv4, but the equivalent check for IPv4-mapped IPv6 addresses did not check for `is_unspecified`.
**Learning:** The Python `ipaddress` module's `.is_unspecified` property must be checked on the mapped IPv4 object as well.
**Prevention:** Always verify that security checks on `ipaddress` objects are identically mirrored on `.ipv4_mapped` objects to prevent bypasses.
