# EP4CE10F17C8 当前板级入口

这个目录现在只保留一件事：为当前默认主线提供板级入口说明喵。

## 当前唯一推荐路线

- 顶层：[ep4ce10_pcm5102_audio_rom_3wire_50m_top.sv](/home/huoshao/FM_Radio/rtl/ep4ce10_pcm5102_audio_rom_3wire_50m_top.sv)
- 工程模板：[ep4ce10_pcm5102_audio_rom_3wire_50m_top.qsf.template](/home/huoshao/FM_Radio/boards/ep4ce10f17c8_core/ep4ce10_pcm5102_audio_rom_3wire_50m_top.qsf.template)
- 时序约束：[ep4ce10_pcm5102_audio_rom_3wire_50m_top.sdc](/home/huoshao/FM_Radio/boards/ep4ce10f17c8_core/ep4ce10_pcm5102_audio_rom_3wire_50m_top.sdc)

推荐原因：

- 它和当前项目主线、仿真 dump、音频对比流程完全对齐
- 只要求板载 `50 MHz` 时钟，不再依赖外部 `12.288 MHz`
- 当前项目的上板目标就是“语音 ROM FM 回环 -> 三线 I2S -> PCM5102”

## 当前使用顺序

1. 阅读 [bringup_checklist.md](/home/huoshao/FM_Radio/boards/ep4ce10f17c8_core/bringup_checklist.md)
2. 按 [pcm5102_wiring_table.md](/home/huoshao/FM_Radio/boards/ep4ce10f17c8_core/pcm5102_wiring_table.md) 接线
3. 运行 [init_project.sh](/home/huoshao/FM_Radio/boards/ep4ce10f17c8_core/init_project.sh) 生成 Quartus 工程
4. 检查 `radio_top.qsf` 里的默认引脚是否与实际接线一致
5. 编译并下载 `SOF`

## 当前生成命令

```sh
cd "/home/huoshao/FM_Radio/boards/ep4ce10f17c8_core"
./init_project.sh pcm5102_audio_rom_3wire_50m "/home/huoshao/altera/ep4ce10_pcm5102_audio_rom_3wire_50m_board"
```

## 当前文档分工

- 主线定义：[current_mainline.md](/home/huoshao/FM_Radio/doc/current_mainline.md)
- 项目进度：[project_progress.md](/home/huoshao/FM_Radio/doc/project_progress.md)
- 上板执行清单：[bringup_checklist.md](/home/huoshao/FM_Radio/boards/ep4ce10f17c8_core/bringup_checklist.md)

旧版多变体展开说明已经归档到：

- [archive/README.md](/home/huoshao/FM_Radio/boards/ep4ce10f17c8_core/archive/README.md)
