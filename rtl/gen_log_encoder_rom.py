#!/usr/bin/env python3

"""Generate the ROM contents used by log_encoder.sv."""

from pathlib import Path


ROM_DEPTH = 1 << 12


def encode_magnitude(scaled_abs: int) -> int:
    if scaled_abs == 0:
        return 0

    segment = 0
    while segment < 7 and scaled_abs >= 16 * ((1 << (segment + 1)) - 1):
        segment += 1

    lower_bound = 16 * ((1 << segment) - 1)
    step = (scaled_abs - lower_bound) >> segment
    step = min(step, 15)
    return (segment << 4) | step


def write_hex() -> None:
    output = Path(__file__).with_name("log_encoder_rom.hex")
    with output.open("w", encoding="ascii") as fh:
        for addr in range(ROM_DEPTH):
            fh.write(f"{encode_magnitude(addr):02x}\n")


def write_mem() -> None:
    output = Path(__file__).with_name("log_encoder_rom.mem")
    with output.open("w", encoding="ascii") as fh:
        for addr in range(ROM_DEPTH):
            fh.write(f"{encode_magnitude(addr):07b}\n")


def write_mif() -> None:
    output = Path(__file__).with_name("log_encoder_rom.mif")
    with output.open("w", encoding="ascii") as fh:
        fh.write(f"DEPTH = {ROM_DEPTH};\n")
        fh.write("WIDTH = 7;\n")
        fh.write("ADDRESS_RADIX = HEX;\n")
        fh.write("DATA_RADIX = HEX;\n")
        fh.write("CONTENT BEGIN\n")
        for addr in range(ROM_DEPTH):
            fh.write(f"    {addr:03x} : {encode_magnitude(addr):02x};\n")
        fh.write("END;\n")


def main() -> None:
    write_hex()
    write_mem()
    write_mif()


if __name__ == "__main__":
    main()
