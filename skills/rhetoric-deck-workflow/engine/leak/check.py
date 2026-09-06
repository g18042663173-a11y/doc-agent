from __future__ import annotations

import hashlib
from decimal import Decimal
import re
from typing import Iterable


CJK_RE = re.compile(r"[\u3400-\u9fff]")
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?%?(?![A-Za-z0-9])")
TERM_RE = re.compile(r"\b(?:[A-Z]{2,}[A-Z0-9-]*|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")


def build_source_fingerprints(fragments: Iterable[str]) -> dict:
    ngrams: set[str] = set()
    numbers: set[str] = set()
    terms: set[str] = set()
    for fragment in fragments:
        cjk = "".join(CJK_RE.findall(fragment))
        ngrams.update(_hash(cjk[index:index + 8]) for index in range(max(0, len(cjk) - 7)))
        numbers.update(_number_hash(value) for value in NUMBER_RE.findall(fragment) if len(value.rstrip("%")) >= 2)
        terms.update(_hash(value.casefold()) for value in TERM_RE.findall(fragment))
    return {
        "format": "rdw_source_fingerprints", "version": "2.0",
        "algorithm": "sha256", "cjk_ngram_size": 8,
        "cjk_ngrams": sorted(ngrams), "numbers": sorted(numbers), "terms": sorted(terms),
    }


def check_output(texts: Iterable, material_text: str, fingerprints: dict, allowed_labels: set[str]) -> dict:
    located: list[tuple[str, str]] = []
    for item in texts:
        if isinstance(item, tuple) and len(item) == 2:
            located.append((str(item[0]), str(item[1])))
        else:
            located.append(("content", str(item)))
    source_ngrams = set(fingerprints.get("cjk_ngrams", []))
    source_numbers = set(fingerprints.get("numbers", []))
    source_terms = set(fingerprints.get("terms", []))
    material_cjk_hashes = _cjk_hashes(material_text)
    number_hash = _number_hash if fingerprints.get("version") == "2.0" else _hash
    material_number_hashes = {number_hash(value) for value in NUMBER_RE.findall(material_text)}
    material_term_hashes = {_hash(value.casefold()) for value in TERM_RE.findall(material_text)}
    blocked_ngrams: set[str] = set()
    blocked_numbers: set[str] = set()
    warned_terms: set[str] = set()
    hits: list[dict[str, str]] = []
    for loc, text in located:
        reduced = text
        for label in allowed_labels:
            reduced = reduced.replace(label, "")
        cjk = "".join(CJK_RE.findall(reduced))
        for index in range(max(0, len(cjk) - 7)):
            value = cjk[index:index + 8]
            digest = _hash(value)
            if digest in source_ngrams and digest not in material_cjk_hashes:
                blocked_ngrams.add(value)
                hits.append({"loc": loc, "kind": "cjk_ngram", "sample": value})
        for value in NUMBER_RE.findall(reduced):
            digest = number_hash(value)
            if digest in source_numbers and digest not in material_number_hashes:
                blocked_numbers.add(value)
                hits.append({"loc": loc, "kind": "number", "sample": value})
        for value in TERM_RE.findall(reduced):
            digest = _hash(value.casefold())
            if digest in source_terms and digest not in material_term_hashes:
                warned_terms.add(value)
    unique_hits: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for hit in hits:
        key = (hit["loc"], hit["kind"], hit["sample"])
        if key in seen:
            continue
        seen.add(key)
        unique_hits.append(hit)
        if len(unique_hits) >= 20:
            break
    return {
        "format": "rdw_leak_report", "version": "1.0",
        "pass": not blocked_ngrams and not blocked_numbers,
        "blocked": {"cjk_ngrams": sorted(blocked_ngrams), "numbers": sorted(blocked_numbers)},
        "warnings": {"terms": sorted(warned_terms)},
        "hits": unique_hits,
    }


def _cjk_hashes(text: str) -> set[str]:
    cjk = "".join(CJK_RE.findall(text))
    return {_hash(cjk[index:index + 8]) for index in range(max(0, len(cjk) - 7))}


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _number_hash(value: str) -> str:
    # Display padding is not a different fact: 01 and 1, 0.50 and .500.
    suffix = "%" if value.endswith("%") else ""
    return _hash(format(Decimal(value.rstrip("%")).normalize(), "f") + suffix)
