from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path("/home/huoshao/altera/fm_radio/output_files")
OUT = Path("/home/huoshao/FM_Radio/doc/figures/quartus")
OUT.mkdir(parents=True, exist_ok=True)


def read_text(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8", errors="ignore")


def parse_resource_summary(text: str) -> dict[str, tuple[int, int]]:
    patterns = {
        "Logic Elements": r"Total logic elements\s*:\s*([\d,]+)\s*/\s*([\d,]+)",
        "Combinational": r"Total combinational functions\s*:\s*([\d,]+)\s*/\s*([\d,]+)",
        "Registers": r"Dedicated logic registers\s*:\s*([\d,]+)\s*/\s*([\d,]+)",
        "Pins": r"Total pins\s*:\s*([\d,]+)\s*/\s*([\d,]+)",
        "Memory Bits": r"Total memory bits\s*:\s*([\d,]+)\s*/\s*([\d,]+)",
        "PLL": r"Total PLLs\s*:\s*([\d,]+)\s*/\s*([\d,]+)",
    }
    data: dict[str, tuple[int, int]] = {}
    for label, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            used = int(match.group(1).replace(",", ""))
            total = int(match.group(2).replace(",", ""))
            data[label] = (used, total)
    return data


def make_resource_figure() -> None:
    text = read_text("radio_top.fit.summary")
    resource_data = parse_resource_summary(text)
    labels = list(resource_data.keys())
    used = [resource_data[k][0] for k in labels]
    total = [resource_data[k][1] for k in labels]
    usage = [u / t * 100 if t else 0 for u, t in zip(used, total)]

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(11, 6.5), dpi=180)
    bars = ax.bar(labels, usage, color=["#355070", "#6d597a", "#b56576", "#e56b6f", "#eaac8b", "#4f772d"])
    ax.set_ylim(0, max(30, max(usage) * 1.25))
    ax.set_ylabel("Resource Utilization (%)")
    ax.set_title("Quartus II Synthesis Resource Utilization")

    for bar, u, t, p in zip(bars, used, total, usage):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.4,
            f"{u}/{t}\n{p:.1f}%",
            ha="center",
            va="bottom",
            fontsize=10,
        )

    fig.tight_layout()
    fig.savefig(OUT / "quartus_resource_usage.png", bbox_inches="tight")
    plt.close(fig)


def parse_timing_summary(text: str) -> pd.DataFrame:
    rows: list[dict[str, str | float]] = []
    current_type = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Type"):
            current_type = line.split(":", 1)[1].strip()
        elif line.startswith("Slack") and current_type:
            slack = float(line.split(":", 1)[1].strip())
            rows.append({"Type": current_type, "Slack": slack})
            current_type = None
    return pd.DataFrame(rows)


def make_timing_figure() -> None:
    text = read_text("radio_top.sta.summary")
    df = parse_timing_summary(text)
    colors = ["#bc4749" if v < 0 else "#386641" for v in df["Slack"]]

    fig, ax = plt.subplots(figsize=(12, 6.8), dpi=180)
    ax.barh(df["Type"], df["Slack"], color=colors)
    ax.axvline(0, color="#222222", linewidth=1.2)
    ax.set_xlabel("Slack (ns)")
    ax.set_title("TimeQuest Timing Summary")
    ax.invert_yaxis()

    for i, value in enumerate(df["Slack"]):
        offset = 0.08 if value >= 0 else -0.08
        ha = "left" if value >= 0 else "right"
        ax.text(value + offset, i, f"{value:.3f}", va="center", ha=ha, fontsize=9)

    fig.tight_layout()
    fig.savefig(OUT / "quartus_timing_summary.png", bbox_inches="tight")
    plt.close(fig)


def parse_pin_rows(text: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        if " : " not in line:
            continue
        if line.startswith(" --") or line.startswith("---") or line.startswith("Pin Name"):
            continue
        parts = [p.strip() for p in line.split(":")]
        if len(parts) < 7:
            continue
        name, location, direction, io_std, voltage, bank, assigned = parts[:7]
        if assigned != "Y":
            continue
        rows.append(
            {
                "Signal": name,
                "Location": location,
                "Direction": direction,
                "Bank": bank,
            }
        )
    return pd.DataFrame(rows)


def make_pin_figure() -> None:
    text = read_text("radio_top.pin")
    df = parse_pin_rows(text)
    focus = df[
        df["Signal"].str.contains(r"^clk$|^reset$|demodulated", regex=True)
    ].copy()
    focus["Order"] = focus["Signal"].map(
        lambda x: 0 if x == "clk" else 1 if x == "reset" else 2
    )
    focus = focus.sort_values(["Order", "Location", "Signal"]).drop(columns=["Order"])

    fig, ax = plt.subplots(figsize=(12, 8.5), dpi=180)
    ax.axis("off")
    ax.set_title("Key FPGA Pin Assignments", fontsize=16, pad=14)

    table = ax.table(
        cellText=focus.values.tolist(),
        colLabels=list(focus.columns),
        cellLoc="center",
        loc="center",
        colColours=["#355070"] * len(focus.columns),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.35)

    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(color="white", weight="bold")
        else:
            cell.set_facecolor("#f7f7f7" if row % 2 else "#e9ecef")

    fig.tight_layout()
    fig.savefig(OUT / "quartus_key_pins.png", bbox_inches="tight")
    plt.close(fig)


def write_readme() -> None:
    text = """# Quartus 综合结果图片说明

本目录中的图片由 Quartus II 13.1 工程原始输出文件自动解析生成，数据来源均为真实综合结果，而非手工捏造。

## 图片列表

- `quartus_resource_usage.png`：根据 `radio_top.fit.summary` 生成，展示逻辑单元、组合逻辑、寄存器、引脚、存储位与 PLL 的资源占用率。
- `quartus_timing_summary.png`：根据 `radio_top.sta.summary` 生成，展示 TimeQuest 时序分析中的各工作角 Slack 结果。
- `quartus_key_pins.png`：根据 `radio_top.pin` 生成，展示论文中最相关的关键引脚，包括 `clk`、`reset` 与 `demodulated[15:0]` 输出。

## 原始数据路径

- `/home/huoshao/altera/fm_radio/output_files/radio_top.fit.summary`
- `/home/huoshao/altera/fm_radio/output_files/radio_top.sta.summary`
- `/home/huoshao/altera/fm_radio/output_files/radio_top.pin`

## 生成脚本

- `/home/huoshao/FM_Radio/tools/generate_quartus_figures.py`

## 复现命令

```bash
"/home/huoshao/miniconda3/bin/python3" "/home/huoshao/FM_Radio/tools/generate_quartus_figures.py"
```
"""
    (OUT / "README.md").write_text(text, encoding="utf-8")


def main() -> None:
    make_resource_figure()
    make_timing_figure()
    make_pin_figure()
    write_readme()


if __name__ == "__main__":
    main()
