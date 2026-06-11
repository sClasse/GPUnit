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

    df["Price"] = pd.to_numeric(df["Price"].astype(str).replace(r'[\$,]', '', regex=True), errors='coerce')
    df_cleaned = df.drop_duplicates().copy()
    print(f"{os.path.basename(csv_path)}: rows after dedup: {len(df_cleaned.index)}")
    out_path = os.path.join(os.path.dirname(csv_path), f"{os.path.splitext(os.path.basename(csv_path))[0].replace(' Sale Price','')} Cleaned.csv")
    df_cleaned.to_csv(out_path, index=False)
    return df_cleaned


def compute_averages_for_df(df_cleaned: pd.DataFrame) -> dict:
    if df_cleaned.empty:
        empty_group = {"used": {}, "parts": {}, "usedVol": {}, "partsVol": {}}
        return {
            "types": empty_group,
            "oems": empty_group,
            "models": empty_group,
            "modelOnly": empty_group,
        }

    df_cleaned["Sale Date"] = pd.to_datetime(df_cleaned["Sale Date"], errors='coerce')
    cutoff = pd.Timestamp.today() - pd.Timedelta(days=90)
    recent = df_cleaned[df_cleaned["Sale Date"] >= cutoff]
    if recent.empty:
        recent = df_cleaned

    if "Details" not in recent.columns:
        recent["Details"] = ""

    def _grouped_stats(df, group_cols):
        group = df.groupby(group_cols)["Price"]
        avg = group.mean().round(2).to_dict()
        vol = group.size().to_dict()
        return avg, vol

    used_df = recent[recent["Details"].astype(str).str.lower() != "parts"].copy()
    parts_df = recent[recent["Details"].astype(str).str.lower() == "parts"].copy()

    types_used_avg, types_used_vol = _grouped_stats(used_df, ["Type"])
    types_parts_avg, types_parts_vol = _grouped_stats(parts_df, ["Type"])

    oems_used_df = used_df[used_df["OEM"].astype(str).str.strip() != ""]
    oems_parts_df = parts_df[parts_df["OEM"].astype(str).str.strip() != ""]
    oems_used_avg, oems_used_vol = _grouped_stats(oems_used_df, ["OEM"])
    oems_parts_avg, oems_parts_vol = _grouped_stats(oems_parts_df, ["OEM"])

    models_used_df = used_df[(used_df["OEM"].astype(str).str.strip() != "") & (used_df["Model"].astype(str).str.strip() != "")]
    models_parts_df = parts_df[(parts_df["OEM"].astype(str).str.strip() != "") & (parts_df["Model"].astype(str).str.strip() != "")]
    models_used_avg, models_used_vol = _grouped_stats(models_used_df, ["Type", "OEM", "Model"])
    models_parts_avg, models_parts_vol = _grouped_stats(models_parts_df, ["Type", "OEM", "Model"])

    model_only_used_df = used_df[used_df["Model"].astype(str).str.strip() != ""]
    model_only_parts_df = parts_df[parts_df["Model"].astype(str).str.strip() != ""]
    model_only_used_avg, model_only_used_vol = _grouped_stats(model_only_used_df, ["Model"])
    model_only_parts_avg, model_only_parts_vol = _grouped_stats(model_only_parts_df, ["Model"])

    def _dictify_model_keys_by_type(d):
        """Convert (type, oem, model) tuples into nested Type -> OEM -> Model structure."""
        result = {}
        for (typ, oem, model), value in d.items():
            if typ not in result:
                result[typ] = {}
            if oem not in result[typ]:
                result[typ][oem] = {}
            result[typ][oem][model] = value
        return result

    models_by_type_used = _dictify_model_keys_by_type(models_used_avg)
    models_by_type_parts = _dictify_model_keys_by_type(models_parts_avg)
    models_by_type_used_vol = _dictify_model_keys_by_type(models_used_vol)
    models_by_type_parts_vol = _dictify_model_keys_by_type(models_parts_vol)

    return {
        "types": {
            "used": types_used_avg,
            "parts": types_parts_avg,
            "usedVol": types_used_vol,
            "partsVol": types_parts_vol,
        },
        "oems": {
            "used": oems_used_avg,
            "parts": oems_parts_avg,
            "usedVol": oems_used_vol,
            "partsVol": oems_parts_vol,
        },
        "models": {
            "used": models_by_type_used,
            "parts": models_by_type_parts,
            "usedVol": models_by_type_used_vol,
            "partsVol": models_by_type_parts_vol,
        },
        "modelOnly": {
            "used": model_only_used_avg,
            "parts": model_only_parts_avg,
            "usedVol": model_only_used_vol,
            "partsVol": model_only_parts_vol,
        },
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
            # types
            jsfile.write("    types: {\n")
            type_keys = sorted(set(list(avgs['types']['used'].keys()) + list(avgs['types']['parts'].keys())))
            for t in type_keys:
                key = str(t).replace("'", "\\'")
                used = avgs['types']['used'].get(t, 0) or 0
                parts = avgs['types']['parts'].get(t, 0) or 0
                used_vol = int(avgs['types']['usedVol'].get(t, 0) or 0)
                parts_vol = int(avgs['types']['partsVol'].get(t, 0) or 0)
                jsfile.write(f"      '{key}': {{ used: {used}, parts: {parts}, usedVol: {used_vol}, partsVol: {parts_vol} }},\n")
            jsfile.write("    },\n")
            # OEMs
            jsfile.write("    oems: {\n")
            oem_keys = sorted(set(list(avgs['oems']['used'].keys()) + list(avgs['oems']['parts'].keys())))
            for oem in oem_keys:
                key = str(oem).replace("'", "\\'")
                used = avgs['oems']['used'].get(oem, 0) or 0
                parts = avgs['oems']['parts'].get(oem, 0) or 0
                used_vol = int(avgs['oems']['usedVol'].get(oem, 0) or 0)
                parts_vol = int(avgs['oems']['partsVol'].get(oem, 0) or 0)
                jsfile.write(f"      '{key}': {{ used: {used}, parts: {parts}, usedVol: {used_vol}, partsVol: {parts_vol} }},\n")
            jsfile.write("    },\n")
            # models nested by Type, then OEM, then Model
            jsfile.write("    models: {\n")
            for typ, by_oem in sorted(avgs['models']['used'].items()):
                typ_key = str(typ).replace("'", "\\'")
                jsfile.write(f"      '{typ_key}': {{\n")
                for oem, models in sorted(by_oem.items()):
                    omekey = str(oem).replace("'", "\\'")
                    jsfile.write(f"        '{omekey}': {{\n")
                    for model, used in sorted(models.items()):
                        mkey = str(model).replace("'", "\\'")
                        parts = avgs['models']['parts'].get(typ, {}).get(oem, {}).get(model, 0) or 0
                        used_vol = int(avgs['models']['usedVol'].get(typ, {}).get(oem, {}).get(model, 0) or 0)
                        parts_vol = int(avgs['models']['partsVol'].get(typ, {}).get(oem, {}).get(model, 0) or 0)
                        jsfile.write(f"          '{mkey}': {{ used: {used}, parts: {parts}, usedVol: {used_vol}, partsVol: {parts_vol} }},\n")
                    jsfile.write("        },\n")
                jsfile.write("      },\n")
            jsfile.write("    },\n")
            # model-only averages
            jsfile.write("    modelOnly: {\n")
            model_only_keys = sorted(set(list(avgs['modelOnly']['used'].keys()) + list(avgs['modelOnly']['parts'].keys())))
            for model in model_only_keys:
                key = str(model).replace("'", "\\'")
                used = avgs['modelOnly']['used'].get(model, 0) or 0
                parts = avgs['modelOnly']['parts'].get(model, 0) or 0
                used_vol = int(avgs['modelOnly']['usedVol'].get(model, 0) or 0)
                parts_vol = int(avgs['modelOnly']['partsVol'].get(model, 0) or 0)
                jsfile.write(f"      '{key}': {{ used: {used}, parts: {parts}, usedVol: {used_vol}, partsVol: {parts_vol} }},\n")
            jsfile.write("    },\n")
            jsfile.write("  },\n")
        jsfile.write("};\n\n")
        jsfile.write("const gpuAverages = dataByCategory.GPU ? dataByCategory.GPU.types : {};\n")
        jsfile.write("const ramAverages = dataByCategory.RAM ? dataByCategory.RAM.types : {};\n")
        jsfile.write("const motherboardAverages = dataByCategory.Motherboard ? dataByCategory.Motherboard.types : {};\n")

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
