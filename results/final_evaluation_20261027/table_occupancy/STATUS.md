# Table-occupancy experiment status

## Audit outcome (27 October 2026 local evidence)
The local file `results/scalability/table_occupancy_pilot_20261027.csv` contains only a header and no observations. Debug runs `table_occupancy_debug_20261027.csv`, `debug2`, and `debug4` are also header-only. `table_occupancy_debug3_20261027.csv` contains two failed rows for occupancy target 2; both report a client termination / JSON parse failure and 100% fallback loss. They are not valid throughput measurements.

The separate `occupancy_pilot_baseline_20261027.csv` and `occupancy_pilot_restart_20261027.csv` each contain one successful five-second UDP observation at 5 Mbps for Tenant A, with receiver throughput around 4.995 Mbps and 0% reported loss. These isolated single observations do not vary or validate table occupancy, and cannot support a lookup-cost or occupancy-performance trend.

## Conclusion
**No defensible table-occupancy-versus-performance result is available from these artifacts.** Do not plot or report these as a completed occupancy benchmark. The implementation in `scripts/table_occupancy.py` attempts to add synthetic nonmatching entries to the decapsulation table and then measure UDP, but a valid campaign must confirm the actual installed entry counts at each VTEP, complete repeated trials at each occupancy level, record errors as failures rather than zero-throughput measurements, and independently validate the installed table state. This status file intentionally records the limitation rather than inventing data.