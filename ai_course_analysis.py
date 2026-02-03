#!/usr/bin/env python3
"""
Analyze NAU course data to identify AI-related curriculum and summarize results.

Inputs:
  - Course CSV with columns: prefix, number, title, description (plus any others)
  - Empty-prefix CSV (from scraper) listing prefixes with no results

Outputs:
  - Full course list with is_ai_related boolean
  - AI-only subset CSV
  - Prefix summary CSV (total + AI-related unique courses)
  - Gap report CSV (prefixes with zero results)
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:  # pragma: no cover - runtime dependency check
    print("Missing dependency: pandas. Install with: pip install pandas", file=sys.stderr)
    raise SystemExit(1)

try:
    from thefuzz import fuzz
except ImportError:  # pragma: no cover - runtime dependency check
    print(
        "Missing dependency: thefuzz. Install with: pip install thefuzz[speedup]",
        file=sys.stderr,
    )
    raise SystemExit(1)

KEYWORDS = [
    "Agent",
    "Agentic",
    "Ethics",
    "LLM",
    "Deep Learning",
    "Generative AI",
    "Artificial Intelligence",
    "Machine Learning",
    "GPT",
    "ChatGPT",
]

NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_text(text: str) -> str:
    lowered = text.lower()
    cleaned = NON_ALNUM_RE.sub(" ", lowered)
    return " ".join(cleaned.split())


def contains_keyword(text_norm: str, keyword_norms: list[str]) -> bool:
    if not text_norm:
        return False
    return any(keyword in text_norm for keyword in keyword_norms)


def max_fuzzy_score(text_norm: str, keyword_norms: list[str]) -> int:
    if not text_norm:
        return 0
    return max(fuzz.partial_ratio(text_norm, keyword) for keyword in keyword_norms)


def read_empty_prefixes(path: Path) -> list[str]:
    if not path.exists():
        return []
    prefixes: list[str] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if not row:
                continue
            first_cell = row[0].strip().lower()
            if first_cell in {"term", "prefix"}:
                continue
            if len(row) >= 3:
                prefix = row[2].strip()
            else:
                prefix = row[0].strip()
            if prefix:
                prefixes.append(prefix)
    return sorted(set(prefixes))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Identify AI-related courses and summarize results."
    )
    parser.add_argument(
        "--input-courses",
        default="nau_courses.csv",
        help="Path to the course CSV (default: nau_courses.csv).",
    )
    parser.add_argument(
        "--input-empty-prefixes",
        default="nau_empty_prefixes.csv",
        help="Path to empty prefixes CSV (default: nau_empty_prefixes.csv).",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory to write outputs (default: current directory).",
    )
    parser.add_argument(
        "--prefix-col",
        default="prefix",
        help="Column name for course prefix (default: prefix).",
    )
    parser.add_argument(
        "--number-col",
        default="number",
        help="Column name for course number (default: number).",
    )
    parser.add_argument(
        "--title-col",
        default="title",
        help="Column name for course title (default: title).",
    )
    parser.add_argument(
        "--description-col",
        default="description",
        help="Column name for course description (default: description).",
    )
    parser.add_argument(
        "--fuzzy-threshold",
        type=int,
        default=85,
        help="Fuzzy match threshold (default: 85).",
    )
    args = parser.parse_args()

    input_courses = Path(args.input_courses)
    if not input_courses.exists():
        print(f"Course CSV not found: {input_courses}", file=sys.stderr)
        raise SystemExit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_courses)
    required_cols = [
        args.prefix_col,
        args.number_col,
        args.title_col,
        args.description_col,
    ]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        print(f"Missing required columns: {missing}", file=sys.stderr)
        raise SystemExit(1)

    keyword_norms = [normalize_text(keyword) for keyword in KEYWORDS]
    text_series = (
        df[args.title_col].fillna("").astype(str)
        + " "
        + df[args.description_col].fillna("").astype(str)
    )
    text_norm_series = text_series.map(normalize_text)

    keyword_match = text_norm_series.map(
        lambda text: contains_keyword(text, keyword_norms)
    )
    fuzzy_scores = text_norm_series.map(
        lambda text: max_fuzzy_score(text, keyword_norms)
    )
    fuzzy_match = fuzzy_scores >= args.fuzzy_threshold

    df["is_ai_related"] = keyword_match | fuzzy_match

    unique_courses = df.drop_duplicates(subset=[args.prefix_col, args.number_col])
    total_counts = (
        unique_courses.groupby(args.prefix_col, dropna=False)
        .size()
        .rename("total_courses")
    )
    ai_counts = (
        unique_courses[unique_courses["is_ai_related"]]
        .groupby(args.prefix_col, dropna=False)
        .size()
        .rename("ai_related_courses")
    )
    summary = (
        pd.concat([total_counts, ai_counts], axis=1)
        .fillna(0)
        .astype({"ai_related_courses": int})
        .reset_index()
        .rename(columns={args.prefix_col: "prefix"})
        .sort_values("prefix")
    )

    ai_subset = (
        df[df["is_ai_related"]]
        .drop_duplicates(subset=[args.prefix_col, args.number_col])
        .sort_values([args.prefix_col, args.number_col])
    )

    full_output = output_dir / "nau_courses_with_ai_flag.csv"
    ai_output = output_dir / "nau_courses_ai_subset.csv"
    summary_output = output_dir / "nau_prefix_summary.csv"
    gap_output = output_dir / "nau_gap_report.csv"

    df.to_csv(full_output, index=False)
    ai_subset.to_csv(ai_output, index=False)
    summary.to_csv(summary_output, index=False)

    empty_prefixes = read_empty_prefixes(Path(args.input_empty_prefixes))
    with gap_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["prefix"])
        for prefix in empty_prefixes:
            writer.writerow([prefix])

    print("Analysis complete.")
    print(f"Full course list with AI flag: {full_output}")
    print(f"AI-only subset: {ai_output}")
    print(f"Prefix summary: {summary_output}")
    print(f"Gap report: {gap_output}")


if __name__ == "__main__":
    main()
