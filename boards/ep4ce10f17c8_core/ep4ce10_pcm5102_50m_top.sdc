create_clock -name clk50m -period 20.000000 [get_ports clk50m]
create_clock -name clk12m288 -period 81.380208 [get_ports clk12m288]
derive_pll_clocks
set_clock_groups -asynchronous -group {clk12m288} -group {clk50m}
derive_clock_uncertainty
set_false_path -from [get_ports {reset_n}]
