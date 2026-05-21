#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SIM_ROOT="${ROOT_DIR}/sim"
MODELSIM_ENV="${MODELSIM_ENV:-/home/huoshao/altera/modelsim32/env.sh}"

usage() {
  cat <<'EOF'
Usage:
  sim/run_modelsim.sh <target> [--vcd]
  sim/run_modelsim.sh fm_loopback_audio_rom_dump [--start-addr N] [--warmup-samples N] [--capture-samples N] [--vcd]
  sim/run_modelsim.sh radio_core_audio_dump [--tone-hz N] [--settle-samples N] [--capture-samples N] [--reference-peak N] [--vcd]

Targets:
  log_encoder
  deemphasis
  cic_3_filter
  fm_loopback
  fm_loopback_audio_rom
  fm_loopback_audio_rom_dump
  fm_loopback_ep4ce6
  i2s_tx
  i2s_tx_3wire
  radio_core
  radio_core_audio
  radio_core_audio_dump
  radio_core_log

Options:
  --vcd              Export a VCD file alongside the batch log and WLF waveform file.
  --start-addr N     Override the ROM start address for fm_loopback_audio_rom_dump.
  --warmup-samples N Override the warm-up audio sample count for fm_loopback_audio_rom_dump.
  --capture-samples N
                     Override the dumped sample count for fm_loopback_audio_rom_dump.
  --tone-hz N        Override the injected audio tone for radio_core_audio_dump.
  --settle-samples N Override the discarded audio sample count for radio_core_audio_dump.
  --reference-peak N Override the injected sine amplitude for radio_core_audio_dump.
EOF
}

target="${1:-}"
if [[ "${target}" == "-h" || "${target}" == "--help" ]]; then
  usage
  exit 0
fi
if [[ -z "${target}" ]]; then
  usage
  exit 1
fi
shift || true

dump_vcd=0
dump_start_addr=""
dump_warmup_samples=""
dump_capture_samples=""
audio_tone_hz=""
audio_settle_samples=""
audio_capture_samples=""
audio_reference_peak=""
used_dump_start_addr=0
used_dump_warmup_samples=0
used_capture_samples=0
used_audio_tone_hz=0
used_audio_settle_samples=0
used_audio_reference_peak=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --vcd)
      dump_vcd=1
      ;;
    --start-addr)
      if [[ $# -lt 2 ]]; then
        printf 'Missing value for %s\n\n' "$1" >&2
        usage >&2
        exit 1
      fi
      dump_start_addr="$2"
      used_dump_start_addr=1
      shift
      ;;
    --warmup-samples)
      if [[ $# -lt 2 ]]; then
        printf 'Missing value for %s\n\n' "$1" >&2
        usage >&2
        exit 1
      fi
      dump_warmup_samples="$2"
      used_dump_warmup_samples=1
      shift
      ;;
    --capture-samples)
      if [[ $# -lt 2 ]]; then
        printf 'Missing value for %s\n\n' "$1" >&2
        usage >&2
        exit 1
      fi
      dump_capture_samples="$2"
      audio_capture_samples="$2"
      used_capture_samples=1
      shift
      ;;
    --tone-hz)
      if [[ $# -lt 2 ]]; then
        printf 'Missing value for %s\n\n' "$1" >&2
        usage >&2
        exit 1
      fi
      audio_tone_hz="$2"
      used_audio_tone_hz=1
      shift
      ;;
    --settle-samples)
      if [[ $# -lt 2 ]]; then
        printf 'Missing value for %s\n\n' "$1" >&2
        usage >&2
        exit 1
      fi
      audio_settle_samples="$2"
      used_audio_settle_samples=1
      shift
      ;;
    --reference-peak)
      if [[ $# -lt 2 ]]; then
        printf 'Missing value for %s\n\n' "$1" >&2
        usage >&2
        exit 1
      fi
      audio_reference_peak="$2"
      used_audio_reference_peak=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n\n' "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

if [[ ! -f "${MODELSIM_ENV}" ]]; then
  printf 'ModelSim environment script not found: %s\n' "${MODELSIM_ENV}" >&2
  exit 1
fi

export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"

# shellcheck source=/dev/null
source "${MODELSIM_ENV}"

dump_compile_defines=()
if [[ -n "${dump_start_addr}" ]]; then
  dump_compile_defines+=("+define+TB_AUDIO_START_ADDR=${dump_start_addr}")
fi
if [[ -n "${dump_warmup_samples}" ]]; then
  dump_compile_defines+=("+define+TB_WARMUP_SAMPLES=${dump_warmup_samples}")
fi
if [[ -n "${dump_capture_samples}" ]]; then
  dump_compile_defines+=("+define+TB_CAPTURE_SAMPLES=${dump_capture_samples}")
fi

audio_dump_compile_defines=()
if [[ -n "${audio_tone_hz}" ]]; then
  audio_dump_compile_defines+=("+define+TB_TONE_HZ=${audio_tone_hz}")
fi
if [[ -n "${audio_settle_samples}" ]]; then
  audio_dump_compile_defines+=("+define+TB_SETTLE_SAMPLES=${audio_settle_samples}")
fi
if [[ -n "${audio_capture_samples}" ]]; then
  audio_dump_compile_defines+=("+define+TB_CAPTURE_SAMPLES=${audio_capture_samples}")
fi
if [[ -n "${audio_reference_peak}" ]]; then
  audio_dump_compile_defines+=("+define+TB_REFERENCE_PEAK=${audio_reference_peak}")
fi

if [[ "${used_dump_start_addr}" -eq 1 || "${used_dump_warmup_samples}" -eq 1 ]]; then
  if [[ "${target}" != "fm_loopback_audio_rom_dump" ]]; then
    printf 'Dump window overrides are only supported for fm_loopback_audio_rom_dump\n' >&2
    exit 1
  fi
fi

if [[ "${used_audio_tone_hz}" -eq 1 || "${used_audio_settle_samples}" -eq 1 || "${used_audio_reference_peak}" -eq 1 ]]; then
  if [[ "${target}" != "radio_core_audio_dump" ]]; then
    printf 'Tone sweep overrides are only supported for radio_core_audio_dump\n' >&2
    exit 1
  fi
fi

if [[ "${used_capture_samples}" -eq 1 ]]; then
  if [[ "${target}" != "fm_loopback_audio_rom_dump" && "${target}" != "radio_core_audio_dump" ]]; then
    printf 'Capture sample overrides are only supported for fm_loopback_audio_rom_dump and radio_core_audio_dump\n' >&2
    exit 1
  fi
fi

case "${target}" in
  log_encoder)
    sim_dir="${SIM_ROOT}/log_encoder"
    top_module="work.tb_log_encoder"
    setup_cmd=(
      ln -sf ../../rtl/log_encoder_rom.mem log_encoder_rom.mem
    )
    vlog_args=(
      -sv
      ../../rtl/log_encoder.sv
      tb_log_encoder.sv
    )
    ;;
  deemphasis)
    sim_dir="${SIM_ROOT}/deemphasis"
    top_module="work.tb_deemphasis"
    setup_cmd=(:)
    vlog_args=(
      -sv
      ../../rtl/deemphasis.sv
      tb_deemphasis.sv
    )
    ;;
  cic_3_filter)
    sim_dir="${SIM_ROOT}/cic_3_filter"
    top_module="work.tb_cic_3_filter"
    setup_cmd=(:)
    vlog_args=(
      -sv
      ../../rtl/cic_3_filter.sv
      tb_cic_3_filter.sv
    )
    ;;
  fm_loopback)
    sim_dir="${SIM_ROOT}/fm_loopback"
    top_module="work.tb_fm_loopback"
    setup_cmd=(:)
    vlog_args=(
      -sv
      +incdir+../../CORDIC/rtl
      ../../CORDIC/rtl/cordic.sv
      ../../rtl/dds.sv
      ../../rtl/differentiator.sv
      ../../rtl/cic_3_filter.sv
      ../../rtl/synchronizer.sv
      ../../rtl/clock_divider.sv
      ../../rtl/cru.sv
      ../../rtl/test_tone.sv
      ../../rtl/iq_modulator.sv
      ../../rtl/radio_core.sv
      ../../rtl/fm_modulator.sv
      ../../rtl/pwm_audio.sv
      ../../rtl/fm_loopback_core.sv
      tb_fm_loopback.sv
    )
    ;;
  fm_loopback_ep4ce6)
    sim_dir="${SIM_ROOT}/fm_loopback_ep4ce6"
    top_module="work.tb_fm_loopback_ep4ce6"
    setup_cmd=(:)
    vlog_args=(
      -sv
      +incdir+../../CORDIC/rtl
      ../../CORDIC/rtl/cordic.sv
      ../../rtl/dds.sv
      ../../rtl/differentiator.sv
      ../../rtl/cic_3_filter.sv
      ../../rtl/synchronizer.sv
      ../../rtl/clock_divider.sv
      ../../rtl/cru.sv
      ../../rtl/iq_modulator.sv
      ../../rtl/radio_core.sv
      ../../rtl/fm_modulator.sv
      ../../rtl/pwm_audio.sv
      ../../rtl/tone_source_1k.sv
      ../../rtl/fm_loopback_ep4ce6_core.sv
      tb_fm_loopback_ep4ce6.sv
    )
    ;;
  fm_loopback_audio_rom)
    sim_dir="${SIM_ROOT}/fm_loopback_audio_rom"
    top_module="work.tb_fm_loopback_audio_rom"
    setup_cmd=(
      ln -sf ../../rtl/audio_clip.mem audio_clip.mem
    )
    vlog_args=(
      -sv
      +incdir+../../CORDIC/rtl
      ../../CORDIC/rtl/cordic.sv
      ../../rtl/dds.sv
      ../../rtl/differentiator.sv
      ../../rtl/cic_3_filter.sv
      ../../rtl/synchronizer.sv
      ../../rtl/clock_divider.sv
      ../../rtl/cru.sv
      ../../rtl/iq_modulator.sv
      ../../rtl/radio_core.sv
      ../../rtl/fm_modulator.sv
      ../../rtl/pwm_audio.sv
      ../../rtl/audio_rom_source.sv
      ../../rtl/audio_sample_bridge.sv
      ../../rtl/fm_loopback_audio_rom_core.sv
      tb_fm_loopback_audio_rom.sv
    )
    ;;
  fm_loopback_audio_rom_dump)
    sim_dir="${SIM_ROOT}/fm_loopback_audio_rom"
    top_module="work.tb_fm_loopback_audio_rom_dump"
    setup_cmd=(
      ln -sf ../../rtl/audio_clip.mem audio_clip.mem
    )
    vlog_args=(
      -sv
      "${dump_compile_defines[@]}"
      +incdir+../../CORDIC/rtl
      ../../CORDIC/rtl/cordic.sv
      ../../rtl/dds.sv
      ../../rtl/differentiator.sv
      ../../rtl/cic_3_filter.sv
      ../../rtl/synchronizer.sv
      ../../rtl/clock_divider.sv
      ../../rtl/cru.sv
      ../../rtl/iq_modulator.sv
      ../../rtl/radio_core.sv
      ../../rtl/fm_modulator.sv
      ../../rtl/pwm_audio.sv
      ../../rtl/audio_rom_source.sv
      ../../rtl/audio_sample_bridge.sv
      ../../rtl/fm_loopback_audio_rom_core.sv
      tb_fm_loopback_audio_rom_dump.sv
    )
    ;;
  i2s_tx)
    sim_dir="${SIM_ROOT}/i2s_tx"
    top_module="work.tb_i2s_tx"
    setup_cmd=(:)
    vlog_args=(
      -sv
      ../../rtl/i2s_tx.sv
      tb_i2s_tx.sv
    )
    ;;
  i2s_tx_3wire)
    sim_dir="${SIM_ROOT}/i2s_tx_3wire"
    top_module="work.tb_i2s_tx_3wire"
    setup_cmd=(:)
    vlog_args=(
      -sv
      ../../rtl/i2s_tx_3wire.sv
      tb_i2s_tx_3wire.sv
    )
    ;;
  radio_core)
    sim_dir="${SIM_ROOT}/radio_core"
    top_module="work.tb_radio_core"
    setup_cmd=(:)
    vlog_args=(
      -sv
      +incdir+../../CORDIC/rtl
      ../../CORDIC/rtl/cordic.sv
      ../../rtl/dds.sv
      ../../rtl/differentiator.sv
      ../../rtl/deemphasis.sv
      ../../rtl/cic_3_filter.sv
      ../../rtl/synchronizer.sv
      ../../rtl/clock_divider.sv
      ../../rtl/cru.sv
      ../../rtl/freq_select.sv
      ../../rtl/test_tone.sv
      ../../rtl/iq_modulator.sv
      ../../rtl/radio_core.sv
      tb_radio_core.sv
    )
    ;;
  radio_core_audio)
    sim_dir="${SIM_ROOT}/radio_core_audio"
    top_module="work.tb_radio_core_audio"
    setup_cmd=(:)
    vlog_args=(
      -sv
      +incdir+../../CORDIC/rtl
      ../../CORDIC/rtl/cordic.sv
      ../../rtl/dds.sv
      ../../rtl/differentiator.sv
      ../../rtl/deemphasis.sv
      ../../rtl/cic_3_filter.sv
      ../../rtl/synchronizer.sv
      ../../rtl/clock_divider.sv
      ../../rtl/cru.sv
      ../../rtl/freq_select.sv
      ../../rtl/test_tone.sv
      ../../rtl/iq_modulator.sv
      ../../rtl/radio_core.sv
      tb_radio_core_audio.sv
    )
    ;;
  radio_core_audio_dump)
    sim_dir="${SIM_ROOT}/radio_core_audio"
    top_module="work.tb_radio_core_audio_dump"
    setup_cmd=(:)
    vlog_args=(
      -sv
      "${audio_dump_compile_defines[@]}"
      +incdir+../../CORDIC/rtl
      ../../CORDIC/rtl/cordic.sv
      ../../rtl/dds.sv
      ../../rtl/differentiator.sv
      ../../rtl/cic_3_filter.sv
      ../../rtl/fm_modulator.sv
      ../../rtl/synchronizer.sv
      ../../rtl/iq_modulator.sv
      ../../rtl/radio_core.sv
      tb_radio_core_audio_dump.sv
    )
    ;;
  radio_core_log)
    sim_dir="${SIM_ROOT}/radio_core_log"
    top_module="work.tb_radio_core_log"
    setup_cmd=(
      ln -sf ../../rtl/log_encoder_rom.mem log_encoder_rom.mem
    )
    vlog_args=(
      -sv
      +incdir+../../CORDIC/rtl
      ../../CORDIC/rtl/cordic.sv
      ../../rtl/dds.sv
      ../../rtl/differentiator.sv
      ../../rtl/deemphasis.sv
      ../../rtl/log_encoder.sv
      ../../rtl/cic_3_filter.sv
      ../../rtl/synchronizer.sv
      ../../rtl/clock_divider.sv
      ../../rtl/cru.sv
      ../../rtl/freq_select.sv
      ../../rtl/test_tone.sv
      ../../rtl/iq_modulator.sv
      ../../rtl/radio_core.sv
      ../../rtl/radio_core_log.sv
      tb_radio_core_log.sv
    )
    ;;
  *)
    printf 'Unsupported target: %s\n\n' "${target}" >&2
    usage >&2
    exit 1
    ;;
esac

cd "${sim_dir}"
mkdir -p outputs
"${setup_cmd[@]}"

timestamp="$(date +%Y%m%d_%H%M%S)"
worklib="outputs/work_${target}_${timestamp}"
wlf_file="outputs/${target}.wlf"
log_file="outputs/${target}.log"

vlib "${worklib}"
vmap work "${worklib}"
vlog -work work "${vlog_args[@]}"

do_cmd='run -all; quit -code 0'
vsim_args=(
  -c
  -wlf "${wlf_file}"
  -l "${log_file}"
)

if [[ "${dump_vcd}" -eq 1 ]]; then
  vcd_file="outputs/${target}.vcd"
  do_cmd="vcd file \"${vcd_file}\"; vcd add -r /*; run -all; vcd flush; quit -code 0"
  vsim_args+=(-voptargs=+acc)
fi

vsim "${vsim_args[@]}" "${top_module}" -do "${do_cmd}"

if grep -Eq "\\*\\* (Error|Fatal):" "${log_file}"; then
  printf 'ModelSim reported an error, see: %s\n' "${sim_dir}/outputs/${target}.log" >&2
  exit 1
fi

printf 'Batch simulation finished: %s\n' "${target}"
printf '  log: %s\n' "${sim_dir}/outputs/${target}.log"
printf '  wlf: %s\n' "${sim_dir}/outputs/${target}.wlf"
if [[ "${dump_vcd}" -eq 1 ]]; then
  printf '  vcd: %s\n' "${sim_dir}/outputs/${target}.vcd"
fi
