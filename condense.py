import csv
import os
import pandas as pd
import re

# Paths
ROOT = os.path.dirname(__file__)
PULLS_DIR = os.path.join(ROOT, "Pulls")

# Fields: include OEM and Model, Category is appended when writing
FIELDNAMES = ["ID", "Type", "OEM", "Model", "Sale Date", "Details", "Price", "Seller", "Shipping", "Category"]
DATA_COLS = FIELDNAMES[:-1]  # without Category


def detect_category_from_filename(filename: str) -> str:
    lname = filename.lower()
    if "gpu" in lname:
        return "GPU"
    if "ram" in lname:
        return "RAM"
    if "mother" in lname or "mobo" in lname or "board" in lname:
        return "Motherboard"
    return "Unknown"


def _row_from_dict_or_list(row, header):
    # row can be a dict (from DictReader) or a list
    values = []
    if isinstance(row, dict):
        for col in DATA_COLS:
            # case-insensitive key lookup
            val = ""
            for k, v in row.items():
                if k and k.strip().lower() == col.lower():
                    val = v
                    break
            values.append((val or "").strip())
    else:
        # list: use positions, pad/truncate
        values = [ (row[i].strip() if i < len(row) and isinstance(row[i], str) else (row[i] if i < len(row) else "")) for i in range(len(DATA_COLS)) ]
        if len(values) < len(DATA_COLS):
            values += [""] * (len(DATA_COLS) - len(values))
    return values


def read_pull_files(pulls_dir: str) -> dict:
    collected = {}
    if not os.path.isdir(pulls_dir):
        print(f"Pulls directory not found: {pulls_dir}")
        return collected

    for fname in os.listdir(pulls_dir):
        fpath = os.path.join(pulls_dir, fname)
        if not os.path.isfile(fpath):
            continue
        category = detect_category_from_filename(fname)
        try:
            with open(fpath, mode='r', encoding='utf-8', errors='ignore') as fh:
                # Try DictReader first to map OEM/Model fields if present
                sample = fh.read(4096)
                fh.seek(0)
                has_header = ',' in sample and any(h.lower() in sample.lower() for h in ["type", "sale date", "price"])
                if has_header:
                    reader = csv.DictReader(fh)
                    for row in reader:
                        if not any(str(v).strip() for v in row.values() if v is not None):
                            continue
                        values = _row_from_dict_or_list(row, reader.fieldnames)
                        values.append(category)
                        collected.setdefault(category, []).append(values)
                else:
                    reader = csv.reader(fh, delimiter=',', skipinitialspace=True)
                    for row in reader:
                        if not any((str(c).strip() for c in row)):
                            continue
                        values = _row_from_dict_or_list(row, None)
                        values.append(category)
                        collected.setdefault(category, []).append(values)
        except Exception as e:
            print(f"Failed to read {fpath}: {e}")

    return collected


def include_existing_cleaned(root_dir: str, collected: dict):
    for candidate in os.listdir(root_dir):
        if not candidate.lower().endswith(" cleaned.csv"):
            continue
        cat = candidate.rsplit(" ", 1)[0]
        cleaned_path = os.path.join(root_dir, candidate)
        try:
            with open(cleaned_path, mode='r', encoding='utf-8', errors='ignore') as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    if not any(str(v).strip() for v in row.values() if v is not None):
                        continue
                    vals = _row_from_dict_or_list(row, reader.fieldnames)
                    vals.append(cat)
                    collected.setdefault(cat, []).append(vals)
        except Exception:
            continue


def write_category_sale_files(root_dir: str, collected: dict):
    written = []
    for cat, rows in collected.items():
        out_path = os.path.join(root_dir, f"{cat} Sale Price.csv")
        with open(out_path, mode='w', encoding='utf-8', newline='') as fh:
            writer = csv.writer(fh)
            writer.writerow(FIELDNAMES)
            for r in rows:
                # ensure row length matches DATA_COLS
                if len(r) < len(DATA_COLS) + 1:  # +1 because category already appended
                    needed = (len(DATA_COLS) + 1) - len(r)
                    r = r[:-1] + ([""] * needed) + [r[-1]]
                writer.writerow(r)
        written.append(out_path)
    return written


def clean_and_dedup(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    print(f"{os.path.basename(csv_path)}: rows before dedup: {len(df.index)}")
    for col in ["Price", "Details", "Type", "Sale Date", "OEM", "Model"]:
        if col not in df.columns:
            df[col] = ""

    df["Price"] = pd.to_numeric(df["Price"].astype(str).replace('[\$,]', '', regex=True), errors='coerce')
    df_cleaned = df.drop_duplicates().copy()
    print(f"{os.path.basename(csv_path)}: rows after dedup: {len(df_cleaned.index)}")
    out_path = os.path.join(os.path.dirname(csv_path), f"{os.path.splitext(os.path.basename(csv_path))[0].replace(' Sale Price','')} Cleaned.csv")
    df_cleaned.to_csv(out_path, index=False)
    return df_cleaned


def compute_averages_for_df(df_cleaned: pd.DataFrame) -> dict:
    if df_cleaned.empty:
        return {"used": {}, "parts": {}, "usedVol": {}, "partsVol": {}}

    df_cleaned["Sale Date"] = pd.to_datetime(df_cleaned["Sale Date"], errors='coerce')
    cutoff = pd.Timestamp.today() - pd.Timedelta(days=90)
    recent = df_cleaned[df_cleaned["Sale Date"] >= cutoff]
    if recent.empty:
        recent = df_cleaned

    if "Details" not in recent.columns:
        recent["Details"] = ""

    used_df = recent[recent["Details"].astype(str).str.lower() != "parts"]
    parts_df = recent[recent["Details"].astype(str).str.lower() == "parts"]

    used_avg = used_df.groupby("Type")["Price"].mean().round(2)
    used_vol = used_df.groupby("Type").size()
    parts_avg = parts_df.groupby("Type")["Price"].mean().round(2)
    parts_vol = parts_df.groupby("Type").size()

    return {
        "used": used_avg.to_dict(),
        "parts": parts_avg.to_dict(),
        "usedVol": used_vol.to_dict(),
        "partsVol": parts_vol.to_dict(),
    }


def update_firefox_data_js(root_dir: str, category_averages: dict):
    data_js_path = os.path.join(root_dir, "firefox_extension", "data.js")
    os.makedirs(os.path.dirname(data_js_path), exist_ok=True)
    with open(data_js_path, "w", encoding="utf-8", newline="\n") as jsfile:
        jsfile.write("// Auto-generated by condense.py. Do not edit manually.\n")
        jsfile.write(f"// Generated on {pd.Timestamp.today().strftime('%Y-%m-%d')}\n")
        jsfile.write("const dataByCategory = {\n")
        for cat, avgs in category_averages.items():
            jsfile.write(f"  '{cat}': {{\n")
            types = sorted(set(list(avgs['used'].keys()) + list(avgs['parts'].keys())))
            for t in types:
                key = str(t).replace("'", "\\'")
                used = avgs['used'].get(t, 0) or 0
                parts = avgs['parts'].get(t, 0) or 0
                used_vol = int(avgs['usedVol'].get(t, 0) or 0)
                parts_vol = int(avgs['partsVol'].get(t, 0) or 0)
                jsfile.write(f"    '{key}': {{ used: {used}, parts: {parts}, usedVol: {used_vol}, partsVol: {parts_vol} }},\n")
            jsfile.write("  },\n")
        jsfile.write("};\n\n")
        jsfile.write("const gpuAverages = dataByCategory.GPU || {};\n")
        jsfile.write("const ramAverages = dataByCategory.RAM || {};\n")
        jsfile.write("const motherboardAverages = dataByCategory.Motherboard || {};\n")

    print(f"Updated '{data_js_path}' with categories: {', '.join(sorted(category_averages.keys()))}.")


def main():
    collected = read_pull_files(PULLS_DIR)
    include_existing_cleaned(ROOT, collected)

    for k in ["GPU", "RAM", "Motherboard"]:
        collected.setdefault(k, [])

    write_category_sale_files(ROOT, collected)

    category_averages = {}
    for cat in collected.keys():
        csv_path = os.path.join(ROOT, f"{cat} Sale Price.csv")
        if not os.path.exists(csv_path):
            df_cleaned = pd.DataFrame(columns=DATA_COLS)
        else:
            df_cleaned = clean_and_dedup(csv_path)
        category_averages[cat] = compute_averages_for_df(df_cleaned)

    update_firefox_data_js(ROOT, category_averages)


if __name__ == "__main__":
    main()
