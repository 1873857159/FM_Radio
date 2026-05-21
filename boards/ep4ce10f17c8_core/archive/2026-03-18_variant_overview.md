# EP4CE10F17C8 核心板方案（归档版）

归档时间：2026-03-18

说明：这份文档保留当时的多变体展开说明，现已不再作为默认入口。当前请优先使用 `ep4ce10_pcm5102_audio_rom_3wire_50m_top` 路线，并阅读上级目录中的当前文档。

这组文件对应 `EP4CE10F17C8` 核心板，仓库里虽然保留了多套顶层，但**当前唯一推荐主线**已经固定为：

- `ep4ce10_pcm5102_audio_rom_3wire_50m_top.sv`
- `ep4ce10_pcm5102_audio_rom_3wire_50m_top.qsf.template`
- `ep4ce10_pcm5102_audio_rom_3wire_50m_top.sdc`

其余顶层继续保留，但它们属于备选或历史路线：

- 轻量 PWM 版：`ep4ce10_loopback_top.sv`
- PCM5102 直时钟版：`ep4ce10_pcm5102_top.sv`
- PCM5102 `50 MHz` 核心板版：`ep4ce10_pcm5102_50m_top.sv`
- PCM5102 `50 MHz` 语音 ROM 版：`ep4ce10_pcm5102_audio_rom_50m_top.sv`
- PCM5102 三线 I2S `50 MHz` 版：`ep4ce10_pcm5102_3wire_50m_top.sv`

## 归档理由

当时保留这份长文档是为了并行比较多套板级路线，但当前仓库已经收敛到单一主线：

- `EP4CE10F17C8`
- `PCM5102`
- `audio ROM FM loopback`
- `three-wire I2S`
- `50 MHz -> 240 MHz PLL`

因此，这份文档中的多分支比较、旧版时钟路线和备选 top 说明不再作为默认入口。

## 当时保留的关键信息

- 三线 I2S 路线不需要外部 `12.288 MHz`
- 板载 `50 MHz` 晶振版本可以通过板内 PLL 生成 `240 MHz`
- `ep4ce10_pcm5102_audio_rom_3wire_50m_top` 已可完整编译并生成 `SOF`
- `PCM5102` 三线接口推荐走摄像头接口引脚

## 当前该看哪里

- 当前板级入口：`../README.md`
- 当前上板清单：`../bringup_checklist.md`
- 当前项目主线：`../../../doc/current_mainline.md`
- 当前项目进度：`../../../doc/project_progress.md`

