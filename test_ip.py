import ipaddress

def is_forbidden_ip(ip_str):
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        if ip_obj.is_link_local:
            return True
        if ip_obj.is_unspecified:
            return True
        if getattr(ip_obj, "ipv4_mapped", None):
            if ip_obj.ipv4_mapped.is_link_local:
                return True
            if ip_obj.ipv4_mapped.is_unspecified:
                return True
        return False
    except ValueError:
        return False

print(is_forbidden_ip("0.0.0.0")) # True
print(is_forbidden_ip("::ffff:0.0.0.0")) # True
