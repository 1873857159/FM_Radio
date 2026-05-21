# EP4CE10F17C8 上板清单

这份清单不进入论文，专门给主人后续拿到板子时快速落地用喵。

## 当前唯一推荐版本

这份清单默认只服务当前仓库唯一推荐主线：

- 顶层：[ep4ce10_pcm5102_audio_rom_3wire_50m_top.sv](/home/huoshao/FM_Radio/rtl/ep4ce10_pcm5102_audio_rom_3wire_50m_top.sv)
- 工程模板：[ep4ce10_pcm5102_audio_rom_3wire_50m_top.qsf.template](/home/huoshao/FM_Radio/boards/ep4ce10f17c8_core/ep4ce10_pcm5102_audio_rom_3wire_50m_top.qsf.template)
- 时序约束：[ep4ce10_pcm5102_audio_rom_3wire_50m_top.sdc](/home/huoshao/FM_Radio/boards/ep4ce10f17c8_core/ep4ce10_pcm5102_audio_rom_3wire_50m_top.sdc)

如果主人只是按当前项目默认路线推进，上板时不要再切回 `pcm5102_3wire_50m` 的无 ROM 版本喵。

## 需要确认的板卡信息

板子到手后，先确认下面 4 件事：

1. 板载晶振是否真的是 `50 MHz`
2. `EP4CE10F17C8` 的配置方式：`JTAG` 还是外挂 `EPCS`
3. 如果直接使用默认模板，确认下面这组推荐映射是否能按实际板子接出来：
   - `clk50m -> E1`
   - `reset_n -> M1`
   - `pcm_bck -> R12`
   - `pcm_lrck -> N9`
   - `pcm_din -> L10`
   - `fm_debug -> D12`
   - `led[3:0] -> D11/C11/E10/F9`
4. PCM5102 小板供电规格和引脚命名

## 推荐连线

FPGA 到 PCM5102 的逻辑连接建议如下：

- `pcm_bck -> PCM5102 BCK`
- `pcm_lrck -> PCM5102 LCK/LRCK`
- `pcm_din -> PCM5102 DIN`
- `GND -> GND`
- `PCM5102 SCK/MCLK`：默认不接

调试信号：

- `fm_debug`：接测试点或逻辑分析仪
- `led[0]`：复位状态
- `led[1]`：`LRCK`
- `led[2]`：`BCK`
- `led[3]`：音频符号位

默认模板中，`PCM5102` 三线接口统一走摄像头接口引脚：

- `R12`：`PCM5102 BCK`
- `N9`：`PCM5102 LRCK`
- `L10`：`PCM5102 DIN`

## 工程生成

在板子资料确认后，执行：

```sh
cd "/home/huoshao/FM_Radio/boards/ep4ce10f17c8_core"
./init_project.sh pcm5102_audio_rom_3wire_50m "/home/huoshao/altera/ep4ce10_pcm5102_audio_rom_3wire_50m_board"
```

然后编辑：

- `/home/huoshao/altera/ep4ce10_pcm5102_audio_rom_3wire_50m_board/radio_top.qsf`

默认情况下这里已经有推荐引脚约束；如果主人改接了别的接口，再按实际接线修改。
这个模式会自动把 `audio_clip.mem` 一起复制到工程目录。

## 编译与烧录

编译：

```sh
cd "/home/huoshao/altera/ep4ce10_pcm5102_audio_rom_3wire_50m_board"
/home/huoshao/altera/13.1/quartus/bin/quartus_sh --flow compile fm_radio -c radio_top
```

成功后，生成文件在：

- `output_files/radio_top.sof`

## 上板后自检顺序

1. 先不接 PCM5102，只看 `led[0:3]`
2. `led[0]` 正常亮，说明复位已释放
3. `led[1]`、`led[2]` 有变化，说明 I2S 时钟已跑起来
4. 再接 PCM5102
5. 最后接有源音箱或功放板

## 当前边界

- `240 MHz` 主链路 setup 已收敛，但 PLL 仍有一条很小的 minimum pulse width 告警
- 真实引脚号必须以主人拿到的核心板原理图为准
