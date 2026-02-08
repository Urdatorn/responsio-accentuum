#!/usr/bin/env python3

# Copyright © Albin Ruben Johannes Thörn Cleland 2026, Lunds universitet, albin.thorn_cleland@klass.lu.se
# https://orcid.org/0009-0003-3731-4038
# This file is part of responsio-accentuum, licensed under the GNU General Public License v3.0.
# See the LICENSE file in the project root for full details.

"""
Extract epodes from Isthmian triads XML and create a separate epodes XML file.

This script reads the Isthmian triads XML file and extracts all lines with metre="epode"
and subsequent lines from each strophe, creating a new XML file containing only the epodes.
"""

from lxml import etree
from pathlib import Path

ROOT = Path.cwd()

def extract_isthmian_epodes():
    """
    Extract epode sections from Isthmian triads and create epodes XML file.
    """
    input_file = ROOT / "data/compiled/triads/ht_isthmians_triads.xml"
    output_file = ROOT / "data/compiled/epodes/ht_isthmians_epodes.xml"
    
    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Parse input XML
    tree = etree.parse(str(input_file))
    root = tree.getroot()
    
    # Create new XML document
    new_root = etree.Element("TEI")
    
    # Add header
    tei_header = etree.SubElement(new_root, "teiHeader")
    file_desc = etree.SubElement(tei_header, "fileDesc")
    title_stmt = etree.SubElement(file_desc, "titleStmt")
    title = etree.SubElement(title_stmt, "title")
    title.text = "Isthmian Odes"
    author = etree.SubElement(title_stmt, "author")
    author.text = "Pindar"
    
    # Add text body
    text = etree.SubElement(new_root, "text")
    body = etree.SubElement(text, "body")
    
    # Process each canticum
    cantica = root.findall(".//canticum")
    epode_cantica_count = 0
    
    for canticum in cantica:
        strophes = canticum.findall(".//strophe")
        if not strophes:
            continue
        
        # Get responsion_id from first strophe
        responsion_id = strophes[0].get('responsion')
        if not responsion_id:
            continue
        
        # Check if any strophe has epode lines
        has_epodes = False
        for strophe in strophes:
            lines = strophe.findall("l")
            for line in lines:
                if line.get('metre') == 'epode':
                    has_epodes = True
                    break
            if has_epodes:
                break
        
        if not has_epodes:
            continue
        
        # Create new canticum for epodes
        new_canticum = etree.SubElement(body, "canticum")
        
        # Process each strophe in this canticum
        for strophe in strophes:
            lines = strophe.findall("l")
            
            # Find the first epode line
            epode_start_idx = None
            for idx, line in enumerate(lines):
                if line.get('metre') == 'epode':
                    epode_start_idx = idx
                    break
            
            if epode_start_idx is None:
                continue
            
            # Create new strophe with only epode lines
            new_strophe = etree.SubElement(new_canticum, "strophe")
            new_strophe.set('type', strophe.get('type', 'strophe'))
            new_strophe.set('responsion', responsion_id)
            
            # Add newline and indentation after opening strophe tag
            new_strophe.text = "\n          "
            
            # Copy epode lines (from first epode line to end)
            for idx, line in enumerate(lines[epode_start_idx:]):
                # Deep copy the line element
                new_line = etree.Element("l")
                # Copy attributes
                for attr, value in line.attrib.items():
                    new_line.set(attr, value)
                # Copy text content
                if line.text:
                    new_line.text = line.text
                # Copy child elements (syllables)
                for child in line:
                    new_line.append(etree.fromstring(etree.tostring(child)))
                
                # Set proper tail for formatting (newline + indentation)
                # Last line should have different indentation for closing tag
                if idx == len(lines[epode_start_idx:]) - 1:
                    new_line.tail = "\n        "  # Less indentation before closing </strophe>
                else:
                    new_line.tail = "\n          "  # Same indentation as opening
                
                new_strophe.append(new_line)
        
        epode_cantica_count += 1
    
    # Write output XML
    tree_out = etree.ElementTree(new_root)
    tree_out.write(
        str(output_file),
        encoding='utf-8',
        xml_declaration=True,
        pretty_print=True
    )
    
    print(f"Successfully extracted {epode_cantica_count} cantica with epodes")
    print(f"Output written to: {output_file}")

if __name__ == "__main__":
    extract_isthmian_epodes()
