#!/usr/bin/env python3
"""Isolated tenant/VTEP scalability tests for the VXLAN P4 project."""

import argparse
import csv
import ipaddress
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Switch, OVSSwitch
from mininet.log import setLogLevel

ROOT = Path(__file__).resolve().parents[1]
JSON = ROOT / "build" / "vxlan_scalability.json"
RESULTS = ROOT / "results" / "scalability"
UNDERLAY_PREFIX = "10.254.0."


class P4Switch(Switch):
    def __init__(self, name, json_path, thrift_port, **kwargs):
        self.json_path = str(json_path)
        self.thrift_port = thrift_port
        self.pidfile = f"/tmp/{name}_scalability.pid"
        self.logfile = f"/tmp/{name}_scalability.log"
        super().__init__(name, **kwargs)

    def start(self, controllers):
        device_id = self.thrift_port - 9089
        args = ["simple_switch", "--device-id", str(device_id)]
        for port, intf in sorted(self.intfs.items()):
            if port:
                args += ["-i", f"{port}@{intf.name}"]
        args += ["--thrift-port", str(self.thrift_port), self.json_path]
        command = " ".join(args)
        self.cmd(f"{command} > {self.logfile} 2>&1 & echo $! > {self.pidfile}")

    def stop(self):
        self.cmd(f"kill $(cat {self.pidfile}) 2>/dev/null || true")
        self.cmd(f"rm -f {self.pidfile}")
        super().stop()


class ScalableTopo(Topo):
    def build(self, tenants=2, vteps=2):
        self.tenants = tenants
        self.vteps = vteps

        for v in range(vteps):
            self.addSwitch(
                f"vtep{v + 1}", cls=P4Switch,
                json_path=JSON, thrift_port=9090 + v,
                dpid=f"{v + 1:016x}"
            )

        underlay = self.addSwitch(
            "underlay", cls=OVSSwitch, failMode="standalone",
            dpid="00000000000000ff"
        )

        for v in range(vteps):
            for t in range(tenants):
                host_num = v * tenants + t + 1
                ip = f"192.168.{t + 1}.{v + 1}/24"
                mac = f"02:00:{t + 1:02x}:{v + 1:02x}:00:01"
                host = self.addHost(
                    f"h{host_num}", ip=ip, mac=mac,
                    defaultRoute=None
                )
                self.addLink(host, f"vtep{v + 1}")

        for v in range(vteps):
            self.addLink(f"vtep{v + 1}", underlay)


def run_cli(thrift_port, commands):
    proc = subprocess.run(
        ["simple_switch_CLI", "--thrift-port", str(thrift_port)],
        input="\n".join(commands) + "\n",
        capture_output=True, text=True, timeout=15
    )
    output = proc.stdout + proc.stderr
    if proc.returncode or "Invalid" in output or "Error" in output:
        raise RuntimeError(
            f"BMv2 CLI failed on port {thrift_port}:\n{output}"
        )
    return output


def host_ip(tenant, vtep):
    return f"192.168.{tenant}.{vtep}"


def underlay_ip(vtep):
    return f"{UNDERLAY_PREFIX}{vtep}"


def underlay_mac(vtep):
    return f"02:fe:00:00:00:{vtep:02x}"


def configure_underlay(net, vteps):
    for v in range(1, vteps + 1):
        sw = net.get(f"vtep{v}")
        # Tenant-facing ports are 1..T; the underlay is port T+1.
        port = len(sw.intfs) - 1
        intf = sw.intfs[port]
        intf.setIP(underlay_ip(v), prefixLen=24)
        intf.setMAC(underlay_mac(v))
        sw.cmd("sysctl -w net.ipv4.ip_forward=0 >/dev/null")
        for remote in range(1, vteps + 1):
            if remote != v:
                sw.cmd(
                    f"ip neigh replace {underlay_ip(remote)} "
                    f"lladdr {underlay_mac(remote)} nud permanent dev {intf.name}"
                )


def configure_rules(net, tenants, vteps):
    for v in range(1, vteps + 1):
        thrift = 9089 + v
        underlay_port = tenants + 1
        src_ip = underlay_ip(v)
        src_mac = underlay_mac(v)
        commands = []

        # Permit only the legitimate local source IP on each tenant port.
        for t in range(1, tenants + 1):
            local_source_ip = host_ip(t, v)
            commands.append(
                "table_add MyIngress.source_guard MyIngress.allow_source "
                f"{t} {local_source_ip} =>"
            )

        # Tenant-facing encapsulation: only same-tenant remote destinations.
        for t in range(1, tenants + 1):
            for remote in range(1, vteps + 1):
                if remote == v:
                    continue
                dst_ip = host_ip(t, remote)
                dst_underlay_ip = underlay_ip(remote)
                dst_mac = underlay_mac(remote)
                vni = 1000 + t
                commands.append(
                    "table_add MyIngress.encap_by_port MyIngress.encapsulate "
                    f"{t} {dst_ip} => {vni} {src_mac} {dst_mac} "
                    f"{src_ip} {dst_underlay_ip} {underlay_port}"
                )

        # Accept inner source addresses only when they belong to the VNI
        # and arrive from the underlay interface.
        for t in range(1, tenants + 1):
            vni = 1000 + t
            for remote in range(1, vteps + 1):
                if remote == v:
                    continue
                remote_source_ip = host_ip(t, remote)
                commands.append(
                    "table_add MyIngress.decap_source_guard "
                    "MyIngress.allow_source "
                    f"{underlay_port} {vni} {remote_source_ip} =>"
                )

        # Decapsulation is authorised only on the underlay ingress port.
        for t in range(1, tenants + 1):
            local_host_ip = host_ip(t, v)
            vni = 1000 + t
            commands.append(
                "table_add MyIngress.decap_by_vni_and_dst "
                f"MyIngress.decapsulate {underlay_port} {vni} "
                f"{local_host_ip} => {t}"
            )

        commands.append("show_tables")
        run_cli(thrift, commands)
        print(f"Configured vtep{v} ({len(commands)-1} rules).")

    # Configure static ARP/neighbor mappings on each VTEP underlay.
    for v in range(1, vteps + 1):
        sw = net.get(f"vtep{v}")
        underlay_port = tenants + 1
        intf = sw.intfs[underlay_port]
        for remote in range(1, vteps + 1):
            if remote != v:
                sw.cmd(
                    f"ip neigh replace {underlay_ip(remote)} "
                    f"lladdr {underlay_mac(remote)} nud permanent dev {intf.name}"
                )


def test_connectivity(net, tenants, vteps):
    positive_total = positive_passed = 0
    cross_total = cross_blocked = 0
    spoof_total = spoof_blocked = 0
    failures = []

    # Install static neighbour entries to avoid ARP broadcasts.
    for tenant in range(1, tenants + 1):
        for source_vtep in range(1, vteps + 1):
            src_num = (source_vtep - 1) * tenants + tenant
            src = net.get(f"h{src_num}")
            intf = src.defaultIntf().name

            for dest_vtep in range(1, vteps + 1):
                if source_vtep == dest_vtep:
                    continue
                for dest_tenant in range(1, tenants + 1):
                    dst_ip = host_ip(dest_tenant, dest_vtep)
                    dst_mac = (
                        f"02:00:{dest_tenant:02x}:"
                        f"{dest_vtep:02x}:00:01"
                    )
                    src.cmd(
                        f"ip neigh replace {dst_ip} lladdr {dst_mac} "
                        f"nud permanent dev {intf}"
                    )

    # 1. Legitimate same-tenant connectivity.
    for tenant in range(1, tenants + 1):
        for source_vtep in range(1, vteps + 1):
            for dest_vtep in range(1, vteps + 1):
                if source_vtep == dest_vtep:
                    continue

                src_num = (source_vtep - 1) * tenants + tenant
                src = net.get(f"h{src_num}")
                dst_ip = host_ip(tenant, dest_vtep)
                positive_total += 1

                result = src.cmd(f"ping -c 1 -W 2 {dst_ip} 2>&1")
                if "1 received" in result or "1 packets received" in result:
                    positive_passed += 1
                else:
                    failures.append(
                        f"LEGITIMATE traffic failed: tenant {tenant}, "
                        f"VTEP {source_vtep}->{dest_vtep}: "
                        f"{result.strip().splitlines()[-1:]}"
                    )

    # 2. Cross-tenant traffic must not reach the destination host.
    for source_tenant in range(1, tenants + 1):
        for source_vtep in range(1, vteps + 1):
            for dest_vtep in range(1, vteps + 1):
                if source_vtep == dest_vtep:
                    continue

                src_num = (source_vtep - 1) * tenants + source_tenant
                src = net.get(f"h{src_num}")

                for dest_tenant in range(1, tenants + 1):
                    if dest_tenant == source_tenant:
                        continue

                    dst_ip = host_ip(dest_tenant, dest_vtep)
                    dst_num = (dest_vtep - 1) * tenants + dest_tenant
                    dst = net.get(f"h{dst_num}")
                    dst_intf = dst.defaultIntf().name
                    capture = (
                        f"/tmp/cross_{source_tenant}_{source_vtep}_"
                        f"{dest_tenant}_{dest_vtep}.log"
                    )
                    cross_total += 1

                    # Observe whether the forbidden ICMP packet arrives.
                    dst.cmd(
                        f"timeout 3 tcpdump -n -i {dst_intf} "
                        f"-c 1 'icmp and dst host {dst_ip}' "
                        f"> {capture} 2>&1 &"
                    )
                    time.sleep(0.2)
                    src.cmd(f"ping -c 1 -W 1 {dst_ip} >/dev/null 2>&1")
                    time.sleep(3.5)
                    observed = dst.cmd(f"cat {capture} 2>/dev/null")

                    if "1 packet captured" in observed:
                        failures.append(
                            f"CROSS-TENANT LEAK: tenant {source_tenant} "
                            f"to tenant {dest_tenant}, "
                            f"VTEP {source_vtep}->{dest_vtep}"
                        )
                    elif "0 packets captured" in observed:
                        cross_blocked += 1
                    else:
                        failures.append(
                            f"CROSS-TENANT TEST INCONCLUSIVE: "
                            f"tenant {source_tenant} to {dest_tenant}: "
                            f"{observed.strip()[-200:]}"
                        )

    # 3. Spoofed inner source addresses must not reach remote tenant hosts.
    for tenant in range(1, tenants + 1):
        if tenants < 2:
            break

        forged_tenant = tenant % tenants + 1

        for source_vtep in range(1, vteps + 1):
            for dest_vtep in range(1, vteps + 1):
                if source_vtep == dest_vtep:
                    continue

                src_num = (source_vtep - 1) * tenants + tenant
                dst_num = (dest_vtep - 1) * tenants + tenant
                src = net.get(f"h{src_num}")
                dst = net.get(f"h{dst_num}")

                src_intf = src.defaultIntf().name
                dst_intf = dst.defaultIntf().name
                src_mac = f"02:00:{tenant:02x}:{source_vtep:02x}:00:01"
                dst_mac = f"02:00:{tenant:02x}:{dest_vtep:02x}:00:01"
                forged_ip = host_ip(forged_tenant, source_vtep)
                dst_ip = host_ip(tenant, dest_vtep)
                capture = (
                    f"/tmp/spoof_{tenant}_{source_vtep}_{dest_vtep}.log"
                )
                spoof_total += 1

                dst.cmd(
                    f"timeout 3 tcpdump -n -i {dst_intf} -c 1 "
                    f"'icmp and src host {forged_ip} and dst host {dst_ip}' "
                    f"> {capture} 2>&1 &"
                )
                time.sleep(0.2)

                send = (
                    "from scapy.all import Ether,IP,ICMP,sendp; "
                    f"sendp(Ether(src='{src_mac}',dst='{dst_mac}')/"
                    f"IP(src='{forged_ip}',dst='{dst_ip}')/ICMP(), "
                    f"iface='{src_intf}', verbose=False)"
                )
                sent = src.cmd(
                    "python3 -c " + shlex.quote(send) + " 2>&1"
                )
                time.sleep(3.5)
                observed = dst.cmd(f"cat {capture} 2>/dev/null")

                if "1 packet captured" in observed:
                    failures.append(
                        f"SPOOFED SOURCE ACCEPTED: forged {forged_ip}, "
                        f"destination {dst_ip}, "
                        f"VTEP {source_vtep}->{dest_vtep}"
                    )
                elif "0 packets captured" in observed and not sent.strip():
                    spoof_blocked += 1
                else:
                    failures.append(
                        f"SPOOF TEST INCONCLUSIVE: forged {forged_ip}: "
                        f"sender={sent.strip()[-120:]}, "
                        f"capture={observed.strip()[-120:]}"
                    )

    print(
        f"Legitimate connectivity: {positive_passed}/{positive_total}"
    )
    print(f"Cross-tenant packets blocked: {cross_blocked}/{cross_total}")
    print(f"Spoofed-source packets blocked: {spoof_blocked}/{spoof_total}")

    if failures:
        print("Security/connectivity failures:")
        for item in failures[:12]:
            print("  " + item)

    all_passed = (
        positive_passed == positive_total
        and cross_blocked == cross_total
        and spoof_blocked == spoof_total
        and positive_total > 0
        and cross_total > 0
        and spoof_total > 0
    )
    return int(all_passed), 1, failures

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("tenants", "vteps"), required=True)
    parser.add_argument("--values", nargs="+", type=int, required=True)
    parser.add_argument("--fixed", type=int, default=2,
                        help="Fixed VTEPs for tenant tests or tenants for VTEP tests")
    args = parser.parse_args()

    if os.geteuid() != 0:
        sys.exit("Run with sudo from WSL.")
    if not JSON.is_file():
        sys.exit(f"Missing {JSON}; compile the scalability P4 program first.")

    RESULTS.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_csv = RESULTS / f"{args.mode}_scalability_{timestamp}.csv"

    with output_csv.open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=[
                "mode", "tenants", "vteps", "security_tests_passed",
                "security_tests_total", "security_tests_ok",
                "setup_seconds", "test_seconds", "notes"
            ]
        )
        writer.writeheader()

        for value in args.values:
            tenants = value if args.mode == "tenants" else args.fixed
            vteps = args.fixed if args.mode == "tenants" else value
            if not 1 <= tenants <= 8:
                raise SystemExit("Tenant count must be between 1 and 8.")
            if not 2 <= vteps <= 4:
                raise SystemExit("VTEP count must be between 2 and 4.")

            print(f"\n=== {tenants} tenants, {vteps} VTEPs ===")
            topo = ScalableTopo(tenants=tenants, vteps=vteps)
            net = Mininet(topo=topo, controller=None, autoSetMacs=False)
            start = time.monotonic()
            passed = total = 0
            notes = ""

            try:
                net.start()
                time.sleep(2)
                configure_underlay(net, vteps)
                configure_rules(net, tenants, vteps)
                setup_seconds = time.monotonic() - start
                test_start = time.monotonic()
                passed, total, failures = test_connectivity(
                    net, tenants, vteps
                )
                test_seconds = time.monotonic() - test_start
                notes = " | ".join(failures[:3])
            except Exception as exc:
                setup_seconds = time.monotonic() - start
                test_seconds = 0
                notes = f"ERROR: {exc}"
                print(notes)
            finally:
                net.stop()

            writer.writerow({
                "mode": args.mode,
                "tenants": tenants,
                "vteps": vteps,
                "security_tests_passed": passed,
                "security_tests_total": total,
                "security_tests_ok": int(total > 0 and passed == total),
                "setup_seconds": round(setup_seconds, 3),
                "test_seconds": round(test_seconds, 3),
                "notes": notes
            })
            f.flush()

    print(f"\nResults saved to: {output_csv}")


if __name__ == "__main__":
    setLogLevel("warning")
    main()
