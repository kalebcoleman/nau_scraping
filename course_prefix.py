"""
Extracts course prefixes from the NAU Course Numbering and Prefixes PDF.

This script uses the `pdfplumber` library to read a PDF file containing a table
of course prefixes and their corresponding subjects. It then uses regular
expressions to find and extract these prefixes.

The main purpose of this script is to generate the `PREFIXES` list used in the
main `scrape.py` scraping script. When run as a standalone script, it prints
the extracted prefixes to the console in a Python list format.
"""
import re
import pdfplumber
from typing import List

# Path to the PDF file containing the course prefixes.
# This may need to be updated if the file name or location changes.
PDF_PATH = "Course-Numbering-and-Prefixes.pdf"


def extract_prefixes(pdf_path: str) -> List[str]:
    """
    Extracts all unique course prefixes from the given PDF file.

    Args:
        pdf_path (str): The file path to the PDF document.

    Returns:
        List[str]: A sorted list of unique course prefixes.
    """
    prefixes = set()

    # Regex to match a line that starts with a course prefix (e.g., "ACC Accounting").
    # A prefix is defined as 2-6 uppercase letters, possibly with an ampersand.
    prefix_pattern = re.compile(r"^([A-Z&]{2,6})\s+([A-Za-z].+)$")

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                line = line.strip()
                match = prefix_pattern.match(line)
                if not match:
                    continue

                code = match.group(1)
                subject = match.group(2).strip()

                # Filter out common table headers or noise that might match the pattern.
                if code in {"Course", "Code", "Subject", "Letter"}:
                    continue
                # Ensure the code is primarily alphabetic, allowing for '&'.
                if not code.isalpha() and "&" not in code:
                    continue

                prefixes.add(code)

    return sorted(list(prefixes))


if __name__ == "__main__":
    print(f"Extracting prefixes from {PDF_PATH}...")
    extracted_prefixes = extract_prefixes(PDF_PATH)
    print(f"Found {len(extracted_prefixes)} unique prefixes.")

    # Print the prefixes in a format that can be easily copied into a Python list.
    print("\n# Copy the list below into scrape.py")
    print("PREFIXES = [")
    for p in extracted_prefixes:
        print(f'    "{p}",')
    print("]")
