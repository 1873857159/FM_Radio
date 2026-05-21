#!/usr/bin/env python3
"""Build real-data figures and a defense-oriented audio-flow tech document."""

from __future__ import annotations

import csv
import json
import math
import re
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np
from scipy import signal


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DUMP_PATH = PROJECT_ROOT / "sim/fm_loopback_audio_rom/outputs/fm_loopback_audio_rom_dump_samples.txt"
I2S_VCD = PROJECT_ROOT / "sim/i2s_tx_3wire/outputs/i2s_tx_3wire.vcd"
CIC_VCD = PROJECT_ROOT / "sim/cic_3_filter/outputs/cic_3_filter.vcd"
OUT_DIR = PROJECT_ROOT / "doc/audio_flow_techdoc"
FIG_DIR = OUT_DIR / "figures"
SAMPLE_RATE = 32_000.0

plt.rcParams["font.family"] = ["AR PL UMing CN", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.facecolor"] = "white"
plt.rcParams["axes.facecolor"] = "white"


@dataclass(frozen=True)
class SignalData:
    name: str
    width: int
    events: list[tuple[int, str]]


def load_dump(path: Path) -> tuple[np.ndarray, np.ndarray]:
    rows: list[tuple[int, int, int]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 3:
            continue
        rows.append((int(parts[0]), int(parts[1]), int(parts[2])))

    if not rows:
        raise ValueError(f"no sample rows found in {path}")

    clean_rows: list[tuple[int, int, int]] = []
    expected = 0
    for row in rows:
        if row[0] != expected:
            break
        clean_rows.append(row)
        expected += 1

    reference = np.asarray([row[1] for row in clean_rows], dtype=np.float64)
    output = np.asarray([row[2] for row in clean_rows], dtype=np.float64)
    return reference, output


def best_alignment(reference: np.ndarray, target: np.ndarray, max_lag: int = 64) -> tuple[int, np.ndarray, np.ndarray]:
    ref = reference - np.mean(reference)
    tgt = target - np.mean(target)
    corr = signal.correlate(tgt, ref, mode="full")
    lags = signal.correlation_lags(tgt.size, ref.size, mode="full")
    valid = np.abs(lags) <= max_lag
    best_idx = np.argmax(np.abs(corr[valid]))
    best_lag = int(lags[valid][best_idx])

    if best_lag >= 0:
        aligned_ref = reference[: reference.size - best_lag]
        aligned_out = target[best_lag:]
    else:
        lag = -best_lag
        aligned_ref = reference[lag:]
        aligned_out = target[: target.size - lag]

    length = min(aligned_ref.size, aligned_out.size)
    return best_lag, aligned_ref[:length], aligned_out[:length]


def compute_metrics(reference: np.ndarray, output: np.ndarray, lag_samples: int, captured_samples: int) -> dict[str, float | int | str]:
    ref_zero = reference - np.mean(reference)
    out_zero = output - np.mean(output)
    err = output - reference
    err_zero = out_zero - ref_zero

    window = np.hanning(reference.size)
    ref_fft = np.abs(np.fft.rfft(ref_zero * window))
    out_fft = np.abs(np.fft.rfft(out_zero * window))

    ref_rms = float(np.sqrt(np.mean(ref_zero**2)))
    err_rms = float(np.sqrt(np.mean(err_zero**2)))
    source_peak = float(np.max(np.abs(reference)))
    output_peak = float(np.max(np.abs(output)))

    return {
        "dump": str(DUMP_PATH),
        "sample_rate": SAMPLE_RATE,
        "best_lag_samples": lag_samples,
        "best_lag_ms": lag_samples / SAMPLE_RATE * 1e3,
        "captured_samples": captured_samples,
        "aligned_samples": int(reference.size),
        "pearson_corr": float(np.corrcoef(ref_zero, out_zero)[0, 1]),
        "spectral_corr": float(np.corrcoef(ref_fft, out_fft)[0, 1]),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "nrmse_pct": float(np.sqrt(np.mean(err**2)) / source_peak * 100.0),
        "source_peak": source_peak,
        "output_peak": output_peak,
        "peak_gain_db": float(20.0 * math.log10(max(output_peak, 1e-9) / max(source_peak, 1e-9))),
        "reference_rms": ref_rms,
        "output_rms": float(np.sqrt(np.mean(out_zero**2))),
        "error_rms": err_rms,
        "snr_like_db": float(20.0 * math.log10(ref_rms / max(err_rms, 1e-9))),
    }


def spectrum_db(samples: np.ndarray, sample_rate: float) -> tuple[np.ndarray, np.ndarray]:
    zero = samples - np.mean(samples)
    window = np.hanning(samples.size)
    freq = np.fft.rfftfreq(samples.size, d=1.0 / sample_rate)
    mag = np.abs(np.fft.rfft(zero * window))
    mag_db = 20.0 * np.log10(np.maximum(mag, 1e-9))
    return freq, mag_db


def signed_from_bits(bits: str) -> int:
    clean = "".join("0" if bit.lower() in {"x", "z"} else bit for bit in bits)
    if not clean:
        return 0
    value = int(clean, 2)
    if clean[0] == "1":
        value -= 1 << len(clean)
    return value


def parse_vcd(path: Path) -> tuple[str, dict[str, SignalData], int]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    scopes: list[str] = []
    id_to_name: dict[str, str] = {}
    id_to_width: dict[str, int] = {}
    id_events: dict[str, list[tuple[int, str]]] = {}
    timescale = "1"
    current_time = 0
    max_time = 0
    in_defs = True

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("$timescale"):
            continue
        if in_defs and not line.startswith("$") and any(unit in line for unit in ("fs", "ps", "ns", "us")):
            timescale = line
            continue
        if line.startswith("$scope"):
            parts = line.split()
            if len(parts) >= 3:
                scopes.append(parts[2])
            continue
        if line.startswith("$upscope"):
            if scopes:
                scopes.pop()
            continue
        if line.startswith("$var"):
            parts = line.split()
            if len(parts) >= 5:
                width = int(parts[2])
                ident = parts[3]
                name = " ".join(parts[4:-1])
                if ident not in id_to_name:
                    id_to_name[ident] = ".".join(scopes + [name])
                    id_to_width[ident] = width
                    id_events[ident] = []
            continue
        if line.startswith("$enddefinitions"):
            in_defs = False
            continue
        if in_defs:
            continue
        if line.startswith("#"):
            current_time = int(line[1:])
            max_time = max(max_time, current_time)
            continue
        if line[0] in "01xXzZ":
            ident = line[1:]
            if ident in id_events:
                id_events[ident].append((current_time, line[0].lower()))
            continue
        if line[0] in "bB":
            parts = line.split()
            if len(parts) == 2 and parts[1] in id_events:
                id_events[parts[1]].append((current_time, parts[0][1:].lower()))

    by_name: dict[str, SignalData] = {}
    for ident, name in id_to_name.items():
        by_name[name] = SignalData(name=name, width=id_to_width[ident], events=id_events.get(ident, []))
    return timescale, by_name, max_time


def timescale_to_seconds(timescale: str) -> float:
    match = re.match(r"([0-9.]+)\s*([a-z]+)", timescale.strip())
    if not match:
        return 1.0
    value = float(match.group(1))
    units = {
        "fs": 1e-15,
        "ps": 1e-12,
        "ns": 1e-9,
        "us": 1e-6,
        "ms": 1e-3,
        "s": 1.0,
    }
    return value * units.get(match.group(2), 1.0)


def value_at(events: list[tuple[int, str]], tick: int) -> str:
    index = bisect_right(events, (tick, "~")) - 1
    if index < 0:
        return "x"
    return events[index][1]


def sample_signal(signal_data: SignalData, ticks: np.ndarray, signed: bool = False) -> np.ndarray:
    values: list[float] = []
    for tick in ticks:
        raw = value_at(signal_data.events, int(tick))
        if signal_data.width == 1:
            bit = 0 if raw.lower() in {"x", "z"} else int(raw)
            values.append(float(-1 if signed and bit else bit))
        else:
            values.append(float(signed_from_bits(raw) if signed else int(raw.replace("x", "0").replace("z", "0"), 2)))
    return np.asarray(values, dtype=np.float64)


def find_signal(by_name: dict[str, SignalData], suffix: str) -> SignalData:
    matches = [data for name, data in by_name.items() if name.endswith(suffix)]
    if not matches:
        raise KeyError(suffix)
    matches.sort(key=lambda item: len(item.name))
    return matches[0]


def figure_path(name: str) -> Path:
    return FIG_DIR / name


def setup_axis(ax: plt.Axes, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.28)


def save_system_flow(path: Path) -> None:
    stages = [
        ("ROM 音频源", "16-bit PCM\n32 kHz"),
        ("板内 FM 调制", "step/phase\n240 MHz"),
        ("1-bit FM 输入", "0/1 方波\n240 MHz"),
        ("DDS 本振", "32-bit 相位\n100 MHz"),
        ("IQ 正交下变频", "I/Q: signed 2-bit\n240 MHz"),
        ("CIC 一级抽取", "R=5\n48 MHz"),
        ("CIC 二级抽取", "R=50\n960 kHz"),
        ("CORDIC 相位", "θ[n]\n17-bit"),
        ("微分鉴频", "Δθ[n]\n960 kHz"),
        ("音频 CIC", "R=30\n32 kHz"),
        ("16 位 PCM", "signed 16-bit\n32 kHz"),
        ("I2S/PCM5102", "BCK 2.048 MHz\nLRCK 32 kHz"),
        ("耳机/扬声器", "模拟音频"),
    ]

    fig, ax = plt.subplots(figsize=(15, 4.8))
    ax.axis("off")
    ax.set_title("基于 FPGA 的全数字 FM 收音机音频转化总流程", fontsize=16, pad=14)

    xs = np.linspace(0.035, 0.965, 7)
    ys = [0.68, 0.30]
    positions: list[tuple[float, float]] = []
    for row, y in enumerate(ys):
        cols = 7 if row == 0 else 6
        row_xs = np.linspace(0.035, 0.965, cols)
        for x in row_xs:
            positions.append((x, y))
    positions = positions[: len(stages)]

    for index, ((title, note), (x, y)) in enumerate(zip(stages, positions)):
        box = FancyBboxPatch(
            (x - 0.06, y - 0.09),
            0.12,
            0.15,
            boxstyle="round,pad=0.012,rounding_size=0.015",
            linewidth=1.2,
            edgecolor="#2f4f6f",
            facecolor="#eef5fb",
        )
        ax.add_patch(box)
        ax.text(x, y + 0.025, title, ha="center", va="center", fontsize=10, weight="bold")
        ax.text(x, y - 0.035, note, ha="center", va="center", fontsize=8.4, color="#333333")
        if index < len(stages) - 1:
            x2, y2 = positions[index + 1]
            ax.annotate(
                "",
                xy=(x2 - 0.07, y2),
                xytext=(x + 0.07, y),
                arrowprops=dict(arrowstyle="->", color="#485465", lw=1.2),
            )

    ax.text(
        0.5,
        0.05,
        "数据来源说明：输入/输出音频对比来自 ROM 回环 dump；I2S/CIC 局部图来自真实模块仿真 VCD；缺少文本导出的中间链路按 RTL 结构标注为重构或原理示意。",
        ha="center",
        fontsize=9,
        color="#555555",
    )
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_reference_audio_figures(reference: np.ndarray) -> None:
    time_ms = np.arange(reference.size) / SAMPLE_RATE * 1e3
    freq, mag_db = spectrum_db(reference, SAMPLE_RATE)

    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.plot(time_ms, reference, color="#1f77b4", linewidth=1.0, label="FM 调制器入口参考音频")
    setup_axis(ax, "参考音频时域波形（真实 dump：source 列）", "时间 / ms", "幅度 / PCM 值")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_path("02_reference_audio_waveform.png"), dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.plot(freq / 1e3, mag_db, color="#1f77b4", linewidth=1.0, label="参考音频 FFT")
    ax.set_xlim(0, 16)
    setup_axis(ax, "参考音频频谱（真实 dump：source 列 FFT）", "频率 / kHz", "幅度 / dB")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_path("03_reference_audio_spectrum.png"), dpi=180)
    plt.close(fig)


def save_fm_reconstruction_figures(reference: np.ndarray) -> None:
    width_phase = 28
    width_audio = 16
    k_carrier_fm = 0x6AAAAAAA >> (32 - width_phase)
    k_deviation_fm = 1_073_742 >> (32 - width_phase)
    step = k_carrier_fm + ((reference.astype(np.int64) * k_deviation_fm) >> (width_audio - 1))

    upsample = 240_000_000 // 32_000
    local_audio = reference[:8].astype(np.int64)
    local_step = step[:8].astype(np.int64)
    repeated_step = np.repeat(local_step, upsample)
    phase = np.cumsum(repeated_step, dtype=np.int64) & ((1 << width_phase) - 1)
    msb = 1 - ((phase >> (width_phase - 1)) & 1)
    ticks = np.arange(repeated_step.size)
    time_us = ticks / 240_000_000 * 1e6

    fig, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=False)
    n = np.arange(64)
    axes[0].step(n[: min(reference.size, 64)], reference[:64], where="post", color="#1f77b4", label="a[n]")
    setup_axis(axes[0], "ROM 音频样本 a[n] 局部波形（真实 source 样本）", "样本序号 n", "PCM 值")
    axes[0].legend()

    axes[1].step(np.arange(min(step.size, 64)), step[:64], where="post", color="#ff7f0e", label="step[n] = Kc + Kd·a[n]")
    setup_axis(axes[1], "频率步进 step[n]（由真实 a[n] 按 RTL 公式重构）", "样本序号 n", "相位步进")
    axes[1].legend()

    display_len = min(len(time_us), 2500)
    axes[2].plot(time_us[:display_len], phase[:display_len], color="#2ca02c", linewidth=0.9, label="phase[n]")
    setup_axis(axes[2], "相位累加 phase[n] 局部（由真实 a[n] 按 RTL 公式重构）", "时间 / us", "相位累加值")
    axes[2].legend()
    fig.tight_layout()
    fig.savefig(figure_path("04_fm_step_phase_reconstruction.png"), dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=False)
    view = min(len(time_us), 900)
    axes[0].step(time_us[:view], msb[:view], where="post", color="#444444", label="MSB 1-bit FM")
    axes[0].set_ylim(-0.25, 1.25)
    setup_axis(axes[0], "MSB 输出 1-bit FM 局部放大（RTL 公式重构）", "时间 / us", "逻辑值")
    axes[0].legend()

    signed_fm = msb.astype(np.float64) * 2.0 - 1.0
    segment = signed_fm[: min(signed_fm.size, 65_536)]
    freq = np.fft.rfftfreq(segment.size, d=1.0 / 240_000_000)
    mag = 20 * np.log10(np.maximum(np.abs(np.fft.rfft((segment - segment.mean()) * np.hanning(segment.size))), 1e-9))
    axes[1].plot(freq / 1e6, mag, color="#6a3d9a", linewidth=0.9, label="1-bit FM FFT")
    axes[1].set_xlim(70, 120)
    setup_axis(axes[1], "1-bit FM 频谱局部（真实输入样本 + RTL 公式重构）", "频率 / MHz", "幅度 / dB")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(figure_path("05_fm_1bit_reconstruction.png"), dpi=180)
    plt.close(fig)


def save_iq_principle_figures() -> None:
    sample_count = 6000
    fs = 240_000_000.0
    t = np.arange(sample_count) / fs
    audio = np.sin(2 * np.pi * 1_000 * t)
    inst_freq = 100_000_000.0 + 60_000.0 * audio
    phase = np.cumsum(2 * np.pi * inst_freq / fs)
    fm = np.where(np.cos(phase) >= 0, 1.0, -1.0)
    lo_i = np.sign(np.cos(2 * np.pi * 100_000_000.0 * t))
    lo_q = -np.sign(np.sin(2 * np.pi * 100_000_000.0 * t))
    i_data = fm * lo_i
    q_data = fm * lo_q
    time_us = t * 1e6

    fig, axes = plt.subplots(4, 1, figsize=(10.5, 8), sharex=True)
    view = 500
    axes[0].step(time_us[:view], (fm[:view] + 1) / 2, where="post", color="#444444", label="1-bit FM")
    axes[1].step(time_us[:view], i_data[:view], where="post", color="#1f77b4", label="I 路")
    axes[2].step(time_us[:view], q_data[:view], where="post", color="#d62728", label="Q 路")
    axes[3].plot(i_data[:view], q_data[:view], ".", color="#2ca02c", markersize=3, label="I/Q 状态点")
    for ax in axes[:3]:
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.28)
        ax.set_ylabel("幅度")
    axes[0].set_title("IQ 下变频原理示意（非系统验证波形）")
    axes[2].set_xlabel("时间 / us")
    axes[3].set_xlabel("I")
    axes[3].set_ylabel("Q")
    axes[3].grid(True, alpha=0.28)
    axes[3].legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(figure_path("06_iq_downconvert_principle.png"), dpi=180)
    plt.close(fig)

    freq, fm_mag = spectrum_db(fm[:4096], fs)
    _, i_mag = spectrum_db(i_data[:4096], fs)
    fig, ax = plt.subplots(figsize=(10.5, 4.7))
    ax.plot(freq / 1e6, fm_mag, color="#444444", label="下变频前 1-bit FM")
    ax.plot(freq / 1e6, i_mag, color="#1f77b4", label="下变频后 I 路")
    ax.set_xlim(0, 120)
    setup_axis(ax, "IQ 下变频频谱搬移原理示意（非系统验证波形）", "频率 / MHz", "幅度 / dB")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_path("07_iq_spectrum_principle.png"), dpi=180)
    plt.close(fig)


def save_cic_vcd_figure() -> None:
    timescale, by_name, max_time = parse_vcd(CIC_VCD)
    factor = timescale_to_seconds(timescale)
    in_sig = find_signal(by_name, "tb_cic_3_filter.in [1:0]")
    out_sig = find_signal(by_name, "tb_cic_3_filter.out [8]")
    # Prefer vector form for input and reconstruct output bits from suffix if VCD expands the bus.
    out_bits = [find_signal(by_name, f"tb_cic_3_filter.out [{bit}]") for bit in range(8, -1, -1)]

    ticks = np.linspace(0, max_time, 900, dtype=np.int64)
    time_us = ticks * factor * 1e6
    in_values = sample_signal(in_sig, ticks, signed=True)
    out_values = []
    for tick in ticks:
        bits = "".join(value_at(bit.events, int(tick)) for bit in out_bits)
        out_values.append(signed_from_bits(bits))
    out_values = np.asarray(out_values, dtype=np.float64)

    fig, axes = plt.subplots(3, 1, figsize=(10.5, 7.2), sharex=True)
    axes[0].step(time_us, in_values, where="post", color="#1f77b4", label="CIC 输入")
    setup_axis(axes[0], "CIC 模块输入时域波形（真实模块仿真 VCD）", "时间 / us", "输入值")
    axes[0].legend()
    axes[1].step(time_us, out_values, where="post", color="#d62728", label="CIC 输出")
    setup_axis(axes[1], "CIC 模块输出时域波形（R=5，真实模块仿真 VCD）", "时间 / us", "输出值")
    axes[1].legend()
    en_sig = find_signal(by_name, "tb_cic_3_filter.en_out")
    en_values = sample_signal(en_sig, ticks)
    axes[2].step(time_us, en_values, where="post", color="#2ca02c", label="en_out")
    axes[2].set_ylim(-0.25, 1.25)
    setup_axis(axes[2], "抽取输出使能 en_out（真实模块仿真 VCD）", "时间 / us", "逻辑值")
    axes[2].legend()
    fig.tight_layout()
    fig.savefig(figure_path("08_cic_real_module_vcd.png"), dpi=180)
    plt.close(fig)


def save_cic_chain_principle(reference: np.ndarray) -> None:
    # A compact deterministic demonstration from the real audio sequence. Marked as principle/RTL explanation.
    x = np.repeat(reference[:128] / max(np.max(np.abs(reference[:128])), 1.0), 30)
    cic1 = signal.decimate(x, 5, ftype="fir", zero_phase=True)
    cic2 = signal.decimate(cic1, 50 if cic1.size > 200 else 5, ftype="fir", zero_phase=True)
    audio = signal.decimate(cic1, 30 if cic1.size > 120 else 3, ftype="fir", zero_phase=True)

    fig, axes = plt.subplots(3, 2, figsize=(12, 8))
    series = [
        ("CIC 输入示意", x, 240_000_000.0, "#444444"),
        ("CIC 一级输出示意 R=5", cic1, 48_000_000.0, "#1f77b4"),
        ("CIC 二级输出示意", cic2, 960_000.0 if cic2.size < cic1.size else 48_000_000.0, "#d62728"),
    ]
    for row, (title, data, fs, color) in enumerate(series):
        time = np.arange(data.size) / fs
        axes[row, 0].plot(time * 1e6, data, color=color, linewidth=0.9)
        setup_axis(axes[row, 0], title + "：时域", "时间 / us", "归一化幅度")
        freq, mag = spectrum_db(data, fs)
        unit = "MHz" if fs > 2_000_000 else "kHz"
        scale = 1e6 if unit == "MHz" else 1e3
        axes[row, 1].plot(freq / scale, mag, color=color, linewidth=0.9)
        setup_axis(axes[row, 1], title + "：频谱", f"频率 / {unit}", "幅度 / dB")
    fig.suptitle("CIC 抽取链路原理示意（由真实参考音频派生，非系统中间导出）", fontsize=14)
    fig.tight_layout()
    fig.savefig(figure_path("09_cic_chain_principle.png"), dpi=180)
    plt.close(fig)


def save_cordic_discriminator_principle(reference: np.ndarray) -> None:
    fs = 960_000.0
    n = np.arange(2400)
    audio = np.interp(np.linspace(0, len(reference) - 1, n.size), np.arange(len(reference)), reference)
    audio = audio / max(np.max(np.abs(audio)), 1.0)
    phase_inc = 0.12 + 0.025 * audio
    theta = np.cumsum(phase_inc)
    i_data = np.cos(theta)
    q_data = np.sin(theta)
    cordic_phase = np.angle(i_data + 1j * q_data)
    unwrap_phase = np.unwrap(cordic_phase)
    diff_phase = np.diff(unwrap_phase, prepend=unwrap_phase[0])

    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.5))
    axes[0, 0].plot(i_data[:1000], q_data[:1000], color="#1f77b4", linewidth=0.9)
    setup_axis(axes[0, 0], "I/Q 平面轨迹（原理示意）", "I", "Q")
    time_ms = n / fs * 1e3
    axes[0, 1].plot(time_ms, cordic_phase, color="#d62728", linewidth=0.9, label="θ[n]")
    setup_axis(axes[0, 1], "CORDIC 输出瞬时相位 θ[n]（原理示意）", "时间 / ms", "相位 / rad")
    axes[0, 1].legend()
    axes[1, 0].plot(time_ms, unwrap_phase, color="#2ca02c", linewidth=0.9, label="unwrap θ[n]")
    setup_axis(axes[1, 0], "相位展开 unwrap 后 θ[n]（原理示意）", "时间 / ms", "相位 / rad")
    axes[1, 0].legend()
    axes[1, 1].plot(time_ms, diff_phase, color="#ff7f0e", linewidth=0.9, label="Δθ[n]")
    setup_axis(axes[1, 1], "微分鉴频 Δθ[n]（原理示意）", "时间 / ms", "相位差")
    axes[1, 1].legend()
    fig.suptitle("CORDIC 相位提取与微分鉴频原理示意（非系统验证波形）", fontsize=14)
    fig.tight_layout()
    fig.savefig(figure_path("10_cordic_discriminator_principle.png"), dpi=180)
    plt.close(fig)

    freq, mag = spectrum_db(diff_phase, fs)
    fig, ax = plt.subplots(figsize=(10.5, 4.7))
    ax.plot(freq / 1e3, mag, color="#ff7f0e", linewidth=0.9, label="Δθ[n] FFT")
    ax.set_xlim(0, 16)
    setup_axis(ax, "微分鉴频输出频谱原理示意", "频率 / kHz", "幅度 / dB")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_path("11_diff_phase_spectrum_principle.png"), dpi=180)
    plt.close(fig)


def save_validation_figures(reference: np.ndarray, output: np.ndarray, metrics: dict[str, float | int | str]) -> None:
    ref_zero = reference - np.mean(reference)
    out_zero = output - np.mean(output)
    time_ms = np.arange(reference.size) / SAMPLE_RATE * 1e3
    freq, ref_mag = spectrum_db(ref_zero, SAMPLE_RATE)
    _, out_mag = spectrum_db(out_zero, SAMPLE_RATE)

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(time_ms, ref_zero, color="#1f77b4", linewidth=1.0, label="输入参考音频（对齐后）")
    ax.plot(time_ms, out_zero, color="#d62728", linewidth=0.9, alpha=0.85, label="解调输出音频（对齐后）")
    setup_axis(ax, "输入参考音频 vs 解调输出音频：时域对比（真实系统验证）", "时间 / ms", "去直流幅度 / PCM 值")
    ax.legend()
    fig.text(0.01, 0.01, f"互相关最佳对齐延迟：{metrics['best_lag_samples']} 样本 / {metrics['best_lag_ms']:.5f} ms", fontsize=9)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(figure_path("12_validation_waveform_aligned.png"), dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(freq / 1e3, ref_mag, color="#1f77b4", linewidth=1.0, label="输入参考音频")
    ax.plot(freq / 1e3, out_mag, color="#d62728", linewidth=0.9, alpha=0.85, label="解调输出音频")
    ax.set_xlim(0, 16)
    setup_axis(ax, "输入参考音频 vs 解调输出音频：频谱对比（真实系统验证）", "频率 / kHz", "幅度 / dB")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_path("13_validation_spectrum_compare.png"), dpi=180)
    plt.close(fig)

    nperseg = min(256, reference.size)
    noverlap = nperseg // 2
    f_ref, t_ref, s_ref = signal.spectrogram(ref_zero, fs=SAMPLE_RATE, window="hann", nperseg=nperseg, noverlap=noverlap, mode="magnitude", scaling="spectrum")
    f_out, t_out, s_out = signal.spectrogram(out_zero, fs=SAMPLE_RATE, window="hann", nperseg=nperseg, noverlap=noverlap, mode="magnitude", scaling="spectrum")
    ref_db = 20 * np.log10(np.maximum(s_ref, 1e-6))
    out_db = 20 * np.log10(np.maximum(s_out, 1e-6))
    vmin = float(min(ref_db.min(), out_db.min()))
    vmax = float(max(ref_db.max(), out_db.max()))

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True, sharey=True)
    img = axes[0].pcolormesh(t_ref * 1e3, f_ref / 1e3, ref_db, shading="auto", cmap="viridis", vmin=vmin, vmax=vmax)
    axes[0].set_title("输入参考音频语谱图（真实系统验证）")
    axes[0].set_ylabel("频率 / kHz")
    axes[1].pcolormesh(t_out * 1e3, f_out / 1e3, out_db, shading="auto", cmap="viridis", vmin=vmin, vmax=vmax)
    axes[1].set_title("解调输出音频语谱图（真实系统验证）")
    axes[1].set_xlabel("时间 / ms")
    axes[1].set_ylabel("频率 / kHz")
    fig.colorbar(img, ax=axes, pad=0.01, label="幅度 / dB")
    fig.tight_layout()
    fig.savefig(figure_path("14_validation_spectrogram_compare.png"), dpi=180)
    plt.close(fig)

    fig = plt.figure(figsize=(11.5, 8), constrained_layout=True)
    grid = fig.add_gridspec(2, 2)
    ax_wave = fig.add_subplot(grid[0, 0])
    peak_idx = int(np.argmax(np.abs(ref_zero)))
    start = max(0, peak_idx - int(SAMPLE_RATE * 0.012))
    stop = min(reference.size, peak_idx + int(SAMPLE_RATE * 0.012))
    ax_wave.plot(time_ms[start:stop], ref_zero[start:stop], color="#1f77b4", label="输入")
    ax_wave.plot(time_ms[start:stop], out_zero[start:stop], color="#d62728", alpha=0.85, label="输出")
    setup_axis(ax_wave, "局部波形叠加", "时间 / ms", "幅度")
    ax_wave.legend()

    ax_spec = fig.add_subplot(grid[0, 1])
    ax_spec.plot(freq / 1e3, ref_mag, color="#1f77b4", label="输入")
    ax_spec.plot(freq / 1e3, out_mag, color="#d62728", alpha=0.85, label="输出")
    ax_spec.set_xlim(0, 16)
    setup_axis(ax_spec, "频谱叠加", "频率 / kHz", "幅度 / dB")
    ax_spec.legend()

    ax_ref = fig.add_subplot(grid[1, 0])
    ax_ref.pcolormesh(t_ref * 1e3, f_ref / 1e3, ref_db, shading="auto", cmap="viridis", vmin=vmin, vmax=vmax)
    ax_ref.set_title("输入语谱图")
    ax_ref.set_xlabel("时间 / ms")
    ax_ref.set_ylabel("频率 / kHz")

    ax_out = fig.add_subplot(grid[1, 1])
    ax_out.pcolormesh(t_out * 1e3, f_out / 1e3, out_db, shading="auto", cmap="viridis", vmin=vmin, vmax=vmax)
    ax_out.set_title("输出语谱图")
    ax_out.set_xlabel("时间 / ms")
    ax_out.set_ylabel("频率 / kHz")
    fig.suptitle("系统验证总览：真实输入与解调输出对比", fontsize=15)
    summary = (
        f"相关系数 {metrics['pearson_corr']:.4f} | 频谱相关 {metrics['spectral_corr']:.4f} | "
        f"NRMSE {metrics['nrmse_pct']:.2f}% | 等效 SNR {metrics['snr_like_db']:.2f} dB | "
        f"延迟 {metrics['best_lag_samples']} 样本"
    )
    fig.text(0.02, 0.015, summary, fontsize=10)
    fig.savefig(figure_path("15_validation_overview.png"), dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(11, 6.4))
    axes[0].plot(time_ms, output, color="#d62728", linewidth=0.9, label="16 位 PCM 输出")
    setup_axis(axes[0], "最终 16 位 PCM 样本波形（真实 output 列）", "时间 / ms", "幅度 / PCM 值")
    axes[0].legend()
    axes[1].plot(freq / 1e3, out_mag, color="#d62728", linewidth=0.9, label="PCM 输出 FFT")
    axes[1].set_xlim(0, 16)
    setup_axis(axes[1], "最终 16 位 PCM 输出频谱（真实 output 列）", "频率 / kHz", "幅度 / dB")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(figure_path("16_pcm16_output_wave_spectrum.png"), dpi=180)
    plt.close(fig)


def save_i2s_vcd_figure() -> None:
    timescale, by_name, max_time = parse_vcd(I2S_VCD)
    factor = timescale_to_seconds(timescale)
    bck = find_signal(by_name, "tb_i2s_tx_3wire.bck")
    lrck = find_signal(by_name, "tb_i2s_tx_3wire.lrck")
    din = find_signal(by_name, "tb_i2s_tx_3wire.din")
    sample = find_signal(by_name, "tb_i2s_tx_3wire.sample [15:0]")

    start = int(max_time * 0.20)
    stop = min(max_time, start + int(80e-6 / factor))
    ticks = np.linspace(start, stop, 1800, dtype=np.int64)
    time_us = (ticks - ticks[0]) * factor * 1e6

    fig, axes = plt.subplots(4, 1, figsize=(11.5, 7), sharex=True)
    for ax, sig, label, color in [
        (axes[0], sample, "PCM 样本 0x5A3C", "#1f77b4"),
        (axes[1], bck, "BCK", "#444444"),
        (axes[2], lrck, "LRCK", "#d62728"),
        (axes[3], din, "DIN", "#2ca02c"),
    ]:
        values = sample_signal(sig, ticks, signed=(sig.width > 1))
        ax.step(time_us, values, where="post", color=color, linewidth=0.9, label=label)
        ax.grid(True, alpha=0.28)
        ax.legend(loc="upper right")
        ax.set_ylabel("值")
    axes[0].set_title("I2S 三线时序（真实 i2s_tx_3wire 模块仿真 VCD）")
    axes[3].set_xlabel("时间 / us")
    fig.tight_layout()
    fig.savefig(figure_path("17_i2s_three_wire_real_vcd.png"), dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 3.5))
    ax.axis("off")
    ax.set_title("I2S 左右声道 64 bit 帧结构", fontsize=14)
    ax.add_patch(Rectangle((0.06, 0.45), 0.42, 0.22, facecolor="#d9ecff", edgecolor="#24527a"))
    ax.add_patch(Rectangle((0.52, 0.45), 0.42, 0.22, facecolor="#ffe5d4", edgecolor="#994d1f"))
    ax.text(0.27, 0.56, "左声道 32 bit\\n{0, PCM[15:0], 15'b0}", ha="center", va="center", fontsize=12)
    ax.text(0.73, 0.56, "右声道 32 bit\\n{0, PCM[15:0], 15'b0}", ha="center", va="center", fontsize=12)
    ax.annotate("LRCK = 0", xy=(0.27, 0.72), ha="center", fontsize=11)
    ax.annotate("LRCK = 1", xy=(0.73, 0.72), ha="center", fontsize=11)
    ax.text(0.5, 0.25, "BCK = 2.048 MHz，LRCK = 32 kHz；单声道 PCM 在本设计中复制到左右两个声道。", ha="center", fontsize=11)
    fig.tight_layout()
    fig.savefig(figure_path("18_i2s_frame_structure.png"), dpi=180)
    plt.close(fig)


def write_csv_outputs(reference: np.ndarray, output: np.ndarray, metrics: dict[str, float | int | str]) -> None:
    with (OUT_DIR / "aligned_audio_samples.csv").open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["index", "time_ms", "reference", "output", "error"])
        for idx, (ref, out) in enumerate(zip(reference, output)):
            writer.writerow([idx, f"{idx / SAMPLE_RATE * 1e3:.6f}", int(round(ref)), int(round(out)), int(round(out - ref))])

    with (OUT_DIR / "metrics.csv").open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["指标", "数值"])
        metric_names = {
            "best_lag_samples": "最佳对齐延迟 / 样本",
            "best_lag_ms": "最佳对齐延迟 / ms",
            "pearson_corr": "皮尔逊相关系数",
            "spectral_corr": "频谱相关系数",
            "rmse": "RMSE",
            "nrmse_pct": "归一化 RMSE / %",
            "snr_like_db": "等效 SNR / dB",
            "peak_gain_db": "输出峰值相对输入增益 / dB",
        }
        for key, name in metric_names.items():
            writer.writerow([name, metrics[key]])

    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_ppt_outline() -> None:
    rows = [
        ("1", "系统总览", "01_system_flow.png", "讲 ROM→FM→IQ→CIC→CORDIC→鉴频→PCM→I2S 主线，并给出 240 MHz、48 MHz、960 kHz、32 kHz 采样率关系。"),
        ("2", "ROM 音频源", "02_reference_audio_waveform.png / 03_reference_audio_spectrum.png", "强调 source 列是真实调制器入口；可配 `audio16[n]=rom_sample[n]<<8` 和跨时钟握手代码。"),
        ("3", "FM 调制机理", "04_fm_step_phase_reconstruction.png / 05_fm_1bit_reconstruction.png", "页面内直接放 `step[n]=Kc+(a[n]·Kd>>>15)`、`phase[n]=phase[n-1]+step[n]` 和 `fm_modulator.sv` 关键代码。"),
        ("4", "DDS 与 MSB", "05_fm_1bit_reconstruction.png", "解释 `fout=K/2^N·fclk`、相位高位取象限、MSB 翻转密度携带 FM，不要把公式放到末页。"),
        ("5", "IQ 下变频", "06_iq_downconvert_principle.png / 07_iq_spectrum_principle.png", "标注为原理示意；页面内放 `x[n]=2·adc[n]-1`、四象限表和 `iq_modulator.sv` 符号翻转代码。"),
        ("6", "CIC 抽取", "08_cic_real_module_vcd.png / 09_cic_chain_principle.png", "区分真实模块仿真与链路原理示意；配 `H(z)`、积分器/梳状器公式和 R=5、R=50、R=30 位宽增长。"),
        ("7", "CORDIC 与鉴频", "10_cordic_discriminator_principle.png / 11_diff_phase_spectrum_principle.png", "讲 `θ[n]=atan2(Q[n],I[n])`、`Δθ[n]=θ[n]-θ[n-1]`，并配 CORDIC 与 differentiator 代码。"),
        ("8", "PCM 输出", "16_pcm16_output_wave_spectrum.png", "展示最终真实 16 位 PCM 数据形态；说明 R=30 音频 CIC、32 bit `demodulated_f` 和高位截取。"),
        ("9", "I2S 输出", "17_i2s_three_wire_real_vcd.png / 18_i2s_frame_structure.png", "讲 BCK、LRCK、DIN、左右声道 32 bit slot，以及 `tick_num/tick_den` 分数分频。"),
        ("10", "系统验证", "12_validation_waveform_aligned.png / 13_validation_spectrum_compare.png / 14_validation_spectrogram_compare.png", "强调互相关对齐、统一 FFT/语谱参数，并现场解释 lag、Pearson、NRMSE、SNR。"),
        ("11", "结果总览", "15_validation_overview.png", "一页讲完真实验证结论和指标，作为答辩收束页。"),
    ]
    lines = [
        "# 音频转化流程 PPT 拆页建议",
        "",
        "| 页码 | 页面主题 | 建议使用图 | 讲解重点 |",
        "|---:|---|---|---|",
    ]
    lines.extend(f"| {page} | {topic} | `{figs}` | {note} |" for page, topic, figs, note in rows)
    lines.append("")
    lines.append("说明：凡是图名中含 `principle` 或文档图注写明“原理示意”的，不要在答辩中称作系统验证结果；真实输入输出验证重点使用第 10、11 页。每页讲对应模块时同步放公式和关键 RTL 代码，不再单独放到最后。")
    (OUT_DIR / "PPT拆页建议.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def fig_md(filename: str, caption: str) -> str:
    return f"![{caption}](figures/{filename})\n\n图注：{caption}\n"


def write_document(metrics: dict[str, float | int | str]) -> None:
    target = OUT_DIR / "基于FPGA的全数字FM收音机音频转化流程技术文档.md"

    if target.exists():
        previous = target.read_text(encoding="utf-8")
        if "## 11. 系统验证：真实输入输出波形、频谱、语谱图和指标" in previous:
            replacements = {
                r"\| 最佳对齐延迟 \| [^|]+ \|": (
                    f"| 最佳对齐延迟 | {metrics['best_lag_samples']} 样本，"
                    f"{metrics['best_lag_ms']:.5f} ms |"
                ),
                r"\| 皮尔逊相关系数 \| [^|]+ \|": f"| 皮尔逊相关系数 | {metrics['pearson_corr']:.6f} |",
                r"\| 频谱相关系数 \| [^|]+ \|": f"| 频谱相关系数 | {metrics['spectral_corr']:.6f} |",
                r"\| 归一化 RMSE \| [^|]+ \|": f"| 归一化 RMSE | {metrics['nrmse_pct']:.4f}% |",
                r"\| 等效 SNR \| [^|]+ \|": f"| 等效 SNR | {metrics['snr_like_db']:.4f} dB |",
                r"\| 输出峰值相对输入增益 \| [^|]+ \|": (
                    f"| 输出峰值相对输入增益 | {metrics['peak_gain_db']:.4f} dB |"
                ),
            }
            updated = previous
            for pattern, value in replacements.items():
                updated = re.sub(pattern, value, updated)
            target.write_text(updated, encoding="utf-8")
            return

    md = f"""# 基于 FPGA 的全数字 FM 收音机音频转化流程技术文档

> 生成说明：本文档由项目真实 dump、RTL 参数以及已有模块仿真 VCD 整理得到。凡是没有真实中间导出数据的部分，均明确标注为“原理示意”或“依据 RTL 公式重构”，不作为系统验证结果使用。

## 1. 系统整体流程

{fig_md("01_system_flow.png", "系统整体流程图。输入从 ROM 音频源开始，经板内 FM 调制、1-bit FM、DDS/IQ 下变频、两级 CIC、CORDIC、微分鉴频、音频 CIC，最终变成 16 位 PCM 并经 I2S/PCM5102 输出。每个框中标出了本项目对应的数据形态、采样率或位宽。")}

本模块输入是什么：ROM 中的 16 位离散音频样本，验证路径使用 `sim/fm_loopback_audio_rom/outputs/fm_loopback_audio_rom_dump_samples.txt` 的 `source` 列。

本模块做了什么处理：顶层链路把音频样本先调制成 1-bit FM 方波，再在接收端完成下变频、抽取、相位提取和鉴频。

本模块输出变成什么：输出端得到 32 kHz、16 位 PCM 样本，随后由三线 I2S 送入 PCM5102 DAC。

波形图怎么看：前级波形表现为音频幅度，调制后变成高频 0/1 翻转，后级又恢复为低速 PCM。

频谱图怎么看：调制过程把音频信息搬移到载波附近，接收过程再把频率变化还原回音频频带。

答辩一句话：这条链路证明了 FPGA 内部可以把参考音频调制成 FM，再用全数字接收通路恢复成可播放 PCM。

## 2. ROM 音频源：音频样本是什么

{fig_md("02_reference_audio_waveform.png", "参考音频时域波形。该图来自 dump 文件 `source` 列，表示 FM 调制器入口处真正参与系统验证的离散 PCM 样本，而不是原始 WAV。")}

{fig_md("03_reference_audio_spectrum.png", "参考音频频谱。该图对同一批 `source` 样本去直流并加 Hann 窗后做 FFT，用来观察音频样本中的频率成分。")}

本模块输入是什么：音频 ROM 输出的 16 位 PCM 样本，采样率为 32 kHz。

本模块做了什么处理：ROM 按音频节拍逐点输出离散样本，样本值代表声音幅度。

本模块输出变成什么：输出仍是 PCM 幅度序列，后续 FM 调制器会读取这些幅度值。

波形图怎么看：横轴是时间，纵轴是 PCM 值，曲线起伏代表声音幅度随时间变化。

频谱图怎么看：频谱不是 ROM 直接存储的内容，而是对时域样本做 FFT 后得到的观察结果。

答辩一句话：ROM 中存的是声音幅度样本，FFT 只是用来观察这些样本里有哪些音频频率。

## 3. FM 调制：幅度怎样变成频率变化

{fig_md("04_fm_step_phase_reconstruction.png", "FM 调制 step 与 phase 重构图。图中 a[n] 来自真实 `source` 样本，step[n] 和 phase[n] 按 `fm_modulator.sv` 的 RTL 公式重构，因此用于解释调制机理，不等同于系统中间信号导出。")}

{fig_md("05_fm_1bit_reconstruction.png", "MSB 1-bit FM 局部波形与频谱重构图。该图由真实输入样本和 RTL 调制公式生成，用来说明 MSB 方波翻转密度怎样携带 FM 信息。")}

本模块输入是什么：32 kHz 的 16 位音频样本 `a[n]`。

本模块做了什么处理：RTL 中先保存最新音频样本，再按 `step[n] = Kc + Kd · a[n]` 得到相位步进，之后持续执行 `phase[n] = phase[n-1] + step[n]`。

本模块输出变成什么：相位累加器 MSB 形成 1-bit FM 方波，逻辑值只有 0/1，但翻转密度随音频幅度变化。

波形图怎么看：a[n] 越大，step[n] 越大，相位上升越快，MSB 翻转越密。

频谱图怎么看：1-bit FM 的能量集中在载波附近，同时包含由音频控制产生的调频信息。

答辩一句话：FM 调制不是直接输出音频幅度，而是把音频幅度变成瞬时频率变化。

## 4. DDS 与 MSB：为什么 1-bit 方波能携带 FM 信息

本模块输入是什么：FM 调制器内部的相位累加值以及载波步进常数。

本模块做了什么处理：DDS 或 NCO 用固定步进产生相位；FM 调制则让步进随音频样本变化。取 MSB 后，输出虽然是方波，但过零或翻转位置已经被相位变化调制。

本模块输出变成什么：输出成为 1-bit 高速方波，供后级数字接收核心作为“广播信号”输入。

波形图怎么看：单个采样点只有 0/1，但局部翻转疏密会变化。

频谱图怎么看：方波会有谐波，但接收链路关注的是围绕目标载波的调频信息。

答辩一句话：MSB 方波不是普通开关量，它的翻转时间由相位控制，所以仍然携带 FM 信息。

## 5. IQ 下变频：高频信号怎样搬到基带

{fig_md("06_iq_downconvert_principle.png", "IQ 下变频原理示意。该图依据 `iq_modulator.sv` 的符号翻转逻辑绘制，说明 0/1 先映射为 +1/-1，再由 DDS 象限信息得到 I/Q。该图不是系统验证波形。")}

{fig_md("07_iq_spectrum_principle.png", "IQ 下变频频谱搬移原理示意。图中展示高频 FM 信号经本振符号翻转后搬移到基带附近的趋势，该图不是系统验证结果。")}

本模块输入是什么：同步后的 1-bit FM 信号 `adc_s` 和 DDS 相位高两位。

本模块做了什么处理：`iq_modulator.sv` 将输入 0/1 映射为 +1/-1，并用 DDS 的四象限信息完成 I/Q 符号翻转，避免使用乘法器。

本模块输出变成什么：输出 I、Q 两路 signed 2-bit 数据，仍运行在 240 MHz 主时钟域。

波形图怎么看：I/Q 是由输入符号和本振象限共同决定的正负序列。

频谱图怎么看：下变频的目标是把载波附近信息搬到基带附近，便于后续低通和抽取。

答辩一句话：本项目用符号翻转实现正交下变频，把高频 FM 信息搬到基带，减少硬件乘法资源。

## 6. CIC 抽取：高速 1-bit 怎样变成低速多位数据

{fig_md("08_cic_real_module_vcd.png", "CIC 单模块真实仿真波形。该图来自 `sim/cic_3_filter/outputs/cic_3_filter.vcd`，展示 R=5 三阶 CIC 输入、输出和抽取使能。它验证的是 CIC 模块行为，不是完整 FM 回环的中间导出。")}

{fig_md("09_cic_chain_principle.png", "CIC 抽取链路原理示意。该图由真实参考音频派生，用于解释 240 MHz→48 MHz→960 kHz→32 kHz 的低通抽取效果，不作为系统中间验证波形。")}

本模块输入是什么：IQ 下变频后的高速 I/Q 数据，以及微分鉴频后的音频侧数据。

本模块做了什么处理：三阶 CIC 由积分器累加、抽取器降采样、梳状器差分组成。接收前端先按 R=5 从 240 MHz 抽到 48 MHz，再按 R=50 抽到 960 kHz；音频侧按 R=30 抽到 32 kHz。

本模块输出变成什么：输出从高速低位宽序列变成低速多位有符号序列。

波形图怎么看：输入可以快速跳变，经过积分和抽取后，输出更新速度下降且幅度位宽增大。

频谱图怎么看：CIC 同时起低通和降采样作用，高频分量被抑制，基带信息被保留。

答辩一句话：CIC 的作用是低通滤波和降采样，为后级 CORDIC 和音频输出降低数据率。

## 7. CORDIC：怎样从 I/Q 得到相位

{fig_md("10_cordic_discriminator_principle.png", "CORDIC 相位提取与微分鉴频原理示意。该图用于说明 I/Q 平面轨迹、瞬时相位、unwrap 相位和相位差之间的关系，不作为系统中间导出结果。")}

本模块输入是什么：二级 CIC 输出后的 I/Q 基带数据。

本模块做了什么处理：CORDIC 工作在 vectoring 模式，根据 I/Q 求反正切，得到瞬时相位 θ[n]。

本模块输出变成什么：输出为 17 位相位序列 `cordic_phase`。

波形图怎么看：I/Q 平面轨迹反映基带复信号的旋转，相位图反映该旋转角度随时间变化。

频谱图怎么看：CORDIC 本身输出的是相位，不直接等于音频；音频信息藏在相位变化速度里。

答辩一句话：CORDIC 把 I/Q 两路基带信号转换成瞬时相位，为后面按相位差恢复频率做准备。

## 8. 微分鉴频：怎样从相位差恢复音频

{fig_md("11_diff_phase_spectrum_principle.png", "微分鉴频输出频谱原理示意。该图说明 Δθ[n] 的低频成分对应调制音频，但并非系统中间导出的真实 Δθ[n]。")}

本模块输入是什么：CORDIC 输出的瞬时相位 θ[n]。

本模块做了什么处理：`differentiator.sv` 对相邻相位做差，公式为 `Δθ[n] = θ[n] - θ[n-1]`。

本模块输出变成什么：输出相位变化率近似量，也就是瞬时频率变化。

波形图怎么看：如果相位变化快，Δθ[n] 较大；变化慢，Δθ[n] 较小。

频谱图怎么看：Δθ[n] 的音频频带成分就是 FM 中承载的声音信息。

答辩一句话：FM 的信息在频率变化里，而频率就是相位变化率，所以相位差能恢复音频。

## 9. 音频 CIC 与 PCM：怎样得到 16 位音频样本

本模块输入是什么：960 kHz 的微分鉴频输出。

本模块做了什么处理：音频 CIC 以 R=30 把 960 kHz 数据抽取到 32 kHz，并在 `radio_core.sv` 中截取高位得到 16 位 `demodulated`。

本模块输出变成什么：输出 32 kHz、signed 16-bit PCM，可送入 PWM 或 I2S。

波形图怎么看：音频 CIC 输出应回到与参考音频相同的低速幅度序列。

频谱图怎么看：输出频谱主要落在音频带宽内，高频抽取残留应被抑制。

答辩一句话：音频 CIC 完成最后一级低通和降采样，让鉴频结果变成可播放的 16 位 PCM。

## 10. I2S 与 PCM5102：怎样真正输出声音

{fig_md("17_i2s_three_wire_real_vcd.png", "I2S 三线真实模块仿真波形。该图来自 `sim/i2s_tx_3wire/outputs/i2s_tx_3wire.vcd`，展示 PCM 样本、BCK、LRCK 和 DIN 的关系。")}

{fig_md("18_i2s_frame_structure.png", "I2S 左右声道帧结构图。单声道 16 位 PCM 被放入左右两个 32 bit slot，PCM5102 根据 BCK/LRCK/DIN 还原数字音频流。")}

本模块输入是什么：32 kHz、16 位单声道 PCM 样本。

本模块做了什么处理：`i2s_tx_3wire.sv` 用 240 MHz 系统时钟分频产生 BCK=2.048 MHz、LRCK=32 kHz，并把单声道样本复制到左右声道。

本模块输出变成什么：输出三线 I2S：BCK、LRCK 和 DIN，送入 PCM5102。

波形图怎么看：BCK 是位时钟，LRCK 区分左右声道，DIN 在 BCK 节拍下串行输出样本位。

频谱图怎么看：I2S 是数字接口时序，不用频谱评价音频质量；音频质量应看 PCM 对比图。

答辩一句话：I2S 把并行 PCM 样本串行化，PCM5102 再把数字音频转换成模拟声音。

## 11. 系统验证：真实输入输出波形、频谱、语谱图和指标

{fig_md("12_validation_waveform_aligned.png", "输入参考音频与解调输出音频的时域对比。两条曲线均来自真实 dump，且先通过互相关完成对齐。")}

{fig_md("13_validation_spectrum_compare.png", "输入参考音频与解调输出音频的频谱对比。两者使用相同采样率、FFT 点数、Hann 窗和 dB 标尺。")}

{fig_md("14_validation_spectrogram_compare.png", "输入参考音频与解调输出音频的语谱图对比。两者使用相同窗长、重叠率和颜色范围。")}

{fig_md("15_validation_overview.png", "系统验证总览图。该图综合局部波形、频谱、语谱图和核心指标，适合直接拆成答辩 PPT。")}

{fig_md("16_pcm16_output_wave_spectrum.png", "最终 16 位 PCM 输出波形和频谱。该图来自真实 dump 的 `output` 列，用于单独展示接收核心输出 PCM 的数据形态。")}

本模块输入是什么：`source` 列，即 FM 调制器入口参考音频。

本模块做了什么处理：先对 `source` 与 `output` 做互相关对齐，再统一采样率、FFT 窗函数和语谱图参数进行比较。

本模块输出变成什么：输出为对齐后的输入/输出图、频谱图、语谱图和指标表。

波形图怎么看：对齐后蓝色输入与红色输出基本重合，说明恢复波形与参考音频一致性较高。

频谱图怎么看：两条频谱主峰位置和整体包络接近，说明音频频率成分被保留下来。

答辩一句话：验证时没有拿原始 WAV 直接比较，而是比较调制器入口样本和接收核心输出样本。

| 指标 | 数值 |
|---|---:|
| 最佳对齐延迟 | {metrics['best_lag_samples']} 样本，{metrics['best_lag_ms']:.5f} ms |
| 皮尔逊相关系数 | {metrics['pearson_corr']:.6f} |
| 频谱相关系数 | {metrics['spectral_corr']:.6f} |
| 归一化 RMSE | {metrics['nrmse_pct']:.4f}% |
| 等效 SNR | {metrics['snr_like_db']:.4f} dB |
| 输出峰值相对输入增益 | {metrics['peak_gain_db']:.4f} dB |

## 12. 答辩常见问题与回答

**问：为什么不能直接拿原始 WAV 和输出音频对比？**  
答：原始 WAV 在进入 FPGA 前可能经过裁剪、量化、ROM 化和起始地址选择。本文比较的是 FM 调制器入口真实 `source` 样本和接收核心真实 `output` 样本，因此验证对象更准确。

**问：为什么 1-bit 方波还能表示 FM？**  
答：1-bit 只表示瞬时逻辑电平，但翻转时间由相位累加器控制。音频改变相位步进，等价于改变瞬时频率，所以翻转密度中仍包含 FM 信息。

**问：CIC 为什么既是滤波器又是抽取器？**  
答：CIC 的积分器先累加输入，抽取器降低采样率，梳状器再做差分。它不需要乘法器，适合 FPGA 中高速、整数倍抽取场景。

**问：CORDIC 输出的相位为什么还要微分？**  
答：FM 的信息不是绝对相位，而是频率变化；频率等于相位变化率，所以要对相邻相位作差。

**问：哪些图是真实验证，哪些图是示意？**  
答：`source/output` 对比图是真实系统验证；I2S 和 CIC 单模块图来自真实模块仿真 VCD；FM step/phase、IQ、CORDIC/鉴频中缺少完整中间导出，因此标为 RTL 重构或原理示意。

**问：如果后续要把所有中间级都变成真实验证图，应补充什么？**  
答：需要在 ROM 回环 testbench 中额外导出 `fm_1bit.txt`、`i_mixer.txt`、`q_mixer.txt`、`i_cic1.txt`、`q_cic1.txt`、`i_cic2.txt`、`q_cic2.txt`、`cordic_phase.txt`、`diff_phase.txt` 和 `audio_cic_out.txt`，再用同一套绘图脚本生成各级真实波形和频谱。
"""
    target.write_text(md, encoding="utf-8")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    reference, output = load_dump(DUMP_PATH)
    lag, aligned_ref, aligned_out = best_alignment(reference, output)
    metrics = compute_metrics(aligned_ref, aligned_out, lag, captured_samples=reference.size)

    save_system_flow(figure_path("01_system_flow.png"))
    save_reference_audio_figures(reference)
    save_fm_reconstruction_figures(reference)
    save_iq_principle_figures()
    save_cic_vcd_figure()
    save_cic_chain_principle(reference)
    save_cordic_discriminator_principle(reference)
    save_validation_figures(aligned_ref, aligned_out, metrics)
    save_i2s_vcd_figure()
    write_csv_outputs(aligned_ref, aligned_out, metrics)
    write_ppt_outline()
    write_document(metrics)

    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    print(f"wrote {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
