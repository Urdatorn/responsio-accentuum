Implement the three stubs in src/baseline.py with minimal collateral changes, matching TODO/nb definitions of T_pos and T_song.

Steps
1) Add needed imports (likely shutil for temp cleanup) near the top of src/baseline.py, keeping other functions unchanged.
2) Map each responsion_id prefix (ol|py|ne|is) to its triads source XML path under data/compiled/triads/ht_*_triads.xml for reuse in both prose/lyric runs.
3) Implement one_t_prose in src/baseline.py: create/clean a temp folder (e.g., ROOT/tmp_stats/prose), load cached prose corpus once, generate a single baseline per victory_odes responsion with existing prose sampling logic (unique lines per position, deterministic seeds), write each to the temp folder via dummy_xml_strophe, compute per-song stats via compatibility_canticum→compatibility_ratios_to_stats then mean for T_song_prose, compute T_pos_prose via compatibility_corpus→compatibility_ratios_to_stats, then remove the temp folder.
4) Implement one_t_lyric similarly: use a separate temp folder, call make_lyric_baseline(..., randomizations=1, outfolder=temp), use the _000 canticum IDs for compatibility_canticum, compute T_song_lyric and T_pos_lyric, and clean up.
5) Implement test_statistics(randomizations=10_000): loop with tqdm for the given count, call one_t_prose and one_t_lyric per iteration, append to four result lists, and return them.
6) Keep all other functions untouched; no signature changes beyond the stubs.

Verification
- Run a lightweight sanity check with randomizations=1 to ensure temp dirs populate and stats compute without errors.
- Optionally dry-run one_t_prose and one_t_lyric individually to confirm temp cleanup and expected file naming.

Decisions
- Use ROOT/tmp_stats/prose and ROOT/tmp_stats/lyric for scratch output to avoid touching existing baseline folders.
- Derive triads source paths from responsion prefixes (ol/py/ne/is) to minimize extra parameters.
