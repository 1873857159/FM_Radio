#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
用法：
  ./init_project.sh <diag_static|loopback|pcm5102|pcm5102_50m|pcm5102_audio_rom_50m|pcm5102_3wire_50m|pcm5102_audio_rom_3wire_50m> <project_dir>

说明：
  1. 在目标目录生成 Quartus 工程骨架：
     - fm_radio.qpf
     - radio_top.qsf
     - radio_top.sdc
  2. EP4CE10 模板已经按“核心板引脚表 + 摄像头接口接 PCM5102”预填推荐引脚。
  3. 如果主人改接别的接口，再按原理图调整 radio_top.qsf 后编译烧录。
EOF
}

if [ "$#" -ne 2 ]; then
  usage
  exit 1
fi

mode="$1"
project_dir="$2"

script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"

case "$mode" in
  diag_static)
    qsf_template="$script_dir/ep4ce10_diag_static_top.qsf.template"
    sdc_template="$script_dir/ep4ce10_diag_static_top.sdc"
    extra_files=()
    ;;
  loopback)
    qsf_template="$script_dir/ep4ce10_loopback_top.qsf.template"
    sdc_template="$script_dir/ep4ce10_loopback_top.sdc"
    extra_files=()
    ;;
  pcm5102)
    qsf_template="$script_dir/ep4ce10_pcm5102_top.qsf.template"
    sdc_template="$script_dir/ep4ce10_pcm5102_top.sdc"
    extra_files=()
    ;;
  pcm5102_50m)
    qsf_template="$script_dir/ep4ce10_pcm5102_50m_top.qsf.template"
    sdc_template="$script_dir/ep4ce10_pcm5102_50m_top.sdc"
    extra_files=()
    ;;
  pcm5102_audio_rom_50m)
    qsf_template="$script_dir/ep4ce10_pcm5102_audio_rom_50m_top.qsf.template"
    sdc_template="$script_dir/ep4ce10_pcm5102_audio_rom_50m_top.sdc"
    extra_files=("$repo_root/rtl/audio_clip.mem")
    ;;
  pcm5102_3wire_50m)
    qsf_template="$script_dir/ep4ce10_pcm5102_3wire_50m_top.qsf.template"
    sdc_template="$script_dir/ep4ce10_pcm5102_3wire_50m_top.sdc"
    extra_files=()
    ;;
  pcm5102_audio_rom_3wire_50m)
    qsf_template="$script_dir/ep4ce10_pcm5102_audio_rom_3wire_50m_top.qsf.template"
    sdc_template="$script_dir/ep4ce10_pcm5102_audio_rom_3wire_50m_top.sdc"
    extra_files=("$repo_root/rtl/audio_clip.mem")
    ;;
  *)
    usage
    exit 1
    ;;
esac

mkdir -p "$project_dir"
cp "$sdc_template" "$project_dir/radio_top.sdc"
for extra_file in "${extra_files[@]}"; do
  cp "$extra_file" "$project_dir/"
done

sed \
  -e "s#../../CORDIC/rtl#$repo_root/CORDIC/rtl#g" \
  -e "s#../../rtl#$repo_root/rtl#g" \
  -e 's#^set_global_assignment -name SDC_FILE .*#set_global_assignment -name SDC_FILE radio_top.sdc#' \
  "$qsf_template" > "$project_dir/radio_top.qsf"

cat > "$project_dir/fm_radio.qpf" <<'EOF'
PROJECT_REVISION = "radio_top"
EOF

cat <<EOF
工程骨架已生成：
  $project_dir/fm_radio.qpf
  $project_dir/radio_top.qsf
  $project_dir/radio_top.sdc
EOF

if [ "${#extra_files[@]}" -gt 0 ]; then
  printf '  %s\n' "${extra_files[@]##*/}"
fi

cat <<EOF

下一步：
  1. 检查 radio_top.qsf 里的推荐引脚是否与实际接线一致
  2. 如有需要，调整 PCM5102 接口引脚
  3. 运行 quartus_sh --flow compile fm_radio -c radio_top
EOF
