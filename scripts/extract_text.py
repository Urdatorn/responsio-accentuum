import os
import xml.etree.ElementTree as ET

def extract_l_lines_from_folder(folder_path, output_file, ignore_files=None):
    if ignore_files is None:
        ignore_files = []

    lines = []

    for root_dir, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".xml") and file not in ignore_files:
                file_path = os.path.join(root_dir, file)
                try:
                    tree = ET.parse(file_path)
                    root = tree.getroot()

                    for l in root.findall(".//l"):
                        # Skip if skip="True" attribute is present
                        if l.attrib.get("skip") == "True":
                            continue

                        line_text = "".join(l.itertext())
                        line_text = line_text.replace("#", "").replace("€", "").strip()
                        if line_text:
                            lines.append(line_text)
                except ET.ParseError as e:
                    print(f"Failed to parse {file_path}: {e}")

    with open(output_file, "w", encoding="utf-8") as out:
        for line in lines:
            out.write(line + "\n")

# Example usage
if __name__ == "__main__":
    folder = "data/scan"
    output = "norma_aristophanis_canticorum.txt"
    ignore = ["responsion_baseline_scan.xml", "responsion_lyricbaseline_scan.xml"]
    extract_l_lines_from_folder(folder, output, ignore_files=ignore)