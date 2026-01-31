"""
This script scrapes course information from the NAU academic catalog.

It uses Selenium to automate a web browser, iterating through a predefined list
of course prefixes and academic terms. For each combination, it fetches a list
of courses, scrapes detailed information from each course page, and stores the
results in a CSV file.

The script is designed to be resumable, loading existing data from the CSV
and skipping courses that have already been scraped unless the `--overwrite`
flag is provided.

Key functionalities:
- Scrapes course details for specified academic terms.
- Handles pagination and dynamic content loading.
- Saves data to a CSV file (`nau_courses.csv`).
- Logs course prefixes that yield no results (`nau_empty_prefixes.csv`).
- Supports headless (default) and headed browser modes for scraping.
- Provides an option to overwrite existing data.
"""
import argparse
import csv
import json
import os
import re
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Dict, List, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    InvalidSessionIdException,
    JavascriptException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)

# =========================
# CONFIG
# =========================

BASE = "https://catalog.nau.edu/Courses"

# Dictionary of academic terms to scrape with their corresponding term codes.
TERM_CODES = {
    "Fall 2025": 1257,
    "Spring 2026": 1261,
}

CSV_PATH = "nau_courses.csv"
EMPTY_PREFIXES_CSV = "nau_empty_prefixes.csv"
PREFIXES_PATH = "prefixes.json"

# Time to wait between requests to be polite to the server.
SLEEP_TIME = 0.25

# =========================
# DATA MODEL
# =========================


@dataclass
class Course:
    """A dataclass to represent a single course."""
    term: str
    catalog_year: Optional[str]
    prefix: str
    number: str
    title: str
    description: Optional[str]
    units: Optional[str]
    sections_offered: Optional[str]
    url: str


# =========================
# UTILS
# =========================


def polite_sleep():
    """Waits for a short period to avoid overwhelming the server."""
    time.sleep(SLEEP_TIME)


def make_driver(headless: bool) -> WebDriver:
    """
    Initializes and returns a Selenium WebDriver instance.

    Configures the driver to run in headless mode if specified and sets a
    default window size.

    Returns:
        WebDriver: The configured Selenium WebDriver instance.
    """
    opts = webdriver.ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1400,900")
    return webdriver.Chrome(options=opts)


def results_url(prefix: str, term_code: int) -> str:
    """
    Constructs the URL for the course results page for a given prefix and term.

    Args:
        prefix (str): The course prefix (e.g., "ACC").
        term_code (int): The internal term code for the academic term.

    Returns:
        str: The fully-qualified URL.
    """
    return f"{BASE}/results?subject={prefix}&catNbr=&term={term_code}"


def load_existing_urls() -> set[str]:
    """
    Loads existing course URLs from the CSV file into a set.

    Returns:
        set[str]: A set of course URLs. Returns an empty set if the file
                  does not exist.
    """
    existing = set()
    try:
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get("url")
                if url:
                    existing.add(url)
        print(f"Loaded {len(existing)} existing courses from {CSV_PATH}")
    except FileNotFoundError:
        print(f"No existing CSV found at {CSV_PATH} — starting fresh.")
    return existing


def load_prefixes(path: str) -> List[str]:
    """
    Loads course prefixes from a JSON file.

    Args:
        path (str): Path to the JSON file containing a list of prefixes.

    Returns:
        List[str]: A list of course prefixes.
    """
    prefixes_path = Path(path)
    if not prefixes_path.exists():
        raise FileNotFoundError(
            f"Prefix file not found at {path}. Run course_prefix.py to generate it."
        )

    with prefixes_path.open(encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list) or not all(isinstance(p, str) for p in data):
        raise ValueError(f"Invalid prefixes format in {path}; expected JSON list.")

    return data


def write_csv(rows: Dict[str, Dict]):
    """
    Writes the given course data to the main CSV file.

    This function overwrites the entire file to ensure consistency.

    Args:
        rows (Dict[str, Dict]): A dictionary of course data, where keys are
                                course URLs.
    """
    if not rows:
        return

    # The fieldnames are derived from the Course dataclass for stability.
    fieldnames = [field.name for field in fields(Course)]

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows.values())


def open_append_writer(fieldnames: List[str]) -> tuple[csv.DictWriter, object]:
    """
    Opens the CSV file in append mode and writes a header if needed.

    Returns:
        tuple[csv.DictWriter, object]: The writer and the file handle (caller closes).
    """
    needs_header = not os.path.exists(CSV_PATH) or os.path.getsize(CSV_PATH) == 0
    f = open(CSV_PATH, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    if needs_header:
        writer.writeheader()
    return writer, f


def log_empty_prefix(term_label: str, term_code: int, prefix: str, error: str):
    """
    Logs a course prefix that returned no results to a separate CSV file.

    Args:
        term_label (str): The human-readable academic term.
        term_code (int): The internal term code.
        prefix (str): The course prefix that was empty.
        error (str): A short description of why it's considered empty.
    """
    # Create the file and write the header if it doesn't exist.
    write_header = not os.path.exists(EMPTY_PREFIXES_CSV)
    with open(EMPTY_PREFIXES_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["term", "term_code", "prefix", "error"]
        )
        if write_header:
            writer.writeheader()
        writer.writerow(
            {
                "term": term_label,
                "term_code": term_code,
                "prefix": prefix,
                "error": error,
            }
        )


# =========================
# SCRAPING HELPERS
# =========================


def get_course_links(
    driver: WebDriver, prefix: str, term_code: int, retries: int = 2, wait_s: int = 15
) -> List[str]:
    """
    Fetches the list of individual course page URLs for a given prefix and term.

    Args:
        driver (WebDriver): The Selenium driver.
        prefix (str): The course prefix.
        term_code (int): The internal term code.
        retries (int): The number of times to retry on timeout.
        wait_s (int): The number of seconds for explicit waits.

    Returns:
        List[str]: A sorted list of unique course page URLs.
    """
    for attempt in range(retries + 1):
        driver.get(results_url(prefix, term_code))
        wait = WebDriverWait(driver, wait_s)

        try:
            # Wait for either the course list or the "no courses found" message.
            wait.until(
                EC.any_of(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "dl#results-list dt.result-item > a")
                    ),
                    EC.presence_of_element_located(
                        (By.XPATH, "//div[@id='main']//h1[normalize-space()='No courses found']")
                    ),
                )
            )
        except TimeoutException:
            if attempt < retries:
                print(f"[WARN] Timeout on {prefix} list page, retrying...")
                continue
            print(f"[WARN] {prefix} list timed out after {retries} retries; skipping.")
            return []

        # If the "no courses found" message is present, return an empty list.
        if driver.find_elements(By.XPATH, "//div[@id='main']//h1[normalize-space()='No courses found']"):
            return []

        # Collect all unique course links from the page.
        links = set()
        for a in driver.find_elements(By.CSS_SELECTOR, "dl#results-list dt.result-item > a"):
            href = a.get_attribute("href")
            if href:
                # Ensure the URL is absolute.
                if href.startswith("course?"):
                    href = f"{BASE}/{href}"
                links.add(href)

        return sorted(list(links))

    return []


def text_after_label(driver: WebDriver, label: str) -> Optional[str]:
    """
    Extracts the text content immediately following a bolded label element.

    This is used to get fields like "Description:" or "Units:".

    Args:
        driver (WebDriver): The Selenium driver.
        label (str): The text of the label to find (e.g., "Description").

    Returns:
        Optional[str]: The text content, or None if the label isn't found.
    """
    try:
        strong_element = driver.find_element(
            By.XPATH,
            f"//div[@id='courseResults']//strong[normalize-space()='{label}:']",
        )
    except NoSuchElementException:
        return None

    # Use JavaScript to get the next sibling text node's content.
    # This is more robust for handling variations in spacing and nested elements.
    try:
        return driver.execute_script(
            """
            let node = arguments[0].nextSibling;
            while (node) {
              const text = (node.textContent || '').trim();
              if (text) return text;
              node = node.nextSibling;
            }
            return null;
            """,
            strong_element,
        )
    except (JavascriptException, WebDriverException):
        return None


def get_catalog_year(driver: WebDriver) -> Optional[str]:
    """
    Extracts the catalog year from the course page header.

    Args:
        driver (WebDriver): The Selenium driver.

    Returns:
        Optional[str]: The catalog year (e.g., "2023-2024"), or None.
    """
    try:
        header_text = driver.find_element(By.CSS_SELECTOR, "#h1-first").text
        match = re.search(r"Catalog Year\s*:\s*([0-9]{4}\s*-\s*[0-9]{4})", header_text)
        if match:
            return match.group(1).replace(" ", "")
    except (NoSuchElementException, StaleElementReferenceException):
        pass
    return None


def get_sections_offered(driver: WebDriver) -> Optional[str]:
    """
    Extracts the "Sections offered" links from the course page.

    Args:
        driver (WebDriver): The Selenium driver.

    Returns:
        Optional[str]: A semicolon-separated string of section terms, or None.
    """
    try:
        anchors = driver.find_elements(
            By.XPATH,
            "//div[@id='courseResults']//strong[normalize-space()='Sections offered:']/following-sibling::a",
        )
        texts = [a.text.strip() for a in anchors if a.text.strip()]
        return "; ".join(texts) if texts else None
    except (StaleElementReferenceException, WebDriverException):
        return None


def scrape_course(driver: WebDriver, url: str, term_label: str) -> Course:
    """
    Scrapes all relevant details from a single course page.

    Args:
        driver (WebDriver): The Selenium driver.
        url (str): The URL of the course page to scrape.
        term_label (str): The human-readable academic term for this scrape.

    Returns:
        Course: A `Course` dataclass instance with the scraped information.
    """
    driver.get(url)
    wait = WebDriverWait(driver, 15)

    # The main header contains the prefix, number, and title.
    h2 = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#courseResults h2"))
    )
    header = h2.text.strip()

    # Regex to parse "PREFIX 123 - Course Title"
    match = re.match(r"^([A-Z&]{2,6})\s+(\d{3}[A-Z]?)\s*-\s*(.+)$", header)
    prefix, number, title = ("", "", header)
    if match:
        prefix, number, title = match.group(1), match.group(2), match.group(3).strip()

    course = Course(
        term=term_label,
        catalog_year=get_catalog_year(driver),
        prefix=prefix,
        number=number,
        title=title,
        description=text_after_label(driver, "Description"),
        units=text_after_label(driver, "Units"),
        sections_offered=get_sections_offered(driver),
        url=url,
    )

    polite_sleep()
    return course


# =========================
# MAIN
# =========================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape NAU course catalog.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing course data instead of skipping duplicates.",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser in headed mode (default is headless).",
    )
    parser.add_argument(
        "--prefixes",
        default=PREFIXES_PATH,
        help="Path to JSON file with course prefixes.",
    )
    return parser.parse_args()


def main():
    """
    The main execution function for the scraper.

    Initializes the driver, loads existing data, iterates through terms and
    prefixes, scrapes new courses, and saves the results.
    """
    args = parse_args()
    prefixes = load_prefixes(args.prefixes)
    driver = make_driver(headless=not args.no_headless)

    fieldnames = [field.name for field in fields(Course)]
    existing_rows: Dict[str, Dict] = {}
    existing_urls: set[str] = set()
    append_writer = None
    append_file = None

    if args.overwrite:
        print("Overwrite enabled: will write CSV once at the end.")
    else:
        existing_urls = load_existing_urls()
        append_writer, append_file = open_append_writer(fieldnames)

    try:
        total_prefixes = len(prefixes) * len(TERM_CODES)
        step = 1
        new_total = 0
        seen_urls = set(existing_urls)

        for term_label, term_code in TERM_CODES.items():
            for prefix in prefixes:
                print(
                    f"[{step}/{total_prefixes}] {term_label} {prefix}: fetching list..."
                )
                links = get_course_links(driver, prefix, term_code)
                print(
                    f"[{step}/{total_prefixes}] {term_label} {prefix}: {len(links)} courses found"
                )

                if not links:
                    log_empty_prefix(term_label, term_code, prefix, "empty")
                    step += 1
                    continue

                new_count = 0
                for link in links:
                    # Skip if we've already seen this course (existing or earlier in run).
                    if link in seen_urls:
                        if not args.overwrite:
                            continue
                        # Avoid duplicate work in overwrite mode as well.
                        continue

                    try:
                        course = scrape_course(driver, link, term_label)
                        row = asdict(course)
                        if args.overwrite:
                            existing_rows[link] = row
                            seen_urls.add(link)
                        else:
                            append_writer.writerow(row)
                            seen_urls.add(link)
                        new_count += 1
                    except InvalidSessionIdException as e:
                        print(
                            f"[WARN] WebDriver session lost while scraping {link}. "
                            "Restarting driver..."
                        )
                        try:
                            driver.quit()
                        except Exception:
                            pass  # Driver may already be gone
                        driver = make_driver(headless=not args.no_headless)
                        # The current link is skipped, but it will be picked up on a future run
                        # because it hasn't been added to `seen_urls`.
                        continue
                    except (
                        TimeoutException,
                        NoSuchElementException,
                        StaleElementReferenceException,
                        WebDriverException,
                    ) as e:
                        print(
                            f"[WARN] Failed to scrape {link}: {type(e).__name__}: {e}"
                        )

                if new_count > 0:
                    new_total += new_count
                    print(
                        f"[{step}/{total_prefixes}] {term_label} {prefix}: Scraped {new_count} new/updated courses"
                    )
                    if not args.overwrite and append_file:
                        append_file.flush()

                step += 1

    finally:
        print("Scraping finished. Shutting down WebDriver.")
        driver.quit()
        if append_file:
            append_file.close()

    if args.overwrite:
        write_csv(existing_rows)
        total = len(existing_rows)
    else:
        total = len(existing_urls) + new_total
    print(f"Finished. Total courses in CSV: {total}")


if __name__ == "__main__":
    main()
