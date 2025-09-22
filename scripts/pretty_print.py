from lxml import etree

input_file = "data/macronized/fourth_pythian_macronized.xml"
output_file = "data/macronized/fourth_pythian_pretty.xml"

# Parse the XML
parser = etree.XMLParser(remove_blank_text=True)
tree = etree.parse(input_file, parser)

# Pretty-print with each <l> on its own line
tree.write(output_file, pretty_print=True, encoding="utf-8", xml_declaration=True)