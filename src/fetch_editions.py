import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw_html")
os.makedirs(RAW_DIR, exist_ok=True)

# List of target editions:
# 1) First edition upon entry into force (01.09.2001)
# 2) End of each year: 2001-12-31 .. 2025-12-31
# 3) Current edition (latest)
EDITIONS = [
    ("2001_09_01", "2001-09-01", "https://zakon.rada.gov.ua/laws/show/2341-14/ed20010901/print"),
]
for year in range(2001, 2026):
    EDITIONS.append((
        str(year),
        f"{year}-12-31",
        f"https://zakon.rada.gov.ua/laws/show/2341-14/ed{year}1231/print"
    ))
EDITIONS.append((
    "current",
    "2026-11-14",
    "https://zakon.rada.gov.ua/laws/show/2341-14/print"
))


def fetch_one(ed_id, snap_date, url):
    filepath = os.path.join(RAW_DIR, f"kk_{ed_id}.html")
    if os.path.exists(filepath) and os.path.getsize(filepath) > 200_000:
        return ed_id, "cached", os.path.getsize(filepath)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            if len(data) < 200_000:
                raise ValueError(f"Response too small ({len(data)} bytes)")
            with open(filepath, "wb") as f:
                f.write(data)
            return ed_id, "downloaded", len(data)
        except Exception as e:
            if attempt == 3:
                return ed_id, f"ERROR: {e}", 0
            time.sleep(1.5 * (attempt + 1))


def main():
    print(f"Downloading {len(EDITIONS)} editions to {RAW_DIR}...")
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(fetch_one, ed_id, snap_date, url): (ed_id, snap_date)
            for ed_id, snap_date, url in EDITIONS
        }
        for fut in as_completed(futures):
            ed_id, status, size = fut.result()
            print(f"  [{ed_id:10s}] {status:12s} ({size:,} bytes)")


if __name__ == "__main__":
    main()

