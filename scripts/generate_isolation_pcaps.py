#!/usr/bin/env python3
"""Generate a compact Scapy isolation test matrix for the P4 VXLAN lab.

This tool only writes crafted Ethernet frames to PCAP files for inspection/replay.
It does not inject traffic by itself. Review PCAPs and replay only in the isolated
Mininet topology. The expected policy is not an observed result.
"""
import argparse
import os
from scapy.all import Ether, IP, UDP, Raw, wrpcap

VXLAN_PORT = 4789

def vxlan_frame(vni, inner_src, inner_dst, inner_src_mac, inner_dst_mac, outer_src, outer_dst):
    # VXLAN header: flags I-bit 0x08, reserved 0, 24-bit VNI, reserved 0.
    vxlan = bytes([0x08, 0, 0, 0]) + int(vni).to_bytes(3, "big") + bytes([0])
    inner = Ether(src=inner_src_mac, dst=inner_dst_mac, type=0x0800) / IP(
        src=inner_src, dst=inner_dst
    ) / UDP(sport=12345, dport=9000) / Raw(load=b"p4-vxlan-isolation-test")
    payload = bytes(inner)
    return Ether(src="02:00:00:00:01:01", dst="02:00:00:00:01:02", type=0x0800) / IP(
        src=outer_src, dst=outer_dst
    ) / UDP(sport=49152, dport=VXLAN_PORT) / Raw(load=vxlan + payload)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output-dir", default="results/isolation-pcaps")
    args = ap.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    cases = [
        ("positive_A_valid", 1001, "192.168.10.1", "192.168.10.2",
         "00:00:00:00:10:01", "00:00:00:00:10:02", "10.0.0.1", "10.0.0.2"),
        ("positive_B_valid", 1002, "192.168.20.1", "192.168.20.2",
         "00:00:00:00:20:01", "00:00:00:00:20:02", "10.0.0.1", "10.0.0.2"),
        ("negative_A_spoof_B_vni", 1002, "192.168.10.1", "192.168.20.2",
         "00:00:00:00:10:01", "00:00:00:00:20:02", "10.0.0.1", "10.0.0.2"),
        ("negative_B_spoof_A_vni", 1001, "192.168.20.1", "192.168.10.2",
         "00:00:00:00:20:01", "00:00:00:00:10:02", "10.0.0.1", "10.0.0.2"),
        ("negative_A_wrong_destination", 1001, "192.168.10.1", "192.168.20.2",
         "00:00:00:00:10:01", "00:00:00:00:20:02", "10.0.0.1", "10.0.0.2"),
        ("negative_unknown_vni", 4095, "192.168.10.1", "192.168.10.2",
         "00:00:00:00:10:01", "00:00:00:00:10:02", "10.0.0.1", "10.0.0.2"),
        ("negative_unknown_destination", 1001, "192.168.10.1", "192.168.10.99",
         "00:00:00:00:10:01", "00:00:00:00:10:99", "10.0.0.1", "10.0.0.2"),
    ]

    matrix_path = os.path.join(args.output_dir, "test-matrix.csv")
    with open(matrix_path, "w", encoding="utf-8") as matrix:
        matrix.write("case,pcap,expected_policy,observed_result,notes\n")
        for case in cases:
            name, vni, inner_src, inner_dst, smac, dmac, outer_src, outer_dst = case
            packet = vxlan_frame(
                vni, inner_src, inner_dst, smac, dmac, outer_src, outer_dst
            )
            pcap_name = name + ".pcap"
            wrpcap(os.path.join(args.output_dir, pcap_name), [packet])
            expected = "deliver" if name.startswith("positive") else "drop"
            matrix.write(
                "%s,%s,%s,,Generated only; outcome must be recorded after isolated-lab replay\n"
                % (name, pcap_name, expected)
            )
    print("Created crafted PCAPs under %s" % args.output_dir)
    print("Created matrix at %s; observed_result is intentionally blank.")
    print("These are VXLAN inner-payload test captures for controlled lab validation, not an injection tool.")

if __name__ == "__main__":
    main()
