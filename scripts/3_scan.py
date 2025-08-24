'''
Adds [] and {} syllable boundaries to a macronized TEI XML file.
'''

from lxml import etree
import os
from tqdm import tqdm
from scansion import scansion

def scan_xml(input_file, output_file):
    tree = etree.parse(input_file)
    root = tree.getroot()

    for l in tqdm(root.findall(".//l")):
        text = l.xpath("string()").strip()

        scanned = scansion(text)

        if scanned is None:
            continue

        # Remove all children and replace with scanned text
        l.clear()  
        l.text = scanned

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    tree.write(
        output_file,
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=True
    )


if __name__ == "__main__":

    input_file = "data/raw/fourth_pythian.xml"
    output_file = "data/macronized/fourth_pythian_macronized.xml"
    scan_xml(input_file, output_file)
