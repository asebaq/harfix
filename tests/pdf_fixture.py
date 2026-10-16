"""Build tiny PDFs whose text layer maps byte codes to Arabic through a ToUnicode CMap.

A correct CMap gives a clean text layer; a shuffled CMap reproduces the "renders fine,
extracts as the wrong letters" fault without needing any font files.
"""

from __future__ import annotations

from harfix.normalize import ARABIC_LETTERS

LETTERS = sorted(ARABIC_LETTERS)
# Byte code for each letter; 0x20 stays a space.
CODES = {letter: 0x21 + i for i, letter in enumerate(LETTERS)}


def _to_unicode(mapping: dict[int, str]) -> bytes:
    entries = "\n".join(f"<{code:02X}> <{ord(ch):04X}>" for code, ch in sorted(mapping.items()))
    return (
        "/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        "/CMapName /Test-UCS def /CMapType 2 def\n"
        "1 begincodespacerange <00> <FF> endcodespacerange\n"
        f"{len(mapping)} beginbfchar\n{entries}\nendbfchar\n"
        "endcmap CMapName currentdict /CMap defineresource pop end end\n"
    ).encode("ascii")


def _encode(text: str) -> str:
    return "".join(
        f"{0x20 if ch == ' ' else CODES[ch]:02X}" for ch in text if ch == " " or ch in CODES
    )


def build_pdf(pages: list[list[tuple[str, str]]], letter_maps: dict[str, dict[str, str]]) -> bytes:
    """`pages`: per page, (font name, text line) pairs; an empty page gets an image only.

    `letter_maps[font]` says which letter each letter's code extracts as.
    """
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    def stream(data: bytes, extra: str = "") -> bytes:
        return f"<< /Length {len(data)} {extra}>>\nstream\n".encode() + data + b"\nendstream"

    font_refs = {}
    for name, letter_map in letter_maps.items():
        mapping = {0x20: " "} | {CODES[letter]: shown for letter, shown in letter_map.items()}
        cmap = add(stream(_to_unicode(mapping)))
        widths = " ".join(["600"] * (len(LETTERS) + 1))
        descriptor = add(
            f"<< /Type /FontDescriptor /FontName /{name} /Flags 32 /FontBBox [0 -200 1000 800] "
            "/ItalicAngle 0 /Ascent 800 /Descent -200 /CapHeight 700 /StemV 80 >>".encode()
        )
        font_refs[name] = add(
            f"<< /Type /Font /Subtype /Type1 /BaseFont /{name} /FirstChar 32 "
            f"/LastChar {0x20 + len(LETTERS)} /Widths [{widths}] "
            f"/FontDescriptor {descriptor} 0 R /ToUnicode {cmap} 0 R >>".encode()
        )
    image = add(
        stream(
            b"\x80",
            "/Type /XObject /Subtype /Image /Width 1 /Height 1 "
            "/ColorSpace /DeviceGray /BitsPerComponent 8 ",
        )
    )
    fonts = " ".join(f"/{name} {ref} 0 R" for name, ref in font_refs.items())

    page_refs = []
    pages_ref = len(objects) + 1 + 2 * len(pages)  # allocated after every page and content
    for lines in pages:
        if lines:
            ops = ["BT", "14 TL", "40 780 Td"]
            for font, text in lines:
                ops.append(f"/{font} 9 Tf <{_encode(text)}> Tj T*")
            ops.append("ET")
        else:
            ops = ["q 200 0 0 200 100 500 cm /Im1 Do Q"]
        content = add(stream("\n".join(ops).encode("ascii")))
        page_refs.append(
            add(
                f"<< /Type /Page /Parent {pages_ref} 0 R /MediaBox [0 0 595 842] "
                f"/Contents {content} 0 R /Resources << /Font << {fonts} >> "
                f"/XObject << /Im1 {image} 0 R >> >> >>".encode()
            )
        )
    kids = " ".join(f"{ref} 0 R" for ref in page_refs)
    assert add(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_refs)} >>".encode()) == pages_ref
    catalog = add(f"<< /Type /Catalog /Pages {pages_ref} 0 R >>".encode())

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R >>\n".encode()
    out += f"startxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
