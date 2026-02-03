#!/usr/bin/env python3
"""
Broad AI recall search to catch anything potentially AI-related.

This script is intentionally permissive and may include false positives.
Use it as a candidate list to review and clean manually.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

# Broad patterns are grouped by label so the output can explain *why* a course matched.
BROAD_PATTERNS: list[tuple[str, str]] = [
    ("artificial_intelligence", r"\bartificial intelligence\b"),
    ("ai", r"\bai\b"),
    ("machine_learning", r"\bmachine learning\b"),
    ("deep_learning", r"\bdeep learning\b"),
    ("generative_ai", r"\bgenerative ai\b"),
    ("llm", r"\blarge language model(s)?\b"),
    ("llm", r"\bllm\b"),
    ("gpt", r"\bgpt\b"),
    ("chatgpt", r"\bchatgpt\b"),
    ("neural_network", r"\bneural network(s)?\b"),
    ("reinforcement_learning", r"\breinforcement learning\b"),
    ("nlp", r"\bnatural language processing\b"),
    ("nlp", r"\bnlp\b"),
    ("computer_vision", r"\bcomputer vision\b"),
    ("machine_vision", r"\bmachine vision\b"),
    ("image_processing", r"\bimage processing\b"),
    ("pattern_recognition", r"\bpattern recognition\b"),
    ("data_mining", r"\bdata mining\b"),
    ("information_retrieval", r"\binformation retrieval\b"),
    ("expert_systems", r"\bexpert systems?\b"),
    ("knowledge_representation", r"\bknowledge representation\b"),
    ("intelligent_systems", r"\bintelligent systems?\b"),
    ("intelligent_agents", r"\bintelligent agents?\b"),
    ("autonomous_systems", r"\bautonomous systems?\b"),
    ("autonomous", r"\bautonomous\b"),
    ("robotics", r"\brobotics?\b"),
    ("computational_intelligence", r"\bcomputational intelligence\b"),
    ("speech_recognition", r"\bspeech recognition\b"),
    ("recommendation_systems", r"\brecommendation systems?\b"),
    ("recommender_systems", r"\brecommender systems?\b"),
    ("decision_support", r"\bdecision support\b"),
    ("intelligent_control", r"\bintelligent control\b"),
    ("data_science", r"\bdata science\b"),
]

BROAD_FUZZY_PHRASES = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "generative ai",
    "large language model",
    "neural network",
    "reinforcement learning",
    "natural language processing",
    "computer vision",
    "pattern recognition",
    "data mining",
    "information retrieval",
    "expert systems",
    "knowledge representation",
    "intelligent systems",
    "intelligent agent",
    "autonomous systems",
    "computational intelligence",
    "speech recognition",
    "recommendation systems",
    "recommender systems",
    "decision support",
    "intelligent control",
    "data science",
]

NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_text(text: str) -> str:
    lowered = text.lower()
    cleaned = NON_ALNUM_RE.sub(" ", lowered)
    return " ".join(cleaned.split())


def max_fuzzy_score(text_norm: str, phrases: list[str]) -> int:
    if not text_norm:
        return 0
    return max(fuzz.partial_ratio(text_norm, phrase) for phrase in phrases)


def best_fuzzy_match(text_norm: str, phrases: list[str]) -> tuple[int, str]:
    if not text_norm:
        return 0, ""
    try:
        from thefuzz import fuzz  # type: ignore
    except ImportError:  # pragma: no cover - runtime dependency check
        print(
            "Missing dependency: thefuzz. Install with: pip install thefuzz[speedup]",
            file=sys.stderr,
        )
        raise SystemExit(1)
    best_score = -1
    best_phrase = ""
    for phrase in phrases:
        score = fuzz.partial_ratio(text_norm, phrase)
        if score > best_score:
            best_score = score
            best_phrase = phrase
    return best_score, best_phrase


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Broad AI recall search (intentionally permissive)."
    )
    parser.add_argument(
        "--input-courses",
        default="outputs/nau_courses.csv",
        help="Path to the course CSV (default: outputs/nau_courses.csv).",
    )
    parser.add_argument(
        "--output",
        default="outputs/nau_courses_ai_candidates.csv",
        help="Output path for the AI candidate list (default: outputs/nau_courses_ai_candidates.csv).",
    )
    parser.add_argument(
        "--fuzzy-threshold",
        type=int,
        default=85,
        help="Fuzzy match threshold (default: 85).",
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

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_courses)
    required_cols = ["prefix", "number", "title", "description"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        print(f"Missing required columns: {missing}", file=sys.stderr)
        raise SystemExit(1)

    compiled = [(label, re.compile(pattern)) for label, pattern in BROAD_PATTERNS]
    fuzzy_phrases = [normalize_text(term) for term in BROAD_FUZZY_PHRASES]

    titles = df["title"].fillna("").astype(str)
    descriptions = df["description"].fillna("").astype(str)
    text_series = titles + " " + descriptions
    text_norm_series = text_series.map(normalize_text)

    reasons: list[str] = []
    matched: list[bool] = []
    fuzzy_scores: list[int] = []
    fuzzy_phrases_matched: list[str] = []

    for text_norm in text_norm_series:
        hits = [label for label, rx in compiled if rx.search(text_norm)]
        reason = ",".join(sorted(set(hits))) if hits else ""
        reasons.append(reason)
        matched.append(bool(hits))

    if args.disable_fuzzy:
        fuzzy_match = [False] * len(df)
        fuzzy_scores = [0] * len(df)
        fuzzy_phrases_matched = [""] * len(df)
    else:
        try:
            from thefuzz import fuzz  # type: ignore
        except ImportError:  # pragma: no cover - runtime dependency check
            print(
                "Missing dependency: thefuzz. Install with: pip install thefuzz[speedup]",
                file=sys.stderr,
            )
            raise SystemExit(1)
        for text in text_norm_series:
            score, phrase = best_fuzzy_match(text, fuzzy_phrases)
            fuzzy_scores.append(score)
            fuzzy_phrases_matched.append(phrase if score >= args.fuzzy_threshold else "")
        fuzzy_match = [score >= args.fuzzy_threshold for score in fuzzy_scores]

    df["is_ai_candidate"] = [m or f for m, f in zip(matched, fuzzy_match)]

    final_reasons: list[str] = []
    for reason, is_fuzzy, phrase in zip(reasons, fuzzy_match, fuzzy_phrases_matched):
        if reason:
            final_reasons.append(reason)
        elif is_fuzzy and phrase:
            final_reasons.append(f"fuzzy:{phrase}")
        else:
            final_reasons.append("")

    df["ai_candidate_reason"] = final_reasons
    df["ai_candidate_fuzzy_phrase"] = fuzzy_phrases_matched
    df["ai_candidate_fuzzy_score"] = fuzzy_scores

    subset = (
        df[df["is_ai_candidate"]]
        .drop_duplicates(subset=["prefix", "number"])
        .sort_values(["prefix", "number"])
    )

    subset.to_csv(output_path, index=False)

    print(f"Wrote {len(subset)} AI candidates to {output_path}")


if __name__ == "__main__":
    main()
