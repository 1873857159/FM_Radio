#!/usr/bin/env python3
"""Generate waveform / spectrum / spectrogram figures from a simulation dump."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from audio_compare_lib import (
    best_alignment,
    compute_metrics,
    load_dump,
    save_single_audio_overview,
    save_spectrogram,
    save_spectrum,
    save_waveform,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", type=Path, required=True, help="样本导出文件")
    parser.add_argument("--output-dir", type=Path, required=True, help="输出目录")
    parser.add_argument("--sample-rate", type=float, default=32000.0, help="样本率，默认 32 kHz")
    parser.add_argument("--max-lag", type=int, default=64, help="对齐搜索最大滞后样本数")
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    reference, output = load_dump(args.dump)
    lag, aligned_ref, aligned_out = best_alignment(reference, output, args.max_lag)
    metrics = compute_metrics(aligned_ref, aligned_out, args.sample_rate, lag, args.dump, captured_samples=reference.size)

    ref_zero = aligned_ref - aligned_ref.mean()
    out_zero = aligned_out - aligned_out.mean()
    save_single_audio_overview(output_dir / "input_audio_overview.png", args.sample_rate, aligned_ref, "输入参考音频", "#1f77b4")
    save_single_audio_overview(output_dir / "output_audio_overview.png", args.sample_rate, aligned_out, "解调输出音频", "#d62728")
    save_waveform(output_dir / "waveform_compare.png", args.sample_rate, aligned_ref, aligned_out)
    save_spectrum(output_dir / "spectrum_compare.png", args.sample_rate, ref_zero, out_zero)
    save_spectrogram(output_dir / "spectrogram_compare.png", args.sample_rate, ref_zero, out_zero)
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
