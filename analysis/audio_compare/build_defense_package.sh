#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DUMP_FILE="${ROOT_DIR}/sim/fm_loopback_audio_rom/outputs/fm_loopback_audio_rom_dump_samples.txt"
OUTPUT_DIR="${ROOT_DIR}/analysis/audio_compare/outputs/defense_package"
ORIGINAL_WAV="${1:-/home/huoshao/下载/你好，南华大学.wav}"

cd "${ROOT_DIR}"
./sim/run_modelsim.sh fm_loopback_audio_rom_dump

python3 "./analysis/audio_compare/build_defense_package.py" \
  --dump "${DUMP_FILE}" \
  --output-dir "${OUTPUT_DIR}" \
  --original-wav "${ORIGINAL_WAV}"

printf 'Defense package ready: %s\n' "${OUTPUT_DIR}"
