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
for odes in ["olympians"]:
    process_file(f"data/scan/ht_{odes}_strophes.xml", f"data/compiled/strophes/ht_{odes}_strophes.xml")