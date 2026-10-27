#!/usr/bin/env python3

from scapy.all import Ether, IP, UDP, Raw, sendp
import argparse

IFACE = "vtep1-eth3"

VTEP1_MAC = "02:00:00:00:01:01"
VTEP2_MAC = "02:00:00:00:01:02"

VTEP1_IP = "10.0.0.1"
VTEP2_IP = "10.0.0.2"

H2_MAC = "00:00:00:00:10:02"
H2_IP = "192.168.10.2"

H4_MAC = "00:00:00:00:20:02"
H4_IP = "192.168.20.2"


def make_packet(vni, inner_dst, inner_dst_mac, test_id):
    inner = (
        Ether(src="02:aa:bb:cc:dd:01", dst=inner_dst_mac)
        / IP(src="192.168.10.1", dst=inner_dst, ttl=64)
        / UDP(sport=12345, dport=9999)
        / Raw(load=("ISOLATION_TEST_" + test_id).encode())
    )

    vxlan = (
        bytes([0x08, 0, 0, 0])
        + int(vni).to_bytes(3, "big")
        + bytes([0])
    )

    return (
        Ether(src=VTEP1_MAC, dst=VTEP2_MAC)
        / IP(src=VTEP1_IP, dst=VTEP2_IP, ttl=64)
        / UDP(sport=40000, dport=4789)
        / Raw(load=vxlan + bytes(inner))
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case",
        choices=["valid", "wrong-dst", "unknown-vni"],
        required=True,
    )
    args = parser.parse_args()

    if args.case == "valid":
        vni, dst, mac = 1001, H2_IP, H2_MAC
    elif args.case == "wrong-dst":
        vni, dst, mac = 1001, H4_IP, H4_MAC
    else:
        vni, dst, mac = 1003, H2_IP, H2_MAC

    packet = make_packet(vni, dst, mac, args.case)

    print(f"Interface: {IFACE}")
    print(f"Case: {args.case}")
    print(f"VNI: {vni}")
    print(f"Inner destination: {dst}")
    print(f"Packet: {packet.summary()}")

    sendp(packet, iface=IFACE, count=1, verbose=False)
    print("Packet injection command completed.")


if __name__ == "__main__":
    main()
