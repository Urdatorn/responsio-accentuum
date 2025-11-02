from src.compile import process_file

print("\n")
print(" -------------- ")
print("< compiling... >")
print(" -------------- ")
print(r"        \   ^__^ ")
print(r"         \  (oo)\_______")
print(r"            (__)\       )\/\ ")
print("                ||----w | ")
print("                ||     || ")
print("\n")

#for odes in ["olympians", "pythians", "nemeans", "isthmians"]:
for odes in [["olympians", "triads"]]:
    process_file(f"data/scan/ht_{odes[0]}_{odes[1]}_corrected.xml", f"data/compiled/{odes[1]}/ht_{odes[0]}_{odes[1]}.xml")