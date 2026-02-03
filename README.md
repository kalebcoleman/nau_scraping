# NAU Course Catalog Scraper

This project scrapes course information from the Northern Arizona University (NAU) academic catalog website. It uses Python and Selenium to automate a web browser, navigate to the course listings, and extract details for each course.

The primary goal of this project is to gather a comprehensive dataset of all courses offered at NAU for specific academic terms, including details like course prefix, number, title, description, and units.

## Features

- Scrapes course data for specified terms (e.g., Fall 2025, Spring 2026).
- Extracts a comprehensive list of course prefixes from a PDF document.
- Saves scraped course data to a CSV file (`nau_courses.csv`).
- Keeps a log of course prefixes that did not return any results (`nau_empty_prefixes.csv`).
- Supports both headless and headed browser operation for debugging.
- Can overwrite existing data or incrementally scrape only new courses.

## Project Structure

```
.
├── course_prefix.py         # Script to extract course prefixes from the PDF.
├── Course-Numbering-and-Prefixes.pdf # PDF document with NAU course prefixes.
├── scrape.py                # The main web scraping script.
├── nau_courses.csv          # Output: Scraped course data.
├── nau_empty_prefixes.csv   # Output: Log of prefixes with no courses.
└── README.md                # This file.
```

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd nau_course_scraping
    ```

2.  **Install dependencies:**
    This project requires Python 3 and the following libraries: `selenium`, `pdfplumber`. You will also need to have Google Chrome and the corresponding ChromeDriver installed.

    You can install the Python libraries using pip:
    ```bash
    pip install selenium pdfplumber
    ```

## How to Run

There are two main scripts in this project.

### 1. `course_prefix.py` (Optional)

This script is used to generate the list of course prefixes from the `Course-Numbering-and-Prefixes.pdf` file. The `PREFIXES` list in `scrape.py` was generated using this script. If the course prefixes change in the future, you can re-run this script to get an updated list.

```bash
python course_prefix.py
```

This will print a Python list of prefixes to the console, which you can then copy into `scrape.py`.

### 2. `scrape.py`

This is the main script that performs the web scraping.

**Basic Usage:**
```bash
python scrape.py
```

This will run the scraper in headless mode and will not overwrite existing data in `nau_courses.csv`. It will pick up where it left off if the script was stopped.

**Command-line Arguments:**

-   `--overwrite`: If included, the script will re-scrape all courses and overwrite `nau_courses.csv` and `nau_empty_prefixes.csv`.
    ```bash
    python scrape.py --overwrite
    ```

-   `--no-headless`: If included, the script will run the Chrome browser in a visible window, which is useful for debugging.
    ```bash
    python scrape.py --no-headless
    ```

## Output Files

-   `nau_courses.csv`: This file contains the scraped course data with the following columns:
    -   `term`: The academic term (e.g., "Fall 2025").
    -   `catalog_year`: The catalog year for the course.
    -   `prefix`: The course prefix (e.g., "ACC").
    -   `number`: The course number (e.g., "255").
    -   `title`: The course title.
    -   `description`: The course description.
    -   `units`: The number of units for the course.
    -   `sections_offered`: A semicolon-separated list of offered sections.
    -   `url`: The URL of the course page.

-   `nau_empty_prefixes.csv`: This file logs any course prefixes that were queried but returned no results for a given term. This is useful for tracking which parts of the catalog might be empty.
    -   `term`: The academic term.
    -   `term_code`: The internal term code used by the NAU website.
    -   `prefix`: The course prefix that was empty.
    -   `error`: The reason it was logged as empty (e.g., "empty").

## AI Curriculum Analysis ("Rock On" Script)

To identify AI-related courses and summarize the curriculum coverage, use the analysis script:

```bash
python3 ai_course_analysis.py
```

This produces:

-   `nau_courses_with_ai_flag.csv`: Full course list with `is_ai_related` boolean column.
-   `nau_courses_ai_subset.csv`: AI-related course subset (deduped by prefix + number).
-   `nau_prefix_summary.csv`: Prefix | Total Courses | AI-Related Courses Found.
-   `nau_gap_report.csv`: Prefixes that yielded zero results during the scrape.

### Why These Keywords

Based on the whiteboard session, the keywords focus on the core AI curriculum and current industry language:

-   Agent, Agentic
-   Ethics
-   LLM, GPT, ChatGPT
-   Deep Learning
-   Generative AI
-   Artificial Intelligence
-   Machine Learning

The script also applies fuzzy matching (via `thefuzz`) to catch typos or small variations in titles/descriptions.

### Dependencies

```bash
pip install pandas thefuzz[speedup]
```
