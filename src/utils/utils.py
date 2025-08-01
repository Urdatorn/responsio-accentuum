'''
I include here some functionality generally useful for the inference scripts and notebooks.
''' 
from src.utils.baselines import baseline_dict

from collections import Counter
from lxml import etree

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

def baseline(metric="comp", one_of_the_six_baseline_types="trimeter_2_strophic", accent=None):
    '''
    args:
        - metric in ["acc", "barys", "comp"]
        - one_of_the_six_baseline_types in ["tetrameter_4_strophes", "trimeter_2_strophic", "trimeter_3_strophes", "trimeter_4_strophes", "tetrameter_2_strophes", "tetrameter_3_strophes"]
        - "comp" takes no accent.
            - for "acc", accent in ["acute", "acute_circumflex", "circumflex", "grave"]
            - for "barys", accent in ["barys_metric", "barys_oxys_metric", "oxys_metric"]
    '''
    if metric == "comp":
        return baseline_dict[metric][one_of_the_six_baseline_types]
    else:
        return baseline_dict[metric][one_of_the_six_baseline_types][accent]


def get_canticum_ids(abbreviations):
    all_ids = []
    for abbreviation in abbreviations:
        file_path = f'data/compiled/responsion_{abbreviation}_compiled.xml'
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



