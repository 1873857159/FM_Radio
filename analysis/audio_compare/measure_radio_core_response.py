#!/usr/bin/env python3
"""Sweep the radio_core audio response with a single-tone FM stimulus."""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from audio_compare_lib import best_alignment, load_dump

plt.rcParams["font.family"] = ["AR PL UMing CN", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

DEFAULT_FREQUENCIES = [500, 1_000, 3_000, 6_000, 8_000, 10_000, 12_000, 14_000]


def fit_tone(samples: np.ndarray, tone_hz: float, sample_rate: float) -> dict[str, float]:
    n = np.arange(samples.size, dtype=np.float64)
    omega = 2.0 * math.pi * tone_hz / sample_rate
    basis = np.column_stack(
        [
            np.sin(omega * n),
            np.cos(omega * n),
            np.ones_like(n),
        ]
    )
    coeff, _, _, _ = np.linalg.lstsq(basis, samples, rcond=None)
    sin_coeff = float(coeff[0])
    cos_coeff = float(coeff[1])
    dc = float(coeff[2])
    fitted = basis @ coeff
    amplitude = float(math.hypot(sin_coeff, cos_coeff))
    phase_deg = float(math.degrees(math.atan2(cos_coeff, sin_coeff)))
    residual_rms = float(np.sqrt(np.mean((samples - fitted) ** 2)))
    return {
        "amplitude": amplitude,
        "phase_deg": phase_deg,
        "dc": dc,
        "residual_rms": residual_rms,
    }


def wrap_phase_deg(value: float) -> float:
    wrapped = (value + 180.0) % 360.0 - 180.0
    if wrapped == -180.0:
        return 180.0
    return wrapped


def run_single_tone(
    repo_root: Path,
    sim_script: Path,
    tone_hz: int,
    settle_samples: int,
    capture_samples: int,
    reference_peak: int,
    sample_rate: float,
    max_lag: int,
    output_dir: Path,
) -> dict[str, float | int | str]:
    cmd = [
        str(sim_script),
        "radio_core_audio_dump",
        "--tone-hz",
        str(tone_hz),
        "--settle-samples",
        str(settle_samples),
        "--capture-samples",
        str(capture_samples),
        "--reference-peak",
        str(reference_peak),
    ]
    subprocess.run(cmd, cwd=repo_root, check=True)

    dump_path = repo_root / "sim" / "radio_core_audio" / "outputs" / "radio_core_audio_dump_samples.txt"
    archived_dump = output_dir / f"radio_core_audio_dump_{tone_hz:05d}hz.txt"
    shutil.copy2(dump_path, archived_dump)

    reference, output = load_dump(archived_dump)
    lag_samples, _, _ = best_alignment(reference, output, max_lag)

    ref_fit = fit_tone(reference.astype(np.float64), tone_hz, sample_rate)
    out_fit = fit_tone(output.astype(np.float64), tone_hz, sample_rate)

    gain_db = float(
        20.0 * math.log10(max(out_fit["amplitude"], 1e-12) / max(ref_fit["amplitude"], 1e-12))
    )
    phase_diff_deg = float(wrap_phase_deg(out_fit["phase_deg"] - ref_fit["phase_deg"]))

    return {
        "tone_hz": int(tone_hz),
        "dump": str(archived_dump.relative_to(repo_root)),
        "captured_samples": int(reference.size),
        "best_lag_samples": int(lag_samples),
        "reference_peak_setting": int(reference_peak),
        "reference_amplitude": ref_fit["amplitude"],
        "output_amplitude": out_fit["amplitude"],
        "gain_db": gain_db,
        "phase_diff_deg": phase_diff_deg,
        "reference_dc": ref_fit["dc"],
        "output_dc": out_fit["dc"],
        "reference_residual_rms": ref_fit["residual_rms"],
        "output_residual_rms": out_fit["residual_rms"],
    }


def save_response_plot(path: Path, rows: list[dict[str, float | int | str]], baseline_hz: int) -> None:
    freq = np.asarray([int(row["tone_hz"]) for row in rows], dtype=np.float64)
    norm_gain_db = np.asarray([float(row["normalized_gain_db"]) for row in rows], dtype=np.float64)
    lag = np.asarray([int(row["best_lag_samples"]) for row in rows], dtype=np.float64)

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True, constrained_layout=True)

    axes[0].plot(freq / 1e3, norm_gain_db, marker="o", linewidth=1.4, color="#d62728")
    axes[0].axhline(0.0, color="#444444", linewidth=0.8, linestyle="--")
    axes[0].axvline(6.0, color="#1f77b4", linewidth=0.8, linestyle=":")
    axes[0].set_ylabel(f"相对 {baseline_hz/1e3:g} kHz 增益 / dB")
    axes[0].set_title("radio_core 音频频响扫频结果")
    axes[0].grid(True, alpha=0.25)

    axes[1].plot(freq / 1e3, lag, marker="o", linewidth=1.2, color="#1f77b4")
    axes[1].axvline(6.0, color="#1f77b4", linewidth=0.8, linestyle=":")
    axes[1].set_xlabel("频率 / kHz")
    axes[1].set_ylabel("最佳整数滞后 / samples")
    axes[1].grid(True, alpha=0.25)

    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_summary_markdown(path: Path, rows: list[dict[str, float | int | str]], baseline_hz: int) -> None:
    lines = [
        "# radio_core 频响扫频摘要",
        "",
        f"- 基准频点: `{baseline_hz} Hz`",
        f"- 扫频点数: `{len(rows)}`",
        "",
        "| 频率 (Hz) | 相对增益 (dB) | 绝对增益 (dB) | 最佳滞后 (samples) |",
        "| ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {int(row['tone_hz'])} | {float(row['normalized_gain_db']):+.3f} | "
            f"{float(row['gain_db']):+.3f} | {int(row['best_lag_samples'])} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2], help="仓库根目录")
    parser.add_argument(
        "--sim-script",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "sim" / "run_modelsim.sh",
        help="ModelSim 入口脚本",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "outputs" / "radio_core_response",
        help="输出目录",
    )
    parser.add_argument("--sample-rate", type=float, default=32_000.0, help="音频样本率")
    parser.add_argument("--settle-samples", type=int, default=128, help="丢弃的稳定化样本数")
    parser.add_argument("--capture-samples", type=int, default=256, help="每个频点的导出样本数")
    parser.add_argument("--reference-peak", type=int, default=8192, help="扫频激励正弦峰值")
    parser.add_argument("--max-lag", type=int, default=64, help="相关性滞后搜索窗口")
    parser.add_argument("--baseline-hz", type=int, default=1_000, help="归一化增益基准频点")
    parser.add_argument("--frequencies", type=int, nargs="+", default=DEFAULT_FREQUENCIES, help="扫频频点列表")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    sim_script = args.sim_script.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, float | int | str]] = []
    for tone_hz in args.frequencies:
        print(f"[measure] tone={tone_hz} Hz")
        row = run_single_tone(
            repo_root=repo_root,
            sim_script=sim_script,
            tone_hz=tone_hz,
            settle_samples=args.settle_samples,
            capture_samples=args.capture_samples,
            reference_peak=args.reference_peak,
            sample_rate=args.sample_rate,
            max_lag=args.max_lag,
            output_dir=output_dir,
        )
        rows.append(row)

    baseline_row = next((row for row in rows if int(row["tone_hz"]) == args.baseline_hz), rows[0])
    baseline_gain = float(baseline_row["gain_db"])
    for row in rows:
        row["normalized_gain_db"] = float(row["gain_db"]) - baseline_gain

    response = {
        "sample_rate": float(args.sample_rate),
        "settle_samples": int(args.settle_samples),
        "capture_samples": int(args.capture_samples),
        "reference_peak": int(args.reference_peak),
        "baseline_hz": int(baseline_row["tone_hz"]),
        "points": rows,
    }

    (output_dir / "response.json").write_text(json.dumps(response, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (output_dir / "response.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    save_response_plot(output_dir / "response_plot.png", rows, int(baseline_row["tone_hz"]))
    save_summary_markdown(output_dir / "summary.md", rows, int(baseline_row["tone_hz"]))

    print(json.dumps(response, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
