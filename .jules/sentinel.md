## 2024-08-17 - SSRF Bypass via IPv4-mapped IPv6 literals
**Vulnerability:** The SSRF protection `is_forbidden_ip` blocked `is_unspecified` on primary IPs but failed to mirror this check for `ipv4_mapped` IPs, allowing bypasses using addresses like `::ffff:0.0.0.0`.
**Learning:** Asymmetric checks on primary vs mapped IPs introduce logical inconsistencies. If a restriction applies to an IP type (like `is_unspecified`), it must identically apply to its mapped equivalent.
**Prevention:** Always mirror IP filtering logic when accessing `ipv4_mapped` properties in custom SSRF/firewall checks.
