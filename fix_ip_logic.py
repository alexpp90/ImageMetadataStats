import ipaddress

def is_forbidden_ip(ip_str):
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        if ip_obj.is_link_local:
            return True
        if ip_obj.is_unspecified:
            return True

        # Check IPv4 mapped
        if hasattr(ip_obj, "ipv4_mapped") and ip_obj.ipv4_mapped is not None:
            mapped = ip_obj.ipv4_mapped
            if mapped.is_link_local:
                return True
            if mapped.is_unspecified:
                return True

        return False
    except ValueError:
        return False

print("Mapped Link Local:", is_forbidden_ip("::ffff:169.254.169.254"))
print("Mapped Unspecified:", is_forbidden_ip("::ffff:0.0.0.0"))
print("Normal Link Local:", is_forbidden_ip("169.254.169.254"))
print("Normal Unspecified:", is_forbidden_ip("0.0.0.0"))
