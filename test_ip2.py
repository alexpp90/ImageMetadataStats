import ipaddress
ip = ipaddress.ip_address("::ffff:0.0.0.0")
print(ip.is_unspecified)
print(ip.is_link_local)
