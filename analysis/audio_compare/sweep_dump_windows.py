#!/usr/bin/env python3
"""Run multiple FM loopback dump windows and summarize metrics."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path

from audio_compare_lib import best_alignment, compute_metrics, load_dump


def analyze_dump(dump_path: Path, sample_rate: float, max_lag: int) -> dict[str, float | int | str]:
    reference, output = load_dump(dump_path)
    lag, aligned_ref, aligned_out = best_alignment(reference, output, max_lag)
    return compute_metrics(
        aligned_ref,
        aligned_out,
        sample_rate,
        lag,
        dump_path,
        captured_samples=reference.size,
    )


def summarize_windows(metrics_list: list[dict[str, float | int | str]]) -> dict[str, object]:
    if not metrics_list:
        raise ValueError("metrics_list is empty")

    def metric_values(key: str) -> list[float]:
        return [float(item[key]) for item in metrics_list]

    def finite_metric_values(key: str) -> list[float]:
        return [value for value in metric_values(key) if math.isfinite(value)]

    def mean_value(values: list[float]) -> float | None:
        if not values:
            return None
        return sum(values) / len(values)

    degenerate_windows = [
        int(item["start_addr"])
        for item in metrics_list
        if (not math.isfinite(float(item["pearson_corr"])))
        or float(item["source_peak"]) == 0.0
        or float(item["reference_rms"]) == 0.0
    ]

    pearson_values = finite_metric_values("pearson_corr")
    spectral_values = finite_metric_values("spectral_corr")
    nrmse_values = finite_metric_values("nrmse_pct")
    peak_gain_values = finite_metric_values("peak_gain_db")
    snr_values = finite_metric_values("snr_like_db")

    return {
        "window_count": len(metrics_list),
        "degenerate_window_count": len(degenerate_windows),
        "degenerate_start_addrs": degenerate_windows,
        "valid_corr_window_count": len(pearson_values),
        "mean_pearson_corr": mean_value(pearson_values),
        "min_pearson_corr": min(pearson_values) if pearson_values else None,
        "mean_spectral_corr": mean_value(spectral_values),
        "min_spectral_corr": min(spectral_values) if spectral_values else None,
        "mean_nrmse_pct": mean_value(nrmse_values),
        "max_nrmse_pct": max(nrmse_values) if nrmse_values else None,
        "mean_peak_gain_db": mean_value(peak_gain_values),
        "max_abs_peak_gain_db": max(abs(value) for value in peak_gain_values) if peak_gain_values else None,
        "mean_snr_like_db": mean_value(snr_values),
        "min_snr_like_db": min(snr_values) if snr_values else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-addrs",
        type=int,
        nargs="+",
        default=[0, 4096, 8192, 12288, 16384, 20480],
        help="要扫的 ROM 起始地址列表",
    )
    parser.add_argument("--warmup-samples", type=int, default=320, help="每个窗口的 warm-up 样本数")
    parser.add_argument("--capture-samples", type=int, default=1024, help="每个窗口的采样长度")
    parser.add_argument("--sample-rate", type=float, default=32000.0, help="分析样本率")
    parser.add_argument("--max-lag", type=int, default=64, help="对齐搜索最大滞后")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "outputs" / "window_sweep",
        help="汇总输出目录",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    dump_output = repo_root / "sim" / "fm_loopback_audio_rom" / "outputs" / "fm_loopback_audio_rom_dump_samples.txt"
    output_dir = args.output_dir
    dumps_dir = output_dir / "dumps"
    dumps_dir.mkdir(parents=True, exist_ok=True)

    window_metrics: list[dict[str, float | int | str]] = []

    for start_addr in args.start_addrs:
        cmd = [
            "./sim/run_modelsim.sh",
            "fm_loopback_audio_rom_dump",
            "--start-addr",
            str(start_addr),
            "--warmup-samples",
            str(args.warmup_samples),
            "--capture-samples",
            str(args.capture_samples),
        ]
        subprocess.run(cmd, cwd=repo_root, check=True)

        window_dump = dumps_dir / f"dump_start_{start_addr}.txt"
        shutil.copyfile(dump_output, window_dump)
        metrics = analyze_dump(window_dump, args.sample_rate, args.max_lag)
        metrics["start_addr"] = start_addr
        window_metrics.append(metrics)

    summary = summarize_windows(window_metrics)

    (output_dir / "summary.json").write_text(
        json.dumps({"summary": summary, "windows": window_metrics}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    report_lines = [
        "# 主线多窗口分析摘要",
        "",
        f"- 扫描窗口数：`{summary['window_count']}`",
        f"- 可用于相关性统计的窗口数：`{summary['valid_corr_window_count']}`",
        f"- 退化/静音窗口数：`{summary['degenerate_window_count']}`",
        "",
        "## 分窗口结果",
        "",
    ]

    if summary["degenerate_start_addrs"]:
        report_lines.extend(
            [
                "## 退化窗口说明",
                "",
                f"- 下列窗口因静音或近静音导致相关性不具代表性：`{summary['degenerate_start_addrs']}`",
                "",
            ]
        )

    metric_lines = []
    if summary["mean_pearson_corr"] is not None:
        metric_lines.extend(
            [
                f"- 平均皮尔逊相关：`{float(summary['mean_pearson_corr']):.6f}`",
                f"- 最低皮尔逊相关：`{float(summary['min_pearson_corr']):.6f}`",
                f"- 平均频谱相关：`{float(summary['mean_spectral_corr']):.6f}`",
                f"- 最低频谱相关：`{float(summary['min_spectral_corr']):.6f}`",
                f"- 平均归一化 RMSE：`{float(summary['mean_nrmse_pct']):.3f}%`",
                f"- 最差归一化 RMSE：`{float(summary['max_nrmse_pct']):.3f}%`",
                f"- 平均峰值增益偏差：`{float(summary['mean_peak_gain_db']):.3f} dB`",
                f"- 最大峰值增益偏差：`{float(summary['max_abs_peak_gain_db']):.3f} dB`",
                f"- 平均等效 SNR：`{float(summary['mean_snr_like_db']):.3f} dB`",
                f"- 最低等效 SNR：`{float(summary['min_snr_like_db']):.3f} dB`",
                "",
            ]
        )
    report_lines[5:5] = metric_lines

    for metrics in window_metrics:
        pearson_text = "nan" if not math.isfinite(float(metrics["pearson_corr"])) else f"{float(metrics['pearson_corr']):.6f}"
        spectral_text = "nan" if not math.isfinite(float(metrics["spectral_corr"])) else f"{float(metrics['spectral_corr']):.6f}"
        report_lines.extend(
            [
                (
                    f"- start_addr=`{int(metrics['start_addr'])}`: "
                    f"pearson=`{pearson_text}`, "
                    f"spectral=`{spectral_text}`, "
                    f"nrmse=`{float(metrics['nrmse_pct']):.3f}%`, "
                    f"peak_gain=`{float(metrics['peak_gain_db']):.3f} dB`, "
                    f"snr_like=`{float(metrics['snr_like_db']):.3f} dB`"
                )
            ]
        )

    (output_dir / "summary.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "output_dir": str(output_dir)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
