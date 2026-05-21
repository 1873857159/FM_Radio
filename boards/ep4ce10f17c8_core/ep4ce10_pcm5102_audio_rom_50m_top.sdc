create_clock -name clk50m -period 20.000000 [get_ports clk50m]
create_clock -name clk12m288 -period 81.380208 [get_ports clk12m288]
derive_pll_clocks
set_clock_groups -asynchronous -group {clk12m288} -group [get_clocks {inst_pll_50m_to_240m|altpll_component|auto_generated|pll1|clk[0] inst_pll_50m_to_240m|altpll_component|auto_generated|pll1|clk[1]}]
set_clock_groups -asynchronous \
  -group [get_clocks {inst_pll_50m_to_240m|altpll_component|auto_generated|pll1|clk[0]}] \
  -group [get_clocks {inst_pll_50m_to_240m|altpll_component|auto_generated|pll1|clk[1]}]
derive_clock_uncertainty
set_false_path -from [get_ports {reset_n}]
