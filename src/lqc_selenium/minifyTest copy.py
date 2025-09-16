import os, pickle

folder = "pickles"

for fn in os.listdir(folder):
    if fn.endswith(".pkl"):
        path = os.path.join(folder, fn)
        with open(path, "rb") as f:
            obj = pickle.load(f)
        print(f"\n--- {fn} ---")
        print(obj)
