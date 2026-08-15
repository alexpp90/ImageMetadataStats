## 2025-03-05 - Incomplete IPv4-Mapped IPv6 SSRF Validation
**Vulnerability:** The `is_forbidden_ip` checks inside `photo_selector_toolbox` lacked parity between `ip_obj` and `ip_obj.ipv4_mapped` evaluations, missing the `.is_unspecified` verification on the mapped object.
**Learning:** Asymmetric validation where security checks for a primary IP structure are not strictly duplicated for its mapped/nested counterparts introduces bypass vectors (like `::ffff:0.0.0.0` passing while `0.0.0.0` is blocked).
**Prevention:** Always perfectly mirror security validations against the derived/mapped values (`ipv4_mapped`) exactly as performed on the parent IP object.
