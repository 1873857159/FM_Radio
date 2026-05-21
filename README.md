# Simple FPGA only FM Radio

## Installation
```shell
git clone https://github.com/pbing/FM_Radio.git
cd FM_Radio
git submodule update --init
```
## Status

- FPGA proven.
- Core FM receive chain adapted for Cyclone IV E + Quartus II 13.1 simulation/synthesis flow.
- Current mainline: `EP4CE10F17C8 + PCM5102 + audio ROM FM loopback`.
- Progress summary: `doc/project_progress.md`

## Docs

- Current status: `doc/project_progress.md`
- Single recommended mainline: `doc/current_mainline.md`
- Board bring-up checklist: `boards/ep4ce10f17c8_core/bringup_checklist.md`
- Archived notes: `doc/archive/README.md`

## Thesis Support

- Reproducible ModelSim batch entry point: `sim/run_modelsim.sh`
- Thesis evidence summary: `doc/thesis_evidence.md`
- Figure generation script: `doc/generate_thesis_figures.py`

## Audio Compare

- Sample dump and compare workflow: `analysis/audio_compare/README.md`
- Dump source/output samples from simulation: `./sim/run_modelsim.sh fm_loopback_audio_rom_dump`
- Generate waveform / spectrum / spectrogram figures:
  `python3 ./analysis/audio_compare/compare_from_dump.py --dump ./sim/fm_loopback_audio_rom/outputs/fm_loopback_audio_rom_dump_samples.txt --output-dir ./analysis/audio_compare/outputs`
- Build a defense-ready package with figures, WAVs, tables and talking points:
  `./analysis/audio_compare/build_defense_package.sh`

## Used Parts
- [Altera Cyclone II FPGA Starter Development Kit](http://www.terasic.com.tw/cgi-bin/page/archive.pl?Language=English&CategoryNo=53&No=83).

## Credits

1. XRadio: A rockin' FPGA-only Radio for Teaching System Design,
   [XCell Journal, issue 84](http://www.xilinx.com/publications/archives/xcell/Xcell84.pdf),
   pp. 28-33.
2. [emard/flearadio](https://github.com/emard/flearadio), Digital FM Radio Receiver for FPGA.
