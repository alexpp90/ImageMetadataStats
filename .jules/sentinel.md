## 2024-05-30 - SSRF IP Validation Bypass
**Vulnerability:** SSRF bypass via IPv4-mapped IPv6 addresses (e.g. ::ffff:0.0.0.0)
**Learning:** Python's ipaddress module requires explicitly checking the .ipv4_mapped property for the same conditions checked on the main IP object, because an IPv4-mapped IPv6 address (like ::ffff:0.0.0.0) might return False for .is_unspecified but its mapped IPv4 address returns True.
**Prevention:** Always ensure any security check applied to the primary IP object is identically mirrored on the ipv4_mapped object.
