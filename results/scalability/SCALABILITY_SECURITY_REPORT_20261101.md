# VXLAN Scalability and Security Test Report

Date: 1 November 2026

## Test results

| Experiment | Tenants | VTEPs | Legitimate | Cross-tenant blocked | Spoofed sources blocked | Result |
|---|---:|---:|---:|---:|---:|---|
| tenant_scaling | 2 | 2 | 4/4 | 4/4 | 4/4 | PASS |
| tenant_scaling | 4 | 2 | 8/8 | 24/24 | 8/8 | PASS |
| tenant_scaling | 6 | 2 | 12/12 | 60/60 | 12/12 | PASS (retest) |
| tenant_scaling | 8 | 2 | 16/16 | 112/112 | 16/16 | PASS |
| vtep_scaling | 2 | 3 | 12/12 | 12/12 | 12/12 | PASS |
| vtep_scaling | 2 | 4 | 24/24 | 24/24 | 24/24 | PASS |

## Security implementation

- Tenant ingress source-IP validation.
- Underlay ingress validation for VXLAN decapsulation.
- VNI and inner source-IP validation.
- VNI and destination-IP validation during decapsulation.
- Default-drop behavior for unmatched table entries.
- Correct outer IPv4 total length: inner IPv4 length + 50 bytes.

## Notes

- All six final configurations passed their recorded tests.
- The initial six-tenant campaign had one inconclusive packet capture.
- The six-tenant retest passed all 60 cross-tenant probes.
- The original configuration CSVs retain setup and test timings.
- This report consolidates the individual test counts from the terminal results.
