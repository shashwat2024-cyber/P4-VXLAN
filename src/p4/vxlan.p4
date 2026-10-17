#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x0800;
const bit<8> IP_PROTO_UDP = 17;
const bit<16> VXLAN_PORT = 4789;

header ethernet_t {
    bit<48> dstAddr;
    bit<48> srcAddr;
    bit<16> etherType;
}

header ipv4_t {
    bit<4> version;
    bit<4> ihl;
    bit<8> diffserv;
    bit<16> totalLen;
    bit<16> identification;
    bit<3> flags;
    bit<13> fragOffset;
    bit<8> ttl;
    bit<8> protocol;
    bit<16> hdrChecksum;
    bit<32> srcAddr;
    bit<32> dstAddr;
}

header udp_t {
    bit<16> srcPort;
    bit<16> dstPort;
    bit<16> length;
    bit<16> checksum;
}

header vxlan_t {
    bit<8> flags;
    bit<24> reserved1;
    bit<24> vni;
    bit<8> reserved2;
}

struct headers_t {
    ethernet_t outer_ethernet;
    ipv4_t outer_ipv4;
    udp_t outer_udp;
    vxlan_t vxlan;
    ethernet_t inner_ethernet;
    ipv4_t inner_ipv4;
    udp_t inner_udp;
}

struct metadata_t {
    bit<1> unused;
}

parser MyParser(
    packet_in packet,
    out headers_t hdr,
    inout metadata_t meta,
    inout standard_metadata_t standard_metadata
) {
    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.outer_ethernet);
        transition select(hdr.outer_ethernet.etherType) {
            TYPE_IPV4: parse_ipv4;
            default: accept;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.outer_ipv4);
        transition select(hdr.outer_ipv4.protocol) {
            IP_PROTO_UDP: parse_udp;
            default: accept;
        }
    }

    state parse_udp {
        packet.extract(hdr.outer_udp);
        transition select(hdr.outer_udp.dstPort) {
            VXLAN_PORT: parse_vxlan;
            default: accept;
        }
    }

    state parse_vxlan {
        packet.extract(hdr.vxlan);
        transition parse_inner_ethernet;
    }

    state parse_inner_ethernet {
        packet.extract(hdr.inner_ethernet);
        transition select(hdr.inner_ethernet.etherType) {
            TYPE_IPV4: parse_inner_ipv4;
            default: accept;
        }
    }

    state parse_inner_ipv4 {
        packet.extract(hdr.inner_ipv4);
        transition select(hdr.inner_ipv4.protocol) {
            IP_PROTO_UDP: parse_inner_udp;
            default: accept;
        }
    }

    state parse_inner_udp {
        packet.extract(hdr.inner_udp);
        transition accept;
    }
}

control MyVerifyChecksum(
    inout headers_t hdr,
    inout metadata_t meta
) {
    apply { }
}

control MyIngress(
    inout headers_t hdr,
    inout metadata_t meta,
    inout standard_metadata_t standard_metadata
) {
    action drop_packet() {
        mark_to_drop(standard_metadata);
    }

    action encapsulate(
        bit<24> vni,
        bit<48> outer_src_mac,
        bit<48> outer_dst_mac,
        bit<32> outer_src_ip,
        bit<32> outer_dst_ip,
        bit<9> output_port
    ) {
        hdr.inner_ethernet = hdr.outer_ethernet;
        hdr.inner_ipv4 = hdr.outer_ipv4;

        if (hdr.outer_udp.isValid()) {
            hdr.inner_udp = hdr.outer_udp;
            hdr.outer_udp.setInvalid();
        }

        hdr.outer_ethernet.setInvalid();
        hdr.outer_ipv4.setInvalid();

        hdr.outer_ethernet.setValid();
        hdr.outer_ipv4.setValid();
        hdr.outer_udp.setValid();
        hdr.vxlan.setValid();

        hdr.outer_ethernet.srcAddr = outer_src_mac;
        hdr.outer_ethernet.dstAddr = outer_dst_mac;
        hdr.outer_ethernet.etherType = TYPE_IPV4;

        hdr.outer_ipv4.version = 4;
        hdr.outer_ipv4.ihl = 5;
        hdr.outer_ipv4.diffserv = 0;
        hdr.outer_ipv4.totalLen = hdr.inner_ipv4.totalLen + 16w30;
        hdr.outer_ipv4.identification = 0;
        hdr.outer_ipv4.flags = 0;
        hdr.outer_ipv4.fragOffset = 0;
        hdr.outer_ipv4.ttl = 64;
        hdr.outer_ipv4.protocol = IP_PROTO_UDP;
        hdr.outer_ipv4.hdrChecksum = 0;
        hdr.outer_ipv4.srcAddr = outer_src_ip;
        hdr.outer_ipv4.dstAddr = outer_dst_ip;

        hdr.outer_udp.srcPort = 16w49152;
        hdr.outer_udp.dstPort = VXLAN_PORT;
        hdr.outer_udp.length = hdr.inner_ipv4.totalLen + 16w30;
        hdr.outer_udp.checksum = 0;

        hdr.vxlan.flags = 8w8;
        hdr.vxlan.reserved1 = 0;
        hdr.vxlan.vni = vni;
        hdr.vxlan.reserved2 = 0;

        hdr.inner_ethernet.setValid();
        hdr.inner_ipv4.setValid();

        standard_metadata.egress_spec = output_port;
    }

    action decapsulate(bit<9> output_port) {
        hdr.outer_ethernet = hdr.inner_ethernet;
        hdr.outer_ipv4 = hdr.inner_ipv4;

        if (hdr.inner_udp.isValid()) {
            hdr.outer_udp = hdr.inner_udp;
        } else {
            hdr.outer_udp.setInvalid();
        }

        hdr.vxlan.setInvalid();
        hdr.inner_ethernet.setInvalid();
        hdr.inner_ipv4.setInvalid();
        hdr.inner_udp.setInvalid();

        standard_metadata.egress_spec = output_port;
    }

    table encap_by_port {
        key = {
            standard_metadata.ingress_port : exact;
        }
        actions = {
            encapsulate;
            drop_packet;
        }
        size = 32;
        default_action = drop_packet();
    }

    table decap_by_vni_and_dst {
        key = {
            hdr.vxlan.vni : exact;
            hdr.inner_ipv4.dstAddr : exact;
        }
        actions = {
            decapsulate;
            drop_packet;
        }
        size = 256;
        default_action = drop_packet();
    }

    apply {
        if (hdr.vxlan.isValid() &&
            hdr.inner_ethernet.isValid() &&
            hdr.inner_ipv4.isValid()) {
            decap_by_vni_and_dst.apply();
        } else if (hdr.outer_ethernet.isValid() &&
                   hdr.outer_ipv4.isValid()) {
            encap_by_port.apply();
        } else {
            drop_packet();
        }
    }
}

control MyEgress(
    inout headers_t hdr,
    inout metadata_t meta,
    inout standard_metadata_t standard_metadata
) {
    apply { }
}

control MyComputeChecksum(
    inout headers_t hdr,
    inout metadata_t meta
) {
    apply {
        update_checksum(
            hdr.outer_ipv4.isValid(),
            {
                hdr.outer_ipv4.version,
                hdr.outer_ipv4.ihl,
                hdr.outer_ipv4.diffserv,
                hdr.outer_ipv4.totalLen,
                hdr.outer_ipv4.identification,
                hdr.outer_ipv4.flags,
                hdr.outer_ipv4.fragOffset,
                hdr.outer_ipv4.ttl,
                hdr.outer_ipv4.protocol,
                hdr.outer_ipv4.srcAddr,
                hdr.outer_ipv4.dstAddr
            },
            hdr.outer_ipv4.hdrChecksum,
            HashAlgorithm.csum16
        );
    }
}

control MyDeparser(
    packet_out packet,
    in headers_t hdr
) {
    apply {
        packet.emit(hdr.outer_ethernet);
        packet.emit(hdr.outer_ipv4);
        packet.emit(hdr.outer_udp);
        packet.emit(hdr.vxlan);
        packet.emit(hdr.inner_ethernet);
        packet.emit(hdr.inner_ipv4);
        packet.emit(hdr.inner_udp);
    }
}

V1Switch(
    MyParser(),
    MyVerifyChecksum(),
    MyIngress(),
    MyEgress(),
    MyComputeChecksum(),
    MyDeparser()
) main;
