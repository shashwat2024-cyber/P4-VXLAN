#!/usr/bin/env python3

import os
import time
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Host
from mininet.cli import CLI
from mininet.log import setLogLevel, info

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
JSON = os.path.join(ROOT, "build", "vxlan_final_security.json", "vxlan.json")


class RoutedVXLANTopo(Topo):
    def build(self):
        h1 = self.addHost("h1", ip="192.168.10.1/24",
                          mac="00:00:00:00:10:01")
        h2 = self.addHost("h2", ip="192.168.10.2/24",
                          mac="00:00:00:00:10:02")
        h3 = self.addHost("h3", ip="192.168.20.1/24",
                          mac="00:00:00:00:20:01")
        h4 = self.addHost("h4", ip="192.168.20.2/24",
                          mac="00:00:00:00:20:02")

        # Each VTEP is a Host, giving it an isolated network namespace.
        v1 = self.addHost("vtep1")
        v2 = self.addHost("vtep2")
        router = self.addHost("r1")

        self.addLink(h1, v1)
        self.addLink(h3, v1)
        self.addLink(h2, v2)
        self.addLink(h4, v2)

        self.addLink(v1, router)
        self.addLink(v2, router)


def run_cmd(node, command):
    output = node.cmd(command)
    print("[%s] %s" % (node.name, output.strip()))
    return output


def configure_interfaces(net):
    v1 = net.get("vtep1")
    v2 = net.get("vtep2")
    r1 = net.get("r1")

    # Remove Mininet's automatic addresses from VTEP interfaces.
    for node, interfaces in [
        (v1, ["vtep1-eth0", "vtep1-eth1", "vtep1-eth2"]),
        (v2, ["vtep2-eth0", "vtep2-eth1", "vtep2-eth2"]),
        (r1, ["r1-eth0", "r1-eth1"])
    ]:
        for interface in interfaces:
            run_cmd(node, "ip addr flush dev %s" % interface)
            run_cmd(node, "ip link set dev %s up" % interface)

    # VTEP underlay MAC addresses.
    run_cmd(v1, "ip link set vtep1-eth2 address 02:00:00:00:01:01")
    run_cmd(v2, "ip link set vtep2-eth2 address 02:00:00:00:01:02")

    # Router interface MAC addresses.
    run_cmd(r1, "ip link set r1-eth0 address 02:00:00:00:aa:01")
    run_cmd(r1, "ip link set r1-eth1 address 02:00:00:00:aa:02")

    # Assign separate underlay subnets.
    run_cmd(v1, "ip addr add 10.0.1.2/24 dev vtep1-eth2")
    run_cmd(r1, "ip addr add 10.0.1.1/24 dev r1-eth0")

    run_cmd(r1, "ip addr add 10.0.2.1/24 dev r1-eth1")
    run_cmd(v2, "ip addr add 10.0.2.2/24 dev vtep2-eth2")

    # Explicit routes through the router.
    run_cmd(v1, "ip route add 10.0.2.0/24 via 10.0.1.1 dev vtep1-eth2")
    run_cmd(v2, "ip route add 10.0.1.0/24 via 10.0.2.1 dev vtep2-eth2")

    # Enable IPv4 forwarding on the router.
    run_cmd(r1, "sysctl -w net.ipv4.ip_forward=1")

    # Static underlay neighbours.
    run_cmd(r1, "ip neigh replace 10.0.1.2 lladdr 02:00:00:00:01:01 nud permanent dev r1-eth0")
    run_cmd(r1, "ip neigh replace 10.0.2.2 lladdr 02:00:00:00:01:02 nud permanent dev r1-eth1")

    # Static tenant neighbours.
    for host, address, mac in [
        ("h1", "192.168.10.2", "00:00:00:00:10:02"),
        ("h2", "192.168.10.1", "00:00:00:00:10:01"),
        ("h3", "192.168.20.2", "00:00:00:00:20:02"),
        ("h4", "192.168.20.1", "00:00:00:00:20:01")
    ]:
        net.get(host).cmd(
            "ip neigh replace %s lladdr %s nud permanent dev %s-eth0"
            % (address, mac, host)
        )


def start_vtep(node, device_id, thrift_port, interfaces):
    args = [
        "simple_switch",
        "--device-id", str(device_id)
    ]

    for port, interface in interfaces:
        args += ["-i", "%d@%s" % (port, interface)]

    args += ["--thrift-port", str(thrift_port), JSON]

    command = " ".join(args)
    logfile = "/tmp/%s_routed.log" % node.name
    pidfile = "/tmp/%s_routed.pid" % node.name

    run_cmd(node, "%s > %s 2>&1 & echo $! > %s"
            % (command, logfile, pidfile))

    # Wait for the Thrift service inside this VTEP namespace.
    for _ in range(60):
        result = node.cmd(
            "printf 'show_tables\\n' | "
            "simple_switch_CLI --thrift-port %d 2>&1"
            % thrift_port
        )
        if "table" in result.lower() or "myingress" in result.lower():
            print("%s BMv2 is ready." % node.name)
            return
        time.sleep(0.25)

    log = node.cmd("cat %s 2>/dev/null" % logfile)
    raise RuntimeError("%s failed to start:\n%s" % (node.name, log))


def install_rules(node, thrift_port, commands):
    command_text = " ".join(
        "'%s'" % command.replace("'", "'\\''")
        for command in commands
    )

    output = node.cmd(
        "printf '%%s\\n' %s | simple_switch_CLI --thrift-port %d"
        % (command_text, thrift_port)
    )

    print("\n=== %s table configuration ===\n%s"
          % (node.name, output))

    if "Invalid" in output or "Error" in output:
        raise RuntimeError("Table installation failed on " + node.name)


def configure_tables(net):
    v1 = net.get("vtep1")
    v2 = net.get("vtep2")

    # Outer source MACs are the VTEP underlay MACs.
    # Outer destination MACs are the router's next-hop MACs.
    install_rules(v1, 9090, [
        "table_add MyIngress.encap_by_port MyIngress.encapsulate 1 => 1001 0x020000000101 0x02000000aa01 0x0a000102 0x0a000202 3",
        "table_add MyIngress.encap_by_port MyIngress.encapsulate 2 => 1002 0x020000000101 0x02000000aa01 0x0a000102 0x0a000202 3",
        "table_add MyIngress.decap_by_vni_and_dst MyIngress.decapsulate 1001 0xc0a80a01 => 1",
        "table_add MyIngress.decap_by_vni_and_dst MyIngress.decapsulate 1002 0xc0a81401 => 2",
        "show_tables"
    ])

    install_rules(v2, 9091, [
        "table_add MyIngress.encap_by_port MyIngress.encapsulate 1 => 1001 0x020000000102 0x02000000aa02 0x0a000202 0x0a000102 3",
        "table_add MyIngress.encap_by_port MyIngress.encapsulate 2 => 1002 0x020000000102 0x02000000aa02 0x0a000202 0x0a000102 3",
        "table_add MyIngress.decap_by_vni_and_dst MyIngress.decapsulate 1001 0xc0a80a02 => 1",
        "table_add MyIngress.decap_by_vni_and_dst MyIngress.decapsulate 1002 0xc0a81402 => 2",
        "show_tables"
    ])


def run():
    if not os.path.isfile(JSON):
        raise SystemExit("Missing compiled P4 JSON: " + JSON)

    topo = RoutedVXLANTopo()
    net = Mininet(topo=topo, controller=None, autoSetMacs=False)

    try:
        net.start()

        configure_interfaces(net)

        # VTEP1: tenant port 1, tenant port 2, routed underlay port 3.
        start_vtep(net.get("vtep1"), 1, 9090, [
            (1, "vtep1-eth0"),
            (2, "vtep1-eth1"),
            (3, "vtep1-eth2")
        ])

        # VTEP2: tenant port 1, tenant port 2, routed underlay port 3.
        start_vtep(net.get("vtep2"), 2, 9091, [
            (1, "vtep2-eth0"),
            (2, "vtep2-eth1"),
            (3, "vtep2-eth2")
        ])

        configure_tables(net)

        info("\n*** Isolated routed P4 VXLAN topology started.\n")
        info("*** VTEP1 namespace: 10.0.1.2/24\n")
        info("*** Router: 10.0.1.1/24 <-> 10.0.2.1/24\n")
        info("*** VTEP2 namespace: 10.0.2.2/24\n")
        info("*** Router forwards the outer VXLAN packets.\n")
        info("*** Test Tenant A: h1 ping -c 5 192.168.10.2\n")
        info("*** Test Tenant B: h3 ping -c 5 192.168.20.2\n")

        CLI(net)

    finally:
        net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    run()
