"""
collection_extractor.py  —  consolidated replacement for the three identical
copies of SteamModCollectionExtractor.py.

Scrapes a Steam Workshop *collection* page for its member mod URLs. Output is a
plain URL-per-line file, which is exactly what steam_mod_crawler.py consumes
with --input-mode urls.

Run:
    python collection_extractor.py --collection-id 2490220997 --output urls.txt
    python collection_extractor.py --collection-id 2490220997   # print only
"""

import argparse
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

# Author/profile links that appear alongside each item; not mods.
SKIP_SUBSTRINGS = ["/id/", "/KI5/", "/myworkshopfiles"]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collection-id", required=True,
                    help="workshop ID of the collection page")
    ap.add_argument("--output",
                    help="write URLs here (default: print to stdout only)")
    ap.add_argument("--scrolls", type=int, default=5,
                    help="max lazy-load scroll passes (default: 5)")
    args = ap.parse_args()

    url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={args.collection_id}"

    print("Starting headless Chrome...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    try:
        print(f"Navigating to {url}")
        driver.get(url)

        print("Waiting for initial JS content...")
        time.sleep(2)

        print("Scrolling to load lazy content...")
        last_height = driver.execute_script("return document.body.scrollHeight")
        for i in range(args.scrolls):
            print(f"Scroll {i + 1}")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print("No more content loaded after scrolling.")
                break
            last_height = new_height

        print("Extracting links...")
        links = driver.find_elements(By.CSS_SELECTOR, ".collectionItemDetails a")
        print(f"Found {len(links)} links.")

        filtered = []
        for a in links:
            href = a.get_attribute("href")
            if href and not any(s in href for s in SKIP_SUBSTRINGS):
                filtered.append(href)
                print(href)
    finally:
        driver.quit()

    print(f"Total filtered hrefs: {len(filtered)}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write("\n".join(filtered) + "\n")
        print(f"Wrote {len(filtered)} URLs to {args.output}")

    print("Done.")


if __name__ == "__main__":
    main()
