create_clock -name clk50m -period 20.000000 [get_ports clk50m]
derive_pll_clocks
set_clock_groups -asynchronous \
  -group [get_clocks {inst_pll_50m_to_240m|altpll_component|auto_generated|pll1|clk[0]}] \
  -group [get_clocks {inst_pll_50m_to_240m|altpll_component|auto_generated|pll1|clk[1]}]
derive_clock_uncertainty
set_false_path -from [get_ports {reset_n}]

proc apply_ce_multicycle {setup_cycles from_pattern to_pattern} {
  set from_regs [get_registers $from_pattern]
  set to_regs   [get_registers $to_pattern]

  if {([get_collection_size $from_regs] > 0) && ([get_collection_size $to_regs] > 0)} {
    set hold_cycles [expr {$setup_cycles - 1}]
    set_multicycle_path -setup $setup_cycles -from $from_regs -to $to_regs
    set_multicycle_path -hold  $hold_cycles  -from $from_regs -to $to_regs
  }
}

# audio_rom_source and the FM deviation pipeline only update at 32 kHz.
apply_ce_multicycle 7500 {*|inst_audio_rom_source|*} {*|inst_fm_modulator|audio_hold[*]}
apply_ce_multicycle 7500 {*|inst_fm_modulator|audio_hold[*]} {*|inst_fm_modulator|deviation_product_reg[*]}
apply_ce_multicycle 7500 {*|inst_fm_modulator|deviation_product_reg[*]} {*|inst_fm_modulator|phase_step_reg[*]}

# The discriminator chain is clock-enabled at 960 kHz.
apply_ce_multicycle 250 {*|inst_cordic|*} {*|inst_cordic|*}
apply_ce_multicycle 250 {*|inst_cordic|*} {*|inst_differentiator|*}
apply_ce_multicycle 250 {*|inst_cordic|*} {*|filter_audio|i_del[*]}
apply_ce_multicycle 250 {*|inst_differentiator|*} {*|filter_audio|i_del[*]}
apply_ce_multicycle 250 {*|If2_disc[*]} {*|inst_cordic|*}
apply_ce_multicycle 250 {*|Qf2_disc[*]} {*|inst_cordic|*}
apply_ce_multicycle 250 {*|inst_clk960k|en} {*|inst_cordic|*}
apply_ce_multicycle 250 {*|inst_clk960k|en} {*|filter_I2|d_dif[*]}
apply_ce_multicycle 250 {*|inst_clk960k|en} {*|filter_I2|d_del[*]}
apply_ce_multicycle 250 {*|inst_clk960k|en} {*|filter_Q2|d_dif[*]}
apply_ce_multicycle 250 {*|inst_clk960k|en} {*|filter_Q2|d_del[*]}
apply_ce_multicycle 250 {*|inst_clk960k|en} {*|filter_audio|i_del[*]}
apply_ce_multicycle 250 {*|filter_audio|i_del[*]} {*|filter_audio|i_del[*]}

# The second CIC stage comb sections only update at 960 kHz.
apply_ce_multicycle 250 {*|filter_I2|i_del[*]} {*|filter_I2|d_dif[*]}
apply_ce_multicycle 250 {*|filter_I2|d_del[*]} {*|filter_I2|d_dif[*]}
apply_ce_multicycle 250 {*|filter_I2|d_dif[*]} {*|filter_I2|d_dif[*]}
apply_ce_multicycle 250 {*|filter_I2|d_dif[*]} {*|filter_I2|d_del[*]}
apply_ce_multicycle 250 {*|filter_Q2|i_del[*]} {*|filter_Q2|d_dif[*]}
apply_ce_multicycle 250 {*|filter_Q2|d_del[*]} {*|filter_Q2|d_dif[*]}
apply_ce_multicycle 250 {*|filter_Q2|d_dif[*]} {*|filter_Q2|d_dif[*]}
apply_ce_multicycle 250 {*|filter_Q2|d_dif[*]} {*|filter_Q2|d_del[*]}

# The second CIC stage integrators only update at 48 MHz.
apply_ce_multicycle 5 {*|filter_I2|i_del[*]} {*|filter_I2|i_del[*]}
apply_ce_multicycle 5 {*|filter_Q2|i_del[*]} {*|filter_Q2|i_del[*]}
apply_ce_multicycle 5 {*|inst_clk48m|en} {*|filter_I2|i_del[*]}
apply_ce_multicycle 5 {*|inst_clk48m|en} {*|filter_Q2|i_del[*]}

# The audio CIC comb section only updates on the 32 kHz decimated sample.
apply_ce_multicycle 7500 {*|filter_audio|i_del[*]} {*|filter_audio|d_dif[*]}
apply_ce_multicycle 7500 {*|filter_audio|d_del[*]} {*|filter_audio|d_dif[*]}
apply_ce_multicycle 7500 {*|filter_audio|d_dif[*]} {*|filter_audio|d_dif[*]}
apply_ce_multicycle 7500 {*|filter_audio|d_dif[*]} {*|filter_audio|d_del[*]}
apply_ce_multicycle 7500 {*|inst_clk48m|en} {*|inst_audio_rom_source|*}
apply_ce_multicycle 7500 {*|inst_clk960k|en} {*|inst_audio_rom_source|*}
apply_ce_multicycle 7500 {*|inst_clk32k|en} {*|inst_audio_rom_source|*}
apply_ce_multicycle 7500 {*|inst_clk48m|en} {*|inst_audio_rom_source|*porta_address_reg*}
apply_ce_multicycle 7500 {*|inst_clk960k|en} {*|inst_audio_rom_source|*porta_address_reg*}
apply_ce_multicycle 7500 {*|inst_clk32k|en} {*|inst_audio_rom_source|*porta_address_reg*}
apply_ce_multicycle 7500 {*|inst_clk32k|en} {*|inst_fm_modulator|audio_hold[*]}
apply_ce_multicycle 7500 {*|inst_clk32k|en} {*|inst_fm_modulator|deviation_product_reg[*]}
apply_ce_multicycle 7500 {*|inst_clk32k|en} {*|inst_fm_modulator|phase_step_reg[*]}
apply_ce_multicycle 7500 {*|inst_clk32k|en} {*|filter_audio|d_dif[*]}
apply_ce_multicycle 7500 {*|inst_clk32k|en} {*|filter_audio|d_del[*]}
apply_ce_multicycle 7500 {*|inst_clk32k|en} {*|inst_i2s_tx_3wire|pending_sample[*]}
