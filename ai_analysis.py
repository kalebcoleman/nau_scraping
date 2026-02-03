#!/usr/bin/env python3
"""
Analyze NAU course data to identify AI-related curriculum and summarize results.

Inputs:
  - Course CSV with columns: prefix, number, title, description (plus any others)

Outputs:
  - Full course list with is_ai_related and is_ethics_related boolean
  - AI-only subset CSV (deduped by prefix + number)
  - Prefix totals CSV (unique courses per prefix)
  - Summary CSV (total unique courses)

Matching logic (high-level):
  1) Primary patterns: explicit AI terms (high precision).
  2) Secondary patterns: ambiguous terms that only count if an AI context term is present.
  3) Fuzzy matching: catches small variations/typos in explicit AI phrases.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from ethics_analysis import EthicsMatcher

try:
    import pandas as pd
except ImportError:  # pragma: no cover - runtime dependency check
    print(
        "Missing dependency: pandas. Install with: pip install pandas", file=sys.stderr
    )
    raise SystemExit(1)

try:
    from thefuzz import fuzz
except ImportError:  # pragma: no cover - runtime dependency check
    print(
        "Missing dependency: thefuzz. Install with: pip install thefuzz[speedup]",
        file=sys.stderr,
    )
    raise SystemExit(1)

# Primary patterns: explicit AI terms (high precision).
PRIMARY_PATTERNS = [
    r"\bartificial intelligence\b",
    r"\bmachine learning\b",
    r"\bdeep learning\b",
    r"\bgenerative ai\b",
    r"\blarge language model(s)?\b",
    r"\bllm\b",
    r"\bgpt\b",
    r"\bchatgpt\b",
    r"\bneural network(s)?\b",
    r"\breinforcement learning\b",
    r"\bnatural language processing\b",
    r"\bnlp\b",
    r"\bcomputer vision\b",
    r"\bintelligent systems?\b",
    r"\bai\b",
    r"\bagentic\b",
    r"\bmulti[- ]agent(s)?\b",
    r"\bintelligent agents?\b",
]

# Secondary patterns: ambiguous terms that require AI context to count.
SECONDARY_PATTERNS = [
    r"\bethic(s|al)?\b",
    r"\bagent(s)?\b",
    r"\bautonomous systems?\b",
]

# Context patterns: AI terms that "unlock" secondary matches.
CONTEXT_PATTERNS = [
    r"\bai\b",
    r"\bartificial intelligence\b",
    r"\bmachine learning\b",
    r"\bdeep learning\b",
    r"\bgenerative ai\b",
    r"\blarge language model(s)?\b",
    r"\bllm\b",
    r"\bgpt\b",
    r"\bchatgpt\b",
    r"\bneural network(s)?\b",
    r"\bnatural language processing\b",
    r"\bnlp\b",
    r"\bcomputer vision\b",
    r"\bintelligent systems?\b",
]

# Fuzzy phrases: explicit AI phrases for typo/variation tolerance.
FUZZY_PHRASES = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "generative ai",
    "large language model",
    "neural network",
    "reinforcement learning",
    "natural language processing",
    "computer vision",
    "intelligent systems",
    "intelligent agent",
    "multi agent",
    "agentic",
]

NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_text(text: str) -> str:
    """Lowercase and normalize whitespace/punctuation for reliable matching."""
    lowered = text.lower()
    cleaned = NON_ALNUM_RE.sub(" ", lowered)
    return " ".join(cleaned.split())


def compile_patterns(patterns: list[str]) -> list[re.Pattern[str]]:
    """Compile regex patterns once for efficient reuse."""
    return [re.compile(pattern) for pattern in patterns]


def matches_any(text_norm: str, patterns: list[re.Pattern[str]]) -> bool:
    """Return True if any compiled pattern matches the normalized text."""
    if not text_norm:
        return False
    return any(pattern.search(text_norm) for pattern in patterns)


def max_fuzzy_score(text_norm: str, keyword_norms: list[str]) -> int:
    """Return the max fuzzy match score against a list of normalized phrases."""
    if not text_norm:
        return 0
    return max(fuzz.partial_ratio(text_norm, keyword) for keyword in keyword_norms)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Identify AI-related courses and summarize results."
    )
    parser.add_argument(
        "--input-courses",
        default="outputs/nau_courses.csv",
        help="Path to the course CSV (default: outputs/nau_courses.csv).",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directory to write outputs (default: outputs).",
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
        default=95,
        help="Fuzzy match threshold (default: 92).",
    )
    parser.add_argument(
        "--disable-fuzzy",
        action="store_true",
        help="Disable fuzzy matching (default: enabled).",
    )
    args = parser.parse_args()

    input_courses = Path(args.input_courses)
    if not input_courses.exists():
        print(f"Course CSV not found: {input_courses}", file=sys.stderr)
        raise SystemExit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load and validate course data.
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

    # Build normalized text for consistent matching across title/description.
    primary_patterns = compile_patterns(PRIMARY_PATTERNS)
    secondary_patterns = compile_patterns(SECONDARY_PATTERNS)
    context_patterns = compile_patterns(CONTEXT_PATTERNS)
    ethics_matcher = EthicsMatcher.build()
    fuzzy_phrases = [normalize_text(keyword) for keyword in FUZZY_PHRASES]
    title_series = df[args.title_col].fillna("").astype(str)
    description_series = df[args.description_col].fillna("").astype(str)
    text_series = title_series + " " + description_series
    text_norm_series = text_series.map(normalize_text)

    # Primary match: explicit AI terms.
    primary_match = text_norm_series.map(
        lambda text: matches_any(text, primary_patterns)
    )
    # Secondary match: ambiguous terms, only counted with AI context.
    secondary_match = text_norm_series.map(
        lambda text: matches_any(text, secondary_patterns)
    )
    context_match = text_norm_series.map(
        lambda text: matches_any(text, context_patterns)
    )
    keyword_match = primary_match | (secondary_match & context_match)

    # Optional fuzzy match for minor typos or small variations.
    if args.disable_fuzzy:
        fuzzy_match = False
    else:
        fuzzy_scores = text_norm_series.map(
            lambda text: max_fuzzy_score(text, fuzzy_phrases)
        )
        fuzzy_match = fuzzy_scores >= args.fuzzy_threshold

    ethics_match = [
        ethics_matcher.is_match(title, description)
        for title, description in zip(title_series, description_series)
    ]

    df["is_ai_related"] = keyword_match | fuzzy_match
    df["is_ethics_related"] = ethics_match

    # Deduplicate by prefix + number and preserve a single AI flag per course.
    ai_flags = (
        df.groupby([args.prefix_col, args.number_col], dropna=False)["is_ai_related"]
        .any()
        .reset_index()
    )
    unique_courses = (
        df.sort_values([args.prefix_col, args.number_col])
        .drop_duplicates(subset=[args.prefix_col, args.number_col])
        .drop(columns=["is_ai_related", "is_ethics_related"])
        .merge(ai_flags, on=[args.prefix_col, args.number_col], how="left")
    )
    unique_courses["is_ai_related"] = unique_courses["is_ai_related"].fillna(False)

    # Total unique courses per prefix.
    prefix_totals = (
        unique_courses.groupby(args.prefix_col, dropna=False)
        .size()
        .rename("total_courses")
        .reset_index()
        .rename(columns={args.prefix_col: "prefix"})
        .sort_values("prefix")
    )

    # AI subset output.
    ai_subset = unique_courses[unique_courses["is_ai_related"]].sort_values(
        [args.prefix_col, args.number_col]
    )
    full_output = output_dir / "nau_courses_with_flag.csv"
    ai_output = output_dir / "nau_courses_ai_subset.csv"
    prefix_totals_output = output_dir / "nau_prefix_totals.csv"
    summary_output = output_dir / "nau_summary.csv"

    df.to_csv(full_output, index=False)
    ai_subset.to_csv(ai_output, index=False)
    prefix_totals.to_csv(prefix_totals_output, index=False)
    pd.DataFrame(
        [{"metric": "total_unique_courses", "value": int(len(unique_courses))}]
    ).to_csv(summary_output, index=False)

    print("Analysis complete.")
    print(f"Full course list with AI flag: {full_output}")
    print(f"AI-only subset: {ai_output}")
    print(f"Prefix totals: {prefix_totals_output}")
    print(f"Summary: {summary_output}")


if __name__ == "__main__":
    main()
