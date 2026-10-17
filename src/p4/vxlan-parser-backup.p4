#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x0800;
const bit<8>  IP_PROTO_UDP = 17;
const bit<16> VXLAN_PORT = 4789;

header ethernet_t {
    bit<48> dstAddr;
    bit<48> srcAddr;
    bit<16> etherType;
}

header ipv4_t {
    bit<4>  version;
    bit<4>  ihl;
    bit<8>  diffserv;
    bit<16> totalLen;
    bit<16> identification;
    bit<3>  flags;
    bit<13> fragOffset;
    bit<8>  ttl;
    bit<8>  protocol;
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
    bit<8>  flags;
    bit<24> reserved1;
    bit<24> vni;
    bit<8>  reserved2;
}

struct headers_t {
    ethernet_t outer_ethernet;
    ipv4_t outer_ipv4;
    udp_t outer_udp;
    vxlan_t vxlan;
    ethernet_t inner_ethernet;
    ipv4_t inner_ipv4;
}

struct metadata_t {
    bit<24> tenant_vni;
    bit<1>  tenant_valid;
}

parser MyParser(
    packet_in packet,
    out headers_t hdr,
    inout metadata_t meta,
    inout standard_metadata_t standard_metadata
) {
    state start {
        meta.tenant_vni = 0;
        meta.tenant_valid = 0;
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
        meta.tenant_vni = hdr.vxlan.vni;
        meta.tenant_valid = 1;
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
    apply {
        // Initial parser foundation only.
        // VNI authorization and forwarding will be added next.
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
    apply { }
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
