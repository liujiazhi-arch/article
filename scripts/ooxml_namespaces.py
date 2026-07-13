from __future__ import annotations

import xml.etree.ElementTree as ET


MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
IGNORABLE_NAMESPACES = {
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
    "w16": "http://schemas.microsoft.com/office/word/2018/wordml",
    "w16cex": "http://schemas.microsoft.com/office/word/2018/wordml/cex",
    "w16cid": "http://schemas.microsoft.com/office/word/2016/wordml/cid",
    "w16sdtdh": "http://schemas.microsoft.com/office/word/2020/wordml/sdtdatahash",
    "w16se": "http://schemas.microsoft.com/office/word/2015/wordml/symex",
    "wp14": "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing",
    "wpc": "http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas",
    "wpg": "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
    "wpi": "http://schemas.microsoft.com/office/word/2010/wordprocessingInk",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
}


def declare_ignorable_namespaces(document_root: ET.Element) -> None:
    ignorable = set(document_root.get(f"{{{MC_NS}}}Ignorable", "").split())
    for prefix, namespace in IGNORABLE_NAMESPACES.items():
        if prefix not in ignorable:
            continue
        ET.register_namespace(prefix, namespace)
        marker = f"{{{namespace}}}"
        namespace_used = any(
            element.tag.startswith(marker) or any(name.startswith(marker) for name in element.attrib)
            for element in document_root.iter()
        )
        if not namespace_used:
            document_root.set(f"xmlns:{prefix}", namespace)


def serialize_opc_root(root: ET.Element, namespace: str) -> bytes:
    ET.register_namespace("", namespace)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
