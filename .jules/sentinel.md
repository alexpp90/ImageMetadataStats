## 2024-05-24 - IPv4-Mapped IPv6 SSRF Bypass via Unspecified Address
**Vulnerability:** The SSRF protection mechanism blocked unmapped `0.0.0.0` but failed to block the mapped equivalent `::ffff:0.0.0.0` (`::ffff:0.0.0.0` can map to localhost routing), bypassing the SSRF filters.
**Learning:** Python's `ipaddress` properties (`is_link_local`, `is_unspecified`) are not universally mirrored on `ipv4_mapped` IPv6 objects. We must enforce checks symmetrically.
**Prevention:** Any IP attribute check applied to the main IP must also be identically evaluated against `ipv4_mapped` if it exists.
