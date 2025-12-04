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
import json
import pickle
from collections import defaultdict
from tqdm import tqdm

from grc_utils import lower_grc, syllabifier

from src.prose import anabasis
from src.scan import rule_scansion
from src.stats import canonical_sylls

punctuation_except_period = r'[\u0387\u037e\u00b7,!?;:\"()\[\]{}<>«»\-—…|⏑⏓†×]'

def preprocess_and_cache_prose_corpus(corpus: str, cache_file: str = "data/cached_prose_corpus.pkl"):
    """
    Preprocess the entire prose corpus once and cache results by syllable length.
    
    Args:
        corpus: the prose text to preprocess
        cache_file: path to save the cached results
        
    Returns:
        dict: syllable_length -> list of processed sentences
    """
    print("Preprocessing prose corpus...")
    
    # Initial corpus processing (done once)
    corpus = re.sub(punctuation_except_period, '', corpus)
    corpus = lower_grc(corpus)
    sentences = corpus.split(".")
    
    # Group processed sentences by syllable count
    sentences_by_length = defaultdict(list)
    
    for sentence in tqdm(sentences, desc="Processing sentences"):
        if not sentence:
            continue
            
        # Get syllables once
        sentence_sylls = syllabifier(sentence)
        if len(sentence_sylls) < 1:  # Skip empty sentences
            continue
            
        # Process for different n_sylls values (we'll cache up to reasonable max length)
        max_length = min(len(sentence_sylls), 50)  # Cache up to 50 syllables
        
        for n_sylls in range(1, max_length + 1):
            if len(sentence_sylls) >= n_sylls:
                # Extract last n syllables
                end_sylls = "".join(sentence_sylls[-n_sylls:])
                
                # Apply rule scansion
                scanned = rule_scansion(end_sylls, correption=False)
                if not scanned:
                    continue
                    
                # Add # after opening brackets
                processed = re.sub(r'([\[{])', r'\1#', scanned)
                
                # Check syllable count matches
                sylls = re.split(r'[\[\]{}]', processed)
                sylls = [syll for syll in sylls if syll]
                
                if len(sylls) == n_sylls:
                    sentences_by_length[n_sylls].append(processed)
    
    # Save cache
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    with open(cache_file, 'wb') as f:
        pickle.dump(dict(sentences_by_length), f)
    
    print(f"Cached {sum(len(v) for v in sentences_by_length.values())} processed sentences")
    print(f"Syllable lengths available: {sorted(sentences_by_length.keys())}")
    print(f"Cache saved to: {cache_file}")
    
    return dict(sentences_by_length)

def load_cached_prose_corpus(cache_file: str = "data/cached_prose_corpus.pkl"):
    """
    Load cached prose corpus data.
    
    Args:
        cache_file: path to the cached results
        
    Returns:
        dict: syllable_length -> list of processed sentences
    """
    if not os.path.exists(cache_file):
        print(f"Cache file {cache_file} not found. Preprocessing corpus...")
        return preprocess_and_cache_prose_corpus(anabasis, cache_file)
    
    with open(cache_file, 'rb') as f:
        return pickle.load(f)

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
        return checked_sentences  # Return all available sentences

    if len(checked_sentences) >= sample_size:
        sample = random.sample(checked_sentences, sample_size)  # Use sample instead of choices to avoid duplicates
        return sample
    else:
        return None

def prose_end_sample_cached(cached_corpus: dict, n_sylls: int, sample_size: int, seed=1453):
    """
    Fast version of prose_end_sample using cached preprocessed corpus.
    
    Args:
        cached_corpus: dict from load_cached_prose_corpus()
        n_sylls: number of syllables to sample
        sample_size: how many samples to return
        seed: random seed for reproducibility
        
    Returns:
        list of processed sentence strings or None if insufficient data
    """
    random.seed(seed)
    
    if n_sylls not in cached_corpus:
        print(f"Warning: No sentences with exactly {n_sylls} syllables found in cached corpus.")
        return []
    
    available_sentences = cached_corpus[n_sylls]
    
    if len(available_sentences) < sample_size:
        print(f"Warning: Only {len(available_sentences)} sentences with exactly {n_sylls} syllables found in corpus, less than requested {sample_size}.")
        return available_sentences  # Return all available sentences
    
    if len(available_sentences) >= sample_size:
        sample = random.sample(available_sentences, sample_size)  # Use sample instead of choices to avoid duplicates
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
    # Get unique syllable counts and determine how many we need of each
    unique_sylls = set(strophe_scheme)
    syll_counts = {n_sylls: strophe_scheme.count(n_sylls) for n_sylls in unique_sylls}
    
    # Generate samples for each unique syllable count
    # We need sample_size * count for each syllable length to avoid repetition within strophes
    lines = {}
    for n_sylls in unique_sylls:
        needed_samples = sample_size * syll_counts[n_sylls]
        sample = prose_end_sample(corpus, n_sylls, needed_samples, seed)
        if sample is not None:
            lines[n_sylls] = sample
        else:
            print(f"Warning: Could not generate sample for {n_sylls} syllables")

    print("Assembling strophes...")
    strophes = []
    # Keep track of how many we've used for each syllable count
    used_indices = {n_sylls: 0 for n_sylls in unique_sylls}
    
    for i in tqdm(range(sample_size)):
        strophe = []
        for n_sylls in strophe_scheme:
            if n_sylls in lines and used_indices[n_sylls] < len(lines[n_sylls]):
                strophe.append(lines[n_sylls][used_indices[n_sylls]])
                used_indices[n_sylls] += 1
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

def dummy_xml_strophe(strophe_sample_lists_dict, outfile, type="Prose"):
    """
    Generate TEI XML from a dictionary of strophe lists.
    
    Args:
        strophe_sample_lists_dict: dict with responsion_id as key and list of strophe lists as value
        outfile: output file path
        type: type of baseline (default "Prose")
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
'''
    
    for responsion_id, strophe_sample_lists in strophe_sample_lists_dict.items():
        xml_content += f'''      <canticum>
'''
        
        index = 1
        for strophe_sample_list in strophe_sample_lists:
            xml_content += f'''        <strophe type="strophe" responsion="{responsion_id}">
'''
            
            for line in strophe_sample_list:
                # Parse the line to extract syllable content and source attribute
                try:
                    line_element = etree.fromstring(line)
                    # Extract source attribute if present
                    source_attr = line_element.get('source', '')
                    source_part = f' source="{source_attr}"' if source_attr else ''
                    
                    # Extract all syllable elements as strings
                    syll_content = ""
                    for syll in line_element.xpath(".//syll"):
                        syll_str = etree.tostring(syll, encoding='unicode', method='xml')
                        syll_content += syll_str
                    
                    xml_content += f'''          <l n="{index}"{source_part}>{syll_content}</l>
'''
                except etree.XMLSyntaxError:
                    # Fallback for malformed XML - just use the content as-is
                    xml_content += f'''          <l n="{index}">{line}</l>
'''
                index += 1

            xml_content += '''        </strophe>
'''
        
        xml_content += '''      </canticum>
'''
    
    xml_content += '''    </body>
  </text>
</TEI>'''
    
    with open(outfile, 'w', encoding='utf-8') as f:
        f.write(xml_content)

def make_prose_baseline(xml_file: str, responsion_id: str, debug: bool = False):

    strophe_scheme = get_shape_canticum(xml_file, responsion_id)

    # Count the number of strophes with the given responsion_id in the original file
    tree = etree.parse(xml_file)
    root = tree.getroot()
    strophes = root.findall(f".//strophe[@responsion='{responsion_id}']")
    sample_size = len(strophes)
    
    if debug:
        print(f"Found {sample_size} strophes with responsion '{responsion_id}' in original file")
        print(f"Strophe scheme: {strophe_scheme}")
        print(f"Generating 100 baseline samples...")
    
    # Generate 100 different baseline samples with different seeds
    strophe_samples_dict = {}
    
    for i in tqdm(range(100)):
        seed = 1453 + i  # Different seed for each sample
        responsion_key = f"{responsion_id}_{i:03d}"  # e.g., "is01_000", "is01_001", etc.
        
        # Generate lines for each position first, ensuring uniqueness within each position
        lines_by_position = []
        
        for line_idx, line_length in enumerate(strophe_scheme):
            position_lines = []
            used_lines = set()  # Track used lines for this position
            
            attempts = 0
            max_attempts = sample_size * 10  # Allow multiple attempts to find unique lines
            
            while len(position_lines) < sample_size and attempts < max_attempts:
                # Use different seed for each attempt
                line_seed = seed + line_idx * 10000 + attempts
                sample_lines = prose_end_sample(anabasis, line_length, 1, line_seed)
                
                if sample_lines and len(sample_lines) > 0:
                    line_text = sample_lines[0]
                    
                    # Check if this line is already used in this position
                    if line_text not in used_lines:
                        position_lines.append(line_text)
                        used_lines.add(line_text)
                    
                attempts += 1
            
            # If we couldn't find enough unique lines, raise an error
            if len(position_lines) < sample_size:
                raise RuntimeError(f"Could not find {sample_size} unique prose lines for position {line_idx+1} (length {line_length}). Only found {len(position_lines)} unique lines after {max_attempts} attempts.")
            
            lines_by_position.append(position_lines)
        
        # Now assemble strophes from the position-specific lines
        strophe_sample_lists = []
        
        for strophe_idx in range(sample_size):
            strophe_lines = []
            
            for line_idx in range(len(strophe_scheme)):
                strophe_lines.append(lines_by_position[line_idx][strophe_idx])
            
            strophe_sample_lists.append(strophe_lines)
        
        strophe_samples_dict[responsion_key] = strophe_sample_lists
    
    outdir = "data/scan/baselines/triads/prose/"
    os.makedirs(outdir, exist_ok=True)
    print(f"Writing prose baseline for responsion {responsion_id} to {outdir}")

    filename = f"baseline_prose_{responsion_id}.xml"
    filepath = os.path.join(outdir, filename)
    dummy_xml_strophe(strophe_samples_dict, filepath, type="Prose")

    if debug:
        # Debug first sample only
        first_key = list(strophe_samples_dict.keys())[0]
        print(f"Debug: First strophe sample for {first_key}:")
        for i, line in enumerate(strophe_samples_dict[first_key][0]):
            print(f"  Line {i+1} (length {strophe_scheme[i]}): {line}")

def make_prose_baseline_fast(xml_file: str, responsion_id: str, debug: bool = False, cache_file: str = "data/cached_prose_corpus.pkl"):
    """
    Fast version of make_prose_baseline using cached preprocessed corpus.
    
    Args:
        xml_file: path to XML file containing the original strophe structure
        responsion_id: the responsion ID to generate baseline for
        debug: whether to print debug information
        cache_file: path to cached corpus data
    """
    
    # Load cached corpus data
    cached_corpus = load_cached_prose_corpus(cache_file)

    strophe_scheme = get_shape_canticum(xml_file, responsion_id)

    # Count the number of strophes with the given responsion_id in the original file
    tree = etree.parse(xml_file)
    root = tree.getroot()
    strophes = root.findall(f".//strophe[@responsion='{responsion_id}']")
    sample_size = len(strophes)
    
    if debug:
        print(f"Found {sample_size} strophes with responsion '{responsion_id}' in original file")
        print(f"Strophe scheme: {strophe_scheme}")
        print(f"Generating 100 baseline samples...")
    
    # Generate 100 different baseline samples with different seeds
    strophe_samples_dict = {}
    
    for i in tqdm(range(100)):
        seed = 1453 + i  # Different seed for each sample
        responsion_key = f"{responsion_id}_{i:03d}"  # e.g., "is01_000", "is01_001", etc.
        
        # Generate lines for each position first, ensuring uniqueness within each position
        lines_by_position = []
        
        for line_idx, line_length in enumerate(strophe_scheme):
            position_lines = []
            used_lines = set()  # Track used lines for this position
            
            attempts = 0
            max_attempts = sample_size * 10  # Allow multiple attempts to find unique lines
            
            while len(position_lines) < sample_size and attempts < max_attempts:
                # Use different seed for each attempt
                line_seed = seed + line_idx * 10000 + attempts
                sample_lines = prose_end_sample_cached(cached_corpus, line_length, 1, line_seed)
                
                if sample_lines and len(sample_lines) > 0:
                    line_text = sample_lines[0]
                    
                    # Check if this line is already used in this position
                    if line_text not in used_lines:
                        position_lines.append(line_text)
                        used_lines.add(line_text)
                    
                attempts += 1
            
            # If we couldn't find enough unique lines, raise an error
            if len(position_lines) < sample_size:
                raise RuntimeError(f"Could not find {sample_size} unique prose lines for position {line_idx+1} (length {line_length}). Only found {len(position_lines)} unique lines after {max_attempts} attempts.")
            
            lines_by_position.append(position_lines)
        
        # Now assemble strophes from the position-specific lines
        strophe_sample_lists = []
        
        for strophe_idx in range(sample_size):
            strophe_lines = []
            
            for line_idx in range(len(strophe_scheme)):
                strophe_lines.append(lines_by_position[line_idx][strophe_idx])
            
            strophe_sample_lists.append(strophe_lines)
        
        strophe_samples_dict[responsion_key] = strophe_sample_lists
    
    outdir = "data/scan/baselines/triads/prose/"
    os.makedirs(outdir, exist_ok=True)
    print(f"Writing prose baseline for responsion {responsion_id} to {outdir}")

    filename = f"baseline_prose_{responsion_id}.xml"
    filepath = os.path.join(outdir, filename)
    dummy_xml_strophe(strophe_samples_dict, filepath, type="Prose")

    if debug:
        # Debug first sample only
        first_key = list(strophe_samples_dict.keys())[0]
        print(f"Debug: First strophe sample for {first_key}:")
        for i, line in enumerate(strophe_samples_dict[first_key][0]):
            print(f"  Line {i+1} (length {strophe_scheme[i]}): {line}")

def make_lyric_baseline(xml_file: str, responsion_id: str, corpus_folder: str = "data/compiled/triads", outfolder: str = "data/compiled/baselines/triads/lyric", debug: bool = False):
    """
    Generate lyric baseline using lyric_line_sample for each line length in the strophe.
    Ensures that corresponding lines (same position) across strophes are unique.
    Excludes the input XML file from the corpus to avoid contamination.
    
    Args:
        xml_file: path to XML file containing the original strophe structure
        responsion_id: the responsion ID to generate baseline for
        corpus_folder: folder containing XML files for lyric line sampling
        outfolder: folder to write the baseline XML file to
        debug: whether to print debug information
    """
    
    strophe_scheme = get_shape_canticum(xml_file, responsion_id)

    # Count the number of strophes with the given responsion_id in the original file
    tree = etree.parse(xml_file)
    root = tree.getroot()
    strophes = root.findall(f".//strophe[@responsion='{responsion_id}']")
    sample_size = len(strophes)
    
    # Get the filename of the input XML to exclude from corpus sampling
    input_filename = os.path.basename(xml_file)
    
    if debug:
        print(f"Found {sample_size} strophes with responsion '{responsion_id}' in original file")
        print(f"Strophe scheme: {strophe_scheme}")
        print(f"Excluding {input_filename} from corpus sampling")
        print(f"Generating 100 baseline samples...")
    
    # Generate 100 different baseline samples with different seeds
    strophe_samples_dict = {}
    
    for i in tqdm(range(100)):
        seed = 1453 + i  # Different seed for each sample
        responsion_key = f"{responsion_id}_{i:03d}"  # e.g., "is01_000", "is01_001", etc.
        
        # Generate lines for each position first, ensuring uniqueness within each position
        lines_by_position = []
        
        for line_idx, line_length in enumerate(strophe_scheme):
            position_lines = []
            used_lines = set()  # Track used lines for this position
            
            attempts = 0
            max_attempts = sample_size * 10  # Allow multiple attempts to find unique lines
            
            while len(position_lines) < sample_size and attempts < max_attempts:
                # Use different seed for each attempt
                line_seed = seed + line_idx * 10000 + attempts
                sample_line = lyric_line_sample(line_length, corpus_folder, seed=line_seed, debug=debug, exclude_file=input_filename)
                
                if sample_line is not None:
                    # Convert XML element to string for comparison
                    line_text = etree.tostring(sample_line, encoding='unicode', method='xml')
                    
                    # Check if this line is already used in this position
                    if line_text not in used_lines:
                        position_lines.append(line_text)
                        used_lines.add(line_text)
                    
                attempts += 1
            
            # If we couldn't find enough unique lines, raise an error
            if len(position_lines) < sample_size:
                raise RuntimeError(f"Could not find {sample_size} unique lines for position {line_idx+1} (length {line_length}). Only found {len(position_lines)} unique lines after {max_attempts} attempts.")
            
            lines_by_position.append(position_lines)
        
        # Now assemble strophes from the position-specific lines
        strophe_sample_lists = []
        
        for strophe_idx in range(sample_size):
            strophe_lines = []
            
            for line_idx in range(len(strophe_scheme)):
                strophe_lines.append(lines_by_position[line_idx][strophe_idx])
            
            strophe_sample_lists.append(strophe_lines)
        
        strophe_samples_dict[responsion_key] = strophe_sample_lists
    
    outdir = outfolder
    os.makedirs(outdir, exist_ok=True)
    print(f"Writing lyric baseline for responsion {responsion_id} to {outdir}")

    filename = f"baseline_lyric_{responsion_id}.xml"
    filepath = os.path.join(outdir, filename)
    dummy_xml_strophe(strophe_samples_dict, filepath, type="Lyric")

    if debug:
        # Debug first sample only
        first_key = list(strophe_samples_dict.keys())[0]
        print(f"Debug: First strophe sample for {first_key}:")
        for i, line in enumerate(strophe_samples_dict[first_key][0]):
            print(f"  Line {i+1} (length {strophe_scheme[i]}): {line}")

def lyric_line_sample(length: int, corpus_folder: str, seed=1453, debug=False, exclude_file=None)-> str:
    '''
    Workflow:
    1. Get the set of all lines of given canonical length from the compiled xml corpus
    2. If non-empty, return a random line from these; 
        if empty search for lines with length +1 and shave off last canonical syllable;
        if still empty search for length -1 and append a random syllable at the end, chosen from the whole corpus.
    
    Args:
        length: target canonical syllable length
        corpus_folder: folder containing XML files to sample from
        seed: random seed for reproducibility
        debug: whether to print debug information
        exclude_file: filename to exclude from corpus sampling (to avoid contamination)
    '''

    random.seed(seed)

    if debug:
        print(f"Searching for lines of length {length} in corpus at {corpus_folder}")
        if exclude_file:
            print(f"Excluding {exclude_file} from sampling")

    xml_files = [f for f in os.listdir(corpus_folder) if f.endswith('.xml')]
    
    # Filter out the excluded file if specified
    if exclude_file:
        xml_files = [f for f in xml_files if f != exclude_file]
    
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
        if debug:
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
            if debug:
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
                if debug:
                    print(f"\033[92mFound {len(candidate_lines)} candidate lines of length {length - 1}, appending random syllable.\033[0m")

                line = random.choice(candidate_lines)
                sylls = line.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]")
                
                # Append a random syllable from the whole corpus (also excluding the specified file)
                all_syllables = []
                for xml_file in xml_files:
                    tree = etree.parse(os.path.join(corpus_folder, xml_file))
                    root = tree.getroot()

                    for syll in root.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]"):
                        all_syllables.append(syll)
                
                random_syllable = random.choice(all_syllables)
                sylls.append(random_syllable)
                
                # Create new <l> element
                new_line = etree.Element("l")
                for syll in sylls:
                    new_line.append(syll)
                
                return new_line

            else:
                if debug:
                    print(f"Warning: No lines found with lengths {length}, {length+1}, or {length-1}.")
                return None

def preprocess_and_cache_lyric_corpus(corpus_folder: str, cache_file: str = "data/cached_lyric_corpus.pkl"):
    """
    Preprocess the entire lyric corpus once and cache results by canonical syllable length.
    
    Args:
        corpus_folder: folder containing XML files to process
        cache_file: path to save the cached results
        
    Returns:
        dict: canonical_length -> list of XML line elements (as strings) with metadata
    """
    print("Preprocessing lyric corpus...")
    
    xml_files = [f for f in os.listdir(corpus_folder) if f.endswith('.xml')]
    
    # Group lines by canonical syllable count
    lines_by_length = defaultdict(list)
    syllables_by_file = {}  # Store all syllables by file for fallback cases
    
    for xml_file in tqdm(xml_files, desc="Processing XML files"):
        file_path = os.path.join(corpus_folder, xml_file)
        tree = etree.parse(file_path)
        root = tree.getroot()
        
        # Store syllables for this file (for fallback operations)
        file_syllables = []
        for syll in root.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]"):
            file_syllables.append(etree.tostring(syll, encoding='unicode', method='xml'))
        syllables_by_file[xml_file] = file_syllables
        
        # Process all canticum elements in this file
        for canticum_idx, canticum in enumerate(root.findall(".//canticum")):
            # Process all strophes within this canticum
            for strophe_idx, strophe in enumerate(canticum.findall(".//strophe")):
                responsion_id = strophe.get('responsion', 'unknown')
                
                # Process all lines within this strophe
                for line_idx, l in enumerate(strophe.findall("l")):
                    try:
                        canonical_length = len(canonical_sylls(l))
                        
                        # Store line as XML string with metadata for contamination checking
                        line_xml = etree.tostring(l, encoding='unicode', method='xml')
                        lines_by_length[canonical_length].append({
                            'xml': line_xml,
                            'file': xml_file,
                            'canticum_idx': canticum_idx,
                            'strophe_idx': strophe_idx,
                            'line_idx': line_idx,
                            'responsion_id': responsion_id
                        })
                    except:
                        # Skip lines that cause errors in canonical_sylls
                        continue
    
    # Also cache the syllables for random selection in fallback cases
    all_syllables = []
    for file_syllables in syllables_by_file.values():
        all_syllables.extend(file_syllables)
    
    cached_data = {
        'lines_by_length': dict(lines_by_length),
        'all_syllables': all_syllables,
        'syllables_by_file': syllables_by_file
    }
    
    # Save cache
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    with open(cache_file, 'wb') as f:
        pickle.dump(cached_data, f)
    
    print(f"Cached {sum(len(v) for v in lines_by_length.values())} lines")
    print(f"Line lengths available: {sorted(lines_by_length.keys())}")
    print(f"Total syllables cached: {len(all_syllables)}")
    print(f"Cache saved to: {cache_file}")
    
    return cached_data

def load_cached_lyric_corpus(cache_file: str = "data/cached_lyric_corpus.pkl", corpus_folder: str = "data/compiled/triads"):
    """
    Load cached lyric corpus data.
    
    Args:
        cache_file: path to the cached results
        corpus_folder: folder containing XML files (for regenerating cache if needed)
        
    Returns:
        dict: cached corpus data
    """
    if not os.path.exists(cache_file):
        print(f"Cache file {cache_file} not found. Preprocessing corpus...")
        return preprocess_and_cache_lyric_corpus(corpus_folder, cache_file)
    
    with open(cache_file, 'rb') as f:
        cached_data = pickle.load(f)
    
    # Check if cache has the new metadata structure
    if 'lines_by_length' in cached_data and cached_data['lines_by_length']:
        # Get a sample line to check structure
        first_length = next(iter(cached_data['lines_by_length']))
        sample_lines = cached_data['lines_by_length'][first_length]
        if sample_lines and isinstance(sample_lines[0], dict):
            # Check if new metadata fields exist
            if 'canticum_idx' not in sample_lines[0]:
                print(f"Cache file {cache_file} is outdated (missing metadata). Regenerating...")
                return preprocess_and_cache_lyric_corpus(corpus_folder, cache_file)
        else:
            print(f"Cache file {cache_file} has old format. Regenerating...")
            return preprocess_and_cache_lyric_corpus(corpus_folder, cache_file)
    
    return cached_data

def lyric_line_sample_cached(length: int, cached_corpus: dict, seed=1453, debug=False, exclude_file=None, used_metrical_positions=None):
    """
    Fast version of lyric_line_sample using cached preprocessed corpus.
    
    Args:
        length: target canonical syllable length
        cached_corpus: dict from load_cached_lyric_corpus()
        seed: random seed for reproducibility
        debug: whether to print debug information
        exclude_file: filename to exclude from corpus sampling (to avoid contamination)
        used_metrical_positions: set of used (file, canticum_idx, strophe_idx, line_idx) tuples
        
    Returns:
        XML element as string, or None if not found
    """
    random.seed(seed)
    
    lines_by_length = cached_corpus['lines_by_length']
    all_syllables = cached_corpus['all_syllables']
    
    if used_metrical_positions is None:
        used_metrical_positions = set()
    
    if debug:
        print(f"Searching for lines of length {length}")
        if exclude_file:
            print(f"Excluding {exclude_file} from sampling")
    
    # Filter out lines from excluded file and ensure metrical independence
    def filter_lines_with_independence_check(lines_data, exclude_file, used_positions, current_position_idx):
        """
        Filter lines ensuring:
        1. Not from excluded file
        2. Statistical independence (no two lines from same metrical position)
        
        Args:
            lines_data: list of line dictionaries with metadata
            exclude_file: filename to exclude
            used_positions: set of (file, canticum_idx, strophe_idx, line_idx) tuples already used
            current_position_idx: the current line position we're filling (for logging)
        """
        filtered = []
        for item in lines_data:
            # Skip excluded file
            if exclude_file and item['file'] == exclude_file:
                continue
                
            # Create position key for independence checking
            position_key = (item['file'], item['canticum_idx'], item['strophe_idx'], item['line_idx'])
            
            # Skip if we've already used a line from this exact metrical position
            if position_key not in used_positions:
                filtered.append(item)
        
        return filtered
    
    # Try exact length first
    if length in lines_by_length:
        candidate_lines = filter_lines_with_independence_check(
            lines_by_length[length], exclude_file, used_metrical_positions, length
        )
        if candidate_lines:
            if debug:
                print(f"Found {len(candidate_lines)} candidate lines of length {length}.")
            selected_item = random.choice(candidate_lines)
            
            # Add this position to used positions
            position_key = (selected_item['file'], selected_item['canticum_idx'], 
                          selected_item['strophe_idx'], selected_item['line_idx'])
            used_metrical_positions.add(position_key)
            
            selected_xml = selected_item['xml']
            line_element = etree.fromstring(selected_xml)
            # Add enhanced source attribute to show contamination prevention
            source_info = f"{selected_item['responsion_id']}, strophe {selected_item['strophe_idx'] + 1}, line {selected_item['line_idx'] + 1}"
            line_element.set('source', source_info)
            return line_element
    
    if debug:
        print(f"\033[93mWarning: No lines found with length {length}. Trying length + 1.\033[0m")
    
    # Try length + 1 and trim
    if (length + 1) in lines_by_length:
        candidate_lines = filter_lines_with_independence_check(
            lines_by_length[length + 1], exclude_file, used_metrical_positions, length
        )
        if candidate_lines:
            if debug:
                print(f"\033[92mFound {len(candidate_lines)} candidate lines of length {length + 1}, trimming last syllable.\033[0m")
            
            selected_item = random.choice(candidate_lines)
            
            # Add this position to used positions
            position_key = (selected_item['file'], selected_item['canticum_idx'], 
                          selected_item['strophe_idx'], selected_item['line_idx'])
            used_metrical_positions.add(position_key)
            
            selected_xml = selected_item['xml']
            line = etree.fromstring(selected_xml)
            sylls = line.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]")
            trimmed_sylls = sylls[:-1]  # remove last syllable
            
            # Create new <l> element and copy attributes from original
            new_line = etree.Element("l")
            # Copy attributes from original line
            for attr, value in line.attrib.items():
                if attr != 'source':  # Don't copy source if it exists
                    new_line.set(attr, value)
            # Add enhanced source attribute to show contamination prevention
            source_info = f"{selected_item['responsion_id']}, strophe {selected_item['strophe_idx'] + 1}, line {selected_item['line_idx'] + 1}"
            new_line.set('source', source_info)
            for syll in trimmed_sylls:
                new_line.append(syll)
            
            return new_line
    
    # Try length + 5 and trim five syllables
    if (length + 5) in lines_by_length:
        candidate_lines = filter_lines_with_independence_check(
            lines_by_length[length + 5], exclude_file, used_metrical_positions, length
        )
        if candidate_lines:
            if debug:
                print(f"\033[92mFound {len(candidate_lines)} candidate lines of length {length + 5}, trimming five syllables.\033[0m")
            
            selected_item = random.choice(candidate_lines)
            
            # Add this position to used positions
            position_key = (selected_item['file'], selected_item['canticum_idx'], 
                          selected_item['strophe_idx'], selected_item['line_idx'])
            used_metrical_positions.add(position_key)
            
            selected_xml = selected_item['xml']
            line = etree.fromstring(selected_xml)
            sylls = line.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]")
            if len(sylls) >= 5:
                trimmed_sylls = sylls[:-5]  # remove last five syllables
                
                # Create new <l> element and copy attributes from original
                new_line = etree.Element("l")
                # Copy attributes from original line
                for attr, value in line.attrib.items():
                    if attr != 'source':  # Don't copy source if it exists
                        new_line.set(attr, value)
                # Add enhanced source attribute to show contamination prevention
                source_info = f"{selected_item['responsion_id']}, strophe {selected_item['strophe_idx'] + 1}, line {selected_item['line_idx'] + 1}"
                new_line.set('source', source_info)
                for syll in trimmed_sylls:
                    new_line.append(syll)
                
                return new_line
    
    # Try length - 1 and append random syllable
    if (length - 1) in lines_by_length:
        candidate_lines = filter_lines_with_independence_check(
            lines_by_length[length - 1], exclude_file, used_metrical_positions, length
        )
        if candidate_lines:
            if debug:
                print(f"\033[92mFound {len(candidate_lines)} candidate lines of length {length - 1}, appending random syllable.\033[0m")
            
            selected_item = random.choice(candidate_lines)
            
            # Add this position to used positions
            position_key = (selected_item['file'], selected_item['canticum_idx'], 
                          selected_item['strophe_idx'], selected_item['line_idx'])
            used_metrical_positions.add(position_key)
            
            selected_xml = selected_item['xml']
            line = etree.fromstring(selected_xml)
            sylls = line.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]")
            
            # Filter syllables to exclude those from the excluded file
            available_syllables = all_syllables
            if exclude_file:
                syllables_by_file = cached_corpus['syllables_by_file']
                excluded_syllables = set(syllables_by_file.get(exclude_file, []))
                available_syllables = [s for s in all_syllables if s not in excluded_syllables]
            
            if available_syllables:
                random_syllable_xml = random.choice(available_syllables)
                random_syllable = etree.fromstring(random_syllable_xml)
                sylls.append(random_syllable)
            
            # Create new <l> element and copy attributes from original
            new_line = etree.Element("l")
            # Copy attributes from original line
            for attr, value in line.attrib.items():
                if attr != 'source':  # Don't copy source if it exists
                    new_line.set(attr, value)
            # Add enhanced source attribute to show contamination prevention
            source_info = f"{selected_item['responsion_id']}, strophe {selected_item['strophe_idx'] + 1}, line {selected_item['line_idx'] + 1}"
            new_line.set('source', source_info)
            for syll in sylls:
                new_line.append(syll)
            
            return new_line
    
    # Try length - 2 and append two random syllables
    if (length - 2) in lines_by_length:
        candidate_lines = filter_lines_with_independence_check(
            lines_by_length[length - 2], exclude_file, used_metrical_positions, length
        )
        if candidate_lines:
            if debug:
                print(f"\033[92mFound {len(candidate_lines)} candidate lines of length {length - 2}, appending two random syllables.\033[0m")
            
            selected_item = random.choice(candidate_lines)
            
            # Add this position to used positions
            position_key = (selected_item['file'], selected_item['canticum_idx'], 
                          selected_item['strophe_idx'], selected_item['line_idx'])
            used_metrical_positions.add(position_key)
            
            selected_xml = selected_item['xml']
            line = etree.fromstring(selected_xml)
            sylls = line.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]")
            
            # Filter syllables to exclude those from the excluded file
            available_syllables = all_syllables
            if exclude_file:
                syllables_by_file = cached_corpus['syllables_by_file']
                excluded_syllables = set(syllables_by_file.get(exclude_file, []))
                available_syllables = [s for s in all_syllables if s not in excluded_syllables]
            
            if available_syllables and len(available_syllables) >= 2:
                # Append two random syllables
                random_syllable1_xml = random.choice(available_syllables)
                random_syllable1 = etree.fromstring(random_syllable1_xml)
                sylls.append(random_syllable1)
                
                random_syllable2_xml = random.choice(available_syllables)
                random_syllable2 = etree.fromstring(random_syllable2_xml)
                sylls.append(random_syllable2)
            
            # Create new <l> element and copy attributes from original
            new_line = etree.Element("l")
            # Copy attributes from original line
            for attr, value in line.attrib.items():
                if attr != 'source':  # Don't copy source if it exists
                    new_line.set(attr, value)
            # Add enhanced source attribute to show contamination prevention
            source_info = f"{selected_item['responsion_id']}, strophe {selected_item['strophe_idx'] + 1}, line {selected_item['line_idx'] + 1}"
            new_line.set('source', source_info)
            for syll in sylls:
                new_line.append(syll)
            
            return new_line
    
    # Final fallback: search external Aristophanes corpus
    if debug:
        print(f"\033[93mTrying external Aristophanes corpus for length {length}...\033[0m")
    
    external_line = search_external_corpus_for_line(length, debug=debug)
    if external_line is not None:
        if debug:
            print(f"\033[92mFound line of length {length} in external corpus.\033[0m")
        return external_line
    
    if debug:
        print(f"Warning: No lines found with lengths {length}, {length+1}, {length-1}, {length-2}, or in external corpus.")
    return None

def search_external_corpus_for_line(length: int, corpus_folder: str = "/Users/albin/git/aristophanis-cantica/data/compiled/", debug=False):
    """
    Search external corpus (Aristophanes) for lines of given length.
    This is a final fallback when the main Pindar corpus doesn't have enough lines.
    
    Args:
        length: target canonical syllable length
        corpus_folder: folder containing external XML files
        debug: whether to print debug information
        
    Returns:
        XML element or None if not found
    """
    try:
        if not os.path.exists(corpus_folder):
            if debug:
                print(f"External corpus folder {corpus_folder} not found.")
            return None
        
        xml_files = [f for f in os.listdir(corpus_folder) if f.endswith('.xml')]
        if not xml_files:
            if debug:
                print(f"No XML files found in external corpus folder {corpus_folder}.")
            return None
        
        # Try exact length first
        candidate_lines = []
        for xml_file in xml_files:
            try:
                file_path = os.path.join(corpus_folder, xml_file)
                tree = etree.parse(file_path)
                root = tree.getroot()
                l_elements = root.findall(".//l")
                
                for l in l_elements:
                    try:
                        canonical_length = len(canonical_sylls(l))
                        if canonical_length == length:
                            candidate_lines.append(l)
                    except:
                        # Skip lines that cause errors in canonical_sylls
                        continue
                        
            except:
                # Skip files that can't be parsed
                if debug:
                    print(f"Could not parse external file: {xml_file}")
                continue
        
        if candidate_lines:
            if debug:
                print(f"Found {len(candidate_lines)} candidate lines of length {length} in external corpus.")
            selected_line = random.choice(candidate_lines)
            # Add source attribute to indicate external corpus
            selected_line.set('source', 'external_aristophanes')
            return selected_line
        
        # Try length + 1 and trim
        candidate_lines = []
        for xml_file in xml_files:
            try:
                file_path = os.path.join(corpus_folder, xml_file)
                tree = etree.parse(file_path)
                root = tree.getroot()
                l_elements = root.findall(".//l")
                
                for l in l_elements:
                    try:
                        canonical_length = len(canonical_sylls(l))
                        if canonical_length == length + 1:
                            candidate_lines.append(l)
                    except:
                        continue
                        
            except:
                continue
        
        if candidate_lines:
            if debug:
                print(f"Found {len(candidate_lines)} candidate lines of length {length + 1} in external corpus, trimming.")
            
            line = random.choice(candidate_lines)
            sylls = line.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]")
            if len(sylls) > 0:
                trimmed_sylls = sylls[:-1]  # remove last syllable
                
                # Create new <l> element
                new_line = etree.Element("l")
                # Add source attribute to indicate external corpus
                new_line.set('source', 'external_aristophanes')
                for syll in trimmed_sylls:
                    new_line.append(syll)
                
                return new_line
        
        # Try length - 1 and append random syllable from external corpus
        candidate_lines = []
        all_external_syllables = []
        
        for xml_file in xml_files:
            try:
                file_path = os.path.join(corpus_folder, xml_file)
                tree = etree.parse(file_path)
                root = tree.getroot()
                
                # Collect syllables for padding
                for syll in root.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]"):
                    all_external_syllables.append(syll)
                
                # Look for length-1 lines
                l_elements = root.findall(".//l")
                for l in l_elements:
                    try:
                        canonical_length = len(canonical_sylls(l))
                        if canonical_length == length - 1:
                            candidate_lines.append(l)
                    except:
                        continue
                        
            except:
                continue
        
        if candidate_lines and all_external_syllables:
            if debug:
                print(f"Found {len(candidate_lines)} candidate lines of length {length - 1} in external corpus, appending syllable.")
            
            line = random.choice(candidate_lines)
            sylls = line.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]")
            
            # Append random syllable from external corpus
            random_syllable = random.choice(all_external_syllables)
            sylls.append(random_syllable)
            
            # Create new <l> element
            new_line = etree.Element("l")
            # Add source attribute to indicate external corpus
            new_line.set('source', 'external_aristophanes')
            for syll in sylls:
                new_line.append(syll)
            
            return new_line
        
        # Try length + 5 and trim five syllables from external corpus
        candidate_lines = []
        for xml_file in xml_files:
            try:
                file_path = os.path.join(corpus_folder, xml_file)
                tree = etree.parse(file_path)
                root = tree.getroot()
                l_elements = root.findall(".//l")
                
                for l in l_elements:
                    try:
                        canonical_length = len(canonical_sylls(l))
                        if canonical_length == length + 5:
                            candidate_lines.append(l)
                    except:
                        continue
                        
            except:
                continue
        
        if candidate_lines:
            if debug:
                print(f"Found {len(candidate_lines)} candidate lines of length {length + 5} in external corpus, trimming five syllables.")
            
            line = random.choice(candidate_lines)
            sylls = line.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]")
            if len(sylls) >= 5:
                trimmed_sylls = sylls[:-5]  # remove last five syllables
                
                # Create new <l> element
                new_line = etree.Element("l")
                # Add source attribute to indicate external corpus
                new_line.set('source', 'external_aristophanes')
                for syll in trimmed_sylls:
                    new_line.append(syll)
                
                return new_line
        
        # Try length - 2 and append two random syllables from external corpus
        candidate_lines = []
        if not all_external_syllables:  # Collect syllables if not done already
            for xml_file in xml_files:
                try:
                    file_path = os.path.join(corpus_folder, xml_file)
                    tree = etree.parse(file_path)
                    root = tree.getroot()
                    
                    for syll in root.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]"):
                        all_external_syllables.append(syll)
                        
                except:
                    continue
        
        for xml_file in xml_files:
            try:
                file_path = os.path.join(corpus_folder, xml_file)
                tree = etree.parse(file_path)
                root = tree.getroot()
                l_elements = root.findall(".//l")
                
                for l in l_elements:
                    try:
                        canonical_length = len(canonical_sylls(l))
                        if canonical_length == length - 2:
                            candidate_lines.append(l)
                    except:
                        continue
                        
            except:
                continue
        
        if candidate_lines and len(all_external_syllables) >= 2:
            if debug:
                print(f"Found {len(candidate_lines)} candidate lines of length {length - 2} in external corpus, appending two syllables.")
            
            line = random.choice(candidate_lines)
            sylls = line.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]")
            
            # Append two random syllables from external corpus
            random_syllable1 = random.choice(all_external_syllables)
            random_syllable2 = random.choice(all_external_syllables)
            sylls.append(random_syllable1)
            sylls.append(random_syllable2)
            
            # Create new <l> element
            new_line = etree.Element("l")
            # Add source attribute to indicate external corpus
            new_line.set('source', 'external_aristophanes')
            for syll in sylls:
                new_line.append(syll)
            
            return new_line
            
    except Exception as e:
        if debug:
            print(f"Error searching external corpus: {e}")
    
    return None

def make_lyric_baseline_fast(xml_file: str, responsion_id: str, corpus_folder: str = "data/compiled/triads", 
                           outfolder: str = "data/compiled/baselines/triads/lyric", 
                           cache_file: str = "data/cached_lyric_corpus.pkl", debug: bool = False):
    """
    Fast version of make_lyric_baseline using cached preprocessed corpus.
    
    Args:
        xml_file: path to XML file containing the original strophe structure
        responsion_id: the responsion ID to generate baseline for
        corpus_folder: folder containing XML files for lyric line sampling
        outfolder: folder to write the baseline XML file to
        cache_file: path to cached corpus data
        debug: whether to print debug information
    """
    
    # Load cached corpus data
    cached_corpus = load_cached_lyric_corpus(cache_file, corpus_folder)
    
    strophe_scheme = get_shape_canticum(xml_file, responsion_id)

    # Count the number of strophes with the given responsion_id in the original file
    tree = etree.parse(xml_file)
    root = tree.getroot()
    strophes = root.findall(f".//strophe[@responsion='{responsion_id}']")
    sample_size = len(strophes)
    
    # Get the filename of the input XML to exclude from corpus sampling
    input_filename = os.path.basename(xml_file)
    
    if debug:
        print(f"Found {sample_size} strophes with responsion '{responsion_id}' in original file")
        print(f"Strophe scheme: {strophe_scheme}")
        print(f"Excluding {input_filename} from corpus sampling")
        print(f"Generating 100 baseline samples...")
    
    # Generate 100 different baseline samples with different seeds
    strophe_samples_dict = {}
    
    for i in tqdm(range(100)):
        seed = 1453 + i  # Different seed for each sample
        responsion_key = f"{responsion_id}_{i:03d}"  # e.g., "is01_000", "is01_001", etc.
        
        # Track used metrical positions across ALL line positions for this sample to ensure independence
        sample_used_metrical_positions = set()
        
        # Generate lines for each position first, ensuring uniqueness within each position
        lines_by_position = []
        
        for line_idx, line_length in enumerate(strophe_scheme):
            position_lines = []
            used_lines = set()  # Track used lines for this position
            
            attempts = 0
            max_attempts = sample_size * 10  # Allow multiple attempts to find unique lines
            
            while len(position_lines) < sample_size and attempts < max_attempts:
                # Use different seed for each attempt
                line_seed = seed + line_idx * 10000 + attempts
                sample_line = lyric_line_sample_cached(line_length, cached_corpus, seed=line_seed, 
                                                     debug=debug, exclude_file=input_filename,
                                                     used_metrical_positions=sample_used_metrical_positions)
                
                if sample_line is not None:
                    # Convert XML element to string for comparison
                    line_text = etree.tostring(sample_line, encoding='unicode', method='xml')
                    
                    # Check if this line is already used in this position
                    if line_text not in used_lines:
                        position_lines.append(line_text)
                        used_lines.add(line_text)
                    
                attempts += 1
            
            # If we couldn't find enough unique lines with the cached method, 
            # fall back to the original slow method which has more fallback options
            if len(position_lines) < sample_size:
                if debug:
                    print(f"Only found {len(position_lines)} unique cached lines for position {line_idx+1} (length {line_length}), trying fallback methods...")
                
                # Try to fill remaining slots with original method
                remaining_needed = sample_size - len(position_lines)
                fallback_attempts = 0
                max_fallback_attempts = remaining_needed * 20
                
                while len(position_lines) < sample_size and fallback_attempts < max_fallback_attempts:
                    fallback_seed = seed + line_idx * 20000 + fallback_attempts + 10000
                    sample_line = lyric_line_sample(line_length, corpus_folder, seed=fallback_seed, 
                                                  debug=debug, exclude_file=input_filename)
                    
                    if sample_line is not None:
                        # Convert XML element to string for comparison
                        line_text = etree.tostring(sample_line, encoding='unicode', method='xml')
                        
                        # Check if this line is already used in this position
                        if line_text not in used_lines:
                            position_lines.append(line_text)
                            used_lines.add(line_text)
                            if debug:
                                print(f"  Found fallback line #{len(position_lines)} for position {line_idx+1}")
                    
                    fallback_attempts += 1
            
            # If we still couldn't find enough unique lines, raise an error
            if len(position_lines) < sample_size:
                raise RuntimeError(f"Could not find {sample_size} unique lines for position {line_idx+1} (length {line_length}). Only found {len(position_lines)} unique lines after {max_attempts} cached attempts and {max_fallback_attempts} fallback attempts.")
            
            lines_by_position.append(position_lines)
        
        # Now assemble strophes from the position-specific lines
        strophe_sample_lists = []
        
        for strophe_idx in range(sample_size):
            strophe_lines = []
            
            for line_idx in range(len(strophe_scheme)):
                strophe_lines.append(lines_by_position[line_idx][strophe_idx])
            
            strophe_sample_lists.append(strophe_lines)
        
        strophe_samples_dict[responsion_key] = strophe_sample_lists
    
    outdir = outfolder
    os.makedirs(outdir, exist_ok=True)
    print(f"Writing lyric baseline for responsion {responsion_id} to {outdir}")

    filename = f"baseline_lyric_{responsion_id}.xml"
    filepath = os.path.join(outdir, filename)
    dummy_xml_strophe(strophe_samples_dict, filepath, type="Lyric")

    if debug:
        # Debug first sample only
        first_key = list(strophe_samples_dict.keys())[0]
        print(f"Debug: First strophe sample for {first_key}:")
        for i, line in enumerate(strophe_samples_dict[first_key][0]):
            print(f"  Line {i+1} (length {strophe_scheme[i]}): {line}")

