# a_extract.py
'''
First step of the XML processing pipeline for the accentual responsion project, Urdatorn/aristophanis-cantica.

Takes a TEI XML file and extracts manually chosen responding strophes, formatting them as <canticum> elements with <strophe> and <antistrophe> children.
'''

from lxml import etree
import re

################
### SETTINGS ###
################

cantica = [
    [(290, 295), (296, 301)],
    [(302, 308), (309, 315)],
]

responsion_prefix = "pl"
responsion_counter = 1
xml_file = "data/source/11pl.xml"
output_file = f"data/raw/responsion_{responsion_prefix}_raw.xml"
author = "Aristophanes"
title = "Plutus"

################
################
################


def is_in_range(line_number, start, end):
    """
    Check if a line number (potentially alphanumeric) is in a given range.

    Args:
        line_number (str): The `n` attribute value (e.g., "41a").
        start (int): The start of the range.
        end (int): The end of the range.

    Returns:
        bool: True if the numeric part of `line_number` is in the range, False otherwise.
    """
    try:
        # Extract numeric part of the line number using regex
        numeric_part = re.match(r'\d+', line_number)
        if numeric_part:
            numeric_value = int(numeric_part.group())
            return start <= numeric_value <= end
        return False
    except (ValueError, AttributeError):
        # Handle cases where line_number is invalid
        return False


#################
### MAIN CODE ###
#################

tree = etree.parse(xml_file)

# 1) Remove namespace prefixes directly from parsed XML
for elem in tree.getiterator():
    elem.tag = etree.QName(elem).localname  # Strip namespace prefix

# 2a) Remove all <pb/> and <lb/> elements
for pb in tree.xpath("//pb"):
    pb.getparent().remove(pb)
for lb in tree.xpath("//lb"):
    lb.getparent().remove(lb)

# 2b) Remove all <hi> elements
for hi in tree.xpath("//hi"):
    parent = hi.getparent()
    if hi.tail is not None:
        if len(hi) > 0:  # if hi has children
            last_child = hi[-1]
            last_child.tail = (last_child.tail or '') + hi.tail
        else:  # if hi has no children
            hi.text = (hi.text or '') + hi.tail
    previous = hi.getprevious()
    if previous is not None:
        previous.tail = (previous.tail or '') + (hi.text or '')
    else:
        parent.text = (parent.text or '') + (hi.text or '')
    parent.remove(hi)

# -----------------------------------------------------------------------------
# 3) Remove <label type="speaker" ...> from within <l>; 
#    if label text is not "Str." or "Ant.", set speaker= on <l>.
# -----------------------------------------------------------------------------
for line_el in tree.xpath("//body//l"):
    labels = line_el.xpath("./label[@type='speaker']")
    for label_el in labels:
        label_text = (label_el.text or "").strip()
        # If label text is neither "Str." nor "Ant.", add speaker= to <l>
        if label_text and label_text not in ["Str.", "Ant."]:
            if "speaker" not in line_el.attrib:
                line_el.set("speaker", label_text)
        # Remove the label element either way
        line_el.remove(label_el)

# -----------------------------------------------------------------------------
# 4) Update any remaining <label> elements (those not inside <l> or 
#    not type="speaker" or unmatched) to be self-closing with speaker= attribute
# -----------------------------------------------------------------------------
for label in tree.xpath("//label"):
    speaker_text = (label.text or "").strip()
    label.attrib.clear()
    label.set("speaker", speaker_text)
    label.text = None

# Optional: remove speaker="" attribute from all elements
for line in tree.xpath("//l"):
    if "speaker" in line.attrib:
        del line.attrib["speaker"]
        print(f"Removed speaker= attribute from {line.tag}")   

# 5) Ensure metre="" is present and ordered correctly
for l in tree.xpath("//body//l"):
    n = l.get("n", "")
    metre = l.get("metre", "")
    
    # Ensure metre is always present (empty if not already set)
    if "metre" not in l.attrib:
        metre = ""

    # Remove the 'rend' attribute from <l>
    if "rend" in l.attrib:
        del l.attrib["rend"]
    
    # Reconstruct attributes in correct order (n, metre, others)
    attribs = {k: v for k, v in l.attrib.items() if k not in ["n", "metre"]}
    new_attribs = [("n", n), ("metre", metre)] + list(attribs.items())
    l.attrib.clear()
    for k, v in new_attribs:
        if v or k == "metre":  # Force-add empty metre=""
            l.set(k, v)

# 6) Replace &lt; and &gt; within text nodes and ensure proper spacing
def clean_and_format_line(text):
    if text:
        # Remove &lt; and &gt;
        text = re.sub(r'&lt;|&gt;', '', text)
        # Ensure space at the end unless enjambment
        if not text.endswith("-"):
            text = text.rstrip() + " "  # Normal space
        return text
    return text

# Apply cleaning to <l> and sub-elements
for element in tree.xpath("//body//l"):
    if element.text:
        element.text = clean_and_format_line(element.text)
    for subelem in element:
        if subelem.tail:
            subelem.tail = clean_and_format_line(subelem.tail)

# 7) Create the root elements (without namespace prefixes)
output_root = etree.Element("TEI")
tei_header = etree.SubElement(output_root, "teiHeader")
file_desc = etree.SubElement(tei_header, "fileDesc")
title_stmt = etree.SubElement(file_desc, "titleStmt")
etree.SubElement(title_stmt, "title").text = title
etree.SubElement(title_stmt, "author").text = author
text_element = etree.SubElement(output_root, "text")
body_element = etree.SubElement(text_element, "body")


line_counts = {}
mismatch_log = []

# 8) Build strophe + multiple antistrophes for each canticum
for canticum in cantica:
    canticum_element = etree.SubElement(body_element, "canticum")
    responsion_str = f"{responsion_prefix}{responsion_counter:02d}"

    strophe_range = canticum[0]
    antistrophes = canticum[1:]

    strophe_element = etree.SubElement(
        canticum_element, "strophe",
        attrib={"type": "strophe", "responsion": responsion_str}
    )
    strophe_element.text = "\n  "
    line_counts[responsion_str] = {"strophe": 0, "antistrophes": []}

    for line in tree.xpath("//body//l"):
        line_number = line.get("n")
        if line_number and is_in_range(line_number, strophe_range[0], strophe_range[1]):
            etree.strip_elements(line, "space", with_tail=False)
            strophe_element.append(line)
            line_counts[responsion_str]["strophe"] += 1

    for anti_range in antistrophes:
        anti_element = etree.SubElement(
            canticum_element, "strophe",
            attrib={"type": "antistrophe", "responsion": responsion_str}
        )
        anti_element.text = "\n  "
        line_count_for_this_antistroph = 0

        for line in tree.xpath("//body//l"):
            line_number = line.get("n")
            if line_number and is_in_range(line_number, anti_range[0], anti_range[1]):
                etree.strip_elements(line, "space", with_tail=False)
                anti_element.append(line)
                line_count_for_this_antistroph += 1

        line_counts[responsion_str]["antistrophes"].append(line_count_for_this_antistroph)

    responsion_counter += 1

# 9) Pretty print the XML
etree.indent(output_root, space="  ")

# 10) Save the updated XML to file
with open(output_file, "wb") as f:
    etree.ElementTree(output_root).write(
        f, encoding="UTF-8", xml_declaration=True, pretty_print=True
    )

print(f"Updated TEI XML saved to {output_file}")