create_clock -name clk240m -period 4.166667 [get_ports clk240m]
create_clock -name clk12m288 -period 81.380208 [get_ports clk12m288]
set_clock_groups -asynchronous -group {clk240m} -group {clk12m288}
derive_clock_uncertainty
set_false_path -from [get_ports {reset_n}]
