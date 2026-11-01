#!/usr/bin/env python3
"""Shared measurement helpers for Mininet/BMv2 experiments."""

import os
import re
from datetime import datetime, timezone
import signal
import subprocess
import threading
import time
from pathlib import Path


def parse_ping_statistics(output):
    """Extract RTT statistics and packet loss from Linux ping output."""

    loss_match = re.search(
        r"(\d+(?:\.\d+)?)%\s+packet loss", output
    )

    rtt_match = re.search(
        r"rtt min/avg/max/(?:mdev|stddev)\s*=\s*"
        r"([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)\s*ms",
        output
    )

    if not loss_match:
        raise RuntimeError(
            "Could not parse ping packet loss:\n" + output[-1500:]
        )

    result = {
        "ping_loss_percent": float(loss_match.group(1)),
        "rtt_min_ms": None,
        "rtt_mean_ms": None,
        "rtt_max_ms": None,
        "rtt_stddev_ms": None,
    }

    if rtt_match:
        result["rtt_min_ms"] = float(rtt_match.group(1))
        result["rtt_mean_ms"] = float(rtt_match.group(2))
        result["rtt_max_ms"] = float(rtt_match.group(3))
        result["rtt_stddev_ms"] = float(rtt_match.group(4))

    return result


def run_with_concurrent_ping(
    client,
    destination,
    iperf_command,
    duration,
    ping_interval=0.2,
):
    """
    Run an iperf3 command and ping concurrently inside a Mininet host.

    Returns:
        iperf_output: Complete iperf3 stdout.
        ping_stats: Parsed concurrent RTT and packet-loss statistics.
    """

    ping_command = [
        "ping",
        "-n",
        "-i", str(ping_interval),
        "-w", str(duration + 2),
        destination,
    ]

    ping_process = client.popen(
        ping_command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        # Give ping a moment to start before the traffic transfer.
        time.sleep(0.3)

        iperf_process = client.popen(
            iperf_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            iperf_stdout, iperf_stderr = iperf_process.communicate(
                timeout=duration + 30
            )
        except subprocess.TimeoutExpired:
            iperf_process.kill()
            iperf_process.communicate()
            raise RuntimeError("iperf3 timed out")

        if iperf_process.returncode != 0:
            raise RuntimeError(
                "iperf3 failed:\n" + (iperf_stderr or iperf_stdout)[-1500:]
            )

    finally:
        if ping_process.poll() is None:
            ping_process.send_signal(signal.SIGINT)

        try:
            ping_output, _ = ping_process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            ping_process.kill()
            ping_output, _ = ping_process.communicate()

    ping_stats = parse_ping_statistics(ping_output)

    return iperf_stdout, ping_stats


def read_simple_switch_rss():
    """
    Read RSS for running simple_switch processes from /proc.

    Returns:
        Dictionary mapping PID to RSS in MiB.
    """

    processes = {}

    proc_root = Path("/proc")

    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue

        pid = int(entry.name)

        try:
            cmdline = (entry / "cmdline").read_bytes()
            command = cmdline.replace(b"\0", b" ").decode(
                errors="replace"
            )

            if "simple_switch" not in command:
                continue

            status = (entry / "status").read_text(
                encoding="utf-8",
                errors="replace"
            )

            match = re.search(
                r"^VmRSS:\s+(\d+)\s+kB",
                status,
                re.MULTILINE
            )

            if match:
                processes[pid] = int(match.group(1)) / 1024.0

        except (FileNotFoundError, PermissionError, ProcessLookupError):
            # A process may exit while /proc is being inspected.
            continue

    return processes


class SimpleSwitchRSSMonitor:
    """Periodically sample simple_switch process RSS."""

    def __init__(self, interval_seconds=0.5):
        if interval_seconds <= 0:
            raise ValueError("Sampling interval must be positive")

        self.interval_seconds = interval_seconds
        self.samples = []
        self._stop_event = threading.Event()
        self._thread = None

    def _sample_loop(self):
        while not self._stop_event.is_set():
            timestamp = time.time()
            rss_by_pid = read_simple_switch_rss()

            if rss_by_pid:
                self.samples.append({
                    "timestamp": timestamp,
                    "processes": rss_by_pid,
                    "total_rss_mib": sum(rss_by_pid.values()),
                })

            self._stop_event.wait(self.interval_seconds)

    def start(self):
        if self._thread is not None:
            raise RuntimeError("RSS monitor has already been started")

        self._thread = threading.Thread(
            target=self._sample_loop,
            name="simple-switch-rss-monitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        if self._thread is None:
            return

        self._stop_event.set()
        self._thread.join()
        if self._thread.is_alive():
            raise RuntimeError("RSS monitor thread did not terminate")
        self._thread = None

    def summary(self):
        if not self.samples:
            return {
                "rss_sample_count": 0,
                "rss_sample_interval_ms": self.interval_seconds * 1000,
                "rss_mean_total_mib": None,
                "rss_peak_total_mib": None,
                "rss_mean_per_process_mib": None,
                "rss_peak_per_process_mib": None,
            }

        totals = [
            sample["total_rss_mib"]
            for sample in self.samples
        ]

        individual_values = [
            rss
            for sample in self.samples
            for rss in sample["processes"].values()
        ]

        return {
            "rss_sample_count": len(self.samples),
            "rss_sample_interval_ms": self.interval_seconds * 1000,
            "rss_mean_total_mib": sum(totals) / len(totals),
            "rss_peak_total_mib": max(totals),
            "rss_mean_per_process_mib": (
                sum(individual_values) / len(individual_values)
            ),
            "rss_peak_per_process_mib": max(individual_values),
        }



class SimpleSwitchCPUMonitor:
    """Sample simple_switch CPU usage using Linux /proc process counters."""

    def __init__(self, interval_seconds=1.0):
        if interval_seconds <= 0:
            raise ValueError("Sampling interval must be positive")
        self.interval_seconds = interval_seconds
        self.samples = []
        self.aggregate_samples = []
        self._previous = {}
        self._stop_event = threading.Event()
        self._thread = None
        self._clock_ticks = os.sysconf("SC_CLK_TCK")

    @staticmethod
    def _read_processes():
        processes = {}
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                pid = int(entry.name)
                cmdline = (entry / "cmdline").read_bytes()
                cmdline = cmdline.replace(bytes([0]), b" ").decode(errors="replace")
                if "simple_switch" not in cmdline:
                    continue

                stat = (entry / "stat").read_text(
                    encoding="utf-8", errors="replace"
                )
                close = stat.rfind(")")
                if close < 0:
                    continue

                fields = stat[close + 2:].split()
                # utime/stime are proc stat fields 14/15; starttime is field 22.
                utime, stime = int(fields[11]), int(fields[12])
                starttime = int(fields[19])
                name = stat[stat.find("(") + 1:close]

                processes[(pid, starttime)] = {
                    "pid": pid,
                    "process": name,
                    "ticks": utime + stime,
                }
            except (
                FileNotFoundError, PermissionError, ProcessLookupError,
                IndexError, ValueError
            ):
                continue
        return processes

    def _sample_loop(self):
        while not self._stop_event.is_set():
            now = time.monotonic()
            timestamp = datetime.now(timezone.utc).isoformat()
            current = self._read_processes()
            interval_values = []

            for key, info in current.items():
                previous = self._previous.get(key)
                if previous is not None:
                    elapsed = now - previous["monotonic"]
                    delta = info["ticks"] - previous["ticks"]

                    if elapsed > 0 and delta >= 0:
                        cpu = (delta / self._clock_ticks) / elapsed * 100.0
                        self.samples.append({
                            "timestamp_utc": timestamp,
                            "elapsed_seconds": now - self._start_monotonic,
                            "pid": info["pid"],
                            "process": info["process"],
                            "process_cpu_percent_one_core": cpu,
                            "sample_interval_seconds": elapsed,
                        })
                        interval_values.append(cpu)

                self._previous[key] = {
                    "ticks": info["ticks"],
                    "monotonic": now,
                }

            # Remove exited processes; starttime distinguishes PID reuse.
            self._previous = {
                key: value for key, value in self._previous.items()
                if key in current
            }

            if interval_values:
                self.aggregate_samples.append({
                    "timestamp_utc": timestamp,
                    "elapsed_seconds": now - self._start_monotonic,
                    "aggregate_cpu_percent_one_core": sum(interval_values),
                    "process_count": len(interval_values),
                })

            self._stop_event.wait(self.interval_seconds)

    def start(self):
        if self._thread is not None:
            raise RuntimeError("CPU monitor has already been started")

        self.samples = []
        self.aggregate_samples = []
        self._previous = {}
        self._stop_event.clear()
        self._start_monotonic = time.monotonic()

        self._thread = threading.Thread(
            target=self._sample_loop,
            name="simple-switch-cpu-monitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        if self._thread is None:
            return
        self._stop_event.set()
        self._thread.join()
        if self._thread.is_alive():
            raise RuntimeError("CPU monitor thread did not terminate")
        self._thread = None

    def summary(self):
        values = [
            row["aggregate_cpu_percent_one_core"]
            for row in self.aggregate_samples
        ]
        return {
            "cpu_sample_count": len(values),
            "cpu_sample_interval_ms": self.interval_seconds * 1000,
            "cpu_mean_aggregate_percent_one_core": (
                sum(values) / len(values) if values else None
            ),
            "cpu_peak_aggregate_percent_one_core": (
                max(values) if values else None
            ),
            "cpu_process_sample_count": len(self.samples),
        }


def run_with_rss_monitor(
    monitor, function, *args, cpu_monitor=None, **kwargs
):
    """Run one measurement while sampling RSS and, optionally, CPU."""
    if monitor is None and cpu_monitor is None:
        return function(*args, **kwargs), None, None

    if monitor is not None:
        monitor.start()
    if cpu_monitor is not None:
        cpu_monitor.start()

    try:
        result = function(*args, **kwargs)
    finally:
        if cpu_monitor is not None:
            cpu_monitor.stop()
        if monitor is not None:
            monitor.stop()

    rss_summary = monitor.summary() if monitor is not None else None

    # Preserve the original two-value API for existing RSS-only experiments.
    if cpu_monitor is None:
        return result, rss_summary

    cpu_summary = cpu_monitor.summary()
    return result, rss_summary, cpu_summary
