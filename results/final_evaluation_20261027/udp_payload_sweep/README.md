# UDP application payload-size sweep (27 October 2026)

## Evidence and method
The local raw trial file records 50 trials: two tenants (A/B), five UDP datagram sizes (256, 512, 768, 1024, 1200 bytes), five trials per tenant/size. Each command used iperf3 UDP at a configured 5 Mbps for 30 seconds. The experiment ID is `20261027T141209Z-779234d7`; the raw records identify source commit `5d8ac01ca3d39e3a2744558641c453d9a9a9725b`.

The summary CSV in this directory is derived from the recorded local summary. Means and sample standard deviations are across five successful trials per group. This experiment varies the iperf3 application datagram size; it is not a direct measurement of VXLAN encapsulation overhead or maximum MTU.

## Results
| Tenant | UDP datagram (bytes) | n | Receiver Mbps (mean ± SD) | Loss % (mean ± SD) | Jitter ms (mean ± SD) |
|---|---:|---:|---:|---:|---:|
| A | 256 | 5 | 4.998 ± 0.001 | 0.0169 ± 0.0262 | 0.2530 ± 0.0747 |
| A | 512 | 5 | 4.999 ± 0.000 | 0.0000 ± 0.0000 | 0.1423 ± 0.0478 |
| A | 768 | 5 | 4.999 ± 0.000 | 0.0000 ± 0.0000 | 0.1223 ± 0.0345 |
| A | 1024 | 5 | 4.999 ± 0.000 | 0.0000 ± 0.0000 | 0.1032 ± 0.0278 |
| A | 1200 | 5 | 4.999 ± 0.000 | 0.0000 ± 0.0000 | 0.1023 ± 0.0152 |
| B | 256 | 5 | 4.895 ± 0.231 | 2.0674 ± 4.6230 | 0.4256 ± 0.2252 |
| B | 512 | 5 | 4.999 ± 0.000 | 0.0000 ± 0.0000 | 0.2087 ± 0.1300 |
| B | 768 | 5 | 4.999 ± 0.000 | 0.0000 ± 0.0000 | 0.2094 ± 0.1523 |
| B | 1024 | 5 | 5.000 ± 0.000 | 0.0000 ± 0.0000 | 0.1067 ± 0.0251 |
| B | 1200 | 5 | 4.999 ± 0.000 | 0.0000 ± 0.0000 | 0.0988 ± 0.0548 |

## Interpretation and limitations
The 256-byte condition has the highest observed loss and variability, especially for Tenant B. The campaign has only five repetitions per condition; this is a descriptive observation, not proof that payload size caused the loss. The offered rate is configured traffic; receiver throughput, loss, and jitter are measured by iperf3. These results apply only to this test topology, software environment, and configuration. See the original local raw trial file and analysis script in the supplied working archive for the full provenance chain.