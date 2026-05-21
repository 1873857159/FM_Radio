#!/usr/bin/env bash
set -euo pipefail

input_path="${1:-/home/huoshao/下载/你好，南华大学.wav}"
output_path="${2:-/home/huoshao/FM_Radio/rtl/audio_clip_acceptance.wav}"

ffmpeg -y -i "$input_path" \
  -ac 1 \
  -ar 16000 \
  -sample_fmt s16 \
  -af "highpass=f=120,\
lowpass=f=3400,\
equalizer=f=1700:t=q:w=1.4:g=4.5,\
equalizer=f=2600:t=q:w=1.2:g=2.5,\
acompressor=threshold=0.10:ratio=2.8:attack=5:release=90:makeup=2.5,\
atempo=0.92,\
alimiter=limit=0.90,\
silenceremove=start_periods=1:start_duration=0:start_threshold=-40dB:stop_periods=-1:stop_duration=0.12:stop_threshold=-40dB" \
  -c:a pcm_s16le \
  "$output_path"

printf 'wrote optimized acceptance audio to %s\n' "$output_path"
