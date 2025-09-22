from lxml import etree

input_file = "data/scan/fourth_pythian_autoscan.xml"
output_file = "data/scan/fourth_pythian_scan.xml"

# Parse the XML
parser = etree.XMLParser(remove_blank_text=True)
tree = etree.parse(input_file, parser)
root = tree.getroot()

# Namespace handling (in case TEI uses a namespace)
nsmap = root.nsmap.get(None)
ns = {"tei": nsmap} if nsmap else {}

# Find all <l> elements
if ns:
    l_elements = root.findall(".//tei:l", namespaces=ns)
else:
    l_elements = root.findall(".//l")

# Add n="" attributes incrementally
for i, l in enumerate(l_elements, start=1):
    l.set("n", str(i))

# Write back to file, pretty-printed
tree.write(output_file, pretty_print=True, encoding="UTF-8", xml_declaration=True)