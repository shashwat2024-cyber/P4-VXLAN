#include <core.p4>
#include <v1model.p4>

/* No-VXLAN L2 forwarding baseline. It intentionally leaves tenant separation
 * out of scope: the purpose is to measure same-tenant forwarding overhead
 * without adding VXLAN headers or encapsulation/decapsulation processing. */

header ethernet_t {
    bit<48> dstAddr;
    bit<48> srcAddr;
    bit<16> etherType;
}

struct headers_t {
    ethernet_t ethernet;
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
        packet.extract(hdr.ethernet);
        transition accept;
    }
}

control MyVerifyChecksum(inout headers_t hdr, inout metadata_t meta) {
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

    action set_egress(bit<9> port) {
        standard_metadata.egress_spec = port;
    }

    table tenant_to_underlay {
        key = {
            standard_metadata.ingress_port : exact;
        }
        actions = {
            set_egress;
            drop_packet;
        }
        size = 32;
        default_action = drop_packet();
    }

    table underlay_to_tenant {
        key = {
            hdr.ethernet.dstAddr : exact;
        }
        actions = {
            set_egress;
            drop_packet;
        }
        size = 256;
        default_action = drop_packet();
    }

    apply {
        if (standard_metadata.ingress_port == 3) {
            underlay_to_tenant.apply();
        } else {
            tenant_to_underlay.apply();
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

control MyComputeChecksum(inout headers_t hdr, inout metadata_t meta) {
    apply { }
}

control MyDeparser(packet_out packet, in headers_t hdr) {
    apply {
        packet.emit(hdr.ethernet);
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
