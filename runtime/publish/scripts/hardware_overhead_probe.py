#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import subprocess
import time
from pathlib import Path
from typing import Any


def _linux_proc_stat() -> dict[str, int]:
    out: dict[str, int] = {}
    p = Path('/proc/stat')
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == 'ctxt' and len(parts) > 1:
            out['context_switches'] = int(parts[1])
        elif parts[0] == 'processes' and len(parts) > 1:
            out['processes_forked'] = int(parts[1])
    return out


def _linux_meminfo() -> dict[str, int]:
    p = Path('/proc/meminfo')
    if not p.exists():
        return {}
    vals: dict[str, int] = {}
    for line in p.read_text().splitlines():
        k, _, rest = line.partition(':')
        if not rest:
            continue
        raw = rest.strip().split()[0]
        if raw.isdigit():
            vals[k] = int(raw) * 1024
    return {
        'mem_total_bytes': vals.get('MemTotal', 0),
        'mem_available_bytes': vals.get('MemAvailable', vals.get('MemFree', 0)),
    }


def _net_dev() -> dict[str, int]:
    p = Path('/proc/net/dev')
    if not p.exists():
        return {}
    rx = tx = 0
    for line in p.read_text().splitlines()[2:]:
        if ':' not in line:
            continue
        _, data = line.split(':', 1)
        cols = data.split()
        if len(cols) >= 9:
            rx += int(cols[0]); tx += int(cols[8])
    return {'net_rx_bytes': rx, 'net_tx_bytes': tx}


def snapshot() -> dict[str, Any]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    snap: dict[str, Any] = {
        'time_ns': time.time_ns(),
        'monotonic_ns': time.monotonic_ns(),
        'platform': platform.platform(),
        'hostname': platform.node(),
        'process_user_cpu_s': usage.ru_utime,
        'process_system_cpu_s': usage.ru_stime,
        'process_maxrss_raw': usage.ru_maxrss,
        'loadavg': list(os.getloadavg()) if hasattr(os, 'getloadavg') else None,
    }
    snap.update(_linux_proc_stat())
    snap.update(_linux_meminfo())
    snap.update(_net_dev())
    return snap


def delta(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    elapsed = max((b['monotonic_ns'] - a['monotonic_ns']) / 1e9, 1e-9)
    out: dict[str, Any] = {'elapsed_s': elapsed}
    for key in ('context_switches','processes_forked','net_rx_bytes','net_tx_bytes'):
        if key in a and key in b:
            out[key + '_delta'] = b[key] - a[key]
    out['process_cpu_s_delta'] = (
        (b['process_user_cpu_s'] + b['process_system_cpu_s']) -
        (a['process_user_cpu_s'] + a['process_system_cpu_s'])
    )
    out['process_cpu_percent_of_one_core'] = 100.0 * out['process_cpu_s_delta'] / elapsed
    if 'context_switches_delta' in out:
        out['context_switches_per_s'] = out['context_switches_delta'] / elapsed
    if 'net_rx_bytes_delta' in out:
        out['net_rx_bytes_per_s'] = out['net_rx_bytes_delta'] / elapsed
        out['net_tx_bytes_per_s'] = out['net_tx_bytes_delta'] / elapsed
    if 'mem_available_bytes' in a and 'mem_available_bytes' in b:
        out['mem_available_delta_bytes'] = b['mem_available_bytes'] - a['mem_available_bytes']
    return out


def run_phase(duration: float, command: list[str] | None) -> dict[str, Any]:
    before = snapshot()
    proc = None
    if command:
        proc = subprocess.Popen(command)
    time.sleep(duration)
    if proc is not None:
        try:
            rc = proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                rc = proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill(); rc = proc.wait()
    else:
        rc = None
    after = snapshot()
    return {'before': before, 'after': after, 'delta': delta(before, after), 'command_returncode': rc}


def main() -> int:
    ap = argparse.ArgumentParser(description='Measure realised BRAINK/KEX host overhead without inventing efficiency claims.')
    ap.add_argument('--duration', type=float, default=5.0)
    ap.add_argument('--active-command', nargs=argparse.REMAINDER)
    ap.add_argument('--out', default='data/hardware_overhead_receipt.json')
    ns = ap.parse_args()

    idle = run_phase(ns.duration, None)
    active = run_phase(ns.duration, ns.active_command or None)
    result = {
        'schema': 'braink.hardware.overhead.receipt.v1',
        'measurement_scope': 'HOST_CONTROL_PLANE',
        'claim_boundary': 'MEASURES_HOST_SOFTWARE_OVERHEAD_NOT_ASIC_SILICON_HASHRATE',
        'idle': idle,
        'active': active,
        'realized_delta': {
            'process_cpu_percent_of_one_core': active['delta']['process_cpu_percent_of_one_core'] - idle['delta']['process_cpu_percent_of_one_core'],
            'context_switches_per_s_delta': (
                active['delta'].get('context_switches_per_s', 0.0) - idle['delta'].get('context_switches_per_s', 0.0)
            ),
            'net_rx_bytes_per_s_delta': active['delta'].get('net_rx_bytes_per_s', 0.0) - idle['delta'].get('net_rx_bytes_per_s', 0.0),
            'net_tx_bytes_per_s_delta': active['delta'].get('net_tx_bytes_per_s', 0.0) - idle['delta'].get('net_tx_bytes_per_s', 0.0),
        },
        'requires_separate_mining_readback': [
            'accepted_share_rate','rejected_share_rate','stale_share_rate','duplicate_work_rate','pool_effective_hashrate','miner_local_hashrate'
        ],
    }
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
