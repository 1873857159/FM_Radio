#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path

from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def qn(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


def paragraph_text(node: etree._Element) -> str:
    return "".join(node.xpath(".//w:t/text()", namespaces=NS)).strip()


def find_first_paragraph(body: etree._Element, matcher) -> etree._Element | None:
    for child in body:
        if etree.QName(child).localname != "p":
            continue
        if matcher(child, paragraph_text(child)):
            return child
    return None


def make_run(
    text: str = "",
    *,
    east_asia_font: str | None = None,
    ascii_font: str = "Times New Roman",
    size: int | None = None,
    bold: bool = False,
) -> etree._Element:
    run = etree.Element(qn("r"))
    if east_asia_font or size or bold:
        rpr = etree.SubElement(run, qn("rPr"))
        fonts = etree.SubElement(rpr, qn("rFonts"))
        fonts.set(qn("ascii"), ascii_font)
        fonts.set(qn("hAnsi"), ascii_font)
        fonts.set(qn("cs"), "Times New Roman")
        if east_asia_font:
            fonts.set(qn("eastAsia"), east_asia_font)
        if bold:
            etree.SubElement(rpr, qn("b"))
        if size:
            sz = etree.SubElement(rpr, qn("sz"))
            sz.set(qn("val"), str(size))
            szcs = etree.SubElement(rpr, qn("szCs"))
            szcs.set(qn("val"), str(size))
    text_node = etree.SubElement(run, qn("t"))
    if text.startswith(" ") or text.endswith(" "):
        text_node.set(XML_SPACE, "preserve")
    text_node.text = text
    return run


def make_paragraph(
    text: str = "",
    *,
    style: str | None = None,
    align: str | None = None,
    page_break_before: bool = False,
    no_indent: bool = False,
    line: int | None = None,
    east_asia_font: str | None = None,
    size: int | None = None,
    bold: bool = False,
) -> etree._Element:
    paragraph = etree.Element(qn("p"))
    ppr = etree.SubElement(paragraph, qn("pPr"))
    if style:
        pstyle = etree.SubElement(ppr, qn("pStyle"))
        pstyle.set(qn("val"), style)
    if page_break_before:
        etree.SubElement(ppr, qn("pageBreakBefore"))
    if line is not None:
        spacing = etree.SubElement(ppr, qn("spacing"))
        spacing.set(qn("line"), str(line))
        spacing.set(qn("lineRule"), "auto")
    if no_indent:
        ind = etree.SubElement(ppr, qn("ind"))
        ind.set(qn("firstLine"), "0")
        ind.set(qn("firstLineChars"), "0")
        ind.set(qn("left"), "0")
        ind.set(qn("leftChars"), "0")
    if align:
        jc = etree.SubElement(ppr, qn("jc"))
        jc.set(qn("val"), align)
    paragraph.append(
        make_run(
            text,
            east_asia_font=east_asia_font,
            size=size,
            bold=bold,
        )
    )
    return paragraph


def make_page_break() -> etree._Element:
    paragraph = etree.Element(qn("p"))
    run = etree.SubElement(paragraph, qn("r"))
    br = etree.SubElement(run, qn("br"))
    br.set(qn("type"), "page")
    return paragraph


def build_declaration_pages() -> list[etree._Element]:
    return [
        make_paragraph("南华大学学位论文原创性声明", style="2"),
        make_paragraph(
            "本人声明：所呈交的毕业设计（论文）是在指导教师指导下独立完成的研究成果。除文中已经注明引用的内容外，本文不包含其他个人或集体已经发表或撰写过的研究成果，也不包含为获得南华大学或其他教育机构的学位、证书而使用过的材料。对本文研究作出贡献的个人和集体，均已在文中以明确方式标注并致谢。本人完全意识到本声明的法律后果由本人承担。",
            style="3",
        ),
        make_paragraph("作者签名：", style="3", no_indent=True),
        make_paragraph("日期：      年   月   日", style="3", no_indent=True),
        make_page_break(),
        make_paragraph("南华大学学位论文版权使用授权书", style="2"),
        make_paragraph(
            "本人完全了解学校关于保存、使用毕业设计（论文）的有关规定，同意学校保留并向有关部门或机构送交毕业设计（论文）的复印件和电子版，允许毕业设计（论文）被查阅、借阅和检索；学校可以采用影印、缩印、扫描或其他复制手段保存、汇编本毕业设计（论文）的全部或部分内容。",
            style="3",
        ),
        make_paragraph("作者签名：                          指导教师签名：", style="3", no_indent=True),
        make_paragraph(
            "日期：      年   月   日              日期：      年   月   日",
            style="3",
            no_indent=True,
        ),
        make_page_break(),
    ]


def build_introduction() -> list[etree._Element]:
    intro_1 = (
        "随着软件无线电和可重构数字硬件的发展，接收机关键处理环节正逐步由模拟域向数字域迁移。"
        "FM 广播接收链路包含下变频、抽取滤波、鉴频与音频输出等典型模块，既能够体现数字接收机的完整信号处理流程，"
        "又便于结合波形、频谱以及实际听感进行结果验证，因此具有较强的教学与工程研究价值。"
    )
    intro_2 = (
        "本文围绕 EP4CE10F17C8 FPGA 平台，构建了“参考音频源、FM 调制、数字接收解调、I2S 音频输出”板内闭环验证链路，"
        "完成 DDS 本振、IQ 正交下变频、三级 CIC 抽取、CORDIC 相位提取、微分鉴频及 PCM5102 音频输出等模块设计，"
        "并通过 ModelSim 仿真、Quartus 综合及时序分析和板级出声测试对系统功能进行验证，为后续接入真实射频前端和开展性能优化提供基础。"
    )
    return [
        make_paragraph("引言", style="2", page_break_before=True),
        make_paragraph(intro_1, style="3"),
        make_paragraph(intro_2, style="3"),
    ]


def insert_nodes(body: etree._Element, anchor: etree._Element, nodes: list[etree._Element]) -> None:
    index = body.index(anchor)
    for node in nodes:
        body.insert(index, deepcopy(node))
        index += 1


def strip_prefix(paragraph: etree._Element, prefix: str) -> None:
    texts = paragraph.xpath(".//w:t", namespaces=NS)
    if not texts:
        return
    full_text = "".join(t.text or "" for t in texts)
    if not full_text.startswith(prefix):
        return
    remaining = full_text[len(prefix) :]
    texts[0].text = remaining
    for node in texts[1:]:
        parent = node.getparent()
        if parent is not None:
            parent.getparent().remove(parent)


def ensure_update_fields(settings_root: etree._Element) -> None:
    update = settings_root.find("w:updateFields", namespaces=NS)
    if update is None:
        update = etree.Element(qn("updateFields"))
        settings_root.append(update)
    update.set(qn("val"), "true")


def main() -> None:
    parser = argparse.ArgumentParser(description="按南华大学模板补齐论文前置结构。")
    parser.add_argument("docx_path", type=Path)
    args = parser.parse_args()

    docx_path = args.docx_path
    temp_dir = Path(tempfile.mkdtemp(prefix="nh_thesis_adjust_"))
    extracted_dir = temp_dir / "unzipped"
    with zipfile.ZipFile(docx_path) as archive:
        archive.extractall(extracted_dir)

    document_path = extracted_dir / "word" / "document.xml"
    settings_path = extracted_dir / "word" / "settings.xml"

    document_root = etree.parse(str(document_path)).getroot()
    settings_root = etree.parse(str(settings_path)).getroot()
    body = document_root.xpath("/w:document/w:body", namespaces=NS)[0]

    if "南华大学学位论文原创性声明" not in etree.tostring(body, encoding="unicode"):
        first_node = body[0]
        insert_nodes(body, first_node, build_declaration_pages())

    abstract_anchor = find_first_paragraph(
        body, lambda _p, txt: txt.startswith("摘要：") or txt == "摘要"
    )
    if abstract_anchor is not None and not find_first_paragraph(body, lambda _p, txt: txt == "摘要"):
        insert_nodes(body, abstract_anchor, [make_paragraph("摘要", style="2")])
        strip_prefix(abstract_anchor, "摘要：")

    english_anchor = find_first_paragraph(
        body, lambda _p, txt: txt.startswith("ABSTRACT:") or txt == "ABSTRACT"
    )
    if english_anchor is not None and not find_first_paragraph(body, lambda _p, txt: txt == "ABSTRACT"):
        insert_nodes(body, english_anchor, [make_paragraph("ABSTRACT", style="2")])
        strip_prefix(english_anchor, "ABSTRACT:")

    first_chapter = find_first_paragraph(
        body,
        lambda p, txt: (
            p.xpath("./w:pPr/w:pStyle/@w:val", namespaces=NS) == ["2"]
            and txt.replace(" ", "").startswith("1绪论")
        ),
    )
    if first_chapter is not None and not find_first_paragraph(body, lambda _p, txt: txt == "引言"):
        insert_nodes(body, first_chapter, build_introduction())

    ensure_update_fields(settings_root)

    etree.ElementTree(document_root).write(
        str(document_path), encoding="UTF-8", xml_declaration=True, standalone="yes"
    )
    etree.ElementTree(settings_root).write(
        str(settings_path), encoding="UTF-8", xml_declaration=True, standalone="yes"
    )

    output_path = temp_dir / "updated.docx"
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(extracted_dir.rglob("*")):
            if file_path.is_dir():
                continue
            archive.write(file_path, file_path.relative_to(extracted_dir).as_posix())

    shutil.copyfile(output_path, docx_path)
    shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()
