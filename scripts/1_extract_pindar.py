# a_extract.py
'''
First step of the XML processing pipeline for the accentual responsion project, Urdatorn/aristophanis-cantica.

Takes a TEI XML file and extracts manually chosen responding strophes, formatting them as <canticum> elements with <strophe> and <antistrophe> children.
'''

input_file = "data/source/02_pythia.xml"
output_file = "data/raw/02_pythia_raw.xml"

import re
from lxml import etree

def transform_tei(input_file, output_file):
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}

    def extract_line_text(line):
        """Return the line text excluding seg[@rend='Marginalia'],
        turning <space/> into a literal space, ignoring <pb/> but
        always keeping element tails. Cleans ⸐ and collapses whitespace."""
        parts = []

        # Text before the first child
        if line.text:
            parts.append(line.text)

        for node in line.iter():
            if node is line:
                continue

            tag = etree.QName(node).localname if isinstance(node.tag, str) else None

            if tag == "seg" and node.get("rend") == "Marginalia":
                if node.tail:
                    parts.append(node.tail)
                continue

            if tag == "space":
                parts.append(" ")
                if node.tail:
                    parts.append(node.tail)
                continue

            if tag == "pb":
                if node.tail:
                    parts.append(node.tail)
                continue

            if node.text:
                parts.append(node.text)
            if node.tail:
                parts.append(node.tail)

        text = "".join(parts)
        # remove ⸐ chars
        text = text.replace("⸐", "")
        # normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    # Parse input
    tree = etree.parse(input_file)
    root = tree.getroot()

    # Build new TEI root
    new_root = etree.Element("TEI")
    new_header = etree.SubElement(new_root, "teiHeader")
    fileDesc = etree.SubElement(new_header, "fileDesc")
    titleStmt = etree.SubElement(fileDesc, "titleStmt")
    title = etree.SubElement(titleStmt, "title")
    title.text = "Pythia"
    author = etree.SubElement(titleStmt, "author")
    author.text = "Pindar"

    new_text = etree.SubElement(new_root, "text")
    new_body = etree.SubElement(new_text, "body")

    # All odes -> one canticum each
    odes = root.xpath("//tei:div[@type='Ode']", namespaces=ns)
    for canticum_index, ode in enumerate(odes, start=1):
        canticum = etree.SubElement(new_body, "canticum")
        responsion_id = f"py{canticum_index:02d}"

        strophe = None
        for line in ode.xpath(".//tei:l", namespaces=ns):
            has_marginalia = line.xpath(".//tei:seg[@rend='Marginalia']", namespaces=ns)
            if has_marginalia:
                strophe = etree.SubElement(
                    canticum,
                    "strophe",
                    type="strophe",
                    responsion=responsion_id,
                )

            if strophe is not None:
                l = etree.SubElement(strophe, "l", n=line.get("n"), metre="")
                l.text = extract_line_text(line)

        # If no marginalia at all
        if not canticum.findall("strophe"):
            strophe = etree.SubElement(
                canticum, "strophe", type="strophe", responsion=responsion_id
            )
            for line in ode.xpath(".//tei:l", namespaces=ns):
                l = etree.SubElement(strophe, "l", n=line.get("n"), metre="")
                l.text = extract_line_text(line)

        # --- Sanity check ---
        lengths = [len(s.findall("l")) for s in canticum.findall("strophe")]
        if lengths and len(set(lengths)) > 1:
            print(
                f"[WARNING] Canticum {canticum_index} has inconsistent strophe lengths: {lengths}"
            )

    # Write output
    out_tree = etree.ElementTree(new_root)
    out_tree.write(
        output_file,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True
    )

if __name__ == "__main__":
    transform_tei(input_file, output_file)



