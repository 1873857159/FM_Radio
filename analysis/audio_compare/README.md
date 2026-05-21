# 音频对比分析

这个目录用于比较：

- 输入到 `fm_modulator` 的参考音频
- `radio_core` 解调后的输出音频

当前优先支持两类输入：

1. 仿真导出的样本文件  
   文件格式：`index source output`
2. 后续上板录回的音频文件  
   可以在此基础上继续扩展成 WAV 对比流程

## 目录结构

- [audio_compare_lib.py](/home/huoshao/FM_Radio/analysis/audio_compare/audio_compare_lib.py)
  公共分析库，统一处理样本加载、对齐、作图和指标计算
- [compare_from_dump.py](/home/huoshao/FM_Radio/analysis/audio_compare/compare_from_dump.py)
  从仿真导出的样本文件生成：
  - 波形图
  - 频谱图
  - 语谱图
  - 指标摘要
- [build_defense_package.py](/home/huoshao/FM_Radio/analysis/audio_compare/build_defense_package.py)
  生成答辩材料包：
  - 总览图
  - 三类对比图
  - 对齐后的参考/输出 WAV
  - 样本表和指标表
  - 摘要文档和讲解提纲
- [build_defense_package.sh](/home/huoshao/FM_Radio/analysis/audio_compare/build_defense_package.sh)
  从仿真到答辩包的一键入口
- `outputs/`
  默认输出目录，存放生成的图片和 `json`

## 推荐流程

1. 先导出仿真样本：

```sh
cd "/home/huoshao/FM_Radio"
./sim/run_modelsim.sh fm_loopback_audio_rom_dump
```

样本文件默认在：

- [fm_loopback_audio_rom_dump_samples.txt](/home/huoshao/FM_Radio/sim/fm_loopback_audio_rom/outputs/fm_loopback_audio_rom_dump_samples.txt)

2. 再生成分析图：

```sh
cd "/home/huoshao/FM_Radio"
python3 "./analysis/audio_compare/compare_from_dump.py" \
  --dump "./sim/fm_loopback_audio_rom/outputs/fm_loopback_audio_rom_dump_samples.txt" \
  --output-dir "./analysis/audio_compare/outputs"
```

3. 生成答辩材料包：

```sh
cd "/home/huoshao/FM_Radio"
./analysis/audio_compare/build_defense_package.sh
```

默认会在：

- [outputs/defense_package](/home/huoshao/FM_Radio/analysis/audio_compare/outputs/defense_package)

下面生成分目录产物。

## 输出内容

默认会生成：

- `waveform_compare.png`
- `spectrum_compare.png`
- `spectrogram_compare.png`
- `metrics.json`

答辩材料包会额外生成：

- `figures/overview_compare.png`
- `audio/reference_aligned.wav`
- `audio/output_aligned.wav`
- `tables/aligned_samples.csv`
- `tables/metrics.csv`
- `report/defense_summary.md`
- `report/talking_points.md`

## 指标说明

- `best_lag_samples`
  输入与输出做互相关后得到的最佳对齐偏移
- `pearson_corr`
  对齐后的皮尔逊相关系数
- `rmse`
  对齐后的均方根误差
- `source_peak` / `output_peak`
  峰值幅度

## 说明

对严格工程比较来说，优先把 `audio_in_dbg` 作为参考基准，而不是原始 `wav`。  
因为送进 FM 调制器之前，音频已经经历了：

- 裁剪静音段
- 8-bit 量化写入 ROM
- `16 kHz -> 32 kHz` 的重复输出展开

所以 `audio_in_dbg -> audio_out_dbg` 的比较最能反映 FM 链路本身的恢复质量喵。

## 答辩建议

- 优先展示 `overview_compare.png`，一页同时说明波形、频谱和语谱图
- 再引用 `defense_summary.md` 里的量化指标
- 如果老师追问听感，可以现场播放 `reference_aligned.wav` 和 `output_aligned.wav`
