'''
Script to prepare both lyric and prose baselines for Pindar's odes. 

baseline B(r, i, j) for strophe with r refrains, and whose shortest line has i syllables and longest j: 
extract sample of r sentences randomly from some prose corpus, 
select only the last n syllables and compute comp score and p value convergence after 100 random samples, 
repeat test for all n in [i, j].
'''

from lxml import etree
import os
import random
import re
from tqdm import tqdm

from grc_utils import lower_grc, syllabifier

from src.prose import anabasis
from src.scan import rule_scansion
from src.stats import canonical_sylls

punctuation_except_period = r'[\u0387\u037e\u00b7,!?;:\"()\[\]{}<>«»\-—…|⏑⏓†×]'


def get_shape(xml_filepath):
    '''
    Prepare for making a text matrix overlay on a heatmap.
    '''
    # Load XML
    tree = etree.parse(xml_filepath)
    root = tree.getroot()

    # Get first <strophe>, because the all have the same shape
    first_strophe = root.find(".//strophe[1]")

    text_matrix = []

    # Iterate over <l> children
    for l in first_strophe.findall("l"):
        line_sylls = []
        buffer = ""
        prev_resolved = False
        
        for syll in l.findall("syll"):
            resolved = syll.get("resolution") == "True"
            content = syll.text or ""
            
            if prev_resolved and resolved:
                # join with previous
                buffer += content
            else:
                # flush previous buffer if any
                if buffer:
                    line_sylls.append(buffer)
                buffer = content
            
            prev_resolved = resolved
        
        # Append any remaining buffer
        if buffer:
            line_sylls.append(buffer)
        
        text_matrix.append(line_sylls)

    row_lengths = [len(row) for row in text_matrix]
    
    return row_lengths

def get_shape_canticum(xml_filepath: str, responsion_id: str) -> list:
    '''
    Prepare for making a text matrix overlay on a heatmap.

    Returns a list of ints like:
    [11, 23, 20, 15, ... ]
    representing the number of canonical syllables per line in the strophe with given responsion_id.
    '''
    # Load XML
    tree = etree.parse(xml_filepath)
    root = tree.getroot()

    # Get first <strophe> with matching responsion attribute
    first_strophe = root.find(f".//strophe[@responsion='{responsion_id}']")

    text_matrix = []

    # Iterate over <l> children
    for l in first_strophe.findall("l"):
        line_sylls = []
        buffer = ""
        prev_resolved = False
        
        for syll in l.findall("syll"):
            resolved = syll.get("resolution") == "True"
            content = syll.text or ""
            
            if prev_resolved and resolved:
                # join with previous
                buffer += content
            else:
                # flush previous buffer if any
                if buffer:
                    line_sylls.append(buffer)
                buffer = content
            
            prev_resolved = resolved
        
        # Append any remaining buffer
        if buffer:
            line_sylls.append(buffer)
        
        text_matrix.append(line_sylls)

    row_lengths = [len(row) for row in text_matrix]
    
    return row_lengths

def prose_end_sample(corpus: str, n_sylls: int, sample_size: int, seed=1453):
    random.seed(seed) # to be able to reproduce the exact baseline

    corpus = re.sub(punctuation_except_period, '', corpus)
    corpus = lower_grc(corpus)
    
    sentences = corpus.split(".")
    sentences = ["".join(syllabifier(sentence)[-n_sylls:]) for sentence in sentences if sentence and len(syllabifier(sentence)) >= n_sylls]
    
    sentences = [rule_scansion(sentence, correption=False) for sentence in sentences if sentence]
    
    # Add # after opening brackets
    sentences = [re.sub(r'([\[{])', r'\1#', sentence) for sentence in sentences]

    checked_sentences = []
    for sentence in sentences:
        sylls = re.split(r'[\[\]{}]', sentence)
        sylls = [syll for syll in sylls if syll]
        if len(sylls) == n_sylls:
            checked_sentences.append(sentence)
    
    if len(checked_sentences) < sample_size:
        print(f"Warning: Only {len(checked_sentences)} sentences with exactly {n_sylls} syllables found in corpus, less than requested {sample_size}.")

    if len(sentences) > sample_size:
        sample = random.choices(sentences, k=sample_size)
        return sample
    else:
        return None
    
def prose_strophe_sample(corpus: str, strophe_scheme: list, sample_size: int, seed=1453):
    ''''
    Example of strophe scheme (Pythia 4): 
    [11, 23, 20, 15, 15, 18, 14, 8, 11, 23, 20, 15, 15, 18, 14, 8, 19, 19, 15, 20, 16, 12, 19]

    Arguments:
        corpus: str, a prose text
        strophe_scheme: list of int, number of syllables per line in the strophe
        sample_size: int, number of samples to draw
        seed: int, random seed for reproducibility
    '''
    lines = {}
    for n_sylls in strophe_scheme:
        sample = prose_end_sample(corpus, n_sylls, sample_size, seed)
        if sample is not None:
            lines[n_sylls] = sample
        else:
            print(f"Warning: Could not generate sample for {n_sylls} syllables")

    print("Assembling strophes...")
    strophes = []
    for i in tqdm(range(sample_size)):
        strophe = []
        for n_sylls in strophe_scheme:
            if n_sylls in lines and len(lines[n_sylls]) > i:
                strophe.append(lines[n_sylls][i])
            else:
                strophe.append("")
        strophes.append(strophe)

    return strophes

def dummy_xml_single_line(string_list: list, outfile: str):
    """
    Generate TEI XML from a list of strings, with each string in an <l> element
    nested inside its own <strophe> element.
    """
    xml_content = '''<?xml version='1.0' encoding='UTF-8'?>
<TEI>
  <teiHeader>
    <fileDesc>
      <titleStmt>
        <title>Baseline</title>
        <author>Prose</author>
      </titleStmt>
    </fileDesc>
  </teiHeader>
  <text>
    <body>
      <canticum>
'''
    
    for i, text in enumerate(string_list, 1):
        xml_content += f'''        <strophe type="strophe" responsion="ba01">
          <l n="{i}">{text}</l>
        </strophe>
'''
    
    xml_content += '''      </canticum>
    </body>
  </text>
</TEI>'''
    
    with open(outfile, 'w', encoding='utf-8') as f:
        f.write(xml_content)

def dummy_xml_strophe(strophe_sample_lists, responsion_id, outfile, type="Prose"):
    """
    Generate TEI XML from a list of strophe lists of l elements.
    """
    xml_content = f'''<?xml version='1.0' encoding='UTF-8'?>
<TEI>
  <teiHeader>
    <fileDesc>
      <titleStmt>
        <title>Baseline</title>
        <author>{type}</author>
      </titleStmt>
    </fileDesc>
  </teiHeader>
  <text>
    <body>
      <canticum>
'''
    
    index = 1
    for strophe_sample_list in strophe_sample_lists:
        xml_content += f'''        <strophe type="strophe" responsion="{responsion_id}">
'''
        
        for line in strophe_sample_list:
            xml_content += f'''          <l n="{index}">{line}</l>
'''
            index += 1

        xml_content += '''        </strophe>
'''
    
    xml_content += '''      </canticum>
    </body>
  </text>
</TEI>'''
    
    with open(outfile, 'w', encoding='utf-8') as f:
        f.write(xml_content)

def make_prose_baseline(xml_file: str, responsion_id: str, debug: bool = False):

    strophe_scheme = get_shape_canticum(xml_file, responsion_id)

    sample_size = 13
    seed = 1453
    strophe_sample_lists = prose_strophe_sample(anabasis, strophe_scheme, sample_size, seed)

    outdir = "data/scan/baselines/prose/"
    filename = f"baseline_prose_{responsion_id}.xml"
    filepath = os.path.join(outdir, filename)
    dummy_xml_strophe(strophe_sample_lists, responsion_id, filepath, type="Prose")

    if debug:
        for sentence in strophe_sample_lists[0]:
            sylls = re.split(r'[\[\]{}]', sentence)
            sylls = [s for s in sylls if s and not s.isspace()]
            print(len(sylls))

def lyric_line_sample(length: int, corpus_folder: str, seed=1453, debug=False)-> str:
    '''
    Workflow:
    1. Get the set of all lines of given canonical length from the compiled xml corpus
    2. If non-empty, return a random line from these; 
        if empty search for lines with length +1 and shave off last canonical syllable;
        if still empty search for length -1 and append a random syllable at the end, chosen from the whole corpus.
    '''

    random.seed(seed)

    print(f"Searching for lines of length {length} in corpus at {corpus_folder}")

    xml_files = [f for f in os.listdir(corpus_folder) if f.endswith('.xml')]
    candidate_lines = []
    for xml_file in xml_files:
        tree = etree.parse(os.path.join(corpus_folder, xml_file))
        root = tree.getroot()
        l_elements = root.findall(".//l")

        for l in l_elements:
            canonical_length = len(canonical_sylls(l)) # i.e. length of e.g. ['heavy', 'light', 'light', 'heavy', 'light', 'light', 'heavy']
            if canonical_length == length:
                # print first word of line after converting to string
                string_words_debug = etree.tostring(l, encoding='unicode', method='text')
                if debug:
                    print("\t" + string_words_debug[:30] + "..." )

                candidate_lines.append(l)
    
    if candidate_lines:
        if debug:
            print(f"Found {len(candidate_lines)} candidate lines of length {length}.")
        return random.choice(candidate_lines)
    else:
        print(f"\033[93mWarning: No lines found with length {length}. Trying length + 1.\033[0m")

        # Try length + 1
        candidate_lines = []
        for xml_file in xml_files:
            tree = etree.parse(os.path.join(corpus_folder, xml_file))
            root = tree.getroot()

            for l in root.findall(".//l"):
                canonical_length = len(canonical_sylls(l))
                if canonical_length == length + 1:
                    candidate_lines.append(l)

        if candidate_lines:
            print(f"\033[92mFound {len(candidate_lines)} candidate lines of length {length + 1}, trimming last syllable.\033[0m")

            line = random.choice(candidate_lines) # this is an etree element, not a string
            sylls = line.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]")
            trimmed_sylls = sylls[:-1]  # remove last syllable

            # Create new <l> element
            new_line = etree.Element("l")
            for syll in trimmed_sylls:
                new_line.append(syll)

            return new_line

        else:
            # Try length - 1
            candidate_lines = []
            for xml_file in xml_files:
                tree = etree.parse(os.path.join(corpus_folder, xml_file))
                root = tree.getroot()

                for l in root.findall(".//l"):
                    canonical_length = len(canonical_sylls(l))
                    if canonical_length == length - 1:
                        candidate_lines.append(l)
            
            if candidate_lines:
                print(f"\033[92mFound {len(candidate_lines)} candidate lines of length {length - 1}, appending random syllable.\033[0m")

                line = random.choice(candidate_lines)
                sylls = line.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]")
                
                # Append a random syllable from the whole corpus
                all_syllables = []
                for xml_file in xml_files:
                    tree = etree.parse(os.path.join(corpus_folder, xml_file))
                    root = tree.getroot()

                    for syll in root.findall(".//syll[not(@resolution='True') and not(@anceps='True')]"):
                        all_syllables.append(syll)
                
                random_syllable = random.choice(all_syllables)
                extended_sylls = sylls.append(random_syllable)
                
                # Create new <l> element
                new_line = etree.Element("l")
                for syll in extended_sylls:
                    new_line.append(syll)
                
                return new_line

            else:
                print(f"Warning: No lines found with lengths {length}, {length+1}, or {length-1}.")
                return None


