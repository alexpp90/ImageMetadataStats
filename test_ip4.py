import ipaddress
ip = ipaddress.ip_address("::ffff:127.0.0.1")
print(ip.is_loopback)
