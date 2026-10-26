#!/usr/bin/env python3
"""Mininet topology for a plain-L2 P4 forwarding baseline without VXLAN.

There are two tenant-facing ports on each P4 switch and port 3 leads to the
shared OVS underlay. Ethernet destination MAC determines the egress port on
underlay ingress. This is a performance baseline, not an isolation design.
"""
import os
import subprocess
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from topology.vxlan_topology import P4Switch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
JSON = os.path.join(ROOT, "build", "baseline.json")

class BaselineTopo(Topo):
    def build(self):
        h1 = self.addHost("h1", ip="192.168.10.1/24", mac="00:00:00:00:10:01")
        h2 = self.addHost("h2", ip="192.168.10.2/24", mac="00:00:00:00:10:02")
        h3 = self.addHost("h3", ip="192.168.20.1/24", mac="00:00:00:00:20:01")
        h4 = self.addHost("h4", ip="192.168.20.2/24", mac="00:00:00:00:20:02")
        v1 = self.addSwitch("vtep1", cls=P4Switch, json_path=JSON, thrift_port=9090)
        v2 = self.addSwitch("vtep2", cls=P4Switch, json_path=JSON, thrift_port=9091)
        underlay = self.addSwitch("s1", cls=OVSSwitch, failMode="standalone")
        self.addLink(h1, v1)
        self.addLink(h3, v1)
        self.addLink(h2, v2)
        self.addLink(h4, v2)
        self.addLink(v1, underlay)
        self.addLink(v2, underlay)

def cli_commands(thrift_port, commands):
    p = subprocess.run(
        ["simple_switch_CLI", "--thrift-port", str(thrift_port)],
        input="\n".join(commands) + "\n", text=True, capture_output=True, timeout=10
    )
    output = p.stdout + p.stderr
    print(f"\n=== Baseline BMv2 CLI port {thrift_port} ===\n{output}")
    if p.returncode or "Invalid" in output or "Error" in output:
        raise RuntimeError(f"Baseline table configuration failed on port {thrift_port}")

def add_rules():
    # From either tenant-facing port, forward the unchanged Ethernet frame
    # into the underlay. On underlay ingress, use destination MAC to select
    # the destination host-facing port.
    cli_commands(9090, [
        "table_add MyIngress.tenant_to_underlay MyIngress.set_egress 1 => 3",
        "table_add MyIngress.tenant_to_underlay MyIngress.set_egress 2 => 3",
        "table_add MyIngress.underlay_to_tenant MyIngress.set_egress 0x000000001001 => 1",
        "table_add MyIngress.underlay_to_tenant MyIngress.set_egress 0x000000002001 => 2",
        "show_tables"
    ])
    cli_commands(9091, [
        "table_add MyIngress.tenant_to_underlay MyIngress.set_egress 1 => 3",
        "table_add MyIngress.tenant_to_underlay MyIngress.set_egress 2 => 3",
        "table_add MyIngress.underlay_to_tenant MyIngress.set_egress 0x000000001002 => 1",
        "table_add MyIngress.underlay_to_tenant MyIngress.set_egress 0x000000002002 => 2",
        "show_tables"
    ])

def run():
    if not os.path.isfile(JSON):
        raise SystemExit(f"Missing compiled baseline P4 JSON: {JSON}")
    net = Mininet(topo=BaselineTopo(), controller=None, autoSetMacs=False)
    try:
        net.start()
        for name,ip,mac in [
            ("h1","192.168.10.2","00:00:00:00:10:02"),
            ("h2","192.168.10.1","00:00:00:00:10:01"),
            ("h3","192.168.20.2","00:00:00:00:20:02"),
            ("h4","192.168.20.1","00:00:00:00:20:01"),
        ]:
            net.get(name).cmd(f"ip neigh replace {ip} lladdr {mac} nud permanent dev {name}-eth0")
        add_rules()
        info("\n*** Plain P4 L2 baseline started; no VXLAN headers are added.\n")
        info("*** This baseline does not enforce tenant isolation.\n")
        CLI(net)
    finally:
        net.stop()

if __name__ == "__main__":
    setLogLevel("info")
    run()
