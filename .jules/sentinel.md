## 2025-02-27 - Fix SSRF bypass via IPv4-mapped unspecified IPs
**Vulnerability:** The application checks for malicious IP addresses (like `is_unspecified` which resolves to `0.0.0.0`) but fails to verify the same on the IPv4-mapped equivalent (`getattr(ip_obj, "ipv4_mapped", None)`). Attackers can bypass SSRF filters by requesting `::ffff:0.0.0.0`.
**Learning:** Security validation functions must check mapped objects identically to their parent IP objects. Assumed parity between IPv4 and IPv4-mapped IPv6 protections creates bypasses.
**Prevention:** Apply identical checks (e.g., `is_link_local`, `is_unspecified`) for the primary IP object and its `ipv4_mapped` version in all IP filtering logic.
