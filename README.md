# 基于 FPGA 的全数字 FM 收音机

本项目是在 FPGA 上实现的全数字 FM 收音机工程，当前主线面向 `EP4CE10F17C8` 开发板和 `PCM5102` 音频 DAC。系统内部使用 ROM 音频作为参考输入，先完成板内 FM 调制，再经过数字接收链路完成下变频、CIC 抽取、CORDIC 相位提取、微分鉴频和 I2S 音频输出。

## 系统主线

```text
ROM 音频源
  -> 板内 FM 调制
  -> 1-bit FM 信号
  -> DDS 正交本振
  -> IQ 下变频
  -> 两级 CIC 抽取
  -> CORDIC 相位提取
  -> 微分鉴频
  -> 音频 CIC 抽取
  -> 16 位 PCM
  -> I2S 三线输出
  -> PCM5102 DAC
```

主处理时钟为 `240 MHz`，接收链路中的关键采样率为：

```text
240 MHz -> 48 MHz -> 960 kHz -> 32 kHz
```

其中 `48 MHz`、`960 kHz` 和 `32 kHz` 在 RTL 中是同步时钟使能信号，不是独立物理时钟。

## 目录说明

```text
rtl/       核心 RTL 代码，包括 FM 调制、接收解调、I2S、音频 ROM 等模块
sim/       ModelSim/VCS 仿真入口和 testbench
boards/    EP4CE10/EP4CE6 板级约束模板、引脚说明和工程初始化脚本
analysis/  音频输入输出对比、频谱/语谱图生成和指标计算脚本
tools/     文档、格式和辅助处理脚本
CORDIC/    CORDIC 子模块
```

## 主要 RTL 模块

```text
rtl/fm_modulator.sv                 板内 FM 调制器
rtl/radio_core.sv                   FM 数字接收核心
rtl/iq_modulator.sv                 1-bit 输入的 IQ 符号翻转下变频
rtl/cic_3_filter.sv                 三阶 CIC 抽取滤波器
rtl/differentiator.sv               相位差分鉴频模块
rtl/audio_rom_source.sv             ROM 音频源
rtl/audio_sample_bridge.sv          音频样本跨时钟域握手
rtl/i2s_tx_3wire.sv                 PCM5102 使用的三线 I2S 输出
rtl/ep4ce10_pcm5102_audio_rom_3wire_50m_top.sv  EP4CE10 板级顶层
```

## 仿真入口

推荐使用统一脚本运行仿真：

```bash
./sim/run_modelsim.sh fm_loopback_audio_rom_dump
```

该仿真会导出参考音频和解调输出的样本，数据格式为：

```text
index source output
```

其中 `source` 是 FM 调制器入口处的真实参考音频，`output` 是接收链路恢复后的 PCM 输出。

## 音频对比分析

生成波形、频谱、语谱图和误差指标：

```bash
python3 ./analysis/audio_compare/compare_from_dump.py \
  --dump ./sim/fm_loopback_audio_rom/outputs/fm_loopback_audio_rom_dump_samples.txt \
  --output-dir ./analysis/audio_compare/outputs
```

生成答辩用分析包：

```bash
./analysis/audio_compare/build_defense_package.sh
```

## 板级工程

EP4CE10F17C8 + PCM5102 的主要板级文件位于：

```text
boards/ep4ce10f17c8_core/
```

常用文件：

```text
ep4ce10_pcm5102_audio_rom_3wire_50m_top.qsf.template  Quartus 引脚约束模板
ep4ce10_pcm5102_audio_rom_3wire_50m_top.sdc           时序约束
pcm5102_wiring_table.md                               PCM5102 接线说明
bringup_checklist.md                                  上板检查清单
```

## 测试音频

测试音频源已经转换为 ROM 初始化文件：

```text
rtl/audio_clip.mem
```

原始测试 WAV 和转换报告保留在：

```text
rtl/audio_clip_acceptance.wav
rtl/audio_clip_report.txt
```

如需重新生成 ROM 文件，可使用：

```bash
python3 rtl/gen_audio_clip_mem.py <input.wav> \
  --output rtl/audio_clip.mem \
  --report rtl/audio_clip_report.txt
```

## 注意事项

- `sim/**/outputs/`、`.vcd`、`.wlf` 等仿真输出不建议提交到仓库。
- `code.zip`、论文文档、查重文件等非工程源码不属于本代码分支内容。
- 若使用 GitHub HTTPS 推送，需要配置 Personal Access Token；普通账号密码无法直接用于推送。

## 参考来源

- XRadio: A rockin' FPGA-only Radio for Teaching System Design, XCell Journal, issue 84.
- [emard/flearadio](https://github.com/emard/flearadio), Digital FM Radio Receiver for FPGA.
