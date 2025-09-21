import re

from grc_utils import count_ambiguous_dichrona_in_open_syllables, is_diphthong, vowel, short_vowel, syllabifier

muta = r'βγδθκπτφχΒΓΔΘΚΠΤΦΧ' # stops
liquida = r'[λΛμΜνΝρῤῥῬ]' # liquids and nasals

to_clean = r'[\u0387\u037e\u00b7\.,!?;:\"()\[\]{}<>«»\-—…|⏑⏓†×]'

def heavy_syll(syll):
    """Check if a syllable is heavy (either ends on a consonant or contains a long vowel/diphthong)."""

    cleaned = re.sub(to_clean, "", syll.strip())

    closed = not vowel(cleaned[-1])

    substrings = [cleaned[i:i+2] for i in range(len(cleaned) - 1)]
    has_diphthong = any(is_diphthong(substring) for substring in substrings)

    has_long = not short_vowel(syll) and count_ambiguous_dichrona_in_open_syllables(syll) == 0 # short_vowel does not include short dichrona
    
    return closed or has_diphthong or has_long

def scansion(input):
    '''
    Scans vowel-length annotated text (^ and _), putting [] around heavy and {} around light sylls.
    '''
    sylls = syllabifier(input)

    # iterate through sylls and next_sylls: if syll 1) does not contain U+02C8 (ˈ), MODIFIER LETTER VERTICAL LINE, and 2) syll[-1] in muta and 3) next_syll[1] in liquida too, then move syll[-1] to the beginning of next_syll.
    for idx, syll in enumerate(sylls):
        next_syll = sylls[idx + 1] if idx + 1 < len(sylls) else ""
        if "ˈ" not in syll and syll[-1] in muta and next_syll[0] in liquida:
            sylls[idx] = syll[:-1]
            sylls[idx + 1] = syll[-1] + next_syll

    line = ""

    for idx, syll in enumerate(sylls):

        syll_clean = re.sub(to_clean, "", syll.strip())
        next_syll = sylls[idx + 1] if idx + 1 < len(sylls) else ""

        # preempt vowel hiatus and correption
        if vowel(syll[-1]) and next_syll.startswith(" ") and vowel(next_syll[1]):
            line = line + "{" + f"{syll}" + "}"

        elif any("_" in char for char in syll):
            line = line + "[" + f"{syll}" + "]"
        elif syll_clean[-1] == "^":
            line = line + "{" + f"{syll}" + "}"
        elif heavy_syll(syll):
            line = line + "[" + f"{syll}" + "]"
        else:
            line = line + "{" + f"{syll}" + "}"

    return line

if __name__ == "__main__":
    input = "ἁνίκ' ἄγκυ_ρα^ν ποτὶ^ χαλκόγενυ^ν"
    scanned = scansion(input)
    print(scanned)
    input = "ὣς φά^το· τὸν μὲν ἐσελθόντ' ἔγˈνον ὀφθαλμοὶ πατρός"
    scanned = scansion(input)
    print(f"\n{scanned}")