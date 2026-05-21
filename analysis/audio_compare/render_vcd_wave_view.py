#!/usr/bin/env python3
"""Render selected VCD signals as waveform-viewer style PNG figures."""

from __future__ import annotations

import argparse
from bisect import bisect_right
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


@dataclass
class Signal:
    label: str
    kind: str
    ids: list[str]
    bit_indices: list[int] | None = None


def parse_vcd(path: Path) -> tuple[str, str, dict[str, str], dict[str, list[tuple[int, str]]], int]:
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    timescale = "1"
    version = "VCD"
    scopes: list[str] = []
    id_to_name: dict[str, str] = {}
    changes: dict[str, list[tuple[int, str]]] = {}
    current_time = 0
    max_time = 0
    in_definitions = True

    for raw in text:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("$version"):
            version = "ModelSim Version 10.1d"
        elif line.startswith("$timescale"):
            continue
        elif line and not line.startswith("$") and timescale == "1" and any(unit in line for unit in ("fs", "ps", "ns")):
            timescale = line
        elif line.startswith("$scope"):
            parts = line.split()
            if len(parts) >= 3:
                scopes.append(parts[2])
        elif line.startswith("$upscope"):
            if scopes:
                scopes.pop()
        elif line.startswith("$var"):
            parts = line.split()
            if len(parts) >= 5:
                ident = parts[3]
                name = " ".join(parts[4:-1])
                full_name = ".".join(scopes + [name])
                if ident not in id_to_name:
                    id_to_name[ident] = full_name
                changes.setdefault(ident, [])
        elif line.startswith("$enddefinitions"):
            in_definitions = False
        elif not in_definitions:
            if line.startswith("#"):
                current_time = int(line[1:])
                max_time = max(max_time, current_time)
            elif line[0] in "01xXzZ":
                ident = line[1:]
                if ident in changes:
                    changes[ident].append((current_time, line[0].lower()))
            elif line[0] in "bB":
                parts = line.split()
                if len(parts) == 2 and parts[1] in changes:
                    changes[parts[1]].append((current_time, parts[0][1:].lower()))

    return version, timescale, id_to_name, changes, max_time


def timescale_factor(timescale: str) -> tuple[float, str]:
    match = re.match(r"([0-9.]+)\s*([a-z]+)", timescale.strip())
    if not match:
        return 1.0, "ticks"
    value = float(match.group(1))
    unit = match.group(2)
    factors = {
        "fs": 1e-15,
        "ps": 1e-12,
        "ns": 1e-9,
        "us": 1e-6,
        "ms": 1e-3,
        "s": 1.0,
    }
    return value * factors.get(unit, 1.0), unit


def format_time(tick: float, factor: float) -> tuple[str, str]:
    seconds = tick * factor
    units = [("s", 1.0), ("ms", 1e-3), ("us", 1e-6), ("ns", 1e-9), ("ps", 1e-12), ("fs", 1e-15)]
    for unit, scale in units:
        value = seconds / scale
        if abs(value) >= 1.0:
            return f"{value:.3g}", unit
    return f"{seconds / 1e-15:.3g}", "fs"


def signal_from_name(id_to_name: dict[str, str], label: str, pattern: str) -> Signal:
    regex = re.compile(pattern)
    vector_ids: list[str] = []
    bit_matches: list[tuple[int, str]] = []

    for ident, full_name in id_to_name.items():
        match = regex.fullmatch(full_name)
        if not match:
            continue
        if "bit" in match.groupdict():
            bit_matches.append((int(match.group("bit")), ident))
        else:
            vector_ids.append(ident)

    if vector_ids:
        return Signal(label=label, kind="bus", ids=[vector_ids[0]])
    if bit_matches:
        bit_matches.sort(reverse=True)
        return Signal(
            label=label,
            kind="bus",
            ids=[ident for _, ident in bit_matches],
            bit_indices=[bit for bit, _ in bit_matches],
        )
    raise ValueError(f"signal not found: {label} / {pattern}")


def value_at(events: list[tuple[int, str]], time: int) -> str:
    index = bisect_right(events, (time, "~")) - 1
    if index < 0:
        return "x"
    return events[index][1]


def bus_value(signal: Signal, changes: dict[str, list[tuple[int, str]]], time: int) -> str:
    if signal.bit_indices is None:
        return value_at(changes.get(signal.ids[0], []), time)
    bits = [value_at(changes.get(ident, []), time) for ident in signal.ids]
    return "".join("0" if bit in "xz" else bit for bit in bits)


def to_int(value: str) -> int:
    if not value or any(ch not in "01" for ch in value):
        return 0
    return int(value, 2)


def render_wave_view(
    vcd: Path,
    output: Path,
    title: str,
    signal_specs: list[tuple[str, str]],
    start_ratio: float,
    stop_ratio: float,
) -> None:
    version, timescale, id_to_name, changes, max_time = parse_vcd(vcd)
    time_factor, _ = timescale_factor(timescale)
    signals = [signal_from_name(id_to_name, label, pattern) for label, pattern in signal_specs]
    start_time = int(max_time * start_ratio)
    stop_time = int(max_time * stop_ratio)
    if stop_time <= start_time:
        stop_time = max_time

    sample_count = 900
    times = [start_time + int((stop_time - start_time) * i / (sample_count - 1)) for i in range(sample_count)]

    fig, ax = plt.subplots(figsize=(14, 7.5))
    fig.patch.set_facecolor("#111318")
    ax.set_facecolor("#151922")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    left_w = 0.28
    top_h = 0.10
    bottom_h = 0.07
    wave_x0 = left_w + 0.02
    wave_x1 = 0.98
    row_top = 1.0 - top_h - 0.03
    row_bottom = bottom_h + 0.03
    row_h = (row_top - row_bottom) / len(signals)

    ax.add_patch(Rectangle((0, 1 - top_h), 1, top_h, color="#20242e"))
    ax.text(0.02, 0.955, title, color="#e9edf5", fontsize=16, va="center", weight="bold")
    ax.text(0.02, 0.915, f"{version}  |  {vcd.name}  |  timescale {timescale}", color="#aeb6c8", fontsize=10, va="center")
    ax.add_patch(Rectangle((0, 0), left_w, 1 - top_h, color="#10131a"))
    ax.text(0.025, row_top + 0.012, "Signals", color="#c9d1e2", fontsize=11, weight="bold")
    ax.text(left_w - 0.03, row_top + 0.012, "Value", color="#c9d1e2", fontsize=11, ha="right", weight="bold")

    for grid_index in range(11):
        x = wave_x0 + (wave_x1 - wave_x0) * grid_index / 10
        ax.plot([x, x], [row_bottom, row_top], color="#343b4a", linewidth=0.8)
        tick_time = start_time + (stop_time - start_time) * grid_index / 10
        tick_label, tick_unit = format_time(tick_time, time_factor)
        ax.text(x, bottom_h * 0.55, tick_label, color="#8993a8", fontsize=8, ha="center", va="center")

    _, axis_unit = format_time(stop_time, time_factor)
    ax.text((wave_x0 + wave_x1) / 2, bottom_h * 0.18, f"simulation time / {axis_unit}", color="#8993a8", fontsize=9, ha="center")

    for row, signal in enumerate(signals):
        y_mid = row_top - row_h * (row + 0.5)
        y0 = y_mid - row_h * 0.28
        y1 = y_mid + row_h * 0.28
        ax.plot([0, 1], [y_mid - row_h * 0.5, y_mid - row_h * 0.5], color="#252b36", linewidth=0.6)
        last_value = bus_value(signal, changes, stop_time)
        value_text = hex(to_int(last_value)) if signal.kind == "bus" and len(last_value) > 1 else last_value
        ax.text(0.025, y_mid, signal.label, color="#dde5f5", fontsize=10, va="center")
        ax.text(left_w - 0.03, y_mid, value_text, color="#8ff0a4", fontsize=10, va="center", ha="right", family="monospace")

        values = [bus_value(signal, changes, time) for time in times]
        xs = [wave_x0 + (wave_x1 - wave_x0) * i / (sample_count - 1) for i in range(sample_count)]
        if signal.kind == "bus" and any(len(value) > 1 for value in values):
            last = values[0]
            x_start = xs[0]
            for x, value in zip(xs[1:], values[1:]):
                if value != last:
                    ax.plot([x_start, x], [y_mid, y_mid], color="#5eead4", linewidth=1.8)
                    if x - x_start > 0.035:
                        ax.text((x_start + x) / 2, y_mid + row_h * 0.18, hex(to_int(last)), color="#dbeafe", fontsize=7, ha="center")
                    x_start = x
                    last = value
            ax.plot([x_start, xs[-1]], [y_mid, y_mid], color="#5eead4", linewidth=1.8)
            if xs[-1] - x_start > 0.035:
                ax.text((x_start + xs[-1]) / 2, y_mid + row_h * 0.18, hex(to_int(last)), color="#dbeafe", fontsize=7, ha="center")
        else:
            ys = [y1 if value == "1" else y0 for value in values]
            ax.step(xs, ys, where="post", color="#facc15", linewidth=1.5)

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", required=True, choices=["i2s", "cic", "log"])
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/software_waveforms"))
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    presets = {
        "i2s": (
            root / "sim/i2s_tx_3wire/outputs/i2s_tx_3wire.vcd",
            "ModelSim Wave - I2S Transmitter Timing",
            [
                ("reset", r"tb_i2s_tx_3wire\.reset"),
                ("sample_stb", r"tb_i2s_tx_3wire\.sample_stb"),
                ("sample[15:0]", r"tb_i2s_tx_3wire\.sample \[15:0\]"),
                ("BCK", r"tb_i2s_tx_3wire\.bck"),
                ("LRCK", r"tb_i2s_tx_3wire\.lrck"),
                ("DIN", r"tb_i2s_tx_3wire\.din"),
            ],
            0.02,
            0.18,
            "modelsim_i2s_wave.png",
        ),
        "cic": (
            root / "sim/cic_3_filter/outputs/cic_3_filter.vcd",
            "ModelSim Wave - CIC Decimation Filter",
            [
                ("reset", r"tb_cic_3_filter\.reset"),
                ("clk", r"tb_cic_3_filter\.clk"),
                ("en_in", r"tb_cic_3_filter\.en_in"),
                ("en_out", r"tb_cic_3_filter\.en_out"),
                ("in[1:0]", r"tb_cic_3_filter\.in \[1:0\]"),
                ("out[8:0]", r"tb_cic_3_filter\.out \[(?P<bit>\d+)\]"),
            ],
            0.0,
            0.32,
            "modelsim_cic_wave.png",
        ),
        "log": (
            root / "sim/log_encoder/outputs/log_encoder.vcd",
            "ModelSim Wave - ROM Logarithmic Encoder",
            [
                ("reset", r"tb_log_encoder\.reset"),
                ("clk", r"tb_log_encoder\.clk"),
                ("en", r"tb_log_encoder\.en"),
                ("pcm_in[15:0]", r"tb_log_encoder\.in \[15:0\]"),
                ("log_out[7:0]", r"tb_log_encoder\.out \[(?P<bit>\d+)\]"),
                ("magnitude[14:0]", r"tb_log_encoder\.dut\.magnitude \[14:0\]"),
                ("rom_addr[11:0]", r"tb_log_encoder\.dut\.rom_addr \[11:0\]"),
            ],
            0.0,
            0.42,
            "modelsim_log_encoder_wave.png",
        ),
    }
    vcd, title, specs, start, stop, filename = presets[args.preset]
    render_wave_view(vcd, args.output_dir / filename, title, specs, start, stop)
    print(args.output_dir / filename)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
