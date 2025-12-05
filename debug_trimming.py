#!/usr/bin/env python3

"""
Debug script to test the discrepancy between canonical_sylls() and xpath syllable counting
in the lyric baseline trimming logic.
"""

from lxml import etree
from src.stats import canonical_sylls

# Test with the actual XML lines from test.py
xml_lines = [
    '''<l n="20" source="ne09, strophe 6, line 2"><syll weight="heavy" anceps="True">θυ</syll><syll weight="light" anceps="True">μὸν </syll><syll weight="heavy" anceps="True">αἰ</syll><syll weight="heavy" anceps="True">σχυν</syll><syll weight="heavy" anceps="True">θῆ</syll><syll weight="light" anceps="True">μεν. </syll><syll weight="heavy" anceps="True">ἐν </syll><syll weight="heavy" anceps="True">γὰρ </syll><syll weight="heavy" anceps="True">δαι</syll><syll weight="light" anceps="True">μο</syll><syll weight="light" anceps="True">νί</syll><syll weight="heavy" anceps="True">οι</syll><syll weight="light" anceps="True">σι </syll><syll weight="light" anceps="True">φό</syll><syll weight="heavy" anceps="True">βοις </syll><syll weight="heavy" anceps="True">φεύ</syll><syll weight="heavy" anceps="True">γον</syll><syll weight="light" anceps="True">τι </syll><syll weight="heavy" anceps="True">καὶ </syll><syll weight="heavy" anceps="True">παῖ</syll><syll weight="heavy" anceps="True">δες </syll><syll weight="light" anceps="True">θε</syll><syll weight="heavy" anceps="True">ῶν.</syll></l>''',
    '''<l n="47" source="is06, strophe 2, line 12"><syll weight="heavy" anceps="True">τὸν </syll><syll weight="light" anceps="True">μὲν </syll><syll weight="heavy" anceps="True">ἐν </syll><syll weight="heavy" anceps="True">ῥι</syll><syll weight="heavy" anceps="True">νῷ </syll><syll weight="light" anceps="True">λέ</syll><syll weight="heavy" anceps="True">ον</syll><syll weight="heavy" anceps="True">τος </syll><syll weight="heavy" anceps="True">στάν</syll><syll weight="light" anceps="True">τα </syll><syll weight="light" anceps="True">κε</syll><syll weight="heavy" anceps="True">λή</syll><syll weight="light" anceps="True">σα</syll><syll weight="light" anceps="True">το </syll><syll weight="heavy" anceps="True">νε</syll><syll weight="light" anceps="True">κτα</syll><syll weight="light" anceps="True">ρέ</syll><syll weight="heavy" anceps="True">αις </syll><syll weight="heavy" anceps="True">σπον</syll><syll weight="heavy" anceps="True">δαῖ</syll><syll weight="light" anceps="True">σιν </syll><syll weight="heavy" anceps="True">ἄρ</syll><syll weight="heavy" anceps="True">ξαι</syll></l>''',
    '''<l n="101" source="ol07, strophe 1, line 10, trimmed -1"><syll weight="heavy" anceps="True">λυμ</syll><syll weight="light" anceps="True">πί</syll><syll weight="heavy" anceps="True">ᾳ </syll><syll weight="heavy" anceps="True">Πυ</syll><syll weight="heavy" anceps="True">θοῖ </syll><syll weight="light" anceps="True">τε </syll><syll weight="heavy" anceps="True">νι</syll><syll weight="heavy" anceps="True">κών</syll><syll weight="heavy" anceps="True">τεσ</syll><syll weight="light" anceps="True">σιν· </syll><syll weight="light" anceps="True">ὁ </syll><syll weight="heavy" anceps="True">δ᾽ὄλ</syll><syll weight="light" anceps="True">βι</syll><syll weight="light" anceps="True">ος, </syll><syll weight="heavy" anceps="True">ὃν </syll><syll weight="heavy" anceps="True">φᾶ</syll><syll weight="heavy" anceps="True">μαι </syll><syll weight="light" anceps="True">κα</syll><syll weight="light" anceps="True">τέ</syll><syll weight="heavy" anceps="True">χωντʼ </syll><syll weight="light" anceps="True">ἀ</syll><syll weight="light" anceps="True">γα</syll></l>''',
]

print("Testing syllable counting discrepancy in trimming logic:")
print("=" * 70)

for i, xml_line_str in enumerate(xml_lines, 1):
    line_element = etree.fromstring(xml_line_str)
    
    # Method 1: canonical_sylls (used for initial length determination)
    canonical_count = len(canonical_sylls(line_element))
    
    # Method 2: xpath (used in trimming logic)
    xpath_sylls = line_element.xpath(".//syll[not(@resolution='True') and not(@anceps='True')]")
    xpath_count = len(xpath_sylls)
    
    # Method 3: all syllables
    all_sylls = line_element.xpath(".//syll")
    all_count = len(all_sylls)
    
    print(f"Line {i}:")
    print(f"  canonical_sylls(): {canonical_count}")
    print(f"  xpath (not resolution/anceps): {xpath_count}")  
    print(f"  all syllables: {all_count}")
    print(f"  Source: {line_element.get('source', 'N/A')}")
    
    if canonical_count != xpath_count:
        print(f"  ⚠️  DISCREPANCY: canonical={canonical_count}, xpath={xpath_count}")
        
        # Let's see what canonical_sylls actually returns
        canonical_result = canonical_sylls(line_element)
        print(f"  canonical_sylls result: {canonical_result}")
        
        # Check for anceps syllables
        anceps_sylls = line_element.xpath(".//syll[@anceps='True']")
        resolution_sylls = line_element.xpath(".//syll[@resolution='True']")
        print(f"  anceps syllables: {len(anceps_sylls)}")
        print(f"  resolution syllables: {len(resolution_sylls)}")
    
    print()

print("ANALYSIS:")
print("The bug is likely that canonical_sylls() and xpath counting treat anceps/resolution differently!")
print("canonical_sylls() handles resolution collapse (two consecutive resolution -> one canonical position)")
print("while xpath simply excludes syllables marked as resolution='True' or anceps='True'.")
print("\nFor trimming to work correctly, it should use the same counting method as canonical_sylls!")