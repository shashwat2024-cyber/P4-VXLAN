#!/usr/bin/env python3
"""Send a tenant-originated VXLAN injection attempt for the second-level review.

Run from the Mininet CLI while the corrected topology is active:
    h1 python3 scripts/test_tenant_vxlan_injection.py

The crafted packet enters VTEP1 through tenant A's host-facing port. It carries
VNI 1002 and inner destination 192.168.20.1 (h3). Sending the packet is not
proof of delivery; capture on h3-eth0 concurrently and verify that no UDP/9999
packet arrives. Keep a same-tenant positive control to ensure normal forwarding
still works.
"""
from scapy.all import Ether, IP, UDP, sendp
from scapy.contrib.vxlan import VXLAN

packet = (
    Ether(src="02:aa:aa:aa:aa:01", dst="02:00:00:00:20:01")
    / IP(src="10.0.0.99", dst="10.0.0.1")
    / UDP(sport=49152, dport=4789)
    / VXLAN(vni=1002)
    / Ether(src="02:bb:bb:bb:bb:01", dst="00:00:00:00:20:01")
    / IP(src="192.168.10.1", dst="192.168.20.1")
    / UDP(sport=40000, dport=9999)
)

print("Sending tenant-originated VXLAN injection on h1-eth0")
sendp(packet, iface="h1-eth0", count=3, inter=0.2, verbose=False)
print("Sent 3 crafted frames. Check a simultaneous capture on h3-eth0.")
