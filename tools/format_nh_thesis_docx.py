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


def get_or_add(parent: etree._Element, tag: str) -> etree._Element:
    child = parent.find(f"w:{tag}", namespaces=NS)
    if child is None:
        child = etree.SubElement(parent, qn(tag))
    return child


def clear_children(parent: etree._Element, tags: list[str]) -> None:
    for tag in tags:
        for node in parent.findall(f"w:{tag}", namespaces=NS):
            parent.remove(node)


def set_style(
    styles_root: etree._Element,
    style_id: str,
    *,
    east_asia: str,
    ascii_font: str = "Times New Roman",
    size: int,
    bold: bool,
    jc: str | None,
    line: int = 360,
    first_line: int | None = None,
    hanging: int | None = None,
    outline: int | None = None,
) -> None:
    style = styles_root.xpath(f'/w:styles/w:style[@w:styleId="{style_id}"]', namespaces=NS)
    if not style:
        style = etree.SubElement(styles_root, qn("style"))
        style.set(qn("type"), "paragraph")
        style.set(qn("styleId"), style_id)
    else:
        style = style[0]

    ppr = get_or_add(style, "pPr")
    clear_children(ppr, ["jc", "spacing", "ind", "outlineLvl"])
    if jc:
        node = etree.SubElement(ppr, qn("jc"))
        node.set(qn("val"), jc)
    spacing = etree.SubElement(ppr, qn("spacing"))
    spacing.set(qn("line"), str(line))
    spacing.set(qn("lineRule"), "auto")
    if first_line is not None or hanging is not None:
        ind = etree.SubElement(ppr, qn("ind"))
        if first_line is not None:
            ind.set(qn("firstLine"), str(first_line))
            ind.set(qn("firstLineChars"), "200" if first_line else "0")
        if hanging is not None:
            ind.set(qn("hanging"), str(hanging))
            ind.set(qn("hangingChars"), "150")
    if outline is not None:
        out = etree.SubElement(ppr, qn("outlineLvl"))
        out.set(qn("val"), str(outline))

    rpr = get_or_add(style, "rPr")
    clear_children(rpr, ["rFonts", "b", "sz", "szCs"])
    fonts = etree.SubElement(rpr, qn("rFonts"))
    fonts.set(qn("ascii"), ascii_font)
    fonts.set(qn("hAnsi"), ascii_font)
    fonts.set(qn("eastAsia"), east_asia)
    fonts.set(qn("cs"), "Times New Roman")
    if bold:
        etree.SubElement(rpr, qn("b"))
    sz = etree.SubElement(rpr, qn("sz"))
    sz.set(qn("val"), str(size))
    szcs = etree.SubElement(rpr, qn("szCs"))
    szcs.set(qn("val"), str(size))


def paragraph_text(p: etree._Element) -> str:
    return "".join(p.xpath(".//w:t/text()", namespaces=NS)).strip()


def set_pstyle(p: etree._Element, style_id: str) -> None:
    ppr = p.find("w:pPr", namespaces=NS)
    if ppr is None:
        ppr = etree.Element(qn("pPr"))
        p.insert(0, ppr)
    pstyle = ppr.find("w:pStyle", namespaces=NS)
    if pstyle is None:
        pstyle = etree.Element(qn("pStyle"))
        ppr.insert(0, pstyle)
    pstyle.set(qn("val"), style_id)


def remove_paragraph_numbering(p: etree._Element) -> None:
    ppr = p.find("w:pPr", namespaces=NS)
    if ppr is None:
        return
    for num_pr in ppr.findall("w:numPr", namespaces=NS):
        ppr.remove(num_pr)


def replace_text(p: etree._Element, new_text: str) -> None:
    texts = p.xpath(".//w:t", namespaces=NS)
    if not texts:
        return
    texts[0].text = new_text
    for t in texts[1:]:
        t.text = ""


def normalize_caption_text(text: str) -> str:
    match = re.match(r"^([图表])\s*(\d+)\.(\d+)\s*[：:]\s*(.+)$", text)
    if not match:
        return text
    kind, chapter, number, title = match.groups()
    return f"{kind}{chapter}.{number} {title.strip()}"


def apply_run_formatting(p: etree._Element, *, east_asia: str, ascii_font: str, size: int, bold: bool | None = None) -> None:
    for r in p.xpath(".//w:r", namespaces=NS):
        rpr = r.find("w:rPr", namespaces=NS)
        if rpr is None:
            rpr = etree.Element(qn("rPr"))
            r.insert(0, rpr)
        clear_children(rpr, ["rFonts", "sz", "szCs"])
        fonts = etree.Element(qn("rFonts"))
        fonts.set(qn("ascii"), ascii_font)
        fonts.set(qn("hAnsi"), ascii_font)
        fonts.set(qn("eastAsia"), east_asia)
        fonts.set(qn("cs"), "Times New Roman")
        rpr.insert(0, fonts)
        sz = etree.SubElement(rpr, qn("sz"))
        sz.set(qn("val"), str(size))
        szcs = etree.SubElement(rpr, qn("szCs"))
        szcs.set(qn("val"), str(size))
        if bold is not None:
            for b in rpr.findall("w:b", namespaces=NS):
                rpr.remove(b)
            if bold:
                etree.SubElement(rpr, qn("b"))


def make_first_label_bold(
    p: etree._Element,
    label_pattern: str,
    *,
    label_east_asia: str = "宋体",
    rest_east_asia: str = "宋体",
    ascii_font: str = "Times New Roman",
) -> None:
    txt = paragraph_text(p)
    match = re.match(label_pattern, txt)
    if not match:
        return
    label = match.group(0)
    rest = txt[len(label):]
    for r in p.xpath("./w:r", namespaces=NS):
        p.remove(r)
    for text, bold in [(label, True), (rest, False)]:
        r = etree.SubElement(p, qn("r"))
        rpr = etree.SubElement(r, qn("rPr"))
        fonts = etree.SubElement(rpr, qn("rFonts"))
        fonts.set(qn("ascii"), ascii_font)
        fonts.set(qn("hAnsi"), ascii_font)
        fonts.set(qn("eastAsia"), label_east_asia if bold else rest_east_asia)
        fonts.set(qn("cs"), "Times New Roman")
        if bold:
            etree.SubElement(rpr, qn("b"))
        sz = etree.SubElement(rpr, qn("sz"))
        sz.set(qn("val"), "24")
        szcs = etree.SubElement(rpr, qn("szCs"))
        szcs.set(qn("val"), "24")
        t = etree.SubElement(r, qn("t"))
        t.text = text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("docx", type=Path)
    args = parser.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="nh_format_"))
    work = tmp / "work"
    with zipfile.ZipFile(args.docx) as z:
        z.extractall(work)

    styles_path = work / "word" / "styles.xml"
    document_path = work / "word" / "document.xml"
    styles_root = etree.parse(str(styles_path)).getroot()
    document_root = etree.parse(str(document_path)).getroot()
    body = document_root.xpath("/w:document/w:body", namespaces=NS)[0]

    set_style(styles_root, "1", east_asia="宋体", size=24, bold=False, jc="both", line=360)
    set_style(styles_root, "2", east_asia="黑体", ascii_font="黑体", size=32, bold=True, jc="center", line=360, outline=0)
    set_style(styles_root, "3", east_asia="宋体", size=24, bold=False, jc="both", line=360, first_line=480, outline=9)
    set_style(styles_root, "4", east_asia="黑体", ascii_font="黑体", size=30, bold=True, jc="left", line=360, outline=1)
    set_style(styles_root, "5", east_asia="黑体", ascii_font="黑体", size=28, bold=True, jc="left", line=360, outline=2)
    set_style(styles_root, "52", east_asia="楷体", size=24, bold=False, jc="both", line=360, outline=9)
    set_style(styles_root, "53", east_asia="宋体", size=24, bold=False, jc="both", line=360, first_line=0, outline=9)
    set_style(styles_root, "54", east_asia="楷体", size=24, bold=False, jc="both", line=360, outline=9)
    set_style(styles_root, "55", east_asia="宋体", size=24, bold=False, jc="both", line=360, outline=9)
    set_style(styles_root, "59", east_asia="宋体", size=21, bold=False, jc="center", line=360, outline=9)
    set_style(styles_root, "60", east_asia="宋体", size=21, bold=False, jc="both", line=360, hanging=315, outline=9)
    set_style(styles_root, "62", east_asia="宋体", size=21, bold=False, jc="center", line=360, outline=9)

    in_refs = False
    ref_no = 1
    abstract_body_seen = False
    english_abstract_body_seen = False
    for p in body.xpath("./w:p", namespaces=NS):
        text = paragraph_text(p)
        if not text:
            continue

        if text == "参考文献":
            in_refs = True
            continue
        if in_refs and text in {"致谢", "附录"}:
            in_refs = False

        if re.match(r"^图\s*\d+\.\d+\s*[：:]", text):
            set_pstyle(p, "59")
            replace_text(p, normalize_caption_text(text))
            apply_run_formatting(p, east_asia="宋体", ascii_font="Times New Roman", size=21, bold=False)
        elif re.match(r"^表\s*\d+\.\d+\s*[：:]", text):
            set_pstyle(p, "62")
            replace_text(p, normalize_caption_text(text))
            apply_run_formatting(p, east_asia="宋体", ascii_font="Times New Roman", size=21, bold=False)

        if in_refs and text != "参考文献" and text not in {"致谢", "附录"}:
            set_pstyle(p, "60")
            remove_paragraph_numbering(p)
            text_without_no = re.sub(r"^\[\d+\]\s*", "", paragraph_text(p))
            replace_text(p, f"[{ref_no}] {text_without_no}")
            apply_run_formatting(p, east_asia="宋体", ascii_font="Times New Roman", size=21, bold=False)
            ref_no += 1

        if "并结合系统集成需要补充了参考音频源" in paragraph_text(p):
            replace_text(
                p,
                paragraph_text(p).replace("并结合系统集成需要补充了参考音频源", "并结合系统集成需求进一步设计了参考音频源"),
            )

        style_vals = p.xpath("./w:pPr/w:pStyle/@w:val", namespaces=NS)
        style_id = style_vals[0] if style_vals else ""

        if style_id == "52" and not abstract_body_seen:
            abstract_body_seen = True
            if not paragraph_text(p).startswith("摘要："):
                replace_text(p, f"摘要：{paragraph_text(p)}")
            make_first_label_bold(p, r"^摘要：", label_east_asia="宋体", rest_east_asia="楷体")
        elif style_id == "53" and not english_abstract_body_seen:
            english_abstract_body_seen = True
            if not paragraph_text(p).startswith("ABSTRACT:"):
                replace_text(p, f"ABSTRACT: {paragraph_text(p)}")
            make_first_label_bold(p, r"^ABSTRACT:", label_east_asia="宋体", rest_east_asia="宋体")
        elif paragraph_text(p).startswith("关键词："):
            set_pstyle(p, "54")
            make_first_label_bold(p, r"^关键词：", label_east_asia="宋体", rest_east_asia="楷体")
        elif paragraph_text(p).startswith("Keywords:"):
            set_pstyle(p, "55")
            apply_run_formatting(p, east_asia="宋体", ascii_font="Times New Roman", size=24, bold=False)
            make_first_label_bold(p, r"^Keywords:", label_east_asia="宋体", rest_east_asia="宋体")

    etree.ElementTree(styles_root).write(str(styles_path), encoding="UTF-8", xml_declaration=True, standalone=True)
    etree.ElementTree(document_root).write(str(document_path), encoding="UTF-8", xml_declaration=True, standalone=True)

    output = tmp / "updated.docx"
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for file in sorted(work.rglob("*")):
            if file.is_file():
                z.write(file, file.relative_to(work).as_posix())
    shutil.copyfile(output, args.docx)
    shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
