"""Shows the structure of a downloaded dataset so we can map it to the database.

Usage (PowerShell, from farm-assistant folder):
    python scripts\\inspect_csv.py data\\your_file.csv

It prints the column names, how many rows there are, how many values are
empty in each column, and the first 5 rows. It changes nothing.
"""
import csv
import sys
from pathlib import Path


def read_rows(path: Path):
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            text = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise SystemExit("Could not read the file as text. Save it as CSV (UTF-8) and try again.")

    sample = text[:5000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(text.splitlines(), dialect)
    rows = list(reader)
    return rows, dialect.delimiter


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts\\inspect_csv.py <path-to-csv>")

    path = Path(sys.argv[1])
    if not path.exists():
        raise SystemExit(f"File not found: {path}")
    if path.suffix.lower() not in (".csv", ".txt"):
        raise SystemExit("Please save the dataset as CSV first (Excel: File > Save As > CSV UTF-8).")

    rows, delimiter = read_rows(path)
    if not rows:
        raise SystemExit("The file is empty.")

    header = rows[0]
    data = rows[1:]
    print(f"File: {path.name}")
    print(f"Delimiter found: {delimiter!r}")
    print(f"Data rows: {len(data)}")
    print(f"Columns: {len(header)}\n")

    print(f"{'#':<4}{'column name':<45}{'empty values':<14}example")
    print("-" * 110)
    for i, name in enumerate(header):
        values = [r[i] if i < len(r) else "" for r in data]
        empty = sum(1 for v in values if not v.strip())
        example = next((v for v in values if v.strip()), "")
        print(f"{i:<4}{name[:43]:<45}{empty:<14}{example[:40]}")

    print("\nFirst 5 rows:")
    for row in data[:5]:
        print(" | ".join(cell[:18] for cell in row))


if __name__ == "__main__":
    main()
