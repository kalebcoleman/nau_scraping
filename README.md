# NAU Course Catalog Scraper

This project scrapes course information from the Northern Arizona University (NAU) academic catalog website. It uses Python and Selenium to automate a web browser, navigate to the course listings, and extract details for each course.

The primary goal of this project is to gather a comprehensive dataset of all courses offered at NAU for specific academic terms, including details like course prefix, number, title, description, and units.

## Features

- Scrapes course data for specified terms (e.g., Fall 2025, Spring 2026).
- Extracts a comprehensive list of course prefixes from a PDF document.
- Saves scraped course data to a CSV file (`outputs/nau_courses.csv`).
- Keeps a log of course prefixes that did not return any results (`outputs/nau_empty_prefixes.csv`).
- Supports both headless and headed browser operation for debugging.
- Can overwrite existing data or incrementally scrape only new courses.

## Project Structure

```
.
├── course_prefix.py         # Script to extract course prefixes from the PDF.
├── data/                    # Input data (PDF + prefixes list).
│   ├── Course-Numbering-and-Prefixes.pdf
│   └── prefixes.json
├── scrape.py                # The main web scraping script.
├── outputs/                 # Output folder for scraper + analysis CSVs.
│   ├── nau_courses.csv       # Scraped course data.
│   └── nau_empty_prefixes.csv # Log of prefixes with no courses.
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

This script is used to generate the list of course prefixes from the `data/Course-Numbering-and-Prefixes.pdf` file. The `PREFIXES` list in `scrape.py` was generated using this script. If the course prefixes change in the future, you can re-run this script to get an updated list.

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

This will run the scraper in headless mode and will not overwrite existing data in `outputs/nau_courses.csv`. It will pick up where it left off if the script was stopped.

**Command-line Arguments:**

-   `--overwrite`: If included, the script will re-scrape all courses and overwrite `outputs/nau_courses.csv` and `outputs/nau_empty_prefixes.csv`.
    ```bash
    python scrape.py --overwrite
    ```

-   `--no-headless`: If included, the script will run the Chrome browser in a visible window, which is useful for debugging.
    ```bash
    python scrape.py --no-headless
    ```

## Output Files

-   `outputs/nau_courses.csv`: This file contains the scraped course data with the following columns:
    -   `term`: The academic term (e.g., "Fall 2025").
    -   `catalog_year`: The catalog year for the course.
    -   `prefix`: The course prefix (e.g., "ACC").
    -   `number`: The course number (e.g., "255").
    -   `title`: The course title.
    -   `description`: The course description.
    -   `units`: The number of units for the course.
    -   `sections_offered`: A semicolon-separated list of offered sections.
    -   `url`: The URL of the course page.

-   `outputs/nau_empty_prefixes.csv`: This file logs any course prefixes that were queried but returned no results for a given term. This is useful for tracking which parts of the catalog might be empty.
    -   `term`: The academic term.
    -   `term_code`: The internal term code used by the NAU website.
    -   `prefix`: The course prefix that was empty.
    -   `error`: The reason it was logged as empty (e.g., "empty").

## AI Curriculum Analysis

To identify AI-related courses and summarize the curriculum coverage, use the analysis script:

```bash
python3 ai_analysis.py
```

This produces (in `outputs/`):

-   `nau_courses_with_flag.csv`: Full course list with `is_ai_related` and `is_ethics_related` boolean columns.
-   `nau_courses_ai_subset.csv`: AI-related course subset (deduped by prefix + number).
-   `nau_prefix_totals.csv`: Prefix | Total Courses (deduped by prefix + number).
-   `nau_summary.csv`: Summary metrics (includes total unique course count).

### Broad AI Candidate Search

If you want to maximize recall and review later, run:

```bash
python3 ai_analysis_broad.py
```

This produces:

-   `nau_courses_ai_candidates.csv`: Broad AI candidate list (may include false positives).

### Why These Keywords

Based on the whiteboard session, the keywords focus on the core AI curriculum and current industry language:

-   Agent, Agentic
-   Ethics
-   LLM, GPT, ChatGPT
-   Deep Learning
-   Generative AI
-   Autonomous Systems
-   Artificial Intelligence
-   Machine Learning

The script also applies fuzzy matching (via `thefuzz`) to catch typos or small variations in titles/descriptions.
For higher precision, it uses word-boundary regex patterns and only treats `ethics`/`agent` as AI-related
when the same course also includes an explicit AI context term.

### Matching Logic (Short Version)

1. **Primary match:** explicit AI terms such as "artificial intelligence", "machine learning",
   "deep learning", "LLM", "GPT", "computer vision", "NLP", etc.
2. **Secondary + context match:** ambiguous terms like "ethics" or "agent" only count
   if the course also contains a primary AI context term.
3. **Fuzzy match (optional):** catches small typos/variations in explicit AI phrases.
4. **Context-gated terms:** ambiguous phrases (including "autonomous systems") only count when
   an explicit AI context term is also present in the title/description for the AI flag.

### Ethics Subset (Separate Script)

For a dedicated ethics list, run:

```bash
python3 ethics_analysis.py
```

This produces:

-   `nau_courses_ethics_subset.csv`: Ethics-related course subset (deduped by prefix + number).

The matching rules live in `ethics_analysis.py`, and the description is always included.

### Expanding Coverage (Still High Relevance)

If you want *more* courses without losing relevance:

- **Add AI-adjacent terms** to `PRIMARY_PATTERNS` and `FUZZY_PHRASES` such as
  `robotics`, `autonomous systems`, `pattern recognition`, `data mining`,
  `knowledge representation`, or `expert systems`.
- **Use context gating** for broader terms (e.g., require "robotics" + "learning" or
  "intelligent systems") to avoid unrelated matches.
- **Tune fuzzy threshold** (default `90`) to slightly lower values like `88` if you are
  missing obvious AI phrasing.

### Known Gaps / Catalog Limits

Some course numbers (e.g., special topics or “contemporary developments” like `499`) can represent
multiple rotating topics across semesters. Because the analysis de-duplicates by `prefix + number`,
those variations are intentionally counted as a single unique course in the totals.

### Dependencies

```bash
pip install pandas thefuzz[speedup]
```
