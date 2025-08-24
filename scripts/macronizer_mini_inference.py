import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification
from syllagreek_utils import preprocess_greek_line, syllabify_joined
from torch.nn.functional import softmax

from grc_utils import is_vowel, short_vowel, is_diphthong, short_set

model_path = "Ericu950/macronizer_mini"
tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=True)
# Use bfloat16 on CUDA if available; fall back to float32 on CPU
dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
model = AutoModelForTokenClassification.from_pretrained(model_path, torch_dtype=dtype)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()

def macronize_mini(line):
    # -------- Preprocess and Syllabify --------
    tokens = preprocess_greek_line(line)
    syllables = syllabify_joined(tokens)

    # -------- Tokenize Input (pre-split syllables) --------
    inputs = tokenizer(
        syllables,
        is_split_into_words=True,
        return_tensors="pt",
        truncation=True,
        max_length=512,         # RoBERTa typical max length
        padding="max_length"    # keep if your model expects fixed length
    )

    # RoBERTa doesn't use token_type_ids, but remove if present to be safe
    if "token_type_ids" in inputs:
        del inputs["token_type_ids"]

    inputs = {k: v.to(device) for k, v in inputs.items()}

    # -------- Predict --------
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits  # [batch, seq_len, num_labels]
        probs = softmax(logits, dim=-1)
        pred_ids = torch.argmax(probs, dim=-1).squeeze(0).cpu().tolist()

    # -------- Tokenize Input (pre-split syllables) --------
    tokenized = tokenizer(
        syllables,
        is_split_into_words=True,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding="max_length"
    )

    # RoBERTa doesn't use token_type_ids, but remove if present to be safe
    if "token_type_ids" in tokenized:
        del tokenized["token_type_ids"]

    inputs = {k: v.to(device) for k, v in tokenized.items()}

    # -------- Predict --------
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits  # [batch, seq_len, num_labels]
        probs = softmax(logits, dim=-1)
        pred_ids = torch.argmax(probs, dim=-1).squeeze(0).cpu().tolist()

    # -------- Align Predictions with Syllables (first subtoken per word) --------
    # Preferred: use BatchEncoding.word_ids(batch_index=0)
    word_ids = tokenized.word_ids(batch_index=0)   # <-- FIX: no () on a list; this is a method on BatchEncoding

    aligned_preds = []
    seen = set()
    for i, w_id in enumerate(word_ids):
        if w_id is None or w_id in seen:
            continue
        aligned_preds.append((syllables[w_id], pred_ids[i]))
        seen.add(w_id)
        if len(aligned_preds) == len(syllables):
            break

    # -------- Rule-based Postprocessing for "clear" syllables --------
    def classify_syllables(syllables, clear_mask):
        definitely_heavy_set = set("ὖὗἆἇἶἷήηωώἠἡἢἣἤἥἦἧὠὡὢὣὤὥὦὧὴὼᾄᾅᾆᾇᾐᾑᾔᾕᾖᾗᾠᾤᾦᾧᾳᾴᾶᾷῂῃῄῆῇῖῦῲῳῴῶῷ")
        ambiguous_set = set("ΐάίΰαιυϊϋύἀἁἂἃἄἅἰἱἲἳἴἵὐὑὓὔὕὰῒὶὺ")
        light_set = set("έεοόἐἑἓἔἕὀὁὂὃὄὅὲὸ")

        mute_consonants = set("βγδθκπτφχ")
        nonmute_consonants = set("λρμν")
        sigma = set("σ")
        all_consonants = mute_consonants | nonmute_consonants | sigma

        def token_contains(token, char_set):
            return any(ch in char_set for ch in token)

        def get_nucleus(syl):
            nucleus_chars = [ch for token in syl for ch in token if ch not in all_consonants]
            return ''.join(nucleus_chars) if nucleus_chars else None

        def classify_single_syllable(syl, next_syl):
            nucleus = get_nucleus(syl)
            if nucleus is None:
                return "light"

            if len(nucleus) >= 2:
                base_class = "heavy"
            elif token_contains(nucleus, definitely_heavy_set):
                base_class = "heavy"
            elif token_contains(nucleus, ambiguous_set):
                base_class = "ambiguous"
            elif token_contains(nucleus, light_set):
                base_class = "light"
            else:
                base_class = "light"

            final_char = syl[-1][-1]

            if base_class == "heavy":
                return "heavy"
            elif base_class == "ambiguous":
                if final_char in nonmute_consonants:
                    return "heavy"
                if final_char in mute_consonants and next_syl is not None:
                    next_onset = next_syl[0][0]
                    if next_onset not in nonmute_consonants:
                        return "heavy"
                return "muta cum liquida"
            elif base_class == "light":
                if final_char in nonmute_consonants or final_char in sigma:
                    return "heavy"
                elif final_char in mute_consonants and next_syl is not None:
                    next_onset = next_syl[0][0]
                    if next_onset in nonmute_consonants:
                        return "muta cum liquida"
                    else:
                        return "heavy"
                else:
                    return "light"

        classifications = []
        for i, syl in enumerate(syllables):
            if not clear_mask[i]:
                classifications.append(None)
                continue
            next_syl = syllables[i+1] if i < len(syllables) - 1 else None
            classifications.append(classify_single_syllable(syl, next_syl))

        return classifications

    # -------- Prepare Data for Classification --------
    only_sylls = [s for s, _ in aligned_preds]
    labels = [l for _, l in aligned_preds]
    clear_mask = [l == 0 for l in labels]  # assumes 0="clear"
    syllables_tokenized = [[ch for ch in syl] for syl in only_sylls]

    # -------- Apply Rule-based Classifier --------
    rule_based = classify_syllables(syllables_tokenized, clear_mask)

    def heavy_syll(syll):
        """Check if a syllable is heavy (either ends on a consonant or contains a long vowel/diphthong)."""
        
        closed = not is_vowel(syll[-1])
        
        substrings = [syll[i:i+2] for i in range(len(syll) - 1)]
        has_diphthong = any(is_diphthong(substring) for substring in substrings)

        has_long = not short_vowel(syll) # short_vowel does not include short dichrona
        
        return closed or has_diphthong or has_long

    macronized_line = ""

    label_map = {0: "", 1: "_", 2: "^"}
    #print("\nMacronization predictions and all syllable weights:", end="\n\t")
    for syll, label in aligned_preds:
        if label_map[label] == "^":
            macronized_line = macronized_line + "{" + f"{syll}{label_map[label]}" + "}"
        elif (label_map[label] == "_" or heavy_syll(syll)):
            macronized_line = macronized_line + "[" + f"{syll}{label_map[label]}" + "]"
        else:
            macronized_line = macronized_line + "{" + f"{syll}{label_map[label]}" + "}"

    return macronized_line

input = "Σάμερον μὲν χρή σε παρ' ἀνδρὶ φίλῳ"
print(macronize_mini(input))