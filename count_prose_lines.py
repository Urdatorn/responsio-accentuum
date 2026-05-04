from responsio_accentuum import prose_end_sample_cached, load_cached_prose_corpus, PROSE_CACHE_PATH

cached_corpus = load_cached_prose_corpus(PROSE_CACHE_PATH)

dictionary = {}
for n_sylls in range(1, 60):
    available_sentences = prose_end_sample_cached(cached_corpus, n_sylls, 10000, seed=1453)
    dictionary[n_sylls] = len(available_sentences)
    print(f"Available prose end samples for {n_sylls} syllables: {len(available_sentences)}")

print(dictionary)