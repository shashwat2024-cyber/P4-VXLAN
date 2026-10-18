#!/usr/bin/env python3

import os
import subprocess
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Switch, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
JSON = os.path.join(ROOT, "build", "vxlan.json")


class P4Switch(Switch):
    def __init__(self, name, json_path, thrift_port, **kwargs):
        self.json_path = json_path
        self.thrift_port = thrift_port
        self.pidfile = "/tmp/%s.pid" % name
        self.logfile = "/tmp/%s.log" % name
        Switch.__init__(self, name, **kwargs)

    def start(self, controllers):
        # Each BMv2 instance needs a unique device ID.
        device_id = self.thrift_port - 9089
        args = ["simple_switch", "--device-id", str(device_id)]
        for port, intf in sorted(self.intfs.items()):
            if port:
                args += ["-i", "%d@%s" % (port, intf.name)]
        args += ["--thrift-port", str(self.thrift_port), self.json_path]

        command = " ".join(args)
        self.cmd("%s > %s 2>&1 & echo $! > %s" %
                 (command, self.logfile, self.pidfile))

    def stop(self):
        self.cmd("kill $(cat %s) 2>/dev/null || true" % self.pidfile)
        self.cmd("rm -f %s" % self.pidfile)
        Switch.stop(self)


class VXLANTopo(Topo):
    def build(self):
        # Tenant hosts
        h1 = self.addHost("h1", ip="192.168.10.1/24",
                          mac="00:00:00:00:10:01")
        h2 = self.addHost("h2", ip="192.168.10.2/24",
                          mac="00:00:00:00:10:02")
        h3 = self.addHost("h3", ip="192.168.20.1/24",
                          mac="00:00:00:00:20:01")
        h4 = self.addHost("h4", ip="192.168.20.2/24",
                          mac="00:00:00:00:20:02")

        # Two P4 VTEPs and an ordinary underlay Ethernet switch.
        v1 = self.addSwitch("vtep1", cls=P4Switch,
                            json_path=JSON, thrift_port=9090)
        v2 = self.addSwitch("vtep2", cls=P4Switch,
                            json_path=JSON, thrift_port=9091)
        underlay = self.addSwitch("s1", cls=OVSSwitch,
                                  failMode="standalone")

        # Port numbering on each P4 VTEP:
        # port 1 = tenant A host; port 2 = tenant B host;
        # port 3 = underlay.
        self.addLink(h1, v1)
        self.addLink(h3, v1)
        self.addLink(h2, v2)
        self.addLink(h4, v2)
        self.addLink(v1, underlay)
        self.addLink(v2, underlay)


def cli_commands(thrift_port, commands):
    result = subprocess.run(
        ["simple_switch_CLI", "--thrift-port", str(thrift_port)],
        input="\n".join(commands) + "\n",
        text=True,
        capture_output=True,
        timeout=10
    )
    output = result.stdout + result.stderr
    print("\n=== BMv2 CLI port %s ===\n%s" % (thrift_port, output))
    if result.returncode != 0:
        raise RuntimeError("simple_switch_CLI failed on port %s" %
                           thrift_port)
    if "Invalid" in output or "Error" in output:
        raise RuntimeError("BMv2 reported a table command error")


def add_rules():
    # MAC addresses used for the underlay-facing interfaces.
    v1_src = "0x020000000101"
    v2_src = "0x020000000102"
    vni_a = "1001"
    vni_b = "1002"
    ip_v1 = "0x0a000001"  # 10.0.0.1
    ip_v2 = "0x0a000002"  # 10.0.0.2

    cli_commands(9090, [
        "table_add MyIngress.encap_by_port MyIngress.encapsulate 1 "
        "=> %s %s %s %s %s 3" %
        (vni_a, v1_src, v2_src, ip_v1, ip_v2),
        "table_add MyIngress.encap_by_port MyIngress.encapsulate 2 "
        "=> %s %s %s %s %s 3" %
        (vni_b, v1_src, v2_src, ip_v1, ip_v2),
        "table_add MyIngress.decap_by_vni_and_dst MyIngress.decapsulate "
        "1001 0xc0a80a01 => 1",
        "table_add MyIngress.decap_by_vni_and_dst MyIngress.decapsulate "
        "1002 0xc0a81401 => 2",
        "show_tables"
    ])

    cli_commands(9091, [
        "table_add MyIngress.encap_by_port MyIngress.encapsulate 1 "
        "=> %s %s %s %s %s 3" %
        (vni_a, v2_src, v1_src, ip_v2, ip_v1),
        "table_add MyIngress.encap_by_port MyIngress.encapsulate 2 "
        "=> %s %s %s %s %s 3" %
        (vni_b, v2_src, v1_src, ip_v2, ip_v1),
        "table_add MyIngress.decap_by_vni_and_dst MyIngress.decapsulate "
        "1001 0xc0a80a02 => 1",
        "table_add MyIngress.decap_by_vni_and_dst MyIngress.decapsulate "
        "1002 0xc0a81402 => 2",
        "show_tables"
    ])


def run():
    if not os.path.isfile(JSON):
        raise SystemExit("Missing compiled P4 JSON: %s" % JSON)

    topo = VXLANTopo()
    net = Mininet(topo=topo, controller=None, autoSetMacs=False)

    try:
        net.start()

        # Match the underlay MACs configured in the P4 table actions.
        v1 = net.get("vtep1")
        v2 = net.get("vtep2")
        v1.cmd("ip link set dev vtep1-eth3 address 02:00:00:00:01:01")
        v2.cmd("ip link set dev vtep2-eth3 address 02:00:00:00:01:02")

        # Static neighbour entries avoid ARP broadcasts for the first test.
        net.get("h1").cmd(
            "ip neigh replace 192.168.10.2 lladdr "
            "00:00:00:00:10:02 nud permanent dev h1-eth0")
        net.get("h2").cmd(
            "ip neigh replace 192.168.10.1 lladdr "
            "00:00:00:00:10:01 nud permanent dev h2-eth0")
        net.get("h3").cmd(
            "ip neigh replace 192.168.20.2 lladdr "
            "00:00:00:00:20:02 nud permanent dev h3-eth0")
        net.get("h4").cmd(
            "ip neigh replace 192.168.20.1 lladdr "
            "00:00:00:00:20:01 nud permanent dev h4-eth0")

        add_rules()

        info("\n*** BMv2 VXLAN topology started.\n")
        info("*** h1 <-> h2 uses VNI 1001.\n")
        info("*** h3 <-> h4 uses VNI 1002.\n")
        info("*** Test with: h1 ping -c 3 192.168.10.2\n")
        info("*** Test with: h3 ping -c 3 192.168.20.2\n")
        CLI(net)
    finally:
        net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    run()
