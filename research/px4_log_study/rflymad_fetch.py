"""Fetch the RflyMAD real-flight subset from Kaggle (xianglile/rflymad): per case, only the PX4 log (.ulg), the test
information workbook (TestInfo_*.xlsx: fault type and parameters) and wind_data.csv. The processed CSVs and ROS bags
are not needed. Needs a Kaggle API token in ~/.kaggle (never in this repository).

RflyMAD: Le et al., IJRR 2025, doi:10.1177/02783649241305153; copyright Reliable Flight Control Group, Beihang
University; non-commercial use.

The file list is cached in OUT_DIR/kaggle_real_files.json ([name, bytes] pairs for Real-*), because listing all
~70,000 files again trips Kaggle's rate limit. Requests back off on HTTP 429.

    ~/.venvs/kaggle/bin/python research/px4_log_study/rflymad_fetch.py OUT_DIR
"""
import json
import os
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

DATASET = "xianglile/rflymad"


def wanted(name):
    base = name.rsplit("/", 1)[-1]
    return name.startswith("Real-") and (base.endswith(".ulg") or base.startswith("TestInfo_") or base == "wind_data.csv")


def list_files(api):
    out, tok = [], None
    while True:
        res = api.dataset_list_files(DATASET, page_token=tok, page_size=1000)
        out += [(f.name, f.total_bytes) for f in res.files]
        tok = res.next_page_token
        if not tok:
            return out


def main(out_dir):
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    cache = os.path.join(out_dir, "kaggle_real_files.json")
    listing = json.load(open(cache)) if os.path.exists(cache) else list_files(api)
    files = [(n, s) for n, s in listing if wanted(n)]
    print(f"{len(files)} files, {sum(s for _, s in files) / 1e9:.2f} GB", flush=True)

    def get(item):
        name, size = item
        dest = os.path.join(out_dir, name)
        if os.path.exists(dest) and os.path.getsize(dest) == size:
            return "have"
        for attempt in range(6):
            try:
                # the API saves to OUT_DIR/<full dataset path>, sometimes as a .zip
                api.dataset_download_file(DATASET, name, path=out_dir, quiet=True)
                if os.path.exists(dest + ".zip"):
                    with zipfile.ZipFile(dest + ".zip") as zf:
                        zf.extractall(os.path.dirname(dest))
                    os.remove(dest + ".zip")
                if os.path.exists(dest) and os.path.getsize(dest) == size:
                    return "ok"
            except Exception as e:
                time.sleep(30 * (attempt + 1) if "429" in str(e) else 5)
        return "fail"

    with ThreadPoolExecutor(3) as ex:
        res = list(ex.map(get, files))
    print({k: res.count(k) for k in set(res)})


if __name__ == "__main__":
    main(sys.argv[1])
