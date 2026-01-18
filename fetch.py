import requests
import json
import re
from bs4 import BeautifulSoup

API_URL = "https://sv.wikipedia.org/w/api.php"
PAGE_TITLE = "Lista_över_namnsdagar_i_Sverige_i_datumordning"
OUTPUT_FILE = "svenska_namnsdagar.json"

HEADERS = {
    "User-Agent": "swedish-nameday-api/1.0 (https://example.com)"
}

MONTH_MAP = {
    "januari": "01",
    "februari": "02",
    "mars": "03",
    "april": "04",
    "maj": "05",
    "juni": "06",
    "juli": "07",
    "augusti": "08",
    "september": "09",
    "oktober": "10",
    "november": "11",
    "december": "12",
}

# Dates that should be empty (contain only junk/holiday info)
EMPTY_DATES = {
    "01-01", "02-02", "02-29", "03-25", "06-24", "11-01", "12-25"
}

# Dates where names have junk in parentheses that needs removal
DATES_WITH_JUNK = {
    "04-30", "05-01", "12-24", "12-26", "12-28"
}


def fetch_html():
    params = {
        "action": "parse",
        "page": PAGE_TITLE,
        "prop": "text",
        "format": "json"
    }

    r = requests.get(API_URL, params=params, headers=HEADERS)
    r.raise_for_status()
    return r.json()["parse"]["text"]["*"]


def parse_tables(html):
    soup = BeautifulSoup(html, "html.parser")
    result = {}

    tables = soup.find_all("table", class_="wikitable")

    for table in tables:
        rows = table.find_all("tr")[1:]  # skip header

        for row in rows:
            cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if len(cols) < 2:
                continue

            date_part = cols[0].lower()
            names_part = cols[1]

            parts = date_part.split()
            if len(parts) != 2:
                continue

            day, month_sv = parts
            month = MONTH_MAP.get(month_sv)
            if not month:
                continue

            key = f"{month}-{int(day):02d}"

            # Handle special dates
            if key in EMPTY_DATES:
                result[key] = []
                continue

            # For dates with junk, remove parenthetical content from each name
            if key in DATES_WITH_JUNK:
                names = []
                for n in names_part.replace(" och ", ",").split(","):
                    cleaned = re.sub(r"\s*\([^)]*\)", "", n).strip()
                    if cleaned:
                        names.append(cleaned)
                result[key] = names
                continue

            names = [
                n.strip()
                for n in names_part.replace(" och ", ",").split(",")
                if n.strip()
            ]

            result[key] = names

    return result


def main():
    print("Fetching Wikipedia data...")
    html = fetch_html()

    print("Parsing name days...")
    data = parse_tables(html)

    print(f"Writing {OUTPUT_FILE} ({len(data)} days)")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Done ✔")


if __name__ == "__main__":
    main()
