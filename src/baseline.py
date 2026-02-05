#!/usr/bin/env python3

# Copyright © Albin Ruben Johannes Thörn Cleland 2026, Lunds universitet, albin.thorn_cleland@klass.lu.se
# https://orcid.org/0009-0003-3731-4038
# This file is part of responsio-accentuum, licensed under the GNU General Public License v3.0.
# See the LICENSE file in the project root for full details.

'''
Script to prepare both lyric and prose baselines for Pindar's odes. 

LYRIC BASELINE FALLBACK SYSTEM (Configurable):
The lyric baseline generation uses a comprehensive configurable fallback system to find lines 
of the required syllable length, maintaining statistical independence and authenticity.

Current configuration (easily adjustable via variables at top of script):
- PINDAR_MAX_TRIMMING = 10 (trim up to 10 syllables from Pindar corpus lines)
- EXTERNAL_MAX_TRIMMING = 10 (trim up to 10 syllables from external corpus lines)  
- PINDAR_MAX_PADDING = 4 (add up to 4 syllables to Pindar corpus lines)
- EXTERNAL_MAX_PADDING = 4 (add up to 4 syllables to external corpus lines)

FALLBACK SEQUENCE:
1. Exact length match - Find lines with exactly the target syllable count
2-(1+PINDAR_MAX_TRIMMING). Pindar trimming - Remove 1 to PINDAR_MAX_TRIMMING syllables from longer Pindar lines
(2+PINDAR_MAX_TRIMMING). External exact length - Aristophanes corpus exact match
(3+PINDAR_MAX_TRIMMING)-(2+PINDAR_MAX_TRIMMING+EXTERNAL_MAX_TRIMMING). External trimming - Remove 1 to EXTERNAL_MAX_TRIMMING syllables from external lines
(3+PINDAR_MAX_TRIMMING+EXTERNAL_MAX_TRIMMING)-(2+PINDAR_MAX_TRIMMING+EXTERNAL_MAX_TRIMMING+PINDAR_MAX_PADDING). Pindar padding - Add 1 to PINDAR_MAX_PADDING syllables to shorter Pindar lines
(3+PINDAR_MAX_TRIMMING+EXTERNAL_MAX_TRIMMING+PINDAR_MAX_PADDING)-(2+PINDAR_MAX_TRIMMING+EXTERNAL_MAX_TRIMMING+PINDAR_MAX_PADDING+EXTERNAL_MAX_PADDING). External padding - Add 1 to EXTERNAL_MAX_PADDING syllables to shorter external lines
(final). Paired-line fallback - Pair two Pindar lines and trim the first to fit

STATISTICAL INDEPENDENCE CONSTRAINTS:
The system enforces three levels of statistical independence to ensure robust baselines:

1. FILE CONTAMINATION PREVENTION:
   - Lines from the target file (e.g., is01.xml) are excluded from baseline generation
   - Prevents circular dependency where a text is compared against itself

2. METRICAL POSITION INDEPENDENCE:
   - No two lines can come from the exact same metrical position
   - Position defined as: (file, canticum_idx, strophe_idx, line_idx)
   - Ensures no duplicate source material across the entire baseline

3. RESPONSION INDEPENDENCE PER LINE POSITION:
   - Within each baseline sample (e.g., is01_000), the same relative line position 
     across different strophes cannot use the same responsion_id
   - Example: if line 16 (pos 1 of strophe 1) is from ol10, then line 33 (pos 1 of strophe 2) 
     cannot also be from ol10
   - Prevents correlation between strophes within the same baseline sample

SOURCE ATTRIBUTION:
Each generated line includes enhanced source attribution for transparency:
- Pindar lines: source="py11, strophe 2, line 4" (responsion_id, strophe index, relative line index)
- External lines: source="external_aristophanes"
This enables easy verification of independence constraints and contamination prevention.

PERFORMANCE OPTIMIZATION:
- Preprocessed corpus caching for fast repeated access
- Comprehensive fallback system reduces failure rates
- Systematic length progression maximizes success probability
'''

from collections import defaultdict
from fractions import Fraction
from lxml import etree
import os
from pathlib import Path
import pickle
import random
import re
from statistics import mean
from tqdm import tqdm

from grc_utils import lower_grc, syllabifier

from compile import process_file
from utils.prose import anabasis
from utils.utils import canticum_with_at_least_two_strophes, victory_odes
from scan import rule_scansion
from stats import canonical_sylls
from stats_comp import compatibility_canticum, compatibility_ratios_to_stats

ROOT = Path(__file__).resolve().parent.parent
PROSE_CACHE_PATH = ROOT / "data/cache/cached_prose_corpus.pkl"
LYRIC_CACHE_PATH = ROOT / "data/cache/cached_lyric_corpus.pkl"

def resolve_path(path_like):
    """Resolve relative paths against the repository root."""
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path

# =============================================================================
# CONFIGURATION VARIABLES - Adjust these to control fallback system behavior
# =============================================================================

# Trimming configuration (how many syllables to remove from longer lines)
PINDAR_MAX_TRIMMING = 10        # Max syllables to trim from Pindar corpus lines
EXTERNAL_MAX_TRIMMING = 10      # Max syllables to trim from external corpus lines

# Padding configuration (how many syllables to add to shorter lines)  
PINDAR_MAX_PADDING = 4          # Max syllables to add to Pindar corpus lines
EXTERNAL_MAX_PADDING = 4        # Max syllables to add to external corpus lines

# =============================================================================

punctuation_except_period = r'[\u0387\u037e\u00b7,!?;:\"()\[\]{}<>«»\-—…|⏑⏓†×]'

######################
### TEST STATISTIC ###
######################

def test_statistics(randomizations=10_000) -> tuple[list[Fraction], list[Fraction]]:
    '''
    Generates 10 000 randomizations of the prose corpus and 
    for each calculates two test statistics without saving to disk (to save space).
    Thus returns two lists of len 10 000.
    Since we use seeds, the generation is replicable. 

    For each of the 10 000 passes we call 
        one_t_prose
        one_t_lyric
    yielding four lists.

    Return: (T_pos_prose_list, T_song_prose_list, T_pos_lyric_list, T_song_lyric_list) 
    where each is a list of 10 000 Fractions corresponding to the test statistics calculated in one_t_prose and one_t_lyric respectively.
    '''
    pass

def one_t_prose() -> Fraction:
    '''
    Creates exactly one baseline for each of the odes, storing the xmls in a tmp folder.

    We then calculate the Fraction mean
        compatibility_ratios_to_stats(compatibility_canticum(ROOT / 'tmp_stats/....xml', 'responsion_id'))
    on each of the 40 xmls and then in turn take the statistics.mean T_song_prose of these Fractions.

    We then calculate the Fraction mean $T_pos_prose = \frac{1}{N} \sum_{i=1}^N$
        compatibility_ratios_to_stats(compatibility_corpus(ROOT / 'tmp_stats'))
    on the entire corpus folder of 40 xmls.

    Then the tmp is deleted.

    Return: (T_pos_prose, T_song_prose)
    '''
    pass

def one_t_lyric() -> Fraction:
    "Mutatis mutandis to one_t_prose, but for lyric baselines instead of prose baselines."
    pass

##########################
### MAKE ALL (TO DISK) ###
##########################

def make_all_prose_baselines(responding_unit, randomizations=10_000):

    for collection in ["olympians", "pythians", "nemeans", "isthmians"]:

        xml_path = ROOT / f"data/compiled/{responding_unit}/ht_{collection}_{responding_unit}.xml"

        for responsion_id in tqdm(victory_odes, desc=f"Preparing {collection} scanned prose baselines"):
            if not canticum_with_at_least_two_strophes(xml_path, responsion_id):
                #print(f"Skipping {responsion_id} in {collection} (less than 2 strophes).")
                continue
            make_prose_baseline(xml_path, responsion_id, randomizations=randomizations)

    baseline_scan_dir = ROOT / "data/scan/baselines/triads/prose/"
    baseline_compiled_dir = ROOT / "data/compiled/baselines/triads/prose/"

    baseline_xmls = os.listdir(baseline_scan_dir)
    for baseline_xml in tqdm(baseline_xmls, desc="Compiling prose baselines"):
        if not baseline_xml.endswith(".xml"):
            continue
        infile = os.path.join(baseline_scan_dir, baseline_xml)
        outfile = os.path.join(baseline_compiled_dir, baseline_xml)
        process_file(infile, outfile)

def make_all_lyric_baselines(randomizations=10_000, responsion_ids=None):
    """
    Generate lyric baselines for selected (or all) victory odes with progress tracking and summary statistics.
    
    Args:
        randomizations: number of baseline samples per responsion
        responsion_ids: optional iterable of responsion_ids to process; defaults to all victory_odes
    """
    target_ids = sorted(responsion_ids) if responsion_ids is not None else sorted(victory_odes)
    print(f"Generating lyric baselines for {len(target_ids)} victory odes...")
    
    # Initialize summary statistics
    total_stats = {
        'total_lines': 0,
        'pindar_lines': 0,
        'external_lines': 0,
        'unaltered_lines': 0,
        'trimmed_lines': 0,
        'padded_lines': 0,
        'paired_fallbacks': 0
    }
    
    failed_odes = []
    
    for responsion_id in tqdm(target_ids, desc="Processing odes"):
        try:
            # Determine the correct XML file based on the ode prefix
            if responsion_id[0:2] == "ol":
                xml_file = resolve_path("data/compiled/triads/ht_olympians_triads.xml")
            elif responsion_id[0:2] == "py":
                xml_file = resolve_path("data/compiled/triads/ht_pythians_triads.xml")
            elif responsion_id[0:2] == "ne":
                xml_file = resolve_path("data/compiled/triads/ht_nemeans_triads.xml")
            elif responsion_id[0:2] == "is":
                xml_file = resolve_path("data/compiled/triads/ht_isthmians_triads.xml")
            else:
                print(f"Warning: Unknown ode prefix for {responsion_id}, skipping...")
                failed_odes.append(responsion_id)
                continue
            
            # Generate baseline and collect statistics
            print(f"\nGenerating {randomizations} lyric baselines for {responsion_id}...")
            stats = make_lyric_baseline(xml_file, responsion_id, randomizations=randomizations)
            
            # Add to summary statistics
            for key in total_stats:
                if key in stats:
                    total_stats[key] += stats[key]
            
        except Exception as e:
            print(f"Error processing {responsion_id}: {e}")
            failed_odes.append(responsion_id)
    
    # Print final summary
    print("\n" + "="*60)
    print("LYRIC BASELINE GENERATION SUMMARY")
    print("="*60)
    print(f"Total odes processed: {len(target_ids) - len(failed_odes)}/{len(target_ids)}")
    if failed_odes:
        print(f"Failed odes: {', '.join(failed_odes)}")
    print(f"\nTotal lines generated: {total_stats['total_lines']:,}")
    print(f"\nSource breakdown:")
    print(f"  Pindar corpus: {total_stats['pindar_lines']:,} ({total_stats['pindar_lines']/total_stats['total_lines']*100:.1f}%)")
    print(f"  External corpus: {total_stats['external_lines']:,} ({total_stats['external_lines']/total_stats['total_lines']*100:.1f}%)")
    print(f"\nModification breakdown:")
    print(f"  Unaltered: {total_stats['unaltered_lines']:,} ({total_stats['unaltered_lines']/total_stats['total_lines']*100:.1f}%)")
    print(f"  Trimmed: {total_stats['trimmed_lines']:,} ({total_stats['trimmed_lines']/total_stats['total_lines']*100:.1f}%)")
    print(f"  Padded: {total_stats['padded_lines']:,} ({total_stats['padded_lines']/total_stats['total_lines']*100:.1f}%)")
    print(f"  Paired fallback: {total_stats['paired_fallbacks']:,} ({total_stats['paired_fallbacks']/total_stats['total_lines']*100:.1f}%)")
    print("="*60)
    
    return total_stats

###################
# MAKE BASELINES  #
###################

def make_prose_baseline(xml_file: str, responsion_id: str, debug: bool = False, cache_file: str = PROSE_CACHE_PATH, randomizations: int = 10_000):
    """
    Fast version of make_prose_baseline using cached preprocessed corpus.
    
    Args:
        xml_file: path to XML file containing the original strophe structure
        responsion_id: the responsion ID to generate baseline for
        debug: whether to print debug information
        cache_file: path to cached corpus data
        randomizations: number of baseline samples to generate
    """
    
    xml_file = resolve_path(xml_file)
    cache_file = resolve_path(cache_file)

    # Load cached corpus data
    cached_corpus = load_cached_prose_corpus(cache_file)

    strophe_scheme = get_shape_canticum(str(xml_file), responsion_id)

    # Count the number of strophes with the given responsion_id in the original file
    tree = etree.parse(str(xml_file))
    root = tree.getroot()
    strophes = root.findall(f".//strophe[@responsion='{responsion_id}']")
    sample_size = len(strophes)
    
    if debug:
        print(f"Found {sample_size} strophes with responsion '{responsion_id}' in original file")
        print(f"Strophe scheme: {strophe_scheme}")
        print(f"Generating 100 baseline samples...")
    
    # Generate baseline samples with different seeds
    strophe_samples_dict = {}
    
    for i in tqdm(range(randomizations)):
        seed = 1453 + i  # Different seed for each sample
        responsion_key = f"{responsion_id}_{i:05d}"  # e.g., "is01_000", "is01_001", etc.
        
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
    
    outdir = ROOT / "data/scan/baselines/triads/prose/"
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"Writing prose baseline for responsion {responsion_id} to {outdir}")

    filename = f"baseline_prose_{responsion_id}.xml"
    filepath = outdir / filename
    dummy_xml_strophe(strophe_samples_dict, str(filepath), type="Prose")

    if debug:
        # Debug first sample only
        first_key = list(strophe_samples_dict.keys())[0]
        print(f"Debug: First strophe sample for {first_key}:")
        for i, line in enumerate(strophe_samples_dict[first_key][0]):
            print(f"  Line {i+1} (length {strophe_scheme[i]}): {line}")

def make_lyric_baseline(xml_file: str, responsion_id: str, corpus_folder: str = "data/compiled/triads", 
                           outfolder: str = "data/compiled/baselines/triads/lyric", 
                           cache_file: str = LYRIC_CACHE_PATH, randomizations=10_000, debug: bool = False):
    """
    Fast version of make_lyric_baseline using cached preprocessed corpus.
    
    Args:
        xml_file: path to XML file containing the original strophe structure
        responsion_id: the responsion ID to generate baseline for
        corpus_folder: folder containing XML files for lyric line sampling
        outfolder: folder to write the baseline XML file to
        cache_file: path to cached corpus data
        debug: whether to print debug information
        
    Returns:
        dict: diagnostic statistics about the baseline generation including:
            - total_lines: total number of lines generated
            - pindar_lines: number of lines from Pindar corpus
            - external_lines: number of lines from external corpus
            - unaltered_lines: number of lines used without modification
            - trimmed_lines: number of lines with syllables removed
            - padded_lines: number of lines with syllables added
            - paired_fallbacks: number of lines produced by paired-line fallback
    """
    
    xml_file = resolve_path(xml_file)
    corpus_folder = resolve_path(corpus_folder)
    outfolder = resolve_path(outfolder)
    cache_file = resolve_path(cache_file)

    # Load cached corpus data
    cached_corpus = load_cached_lyric_corpus(cache_file, corpus_folder)
    
    strophe_scheme = get_shape_canticum(str(xml_file), responsion_id)

    # Count the number of strophes with the given responsion_id in the original file
    tree = etree.parse(str(xml_file))
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
    
    # Initialize diagnostic statistics tracking
    total_lines = 0
    pindar_lines = 0
    external_lines = 0
    unaltered_lines = 0
    trimmed_lines = 0
    padded_lines = 0
    paired_fallbacks = 0
    
    # Generate different baseline samples with different seeds
    strophe_samples_dict = {}
    
    for i in range(randomizations):
        seed = 1453 + i  # Different seed for each sample
        responsion_key = f"{responsion_id}_{i:03d}"  # e.g., "is01_000", "is01_001", etc.
        
        # Track used metrical positions across ALL line positions for this sample to ensure independence
        sample_used_metrical_positions = set()
        
        # Track used responsion_ids per relative line position to prevent correlation between strophes
        used_responsions_per_position = [set() for _ in range(len(strophe_scheme))]
        
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
                                                     used_metrical_positions=sample_used_metrical_positions,
                                                     used_responsions_this_position=used_responsions_per_position[line_idx])
                
                if sample_line is not None:
                    # Convert XML element to string for comparison
                    line_text = etree.tostring(sample_line, encoding='unicode', method='xml')
                    
                    # Check if this line is already used in this position
                    if line_text not in used_lines:
                        # Extract responsion_id from the source attribute to track it
                        source_attr = sample_line.get('source', '')
                        if ',' in source_attr:  # Parse enhanced source format
                            responsion_from_source = source_attr.split(',')[0].strip()
                        else:  # Handle simple format or external corpus
                            responsion_from_source = source_attr
                        
                        # Track statistics
                        total_lines += 1
                        if source_attr.startswith('external'):
                            external_lines += 1
                        else:
                            pindar_lines += 1
                        
                        # Check if line was modified
                        if 'trimmed' in source_attr:
                            trimmed_lines += 1
                        elif 'padded' in source_attr:
                            padded_lines += 1
                        else:
                            unaltered_lines += 1
                        
                        # Add responsion to used set for this position
                        used_responsions_per_position[line_idx].add(responsion_from_source)
                        
                        position_lines.append(line_text)
                        used_lines.add(line_text)
                    
                attempts += 1
            
            # If we couldn't find enough unique lines with the cached method, try paired-line fallback before erroring
            if len(position_lines) < sample_size:
                needed = sample_size - len(position_lines)

                def paired_line_fallback(target_len):
                    # Flatten all Pindar lines with metadata, respecting exclusions/independence
                    candidates = []
                    for length_key, lines_list in cached_corpus['lines_by_length'].items():
                        for item in lines_list:
                            # Skip excluded file
                            if input_filename and item['file'] == input_filename:
                                continue
                            position_key = (item['file'], item['canticum_idx'], item['strophe_idx'], item['line_idx'])
                            if position_key in sample_used_metrical_positions:
                                continue
                            if item['responsion_id'] in used_responsions_per_position[line_idx]:
                                continue
                            candidates.append((length_key, item))

                    if len(candidates) < 2:
                        return None

                    max_pairs = min(500, len(candidates) ** 2)
                    for _ in range(max_pairs):
                        length1, item1 = random.choice(candidates)
                        length2, item2 = random.choice(candidates)
                        # ensure independence between the pair themselves
                        pos1 = (item1['file'], item1['canticum_idx'], item1['strophe_idx'], item1['line_idx'])
                        pos2 = (item2['file'], item2['canticum_idx'], item2['strophe_idx'], item2['line_idx'])
                        if pos1 == pos2 or pos2 in sample_used_metrical_positions:
                            continue
                        if item2['responsion_id'] in used_responsions_per_position[line_idx]:
                            continue
                        if length1 + length2 < target_len:
                            continue

                        # Build combined line and trim from the beginning of the first
                        line1 = etree.fromstring(item1['xml'])
                        line2 = etree.fromstring(item2['xml'])
                        sylls1 = line1.xpath(".//syll")
                        sylls2 = line2.xpath(".//syll")
                        total_len = len(sylls1) + len(sylls2)
                        trim_needed = total_len - target_len
                        if trim_needed < 0 or trim_needed > len(sylls1):
                            continue

                        trimmed_sylls1 = sylls1[trim_needed:] if trim_needed else sylls1
                        combined_sylls = trimmed_sylls1 + sylls2
                        if len(combined_sylls) != target_len:
                            continue

                        new_line = etree.Element("l")
                        for attr, value in line1.attrib.items():
                            if attr != 'source':
                                new_line.set(attr, value)
                        source_info = (
                            f"paired:{item1['responsion_id']}+{item2['responsion_id']}, "
                            f"trimmed_first -{trim_needed}"
                        )
                        new_line.set('source', source_info)
                        for syll in combined_sylls:
                            new_line.append(syll)

                        # Update independence trackers
                        sample_used_metrical_positions.add(pos1)
                        sample_used_metrical_positions.add(pos2)
                        used_responsions_per_position[line_idx].add(item1['responsion_id'])
                        used_responsions_per_position[line_idx].add(item2['responsion_id'])
                        return new_line, trim_needed

                    return None

                for _ in range(needed):
                    fallback_result = paired_line_fallback(line_length)
                    if fallback_result is not None:
                        fallback_line, trim_needed = fallback_result
                        line_text = etree.tostring(fallback_line, encoding='unicode', method='xml')
                        position_lines.append(line_text)
                        used_lines.add(line_text)
                        total_lines += 1
                        pindar_lines += 1
                        if trim_needed == 0:
                            unaltered_lines += 1
                        else:
                            trimmed_lines += 1
                        paired_fallbacks += 1
                    else:
                        break

            if len(position_lines) < sample_size:
                raise RuntimeError(f"Could not find {sample_size} unique lines for position {line_idx+1} (length {line_length}). Only found {len(position_lines)} unique lines after {max_attempts} attempts including paired-line fallback.")
            
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
    outdir.mkdir(parents=True, exist_ok=True)
    if debug:
        print(f"Writing lyric baseline for responsion {responsion_id} to {outdir}")

    filename = f"baseline_lyric_{responsion_id}.xml"
    filepath = outdir / filename
    
    # Add anceps="True" to syllables that don't have resolution or anceps attributes
    for responsion_key, strophe_sample_lists in strophe_samples_dict.items():
        for strophe_idx, strophe_sample_list in enumerate(strophe_sample_lists):
            for line_idx, line in enumerate(strophe_sample_list):
                try:
                    line_element = etree.fromstring(line)
                    # Find all syllable elements
                    for syll in line_element.xpath(".//syll"):
                        # Check if syllable already has resolution="True" or anceps="True"
                        if syll.get("resolution") != "True" and syll.get("anceps") != "True":
                            syll.set("anceps", "True")
                    
                    # Convert back to string and update the list
                    updated_line = etree.tostring(line_element, encoding='unicode', method='xml')
                    strophe_samples_dict[responsion_key][strophe_idx][line_idx] = updated_line
                    
                except etree.XMLSyntaxError:
                    # Skip malformed XML lines
                    continue
    
    dummy_xml_strophe(strophe_samples_dict, str(filepath), type="Lyric")

    if debug:
        # Debug first sample only
        first_key = list(strophe_samples_dict.keys())[0]
        print(f"Debug: First strophe sample for {first_key}:")
        for i, line in enumerate(strophe_samples_dict[first_key][0]):
            print(f"  Line {i+1} (length {strophe_scheme[i]}): {line}")
    
    # Return diagnostic statistics
    return {
        'responsion_id': responsion_id,
        'total_lines': total_lines,
        'pindar_lines': pindar_lines,
        'external_lines': external_lines,
        'unaltered_lines': unaltered_lines,
        'trimmed_lines': trimmed_lines,
        'padded_lines': padded_lines,
        'paired_fallbacks': paired_fallbacks
    }

#####################
# PREPROCESS CORPUS #
#####################

def preprocess_and_cache_prose_corpus(corpus: str, cache_file: str = PROSE_CACHE_PATH):
    """
    Preprocess the entire prose corpus once and cache results by syllable length.
    
    Args:
        corpus: the prose text to preprocess
        cache_file: path to save the cached results
        
    Returns:
        dict: syllable_length -> list of processed sentences
    """
    cache_file = resolve_path(cache_file)

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
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, 'wb') as f:
        pickle.dump(dict(sentences_by_length), f)
    
    print(f"Cached {sum(len(v) for v in sentences_by_length.values())} processed sentences")
    print(f"Syllable lengths available: {sorted(sentences_by_length.keys())}")
    print(f"Cache saved to: {cache_file}")
    
    return dict(sentences_by_length)

def load_cached_prose_corpus(cache_file: str = PROSE_CACHE_PATH):
    """
    Load cached prose corpus data.
    
    Args:
        cache_file: path to the cached results
        
    Returns:
        dict: syllable_length -> list of processed sentences
    """
    cache_file = resolve_path(cache_file)

    if not cache_file.exists():
        print(f"Cache file {cache_file} not found. Preprocessing corpus...")
        return preprocess_and_cache_prose_corpus(anabasis, cache_file)
    
    with open(cache_file, 'rb') as f:
        return pickle.load(f)
    
def preprocess_and_cache_lyric_corpus(corpus_folder: str, cache_file: str = LYRIC_CACHE_PATH):
    """
    Preprocess the entire lyric corpus once and cache results by canonical syllable length.
    
    Args:
        corpus_folder: folder containing XML files to process
        cache_file: path to save the cached results
        
    Returns:
        dict: canonical_length -> list of XML line elements (as strings) with metadata
    """
    corpus_folder = resolve_path(corpus_folder)
    cache_file = resolve_path(cache_file)

    print("Preprocessing lyric corpus...")
    
    xml_files = [f for f in os.listdir(corpus_folder) if f.endswith('.xml')]
    
    # Group lines by canonical syllable count
    lines_by_length = defaultdict(list)
    syllables_by_file = {}  # Store all syllables by file for fallback cases
    
    for xml_file in tqdm(xml_files, desc="Processing XML files"):
        file_path = Path(corpus_folder) / xml_file
        tree = etree.parse(str(file_path))
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
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, 'wb') as f:
        pickle.dump(cached_data, f)
    
    print(f"Cached {sum(len(v) for v in lines_by_length.values())} lines")
    print(f"Line lengths available: {sorted(lines_by_length.keys())}")
    print(f"Total syllables cached: {len(all_syllables)}")
    print(f"Cache saved to: {cache_file}")
    
    return cached_data

def load_cached_lyric_corpus(cache_file: str = LYRIC_CACHE_PATH, corpus_folder: str = "data/compiled/triads"):
    """
    Load cached lyric corpus data.
    
    Args:
        cache_file: path to the cached results
        corpus_folder: folder containing XML files (for regenerating cache if needed)
        
    Returns:
        dict: cached corpus data
    """
    cache_file = resolve_path(cache_file)
    corpus_folder = resolve_path(corpus_folder)

    if not cache_file.exists():
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
    
########################
# BASELINE AUXILIARIES #
########################

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

def lyric_line_sample_cached(length: int, cached_corpus: dict, seed=1453, debug=False, exclude_file=None, used_metrical_positions=None, used_responsions_this_position=None):
    """
    Fast version of lyric_line_sample using cached preprocessed corpus.
    
    Args:
        length: target canonical syllable length
        cached_corpus: dict from load_cached_lyric_corpus()
        seed: random seed for reproducibility
        debug: whether to print debug information
        exclude_file: filename to exclude from corpus sampling (to avoid contamination)
        used_metrical_positions: set of used (file, canticum_idx, strophe_idx, line_idx) tuples
        used_responsions_this_position: set of responsion_ids already used for this line position
        
    Returns:
        XML element as string, or None if not found
    """
    random.seed(seed)
    
    lines_by_length = cached_corpus['lines_by_length']
    all_syllables = cached_corpus['all_syllables']
    
    if used_metrical_positions is None:
        used_metrical_positions = set()
    
    if used_responsions_this_position is None:
        used_responsions_this_position = set()
    
    if debug:
        print(f"Searching for lines of length {length}")
        if exclude_file:
            print(f"Excluding {exclude_file} from sampling")
        if used_responsions_this_position:
            print(f"Excluding responsions already used in this position: {used_responsions_this_position}")
    
    # Filter out lines from excluded file, ensure metrical independence, and responsion independence per position
    def filter_lines_with_all_independence_checks(lines_data, exclude_file, used_positions, used_responsions, current_position_idx):
        """
        Filter lines ensuring:
        1. Not from excluded file
        2. Statistical independence (no two lines from same metrical position)
        3. Responsion independence per line position (no same responsion_id for same relative line position)
        
        Args:
            lines_data: list of line dictionaries with metadata
            exclude_file: filename to exclude
            used_positions: set of (file, canticum_idx, strophe_idx, line_idx) tuples already used
            used_responsions: set of responsion_ids already used for this line position
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
            if position_key in used_positions:
                continue
                
            # Skip if we've already used this responsion_id for this line position
            if item['responsion_id'] in used_responsions:
                continue
            
            filtered.append(item)
        
        return filtered
    
    # Try exact length first
    if length in lines_by_length:
        candidate_lines = filter_lines_with_all_independence_checks(
            lines_by_length[length], exclude_file, used_metrical_positions, used_responsions_this_position, length
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
        print(f"\033[93mWarning: No lines found with length {length}. Trying trimming from Pindar corpus.\033[0m")
    
    # Try length + 1 through + MAX and trim syllables (Pindar corpus)
    for extra_length in range(1, PINDAR_MAX_TRIMMING + 1):
        target_length = length + extra_length
        if target_length in lines_by_length:
            candidate_lines = filter_lines_with_all_independence_checks(
                lines_by_length[target_length], exclude_file, used_metrical_positions, used_responsions_this_position, length
            )
            if candidate_lines:
                if debug:
                    print(f"\033[92mFound {len(candidate_lines)} candidate lines of length {target_length}, trimming {extra_length} syllables.\033[0m")
                
                selected_item = random.choice(candidate_lines)
                
                # Add this position to used positions
                position_key = (selected_item['file'], selected_item['canticum_idx'], 
                              selected_item['strophe_idx'], selected_item['line_idx'])
                used_metrical_positions.add(position_key)
                
                selected_xml = selected_item['xml']
                line = etree.fromstring(selected_xml)
                sylls = line.xpath(".//syll")  # Use all syllables, not just non-anceps/non-resolution
                if len(sylls) >= extra_length:
                    trimmed_sylls = sylls[:-extra_length]  # remove last syllables
                    
                    # Create new <l> element and copy attributes from original
                    new_line = etree.Element("l")
                    # Copy attributes from original line
                    for attr, value in line.attrib.items():
                        if attr != 'source':  # Don't copy source if it exists
                            new_line.set(attr, value)
                    # Add enhanced source attribute to show contamination prevention
                    source_info = f"{selected_item['responsion_id']}, strophe {selected_item['strophe_idx'] + 1}, line {selected_item['line_idx'] + 1}, trimmed -{extra_length}"
                    new_line.set('source', source_info)
                    for syll in trimmed_sylls:
                        new_line.append(syll)
                    
                    return new_line
    
    # Final fallback: search external Aristophanes corpus
    if debug:
        print(f"\033[93mTrying external Aristophanes corpus for length {length}...\033[0m")
    
    external_line = search_external_corpus_for_line(length, cached_corpus, all_syllables, exclude_file, used_metrical_positions, used_responsions_this_position, debug=debug)
    if external_line is not None:
        if debug:
            print(f"\033[92mFound line of length {length} in external corpus.\033[0m")
        return external_line
    
    if debug:
        print(f"Warning: No lines found with lengths {length}, {length+1}, {length-1}, {length-2}, or in external corpus.")
    return None

def search_external_corpus_for_line(length: int, cached_corpus: dict, all_syllables: list, exclude_file: str, used_metrical_positions: set, used_responsions_this_position: set, corpus_folder: str = "external/aristophanis-cantica/data/compiled/", debug=False):
    """
    Search external corpus (Aristophanes) for lines of given length.
    This is a final fallback when the main Pindar corpus doesn't have enough lines.
    
    Args:
        length: target canonical syllable length
        cached_corpus: dict from load_cached_lyric_corpus() 
        all_syllables: list of all syllables from cached corpus
        exclude_file: filename to exclude
        used_metrical_positions: set of used metrical positions
        used_responsions_this_position: set of responsion_ids already used for this line position
        corpus_folder: folder containing external XML files
        debug: whether to print debug information
        
    Returns:
        XML element or None if not found
    """
    
    # Filter function for Pindar corpus independence checks
    def filter_lines_with_all_independence_checks(lines_data, exclude_file, used_positions, used_responsions, current_position_idx):
        """
        Filter lines ensuring:
        1. Not from excluded file
        2. Statistical independence (no two lines from same metrical position)
        3. Responsion independence per line position (no same responsion_id for same relative line position)
        """
        filtered = []
        for item in lines_data:
            # Skip excluded file
            if exclude_file and item['file'] == exclude_file:
                continue
                
            # Create position key for independence checking
            position_key = (item['file'], item['canticum_idx'], item['strophe_idx'], item['line_idx'])
            
            # Skip if we've already used a line from this exact metrical position
            if position_key in used_positions:
                continue
                
            # Skip if we've already used this responsion_id for this line position
            if item['responsion_id'] in used_responsions:
                continue
            
            filtered.append(item)
        
        return filtered
    try:
        corpus_folder = resolve_path(corpus_folder)

        if not corpus_folder.exists():
            if debug:
                print(f"External corpus folder {corpus_folder} not found.")
            return None
        
        xml_files = [f for f in os.listdir(corpus_folder) if f.endswith('.xml')]
        if not xml_files:
            if debug:
                print(f"No XML files found in external corpus folder {corpus_folder}.")
            return None
        
        # Try exact length first
        candidate_lines_with_metadata = []
        for xml_file in xml_files:
            try:
                file_path = corpus_folder / xml_file
                tree = etree.parse(str(file_path))
                root = tree.getroot()
                
                # Find all strophes to extract proper responsion_ids 
                for canticum_idx, canticum in enumerate(root.findall(".//canticum")):
                    for strophe_idx, strophe in enumerate(canticum.findall(".//strophe")):
                        responsion_id = strophe.get('responsion', 'unknown')
                        
                        for line_idx, l in enumerate(strophe.findall("l")):
                            try:
                                canonical_length = len(canonical_sylls(l))
                                if canonical_length == length:
                                    # Create metadata similar to cached corpus format
                                    line_metadata = {
                                        'xml': etree.tostring(l, encoding='unicode', method='xml'),
                                        'file': xml_file,
                                        'canticum_idx': canticum_idx,
                                        'strophe_idx': strophe_idx, 
                                        'line_idx': line_idx,
                                        'responsion_id': responsion_id
                                    }
                                    candidate_lines_with_metadata.append(line_metadata)
                            except:
                                # Skip lines that cause errors in canonical_sylls
                                continue
                        
            except:
                # Skip files that can't be parsed
                if debug:
                    print(f"Could not parse external file: {xml_file}")
                continue
        
        if candidate_lines_with_metadata:
            # Apply same independence filtering as internal corpus
            filtered_lines = filter_lines_with_all_independence_checks(
                candidate_lines_with_metadata, exclude_file, used_metrical_positions, used_responsions_this_position, length
            )
            
            if filtered_lines:
                if debug:
                    print(f"Found {len(filtered_lines)} candidate lines of length {length} in external corpus after filtering.")
                
                selected_metadata = random.choice(filtered_lines)
                selected_line = etree.fromstring(selected_metadata['xml'])
                
                # Add proper source attribution showing it's from external corpus but with real responsion
                source_info = f"external:{selected_metadata['responsion_id']}, strophe {selected_metadata['strophe_idx'] + 1}, line {selected_metadata['line_idx'] + 1}"
                selected_line.set('source', source_info)
                
                # Update tracking sets
                position_key = (selected_metadata['file'], selected_metadata['canticum_idx'], 
                              selected_metadata['strophe_idx'], selected_metadata['line_idx'])
                used_metrical_positions.add(position_key)
                used_responsions_this_position.add(selected_metadata['responsion_id'])
                
                return selected_line
            elif debug:
                print(f"Found {len(candidate_lines_with_metadata)} lines of length {length} in external corpus but all filtered out by independence constraints.")
        
        # Try external corpus length + 1 through + MAX and trim syllables
        for extra_length in range(1, EXTERNAL_MAX_TRIMMING + 1):
            candidate_lines_with_metadata = []
            target_length = length + extra_length
            
            for xml_file in xml_files:
                try:
                    file_path = corpus_folder / xml_file
                    tree = etree.parse(str(file_path))
                    root = tree.getroot()
                    
                    # Find all strophes to extract proper responsion_ids
                    for canticum_idx, canticum in enumerate(root.findall(".//canticum")):
                        for strophe_idx, strophe in enumerate(canticum.findall(".//strophe")):
                            responsion_id = strophe.get('responsion', 'unknown')
                            
                            for line_idx, l in enumerate(strophe.findall("l")):
                                try:
                                    canonical_length = len(canonical_sylls(l))
                                    if canonical_length == target_length:
                                        line_metadata = {
                                            'xml': etree.tostring(l, encoding='unicode', method='xml'),
                                            'file': xml_file,
                                            'canticum_idx': canticum_idx,
                                            'strophe_idx': strophe_idx,
                                            'line_idx': line_idx,
                                            'responsion_id': responsion_id
                                        }
                                        candidate_lines_with_metadata.append(line_metadata)
                                except:
                                    continue
                        
                except:
                    continue
            
            if candidate_lines_with_metadata:
                # Apply independence filtering
                filtered_lines = filter_lines_with_all_independence_checks(
                    candidate_lines_with_metadata, exclude_file, used_metrical_positions, used_responsions_this_position, length
                )
                
                if filtered_lines:
                    if debug:
                        print(f"Found {len(filtered_lines)} candidate lines of length {target_length} in external corpus, trimming {extra_length} syllables.")
                    
                    selected_metadata = random.choice(filtered_lines)
                    line = etree.fromstring(selected_metadata['xml'])
                    sylls = line.xpath(".//syll")  # Use all syllables, not just non-anceps/non-resolution
                    
                    if len(sylls) >= extra_length:
                        trimmed_sylls = sylls[:-extra_length]  # remove last syllables
                        
                        # Create new <l> element
                        new_line = etree.Element("l")
                        # Add source attribute showing external corpus with real responsion
                        source_info = f"external:{selected_metadata['responsion_id']}, strophe {selected_metadata['strophe_idx'] + 1}, line {selected_metadata['line_idx'] + 1}, trimmed -{extra_length}"
                        new_line.set('source', source_info)
                        for syll in trimmed_sylls:
                            new_line.append(syll)
                        
                        # Update tracking sets
                        position_key = (selected_metadata['file'], selected_metadata['canticum_idx'], 
                                      selected_metadata['strophe_idx'], selected_metadata['line_idx'])
                        used_metrical_positions.add(position_key)
                        used_responsions_this_position.add(selected_metadata['responsion_id'])
                        
                        return new_line
        
        # Try Pindar corpus with padding (length - 1 through length - MAX_PADDING)
        lines_by_length = cached_corpus['lines_by_length']
        for padding_amount in range(1, PINDAR_MAX_PADDING + 1):
            target_length = length - padding_amount
            if target_length in lines_by_length:
                candidate_lines = filter_lines_with_all_independence_checks(
                    lines_by_length[target_length], exclude_file, used_metrical_positions, used_responsions_this_position, length
                )
                if candidate_lines:
                    if debug:
                        print(f"\033[92mFound {len(candidate_lines)} candidate lines of length {target_length} in Pindar corpus, appending {padding_amount} random syllables.\033[0m")
                    
                    selected_item = random.choice(candidate_lines)
                    
                    # Add this position to used positions
                    position_key = (selected_item['file'], selected_item['canticum_idx'], 
                                  selected_item['strophe_idx'], selected_item['line_idx'])
                    used_metrical_positions.add(position_key)
                    
                    selected_xml = selected_item['xml']
                    line = etree.fromstring(selected_xml)
                    sylls = line.xpath(".//syll")  # Use all syllables, not just non-anceps/non-resolution
                    
                    # Filter syllables to exclude those from the excluded file
                    available_syllables = all_syllables
                    if exclude_file:
                        syllables_by_file = cached_corpus['syllables_by_file']
                        excluded_syllables = set(syllables_by_file.get(exclude_file, []))
                        available_syllables = [s for s in all_syllables if s not in excluded_syllables]
                    
                    if available_syllables and len(available_syllables) >= padding_amount:
                        # Append the required number of random syllables
                        for i in range(padding_amount):
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
                    source_info = f"{selected_item['responsion_id']}, strophe {selected_item['strophe_idx'] + 1}, line {selected_item['line_idx'] + 1}, padded +{padding_amount}"
                    new_line.set('source', source_info)
                    for syll in sylls:
                        new_line.append(syll)
                    
                    return new_line
        
        # Try external corpus with padding (length - 1 through length - MAX_PADDING)
        all_external_syllables = []
        for padding_amount in range(1, EXTERNAL_MAX_PADDING + 1):
            candidate_lines_with_metadata = []
            target_length = length - padding_amount
            
            # Collect syllables if not done already
            if not all_external_syllables:
                for xml_file in xml_files:
                    try:
                        file_path = corpus_folder / xml_file
                        tree = etree.parse(str(file_path))
                        root = tree.getroot()
                        
                        for syll in root.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]"):
                            all_external_syllables.append(syll)
                            
                    except:
                        continue
            
            # Find candidate lines of target length with proper metadata
            for xml_file in xml_files:
                try:
                    file_path = corpus_folder / xml_file
                    tree = etree.parse(str(file_path))
                    root = tree.getroot()
                    
                    for canticum_idx, canticum in enumerate(root.findall(".//canticum")):
                        for strophe_idx, strophe in enumerate(canticum.findall(".//strophe")):
                            responsion_id = strophe.get('responsion', 'unknown')
                            
                            for line_idx, l in enumerate(strophe.findall("l")):
                                try:
                                    canonical_length = len(canonical_sylls(l))
                                    if canonical_length == target_length:
                                        line_metadata = {
                                            'xml': etree.tostring(l, encoding='unicode', method='xml'),
                                            'file': xml_file,
                                            'canticum_idx': canticum_idx,
                                            'strophe_idx': strophe_idx,
                                            'line_idx': line_idx,
                                            'responsion_id': responsion_id
                                        }
                                        candidate_lines_with_metadata.append(line_metadata)
                                except:
                                    continue
                        
                except:
                    continue
            
            if candidate_lines_with_metadata and len(all_external_syllables) >= padding_amount:
                # Apply independence filtering
                filtered_lines = filter_lines_with_all_independence_checks(
                    candidate_lines_with_metadata, exclude_file, used_metrical_positions, used_responsions_this_position, length
                )
                
                if filtered_lines:
                    if debug:
                        print(f"Found {len(filtered_lines)} candidate lines of length {target_length} in external corpus, appending {padding_amount} syllables.")
                    
                    selected_metadata = random.choice(filtered_lines)
                    line = etree.fromstring(selected_metadata['xml'])
                    sylls = line.xpath(".//syll")  # Use all syllables, not just non-anceps/non-resolution
                    
                    # Append required number of random syllables from external corpus
                    for i in range(padding_amount):
                        random_syllable = random.choice(all_external_syllables)
                        sylls.append(random_syllable)
                    
                    # Create new <l> element
                    new_line = etree.Element("l")
                    # Add source attribute showing external corpus with real responsion
                    source_info = f"external:{selected_metadata['responsion_id']}, strophe {selected_metadata['strophe_idx'] + 1}, line {selected_metadata['line_idx'] + 1}, padded +{padding_amount}"
                    new_line.set('source', source_info)
                    for syll in sylls:
                        new_line.append(syll)
                    
                    # Update tracking sets
                    position_key = (selected_metadata['file'], selected_metadata['canticum_idx'], 
                                  selected_metadata['strophe_idx'], selected_metadata['line_idx'])
                    used_metrical_positions.add(position_key)
                    used_responsions_this_position.add(selected_metadata['responsion_id'])
                    
                    return new_line
            
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

#######
# XML #
#######

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

###################
# SHAPE AUX       #
###################

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