'''
baseline B(r, i, j) for strophe with r refrains, and whose shortest line has i syllables and longest j: 
extract sample of r sentences randomly from some prose corpus, 
select only the last n syllables and compute comp score and p value convergence after 100 random samples, 
repeat test for all n in [i, j].
'''

from lxml import etree
import random
import re
from tqdm import tqdm

from grc_utils import lower_grc, syllabifier
from src.scan import rule_scansion

punctuation_except_period = r'[\u0387\u037e\u00b7,!?;:\"()\[\]{}<>«»\-—…|⏑⏓†×]'


def get_shape(xml_filepath):
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

def dummy_xml_strophe(strophe_sample_lists, outfile):
    """
    Generate TEI XML from a list of strophe lists of l elements.
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
    
    index = 1
    for strophe_sample_list in strophe_sample_lists:
        xml_content += f'''        <strophe type="strophe" responsion="ba01">
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