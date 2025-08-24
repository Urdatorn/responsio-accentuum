from grc_macronizer import Macronizer
from grc_utils import is_diphthong, is_vowel, short_vowel, syllabifier

to_clean = r'[\u0387\u037e\u00b7\.,!?;:\"()\[\]{}<>«»\-—…|⏑⏓†×]'

def heavy_syll(syll):
    """Check if a syllable is heavy (either ends on a consonant or contains a long vowel/diphthong)."""

    cleaned = syll.strip().translate(str.maketrans("", "", to_clean))
    closed = not is_vowel(cleaned[-1])

    substrings = [cleaned[i:i+2] for i in range(len(cleaned) - 1)]
    has_diphthong = any(is_diphthong(substring) for substring in substrings)

    has_long = not short_vowel(syll) # short_vowel does not include short dichrona
    
    return closed or has_diphthong or has_long

def scansion(input):
    '''
    Scans vowel-length annotated text (^ and _), putting [] around heavy and {} around light sylls.
    '''

    line = ""

    sylls = syllabifier(input)
    for syll in sylls:
        if any("^" in char for char in syll):
            line = line + "{" + f"{syll}" + "}"
        elif any("_" in char for char in syll):
            line = line + "[" + f"{syll}" + "]"
        elif heavy_syll(syll):
            line = line + "[" + f"{syll}" + "]"
        else:
            line = line + "{" + f"{syll}" + "}"

    return line

if __name__ == "__main__":
    input = "Δαρείου καὶ Παρυσάτιδος γίγνονται παῖδες δύο, πρεσβύτερος μὲν Ἀρταξέρξης, νεώτερος δὲ Κῦρος"
    scanned = scansion(input)
    print(scanned)