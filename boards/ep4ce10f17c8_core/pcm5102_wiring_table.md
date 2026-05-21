# EP4CE10F17C8 核心板与 PCM5102 接线表

这份文档用于主人拿到 `EP4CE10F17C8` 核心板后直接接线喵。

当前默认工程使用三线 `I2S` 语音 ROM 版本：

- 顶层：[ep4ce10_pcm5102_audio_rom_3wire_50m_top.sv](/home/huoshao/FM_Radio/rtl/ep4ce10_pcm5102_audio_rom_3wire_50m_top.sv)
- 模板：[ep4ce10_pcm5102_audio_rom_3wire_50m_top.qsf.template](/home/huoshao/FM_Radio/boards/ep4ce10f17c8_core/ep4ce10_pcm5102_audio_rom_3wire_50m_top.qsf.template)

## FPGA 到 PCM5102 接线表

| FPGA 顶层端口 | 核心板管脚 | 板上资源名 | PCM5102 引脚 | 说明 |
| --- | --- | --- | --- | --- |
| `clk50m` | `E1` | `sys_clk` | 不接 | 板载 `50 MHz` 晶振输入，FPGA 自用 |
| `reset_n` | `M1` | `sys_rst_n` | 不接 | 板载复位输入，低有效 |
| `pcm_bck` | `R12` | `cam_pwdn` | `BCK` | `I2S` 位时钟 |
| `pcm_lrck` | `N9` | `cam_scl` | `LCK/LRCK` | `I2S` 左右声道时钟，当前为 `32 kHz` |
| `pcm_din` | `L10` | `cam_sda` | `DIN` | `I2S` 串行音频数据 |
| `fm_debug` | `D12` | `beep` | 不接 | 调试输出，建议留测试点 |
| `led[0]` | `D11` | `DS0` | 不接 | 复位状态指示 |
| `led[1]` | `C11` | `DS1` | 不接 | `LRCK` 活动指示 |
| `led[2]` | `E10` | `DS2` | 不接 | `BCK` 活动指示 |
| `led[3]` | `F9` | `DS3` | 不接 | 音频符号位指示 |

## 供电与模拟输出接线表

| 连接端 | 目标端 | 说明 |
| --- | --- | --- |
| 核心板 `3.3V` 或模块 `VIN` 允许电压 | `PCM5102 VIN` | 以主人手里 PCM5102 小板丝印和规格为准 |
| 核心板 `GND` | `PCM5102 GND` | 必须共地 |
| `PCM5102 SCK/MCLK` | 不接 | 当前工程为三线 `I2S` 版本 |
| `PCM5102 LOUT/ROUT` | 有源音箱或功放板输入 | 不要直接接无源喇叭 |

## 最小接线示意

```text
EP4CE10F17C8                PCM5102
-----------------------------------------
R12  (pcm_bck)   ---------> BCK
N9   (pcm_lrck)  ---------> LCK/LRCK
L10  (pcm_din)   ---------> DIN
GND               ---------> GND
3.3V/VIN          ---------> VIN
SCK/MCLK          ---------> 悬空不接
```

## 上电前检查

1. 先确认 `PCM5102` 小板电源输入规格，避免把 `5V only` 和 `3.3V only` 模块接错。
2. 先确认核心板 `E1` 确实接的是板载 `50 MHz` 晶振。
3. `pcm_bck`、`pcm_lrck`、`pcm_din` 当前借用的是摄像头接口那组脚，接线时不要和别的模块共用。
4. `fm_debug` 建议拉到测试点，后续可用示波器或逻辑分析仪观察。
5. `PCM5102` 输出后面应接有源音箱或功放板，不要直接驱动无源喇叭。

## 推荐上板顺序

1. 先只烧录 FPGA，不接 `PCM5102`，观察 `DS0~DS3` 是否有预期变化。
2. 再接 `PCM5102` 的 `BCK/LRCK/DIN/GND/VIN`。
3. 最后接有源音箱或功放板输入。
4. 如无声音，优先检查：
   - `GND` 是否共地
   - `VIN` 是否正确
   - `BCK/LRCK/DIN` 是否接反
   - `PCM5102` 模块是否默认静音或带使能脚
