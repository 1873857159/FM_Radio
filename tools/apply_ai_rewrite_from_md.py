#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


def qn(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


def paragraph_text(p: etree._Element) -> str:
    return "".join(p.xpath(".//w:t/text()", namespaces=NS)).strip()


def replace_paragraph_text(p: etree._Element, text: str) -> None:
    text_nodes = p.xpath(".//w:t", namespaces=NS)
    if text_nodes:
        text_nodes[0].text = text
        for node in text_nodes[1:]:
            node.text = ""
        return

    run = etree.SubElement(p, qn("r"))
    t = etree.SubElement(run, qn("t"))
    t.text = text


def load_pairs(md_path: Path) -> list[tuple[str, str, str]]:
    text = md_path.read_text(encoding="utf-8")
    pairs: list[tuple[str, str, str]] = []
    for block in re.split(r"\n## 片段 ", text)[1:]:
        head = block.split("\n", 1)[0].strip()
        match = re.search(
            r"原文：\n(.+?)\n\n修改后：\n(.+?)(?=\n\n##|\Z)",
            "## 片段 " + block,
            re.S,
        )
        if not match:
            raise RuntimeError(f"无法解析片段：{head}")
        pairs.append((head, match.group(1).strip(), match.group(2).strip()))
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description="将 AIGC 对照改写稿回填到 docx。")
    parser.add_argument("docx", type=Path)
    parser.add_argument("rewrite_md", type=Path)
    args = parser.parse_args()

    pairs = load_pairs(args.rewrite_md)
    tmp = Path(tempfile.mkdtemp(prefix="ai_rewrite_docx_"))
    work = tmp / "work"
    with zipfile.ZipFile(args.docx) as archive:
        archive.extractall(work)

    document_path = work / "word" / "document.xml"
    root = etree.parse(str(document_path)).getroot()
    paragraphs = root.xpath("/w:document/w:body/w:p", namespaces=NS)

    replaced: list[str] = []
    missing: list[str] = []
    for head, old, new in pairs:
        found = False
        for p in paragraphs:
            if paragraph_text(p) == old:
                replace_paragraph_text(p, new)
                replaced.append(head)
                found = True
                break
        if not found:
            missing.append(head)

    if missing:
        raise RuntimeError(f"以下片段未能在 docx 中精确匹配：{', '.join(missing)}")

    etree.ElementTree(root).write(
        str(document_path), encoding="UTF-8", xml_declaration=True, standalone=True
    )

    output = tmp / "updated.docx"
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(work.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(work).as_posix())

    shutil.copyfile(output, args.docx)
    shutil.rmtree(tmp)
    print(f"replaced={len(replaced)}")
    for item in replaced:
        print(item)


if __name__ == "__main__":
    main()
