from pathlib import Path
import pickle

from responsio_accentuum import test_statistics

ROOT = Path.cwd()

randomizations = 10000
workers = 8
chunk_size = 100

if __name__ == "__main__":
    
    T_exp_pos_prose_list, T_exp_song_prose_list, T_exp_pos_lyric_list, T_exp_song_lyric_list, lyric_stats_summary = test_statistics(
        randomizations,
        workers=workers,
        chunk_size=chunk_size,
        include_lyric_stats=True,
    )

    print("\nFirst sample in each test statistic series:\n")
    print(f"T_pos_prose_list: \033[1;32m{T_exp_pos_prose_list[0]:.3f}\033[0m")
    print(f"T_song_prose_list: \033[1;32m{T_exp_song_prose_list[0]:.3f}\033[0m")
    print(f"T_pos_lyric_list: \033[1;32m{T_exp_pos_lyric_list[0]:.3f}\033[0m")
    print(f"T_song_lyric_list: \033[1;32m{T_exp_song_lyric_list[0]:.3f}\033[0m")

    if lyric_stats_summary:
        print("\nLyric baseline composition (aggregated):")
        for k, v in lyric_stats_summary.items():
            print(f"  {k}: {v}")

    pickle_output = ROOT / "data/cache/test_statistics.pkl"
    with open(pickle_output, "wb") as f:
        pickle.dump((T_exp_pos_prose_list, T_exp_song_prose_list, T_exp_pos_lyric_list, T_exp_song_lyric_list, lyric_stats_summary), f)

    