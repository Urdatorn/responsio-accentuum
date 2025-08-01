import xml.etree.ElementTree as ET
from grc_utils import vowel

def space_before(syll):
    """Returns True if there is a space before the first vowel in the syllable's text."""
    text = syll.text if syll.text else ""
    for i, char in enumerate(text):
        if vowel(char):  # Find the first vowel
            return i > 0 and text[i - 1] == " "
    return False


def space_after(syll):
    """Returns True if there is a space after the last vowel in the syllable's text."""
    text = syll.text if syll.text else ""
    last_vowel_index = -1

    for i, char in enumerate(text):
        if vowel(char):
            last_vowel_index = i  # Keep track of the last vowel position

    return last_vowel_index != -1 and last_vowel_index < len(text) - 1 and text[last_vowel_index + 1] == " "


def get_words_xml(l_element):
    '''
    Doesn't support resolution yet
    '''
    words = []
    current_word = []

    syllables = [child for child in l_element if child.tag == "syll"]

    for i, syll in enumerate(syllables):
        syll_xml = ET.tostring(syll, encoding='unicode', method='xml')
        current_word.append(syll_xml)
        next_syll = syllables[i + 1] if i + 1 < len(syllables) else None

        if space_after(syll):
            #print()
            #print(f'SPACE AFTER CASE: |{syll}|')
            words.append("".join(current_word))  # Store current word
            current_word = []  # Start a new word
        elif syll.tail and " " in syll.tail:
            #print()
            #print(f'TAIL CASE: |{syll.tail}|')
            words.append("".join(current_word))
            current_word = []
        elif next_syll is not None and space_before(next_syll):
            #print()
            #print(f'SPACE BEFORE NEXT CASE: |{next_syll}|')
            words.append("".join(current_word))
            current_word = []

    if current_word:
        words.append("".join(current_word))

    cleaned_words = []
    for word in words:
        root = ET.fromstring(f"<wrapper>{word}</wrapper>")
        for syll in root.iter("syll"):  
            syll.tail = None

        cleaned_words.append("".join(ET.tostring(syll, encoding="unicode", method="xml") for syll in root))
    words = cleaned_words

    return words


#test_line = '<l n="204" metre="4 tr^" speaker="ΧΟ."><syll weight="heavy">Τῇ</syll><syll weight="light">δε</syll> <syll weight="heavy">πᾶ</syll><syll weight="light" anceps="True">ς ἕ</syll><syll weight="heavy">που</syll>, </l>'
#root = etree.fromstring(test_line)
#words_xml = get_words_xml(root)
#print(f'WORDS: {words_xml}')  #
#if words_xml == ['<syll weight="heavy">Τῇ</syll><syll weight="light">δε</syll>', '<syll weight="heavy">πᾶ</syll>', '<syll weight="light" anceps="True">ς ἕ</syll><syll weight="heavy">που</syll>']:
#    print('PASS')
#else:
#    print('FAIL')