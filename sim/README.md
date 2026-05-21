# ModelSim Batch 仿真说明

这个目录现在提供了一套固定入口，用于在本机的 Quartus 13.1 / ModelSim ASE 环境下重跑核心功能仿真。

当前项目状态与唯一主线请优先参考：

- `doc/project_progress.md`
- `doc/current_mainline.md`

## 环境前提

- 仓库路径：`/home/huoshao/FM_Radio`
- ModelSim 兼容环境脚本：`/home/huoshao/altera/modelsim32/env.sh`
- 已验证可运行的仿真目标：
  - `log_encoder`
  - `deemphasis`
  - `cic_3_filter`
  - `fm_loopback`
  - `fm_loopback_audio_rom`
  - `fm_loopback_audio_rom_dump`
  - `fm_loopback_ep4ce6`
  - `i2s_tx`
  - `i2s_tx_3wire`
  - `radio_core`
  - `radio_core_audio`
  - `radio_core_log`

如果兼容环境脚本放在别处，可以通过环境变量覆盖：

```sh
MODELSIM_ENV="/path/to/env.sh" ./sim/run_modelsim.sh radio_core
```

## 统一入口

在仓库根目录执行：

```sh
./sim/run_modelsim.sh deemphasis
./sim/run_modelsim.sh cic_3_filter
./sim/run_modelsim.sh fm_loopback
./sim/run_modelsim.sh fm_loopback_audio_rom
./sim/run_modelsim.sh fm_loopback_audio_rom_dump
./sim/run_modelsim.sh fm_loopback_ep4ce6
./sim/run_modelsim.sh i2s_tx
./sim/run_modelsim.sh i2s_tx_3wire
./sim/run_modelsim.sh radio_core
./sim/run_modelsim.sh radio_core_audio
./sim/run_modelsim.sh log_encoder
./sim/run_modelsim.sh radio_core_log
```

如果需要论文用的波形原始数据，可以加 `--vcd`：

```sh
./sim/run_modelsim.sh deemphasis --vcd
./sim/run_modelsim.sh cic_3_filter --vcd
./sim/run_modelsim.sh fm_loopback --vcd
./sim/run_modelsim.sh fm_loopback_audio_rom --vcd
./sim/run_modelsim.sh fm_loopback_ep4ce6 --vcd
./sim/run_modelsim.sh i2s_tx --vcd
./sim/run_modelsim.sh i2s_tx_3wire --vcd
./sim/run_modelsim.sh radio_core --vcd
./sim/run_modelsim.sh radio_core_audio --vcd
./sim/run_modelsim.sh log_encoder --vcd
./sim/run_modelsim.sh radio_core_log --vcd
```

## 输出文件

每个仿真目录下会生成 `outputs/`，里面包含：

- `*.log`：ModelSim batch 日志
- `*.wlf`：ModelSim 波形文件，可用 GUI 打开
- `*.vcd`：可选导出的 VCD 波形文件
- `work_*`：对应批次的编译库

示例：

- `sim/deemphasis/outputs/deemphasis.log`
- `sim/cic_3_filter/outputs/cic_3_filter.vcd`
- `sim/fm_loopback/outputs/fm_loopback.wlf`
- `sim/fm_loopback_audio_rom/outputs/fm_loopback_audio_rom.log`
- `sim/fm_loopback_audio_rom/outputs/fm_loopback_audio_rom_dump_samples.txt`
- `sim/fm_loopback_ep4ce6/outputs/fm_loopback_ep4ce6.wlf`
- `sim/i2s_tx/outputs/i2s_tx.wlf`
- `sim/i2s_tx_3wire/outputs/i2s_tx_3wire.wlf`
- `sim/radio_core/outputs/radio_core.wlf`
- `sim/radio_core_audio/outputs/radio_core_audio.vcd`
- `sim/log_encoder/outputs/log_encoder.vcd`
- `sim/radio_core_log/outputs/radio_core_log.vcd`

## 当前建议

如果当前只保留一个主线仿真目标，默认使用：

```sh
./sim/run_modelsim.sh fm_loopback_audio_rom_dump
```

原因：

- 它和当前板级主线 `ep4ce10_pcm5102_audio_rom_3wire_50m_top` 对应的“语音 ROM FM 回环”一致。
- 它会导出 `audio_in_dbg / audio_out_dbg`，可以直接接到 `analysis/audio_compare/`。
- 它比 `radio_core`、`i2s_tx_3wire` 这类模块级验证更接近当前项目的完整目标。

其他目标仍然可用，但它们属于补充验证，不是当前唯一推荐主线。

论文补证据时，优先保留下面这些结果：

- `fm_loopback_audio_rom_dump`：导出 `audio_in_dbg / audio_out_dbg` 样本，供离线画波形图、频谱图和语谱图
- `analysis/audio_compare/build_defense_package.sh`：在 dump 基础上生成答辩用图表、WAV、指标表和讲解摘要
- `i2s_tx_3wire`：三线 I2S 串行帧格式的接口级补充验证
- `radio_core`：整条 FM 数字接收链路的模块级补充验证
- `fm_loopback_audio_rom`：不导出 dump 的闭环回归版本
- `fm_loopback`：板内测试音闭环结果
- `fm_loopback_ep4ce6`：面向 EP4CE6 轻量化音源的板内闭环结果
- `i2s_tx`：带外部 `12.288 MHz` 的旧 I2S 路线验证
- `radio_core_audio`：1 kHz 调制 FM 输入下的音频恢复结果
- `cic_3_filter`：抽取与降采样结果
- `deemphasis`：去加重前后响应
- `log_encoder`：ROM 对数编码结果
- `radio_core_log`：FM 解调后直接进入 ROM 对数编码

如果后续要导出截图，建议先生成 `WLF` 或 `VCD`，再用 GUI 或波形工具做定点截图，避免每次手工重新编译。
