## 2024-08-26 - SSRF Bypass via IPv4-mapped IPv6 Address
**Vulnerability:** The SSRF protection mechanism correctly checked `is_unspecified` on regular IP addresses but missed checking `is_unspecified` on `ipv4_mapped` addresses.
**Learning:** Python's `ipaddress` library handles IPv4-mapped IPv6 literals (`::ffff:0.0.0.0`) by requiring properties to be checked on both the primary object and the `ipv4_mapped` attribute to ensure complete validation.
**Prevention:** Always symmetrically check both the primary object and its `ipv4_mapped` counterpart when enforcing IP-based filtering in Python.
