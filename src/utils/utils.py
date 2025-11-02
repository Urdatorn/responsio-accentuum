'''
I include here some functionality generally useful for the inference scripts and notebooks.
''' 

from collections import Counter
from lxml import etree

#################################
### General utility functions ###
#################################

def get_canticum_ids(file_path: str) -> list[str]:
    all_ids = []

    tree = etree.parse(file_path)
    root = tree.getroot()
    strophe_elements = root.xpath("//strophe")
    all_ids.extend(strophe.get("responsion") for strophe in strophe_elements)

    seen = set()
    return [x for x in all_ids if x not in seen and not seen.add(x)]

def get_syll_count(canticum_ids):
    syll_count = {}
    for abbreviation in abbreviations:
        file_path = f'data/compiled/responsion_{abbreviation}_compiled.xml'
        tree = etree.parse(file_path)
        root = tree.getroot()
        for strophe in root.xpath("//strophe"):
            responsion_id = strophe.get("responsion")
            if responsion_id in canticum_ids:
                syllables = strophe.xpath(".//syll")
                syll_count[responsion_id] = len(syllables)
    return syll_count

def get_strophicity(abbreviations):
    responsion_counts = Counter()

    for abbreviation in abbreviations:
        file_path = f'data/compiled/responsion_{abbreviation}_compiled.xml'
        tree = etree.parse(file_path)
        root = tree.getroot()

        elements = root.xpath("//strophe[@responsion]") + root.xpath("//antistrophe[@responsion]")
        for el in elements:
            rid = el.get("responsion")
            if rid:
                responsion_counts[rid] += 1

    more_than_two = [rid for rid, count in responsion_counts.items() if count > 2]
    exactly_two = [rid for rid, count in responsion_counts.items() if count == 2]

    return more_than_two, exactly_two

from lxml import etree

def get_text_matrix(xml_filepath: str, responsion_attribute: str, representative_strophe: int):
    '''
    Get a 2D list (matrix) representing the syllable structure 
    of the text of the first strophe in the given XML file,
    so it can be superpositioned over a heatmap.

    xml_filepath: path to the XML file
    responsion_attribute: the value of the responsion attribute of the song in question
    representative_strophe: 1-based index of the strophe whose text to use
    '''
    # Load XML
    tree = etree.parse(xml_filepath)
    root = tree.getroot()

    desired_strophes = root.findall(f".//strophe[@responsion='{responsion_attribute}']")
    picked_strophe = desired_strophes[representative_strophe - 1] if desired_strophes else None

    text_matrix = []

    # Iterate over <l> children
    for l in picked_strophe.findall("l"):
        line_sylls = []
        buffer = ""
        prev_resolved = False
        
        for syll in l.findall("syll"):
            resolved = syll.get("resolution") == "True"
            content = syll.text or ""
            
            if prev_resolved and resolved: # and not prev_space # to accomodate the special handling of word-end between in resolved pairs in get_contours_line (in stats_comp.py)
                # join with previous
                buffer += content
            else:
                # flush previous buffer if any
                if buffer:
                    line_sylls.append(buffer)
                buffer = content
            
            #prev_space = content.endswith(" ")
            prev_resolved = resolved
        
        # Append any remaining buffer
        if buffer:
            line_sylls.append(buffer)
        
        text_matrix.append(line_sylls)

    row_lengths = [len(row) for row in text_matrix]
    return text_matrix, row_lengths

#################################
### Particular to Aristphanes ###
#################################

abbreviations = [
    'ach',
    'eq',
    'nu',
    'v',
    'pax',
    'av',
    'lys',
    'th',
    'ra',
    'ec',
    'pl'
]

polystrophic_cantica = ["ach05", # 4
                        "eq07", # 4
                        "pax01", # 3
                        "lys08", # 4
                        "ra04", # 3
                        "ra08" # 4
]

four_strophe_cantica = [
    "ach05",
    "eq07",
    "lys08",
    "ra08"
]

three_strophe_cantica = [
    "pax01",
    "ra04"
]