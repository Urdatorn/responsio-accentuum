from lxml import etree
import os
import re
from tqdm import tqdm

from .macronizer_mini import macronize_mini

def macronize_xml(input_file, output_file):

    # Use parser that strips blank text → needed for pretty_print
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(input_file, parser)
    root = tree.getroot()

    # Namespace handling (TEI often has a default namespace)
    nsmap = root.nsmap.get(None)
    ns = {"tei": nsmap} if nsmap else {}

    # Find all <l> elements (with or without namespace)
    if ns:
        l_elements = root.findall(".//tei:l", namespaces=ns)
    else:
        l_elements = root.findall(".//l")

    # Macronize each <l>
    for l in tqdm(l_elements):
        text = l.xpath("string()").strip()
        macronized = macronize_mini(text)
        macronized = re.sub(r"\{|\}|\[|\]", "", macronized)  # remove all brackets

        if macronized is None:
            continue

        # Remove all children and replace with macronized text
        l.clear()
        l.text = macronized

    # Add n="" attributes incrementally
    for i, l in enumerate(l_elements, start=1):
        l.set("n", str(i))

    # Ensure output dir exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Pretty-print output
    tree.write(
        output_file,
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=True
    )