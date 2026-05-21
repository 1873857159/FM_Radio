#!/usr/bin/env python3
"""Shared helpers for FM audio comparison and defense material generation."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal
from scipy.io import wavfile

plt.rcParams["font.family"] = ["AR PL UMing CN", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def load_dump(path: Path) -> tuple[np.ndarray, np.ndarray]:
    rows: list[tuple[int, int, int]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 3:
            continue
        try:
            rows.append((int(parts[0]), int(parts[1]), int(parts[2])))
        except ValueError:
            continue

    if not rows:
        raise ValueError(f"no samples found in {path}")

    clean_rows: list[tuple[int, int, int]] = []
    expected_index = 0
    for row in rows:
        if row[0] != expected_index:
            break
        clean_rows.append(row)
        expected_index += 1

    if not clean_rows:
        raise ValueError(f"no monotonic sample window found in {path}")

    reference = np.asarray([row[1] for row in clean_rows], dtype=np.float64)
    output = np.asarray([row[2] for row in clean_rows], dtype=np.float64)
    return reference, output


def best_alignment(reference: np.ndarray, target: np.ndarray, max_lag: int) -> tuple[int, np.ndarray, np.ndarray]:
    ref = reference - np.mean(reference)
    tgt = target - np.mean(target)
    corr = signal.correlate(tgt, ref, mode="full")
    lags = signal.correlation_lags(tgt.size, ref.size, mode="full")

    valid = np.abs(lags) <= max_lag
    best_idx = np.argmax(np.abs(corr[valid]))
    best_lag = int(lags[valid][best_idx])

    if best_lag >= 0:
        aligned_ref = reference[: reference.size - best_lag]
        aligned_tgt = target[best_lag:]
    else:
        lag = -best_lag
        aligned_ref = reference[lag:]
        aligned_tgt = target[: target.size - lag]

    length = min(aligned_ref.size, aligned_tgt.size)
    return best_lag, aligned_ref[:length], aligned_tgt[:length]


def parse_clip_report(path: Path) -> dict[str, str]:
    report: dict[str, str] = {}
    if not path.exists():
        return report
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        report[key.strip()] = value.strip()
    return report


def compute_metrics(
    reference: np.ndarray,
    output: np.ndarray,
    sample_rate: float,
    lag_samples: int,
    dump_path: Path | None = None,
    captured_samples: int | None = None,
) -> dict[str, float | int | str]:
    ref_zero = reference - np.mean(reference)
    out_zero = output - np.mean(output)
    error = output - reference

    rmse = float(np.sqrt(np.mean(error**2)))
    ref_rms = float(np.sqrt(np.mean(ref_zero**2)))
    out_rms = float(np.sqrt(np.mean(out_zero**2)))
    err_rms = float(np.sqrt(np.mean((out_zero - ref_zero) ** 2)))
    source_peak = float(np.max(np.abs(reference)))
    output_peak = float(np.max(np.abs(output)))

    pearson = float(np.corrcoef(ref_zero, out_zero)[0, 1]) if reference.size > 1 else 0.0
    nrmse_pct = float(rmse / source_peak * 100.0) if source_peak > 0.0 else 0.0
    snr_like_db = float(20.0 * math.log10(ref_rms / max(err_rms, 1e-9))) if ref_rms > 0.0 else 0.0
    peak_gain_db = float(20.0 * math.log10(max(output_peak, 1e-9) / max(source_peak, 1e-9)))

    window = np.hanning(reference.size)
    ref_fft = np.abs(np.fft.rfft(ref_zero * window))
    out_fft = np.abs(np.fft.rfft(out_zero * window))
    spectral_corr = float(np.corrcoef(ref_fft, out_fft)[0, 1]) if ref_fft.size > 1 else 0.0

    return {
        "dump": str(dump_path) if dump_path is not None else "",
        "sample_rate": float(sample_rate),
        "best_lag_samples": int(lag_samples),
        "best_lag_ms": float(lag_samples / sample_rate * 1e3),
        "captured_samples": int(reference.size if captured_samples is None else captured_samples),
        "aligned_samples": int(reference.size),
        "pearson_corr": pearson,
        "spectral_corr": spectral_corr,
        "rmse": rmse,
        "nrmse_pct": nrmse_pct,
        "source_peak": source_peak,
        "output_peak": output_peak,
        "peak_gain_db": peak_gain_db,
        "reference_rms": ref_rms,
        "output_rms": out_rms,
        "error_rms": err_rms,
        "snr_like_db": snr_like_db,
    }


def _spectrogram_db(samples: np.ndarray, sample_rate: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    nperseg = min(256, samples.size)
    noverlap = max(0, nperseg // 2)
    freq, time_axis, spec = signal.spectrogram(
        samples,
        fs=sample_rate,
        window="hann",
        nperseg=nperseg,
        noverlap=noverlap,
        detrend=False,
        scaling="spectrum",
        mode="magnitude",
    )
    spec_db = 20 * np.log10(np.maximum(spec, 1e-6))
    return freq, time_axis, spec_db


def save_waveform(path: Path, sample_rate: float, reference: np.ndarray, output: np.ndarray) -> None:
    duration = reference.size / sample_rate
    time_axis = np.linspace(0.0, duration, reference.size, endpoint=False) * 1e3

    fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    axes[0].plot(time_axis, reference, color="#1f77b4", linewidth=1.0)
    axes[0].set_title("输入参考音频波形")
    axes[0].set_ylabel("幅度")
    axes[0].grid(True, alpha=0.25)

    axes[1].plot(time_axis, output, color="#d62728", linewidth=1.0)
    axes[1].set_title("解调输出音频波形")
    axes[1].set_ylabel("幅度")
    axes[1].set_xlabel("时间 / ms")
    axes[1].grid(True, alpha=0.25)

    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_spectrum(path: Path, sample_rate: float, reference: np.ndarray, output: np.ndarray) -> None:
    window = np.hanning(reference.size)
    ref_fft = np.fft.rfft(reference * window)
    out_fft = np.fft.rfft(output * window)
    freq = np.fft.rfftfreq(reference.size, d=1.0 / sample_rate)

    ref_mag = 20 * np.log10(np.maximum(np.abs(ref_fft), 1e-6))
    out_mag = 20 * np.log10(np.maximum(np.abs(out_fft), 1e-6))
    y_min = float(min(ref_mag.min(), out_mag.min()))
    y_max = float(max(ref_mag.max(), out_mag.max()))

    fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True, sharey=True)
    axes[0].plot(freq / 1e3, ref_mag, linewidth=1.0, color="#1f77b4")
    axes[0].set_title("输入参考音频频谱")
    axes[0].set_ylabel("幅度 / dB")
    axes[0].set_ylim(y_min - 3.0, y_max + 3.0)
    axes[0].grid(True, alpha=0.25)

    axes[1].plot(freq / 1e3, out_mag, linewidth=1.0, color="#d62728")
    axes[1].set_title("解调输出音频频谱")
    axes[1].set_xlim(0.0, sample_rate / 2e3)
    axes[1].set_xlabel("频率 / kHz")
    axes[1].set_ylabel("幅度 / dB")
    axes[1].grid(True, alpha=0.25)

    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_spectrogram(path: Path, sample_rate: float, reference: np.ndarray, output: np.ndarray) -> None:
    ref_freq, ref_time, ref_db = _spectrogram_db(reference, sample_rate)
    out_freq, out_time, out_db = _spectrogram_db(output, sample_rate)
    color_min = float(min(ref_db.min(), out_db.min()))
    color_max = float(max(ref_db.max(), out_db.max()))

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True, sharey=True, constrained_layout=True)
    image = axes[0].pcolormesh(
        ref_time * 1e3,
        ref_freq / 1e3,
        ref_db,
        shading="auto",
        cmap="viridis",
        vmin=color_min,
        vmax=color_max,
    )
    axes[0].set_title("输入参考语谱图")
    axes[0].set_ylabel("频率 / kHz")

    axes[1].pcolormesh(
        out_time * 1e3,
        out_freq / 1e3,
        out_db,
        shading="auto",
        cmap="viridis",
        vmin=color_min,
        vmax=color_max,
    )
    axes[1].set_title("解调输出语谱图")
    axes[1].set_ylabel("频率 / kHz")
    axes[1].set_xlabel("时间 / ms")

    fig.colorbar(image, ax=axes, pad=0.01, label="幅度 / dB")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_single_audio_overview(path: Path, sample_rate: float, samples: np.ndarray, title: str, color: str) -> None:
    zero_mean = samples - np.mean(samples)
    duration = samples.size / sample_rate
    time_axis = np.linspace(0.0, duration, samples.size, endpoint=False) * 1e3

    window = np.hanning(samples.size)
    freq = np.fft.rfftfreq(samples.size, d=1.0 / sample_rate)
    mag_db = 20 * np.log10(np.maximum(np.abs(np.fft.rfft(zero_mean * window)), 1e-6))
    spec_freq, spec_time, spec_db = _spectrogram_db(zero_mean, sample_rate)

    fig = plt.figure(figsize=(11, 8), constrained_layout=True)
    grid = fig.add_gridspec(3, 1, height_ratios=[1.0, 0.9, 1.25])
    fig.suptitle(title, fontsize=15)

    ax_wave = fig.add_subplot(grid[0, 0])
    ax_wave.plot(time_axis, samples, color=color, linewidth=0.9)
    ax_wave.set_title("时域波形")
    ax_wave.set_ylabel("幅度")
    ax_wave.grid(True, alpha=0.25)

    ax_spec = fig.add_subplot(grid[1, 0])
    ax_spec.plot(freq / 1e3, mag_db, color=color, linewidth=0.9)
    ax_spec.set_xlim(0.0, sample_rate / 2e3)
    ax_spec.set_title("频谱")
    ax_spec.set_xlabel("频率 / kHz")
    ax_spec.set_ylabel("幅度 / dB")
    ax_spec.grid(True, alpha=0.25)

    ax_sgram = fig.add_subplot(grid[2, 0])
    image = ax_sgram.pcolormesh(
        spec_time * 1e3,
        spec_freq / 1e3,
        spec_db,
        shading="auto",
        cmap="viridis",
    )
    ax_sgram.set_title("语谱图")
    ax_sgram.set_xlabel("时间 / ms")
    ax_sgram.set_ylabel("频率 / kHz")
    fig.colorbar(image, ax=ax_sgram, pad=0.01, label="幅度 / dB")

    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_overview(path: Path, sample_rate: float, reference: np.ndarray, output: np.ndarray, metrics: dict[str, float | int | str]) -> None:
    ref_zero = reference - np.mean(reference)
    out_zero = output - np.mean(output)
    peak_index = int(np.argmax(np.abs(ref_zero))) if ref_zero.size else 0
    half_window = max(1, int(round(sample_rate * 0.02)))
    start = max(0, peak_index - half_window)
    stop = min(reference.size, peak_index + half_window)
    time_axis = np.arange(start, stop) / sample_rate * 1e3

    ref_freq, ref_time, ref_db = _spectrogram_db(ref_zero, sample_rate)
    out_freq, out_time, out_db = _spectrogram_db(out_zero, sample_rate)
    color_min = float(min(ref_db.min(), out_db.min()))
    color_max = float(max(ref_db.max(), out_db.max()))

    fig = plt.figure(figsize=(12, 8), constrained_layout=True)
    grid = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.3])

    ax_wave = fig.add_subplot(grid[0, 0])
    ax_wave.plot(time_axis, ref_zero[start:stop], label="输入参考", color="#1f77b4", linewidth=1.0)
    ax_wave.plot(time_axis, out_zero[start:stop], label="解调输出", color="#d62728", linewidth=1.0, alpha=0.85)
    ax_wave.set_title("局部波形叠加对比")
    ax_wave.set_xlabel("时间 / ms")
    ax_wave.set_ylabel("幅度")
    ax_wave.grid(True, alpha=0.25)
    ax_wave.legend(loc="upper right")

    ax_spec = fig.add_subplot(grid[0, 1])
    freq = np.fft.rfftfreq(ref_zero.size, d=1.0 / sample_rate)
    window = np.hanning(ref_zero.size)
    ref_mag = 20 * np.log10(np.maximum(np.abs(np.fft.rfft(ref_zero * window)), 1e-6))
    out_mag = 20 * np.log10(np.maximum(np.abs(np.fft.rfft(out_zero * window)), 1e-6))
    ax_spec.plot(freq / 1e3, ref_mag, label="输入参考", color="#1f77b4", linewidth=1.0)
    ax_spec.plot(freq / 1e3, out_mag, label="解调输出", color="#d62728", linewidth=1.0, alpha=0.85)
    ax_spec.set_title("频谱对比")
    ax_spec.set_xlabel("频率 / kHz")
    ax_spec.set_ylabel("幅度 / dB")
    ax_spec.set_xlim(0.0, sample_rate / 2e3)
    ax_spec.grid(True, alpha=0.25)
    ax_spec.legend(loc="upper right")

    ax_ref = fig.add_subplot(grid[1, 0])
    image = ax_ref.pcolormesh(
        ref_time * 1e3,
        ref_freq / 1e3,
        ref_db,
        shading="auto",
        cmap="viridis",
        vmin=color_min,
        vmax=color_max,
    )
    ax_ref.set_title("输入参考语谱图")
    ax_ref.set_xlabel("时间 / ms")
    ax_ref.set_ylabel("频率 / kHz")

    ax_out = fig.add_subplot(grid[1, 1])
    ax_out.pcolormesh(
        out_time * 1e3,
        out_freq / 1e3,
        out_db,
        shading="auto",
        cmap="viridis",
        vmin=color_min,
        vmax=color_max,
    )
    ax_out.set_title("解调输出语谱图")
    ax_out.set_xlabel("时间 / ms")
    ax_out.set_ylabel("频率 / kHz")

    fig.colorbar(image, ax=[ax_ref, ax_out], pad=0.02, label="幅度 / dB")

    summary_lines = [
        f"相关系数: {float(metrics['pearson_corr']):.4f}",
        f"频谱相关: {float(metrics['spectral_corr']):.4f}",
        f"归一化 RMSE: {float(metrics['nrmse_pct']):.2f}%",
        f"等效 SNR: {float(metrics['snr_like_db']):.2f} dB",
        f"对齐延迟: {float(metrics['best_lag_ms']):.3f} ms",
    ]
    fig.text(0.015, 0.02, "  |  ".join(summary_lines), fontsize=11)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_aligned_csv(path: Path, sample_rate: float, reference: np.ndarray, output: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["index", "time_ms", "reference", "output", "error"])
        for index, (ref_value, out_value) in enumerate(zip(reference, output)):
            writer.writerow(
                [
                    index,
                    f"{index / sample_rate * 1e3:.6f}",
                    int(round(ref_value)),
                    int(round(out_value)),
                    int(round(out_value - ref_value)),
                ]
            )


def save_metrics_csv(path: Path, metrics: dict[str, float | int | str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["metric", "value"])
        for key, value in metrics.items():
            writer.writerow([key, value])


def save_audio_wav(path: Path, sample_rate: float, samples: np.ndarray, peak_reference: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    scale = 32767.0 / max(peak_reference, 1.0)
    clipped = np.clip(np.round(samples * scale), -32768, 32767).astype(np.int16)
    wavfile.write(path, int(round(sample_rate)), clipped)
