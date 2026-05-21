#!/usr/bin/env python3
"""Convert a WAV speech clip into an 8-bit ROM init file."""

from __future__ import annotations

import argparse
import struct
import wave
from pathlib import Path


def find_active_window(samples: list[int], threshold: int, pre: int, post: int) -> tuple[int, int]:
    first = next((i for i, v in enumerate(samples) if abs(v) >= threshold), 0)
    last = len(samples) - 1 - next((i for i, v in enumerate(reversed(samples)) if abs(v) >= threshold), 0)
    start = max(0, first - pre)
    end = min(len(samples), last + post + 1)
    return start, end


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_wav", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("audio_clip.mem"))
    parser.add_argument("--report", type=Path, default=Path(__file__).with_name("audio_clip_report.txt"))
    parser.add_argument("--threshold", type=int, default=500)
    parser.add_argument("--pre-roll", type=int, default=800)
    parser.add_argument("--post-roll", type=int, default=800)
    args = parser.parse_args()

    with wave.open(str(args.input_wav), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
        raw = wav_file.readframes(frame_count)

    if channels != 1:
        raise SystemExit(f"expected mono WAV, got {channels} channels")
    if sample_width != 2:
        raise SystemExit(f"expected 16-bit PCM WAV, got sample width {sample_width}")
    if sample_rate != 16_000:
        raise SystemExit(f"expected 16 kHz WAV, got {sample_rate} Hz")

    samples = list(struct.unpack("<" + "h" * frame_count, raw))
    start, end = find_active_window(samples, args.threshold, args.pre_roll, args.post_roll)
    trimmed = samples[start:end]

    peak = max(1, max(abs(v) for v in trimmed))
    scale = 127.0 / peak

    quantized: list[int] = []
    for value in trimmed:
        scaled = int(round(value * scale))
        if scaled > 127:
            scaled = 127
        elif scaled < -128:
            scaled = -128
        quantized.append(scaled)

    args.output.write_text("\n".join(f"{value & 0xFF:02x}" for value in quantized) + "\n", encoding="ascii")
    args.report.write_text(
        "\n".join(
            [
                f"input={args.input_wav}",
                f"sample_rate={sample_rate}",
                "rom_width_bits=8",
                "playback_sample_rate=32000",
                "interpolation=sample_repeat_x2",
                f"original_samples={len(samples)}",
                f"trim_start={start}",
                f"trim_end={end}",
                f"trimmed_samples={len(trimmed)}",
                f"duration_s={len(trimmed) / sample_rate:.6f}",
                f"peak={peak}",
                f"scale={scale:.8f}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"wrote {len(trimmed)} samples to {args.output}")
    print(f"report saved to {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
