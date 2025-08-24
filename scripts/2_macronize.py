'''
1. Normalize the orthography. Fix weird prosodical unicode markup.
2. Macronize (including using the few included unicode lengths) and syllabify.
    - the annotator has the symbol "ˈ" (MODIFIER LETTER VERTICAL LINE) for heterosyllabicity;
    thus should make my syllabifier default to homosyllabicity and use those signs as exceptions?
3. Compare schemes within cantica, and find and fix exceptions.   
'''

from lxml import etree
import os
from tqdm import tqdm

from grc_macronizer import Macronizer

def macronize_xml(input_file, output_file):

    macronizer = Macronizer(make_prints=False)

    tree = etree.parse(input_file)
    root = tree.getroot()

    for l in tqdm(root.findall(".//l")):
        text = l.xpath("string()").strip()
        macronized = macronizer.macronize(text)

        if macronized is None:
            continue

        # Remove all children and replace with macronized text
        l.clear()  
        l.text = macronized

    # Ensure output dir exists
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
    macronize_xml(input_file, output_file)
