#!/usr/bin/env python3
"""Build a defense-friendly comparison package from simulation dump data."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from audio_compare_lib import (
    best_alignment,
    compute_metrics,
    load_dump,
    parse_clip_report,
    save_aligned_csv,
    save_audio_wav,
    save_metrics_csv,
    save_overview,
    save_spectrogram,
    save_spectrum,
    save_waveform,
)


def write_summary(
    path: Path,
    metrics: dict[str, float | int | str],
    clip_report: dict[str, str],
    figures_dir: Path,
    audio_dir: Path,
    tables_dir: Path,
) -> None:
    lines = [
        "# FM 语音回环对比摘要",
        "",
        "## 结论",
        "",
        (
            f"- 当前参考音频与解调输出的皮尔逊相关系数为 `{float(metrics['pearson_corr']):.4f}`，"
            f"频谱相关系数为 `{float(metrics['spectral_corr']):.4f}`。"
        ),
        (
            f"- 最佳对齐延迟为 `{int(metrics['best_lag_samples'])}` 个样本，"
            f"约 `{float(metrics['best_lag_ms']):.3f} ms`。"
        ),
        (
            f"- 归一化均方根误差为 `{float(metrics['nrmse_pct']):.2f}%`，"
            f"等效信噪比约 `{float(metrics['snr_like_db']):.2f} dB`。"
        ),
        "",
        "## 对比基准说明",
        "",
        "- 原始 WAV 先经过静音裁剪、8-bit 量化写入 ROM 和 16 kHz 到 32 kHz 的重复输出展开。",
        "- 因此真正用于评价 FM 链路恢复质量的参考信号是 `audio_in_dbg`，而不是未经处理的原始 WAV。",
        "- `audio_out_dbg` 则表示 `radio_core` 解调后的音频样本流。",
        "",
        "## 原始音频预处理信息",
        "",
        f"- 原始文件：`{clip_report.get('input', 'unknown')}`",
        f"- 原始采样率：`{clip_report.get('sample_rate', 'unknown')} Hz`",
        f"- 原始样本数：`{clip_report.get('original_samples', 'unknown')}`",
        f"- 裁剪区间：`{clip_report.get('trim_start', 'unknown')} ~ {clip_report.get('trim_end', 'unknown')}`",
        f"- 保留样本数：`{clip_report.get('trimmed_samples', 'unknown')}`",
        f"- 保留时长：`{clip_report.get('duration_s', 'unknown')} s`",
        "",
        "## 核心指标",
        "",
        f"- 样本率：`{float(metrics['sample_rate']):.0f} Hz`",
        f"- 参与对齐样本数：`{int(metrics['aligned_samples'])}`",
        f"- 输入峰值：`{float(metrics['source_peak']):.1f}`",
        f"- 输出峰值：`{float(metrics['output_peak']):.1f}`",
        f"- 输出峰值相对输入：`{float(metrics['peak_gain_db']):.2f} dB`",
        f"- RMSE：`{float(metrics['rmse']):.2f}`",
        "",
        "## 图表与音频产物",
        "",
        f"- 总览图：`{figures_dir / 'overview_compare.png'}`",
        f"- 波形图：`{figures_dir / 'waveform_compare.png'}`",
        f"- 频谱图：`{figures_dir / 'spectrum_compare.png'}`",
        f"- 语谱图：`{figures_dir / 'spectrogram_compare.png'}`",
        f"- 对齐样本表：`{tables_dir / 'aligned_samples.csv'}`",
        f"- 指标表：`{tables_dir / 'metrics.csv'}`",
        f"- 参考音频试听：`{audio_dir / 'reference_aligned.wav'}`",
        f"- 解调音频试听：`{audio_dir / 'output_aligned.wav'}`",
        "",
        "## 答辩时建议讲法",
        "",
        "- 先说明比较对象不是直接拿原始 WAV 生硬对比，而是拿真正送入 FM 调制器的参考音频对比。",
        "- 再指出波形、频谱和语谱图三者都保持了主要结构一致性，说明 FM 解调链路恢复有效。",
        "- 最后用相关系数、延迟和等效信噪比给出量化结论，避免只停留在主观听感。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_talking_points(path: Path, metrics: dict[str, float | int | str]) -> None:
    lines = [
        "# 答辩讲解提纲",
        "",
        "1. 这组图比较的是 `audio_in_dbg` 和 `audio_out_dbg`，专门评价 FM 调制解调链路本身，而不是评价外部录音环境。",
        (
            f"2. 输入输出先做互相关对齐，当前最佳延迟是 `{int(metrics['best_lag_samples'])}` 个样本，"
            f"约 `{float(metrics['best_lag_ms']):.3f} ms`。"
        ),
        (
            f"3. 对齐后皮尔逊相关系数达到 `{float(metrics['pearson_corr']):.4f}`，"
            f"频谱相关系数达到 `{float(metrics['spectral_corr']):.4f}`。"
        ),
        (
            f"4. 归一化 RMSE 为 `{float(metrics['nrmse_pct']):.2f}%`，"
            f"等效信噪比约 `{float(metrics['snr_like_db']):.2f} dB`，"
            "说明主要语音信息已经被恢复。"
        ),
        "5. 后续上板时，只需把 PCM5102 实际输出再录回电脑，就能沿用同一套对比流程做硬件结果验证。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", type=Path, required=True, help="仿真导出的样本文件")
    parser.add_argument("--output-dir", type=Path, required=True, help="答辩材料输出目录")
    parser.add_argument(
        "--clip-report",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "rtl" / "audio_clip_report.txt",
        help="原始音频预处理报告",
    )
    parser.add_argument("--sample-rate", type=float, default=32000.0, help="样本率，默认 32 kHz")
    parser.add_argument("--max-lag", type=int, default=64, help="互相关对齐最大滞后样本数")
    parser.add_argument("--original-wav", type=Path, help="可选：复制原始 WAV 到答辩包")
    args = parser.parse_args()

    output_dir = args.output_dir
    figures_dir = output_dir / "figures"
    audio_dir = output_dir / "audio"
    tables_dir = output_dir / "tables"
    report_dir = output_dir / "report"
    for directory in [figures_dir, audio_dir, tables_dir, report_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    reference, output = load_dump(args.dump)
    lag, aligned_ref, aligned_out = best_alignment(reference, output, args.max_lag)
    metrics = compute_metrics(
        aligned_ref,
        aligned_out,
        args.sample_rate,
        lag,
        args.dump,
        captured_samples=reference.size,
    )
    clip_report = parse_clip_report(args.clip_report)

    ref_zero = aligned_ref - aligned_ref.mean()
    out_zero = aligned_out - aligned_out.mean()
    save_waveform(figures_dir / "waveform_compare.png", args.sample_rate, aligned_ref, aligned_out)
    save_spectrum(figures_dir / "spectrum_compare.png", args.sample_rate, ref_zero, out_zero)
    save_spectrogram(figures_dir / "spectrogram_compare.png", args.sample_rate, ref_zero, out_zero)
    save_overview(figures_dir / "overview_compare.png", args.sample_rate, aligned_ref, aligned_out, metrics)

    peak_reference = max(float(metrics["source_peak"]), float(metrics["output_peak"]), 1.0)
    save_audio_wav(audio_dir / "reference_aligned.wav", args.sample_rate, aligned_ref, peak_reference)
    save_audio_wav(audio_dir / "output_aligned.wav", args.sample_rate, aligned_out, peak_reference)
    if args.original_wav is not None and args.original_wav.exists():
        shutil.copyfile(args.original_wav, audio_dir / args.original_wav.name)

    save_aligned_csv(tables_dir / "aligned_samples.csv", args.sample_rate, aligned_ref, aligned_out)
    save_metrics_csv(tables_dir / "metrics.csv", metrics)
    (tables_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    write_summary(report_dir / "defense_summary.md", metrics, clip_report, figures_dir, audio_dir, tables_dir)
    write_talking_points(report_dir / "talking_points.md", metrics)

    print(json.dumps({"output_dir": str(output_dir), "metrics": metrics}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
