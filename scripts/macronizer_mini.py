import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification
from syllagreek_utils import preprocess_greek_line, syllabify_joined
from torch.nn.functional import softmax

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
    word_ids = tokenized.word_ids(batch_index=0)

    aligned_preds = []
    seen = set()
    for i, w_id in enumerate(word_ids):
        if w_id is None or w_id in seen:
            continue
        aligned_preds.append((syllables[w_id], pred_ids[i]))
        seen.add(w_id)
        if len(aligned_preds) == len(syllables):
            break

    macronized_line = ""
    label_map = {0: "", 1: "_", 2: "^"}
    for syll, label in aligned_preds:
        macronized_line = macronized_line + f"{syll}{label_map[label]}"

    return macronized_line

