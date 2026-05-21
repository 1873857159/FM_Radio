# EP4CE6F17C8 核心板最小上板方案

这组文件用于把当前轻量化闭环方案迁到裸 `EP4CE6F17C8` 核心板：

- [ep4ce6_loopback_top.sv](/home/huoshao/FM_Radio/rtl/ep4ce6_loopback_top.sv)
- [ep4ce6_loopback_top.qsf.template](/home/huoshao/FM_Radio/boards/ep4ce6f17c8_core/ep4ce6_loopback_top.qsf.template)
- [ep4ce6_loopback_top.sdc](/home/huoshao/FM_Radio/boards/ep4ce6f17c8_core/ep4ce6_loopback_top.sdc)

## 功能

顶层内部链路为：

`tone_source_1k -> fm_modulator -> radio_core -> pwm_audio`

输出接口含义：

- `pwm_audio`：PWM 音频输出，外接 RC 低通和有源音箱/耳放
- `fm_debug`：板内 FM 调制后的 1-bit 波形，可接示波器观察
- `led[0]`：复位状态
- `led[1]`：PWM 输出活动
- `led[2]`：FM 输出活动
- `led[3]`：解调音频符号位

## 时钟要求

当前设计仍然要求 `240 MHz` 输入时钟。

如果核心板本身不是 `240 MHz` 晶振，而是 `50 MHz` 或其他频率，需要后续再补一个适配该板卡的 PLL 或时钟方案。这里先保留最小可接线版本，不擅自假设板卡时钟资源。

## 引脚模板使用方法

1. 根据核心板原理图或卖家资料，确认：
   - 时钟输入引脚
   - 复位按键或复位输入引脚
   - 可用 LED 引脚
   - 一个可接 RC 低通的普通 GPIO 作为 `pwm_audio`
   - 一个可选调试 GPIO 作为 `fm_debug`
2. 复制 `ep4ce6_loopback_top.qsf.template`
3. 把其中的 `PIN_XXX` 替换成真实管脚号
4. 如果没有 4 个 LED，可以删掉多余 LED 约束和顶层端口

## 最小硬件连接建议

- `pwm_audio` -> `1k` 电阻 -> 节点 A
- 节点 A -> `10nF ~ 100nF` 电容到地
- 节点 A -> 有源音箱输入或耳放模块输入
- `fm_debug` 仅用于示波器/逻辑分析仪观察，不建议直接接负载

这套连接足够先验证“板内音频 -> FM -> 解调 -> PWM 音频输出”的闭环。

## PCM5102 方案

如果改用 `PCM5102` 模块输出音频，可以使用下面这组文件：

- [ep4ce6_pcm5102_top.sv](/home/huoshao/FM_Radio/rtl/ep4ce6_pcm5102_top.sv)
- [ep4ce6_pcm5102_top.qsf.template](/home/huoshao/FM_Radio/boards/ep4ce6f17c8_core/ep4ce6_pcm5102_top.qsf.template)
- [ep4ce6_pcm5102_top.sdc](/home/huoshao/FM_Radio/boards/ep4ce6f17c8_core/ep4ce6_pcm5102_top.sdc)

这一路改成：

`tone_source_1k -> fm_modulator -> radio_core -> I2S -> PCM5102`

额外要求：

- `clk240m`：FM 数字链路时钟
- `clk12m288`：I2S 音频时钟

PCM5102 接线关系：

- `pcm_sck` -> PCM5102 `SCK/MCLK`（如果模块引出了这根脚）
- `pcm_bck` -> PCM5102 `BCK`
- `pcm_lrck` -> PCM5102 `LCK/LRCK`
- `pcm_din` -> PCM5102 `DIN`
- 模块电源和模拟输出按 PCM5102 小板资料连接

如果核心板只有单一晶振，还需要后续再补一个 PLL，生成 `240 MHz` 和 `12.288 MHz` 两路时钟。
