#!/usr/bin/env python3

import argparse
from scapy.all import Ether, IP, UDP, Raw, sendp

parser = argparse.ArgumentParser()
parser.add_argument("--iface", required=True)
args = parser.parse_args()

inner = (
    Ether(
        src="02:aa:bb:cc:dd:01",
        dst="00:00:00:00:10:02"
    )
    / IP(src="192.168.10.1", dst="192.168.10.2", ttl=64)
    / UDP(sport=12345, dport=9999)
    / Raw(load=b"INGRESS_GUARD_TEST")
)

vxlan = bytes([0x08, 0, 0, 0]) + (1001).to_bytes(3, "big") + bytes([0])

packet = (
    Ether(src="02:00:00:00:01:01", dst="02:00:00:00:01:02")
    / IP(src="10.0.0.1", dst="10.0.0.2")
    / UDP(sport=40000, dport=4789)
    / Raw(load=vxlan + bytes(inner))
)

print("Injection interface:", args.iface)
print("VNI: 1001")
print("Inner destination: 192.168.10.2")

sendp(packet, iface=args.iface, count=1, verbose=False)

print("Injection completed.")
