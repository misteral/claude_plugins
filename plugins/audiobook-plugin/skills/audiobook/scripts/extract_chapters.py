#!/usr/bin/env python3
"""
Extract specific chapters from a book text file.
Supports Russian (Глава) and English (Chapter) chapter markers.
"""
import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple, Optional


# Chapter patterns for different formats
CHAPTER_PATTERNS = [
    # Russian: Глава 1, ГЛАВА 1, Глава I
    r'(?:^|\n)\s*(Глава|ГЛАВА)\s+(\d+|[IVXLCDM]+)[\s\.\:\-]*',
    # English: Chapter 1, CHAPTER 1, Chapter I
    r'(?:^|\n)\s*(Chapter|CHAPTER)\s+(\d+|[IVXLCDM]+)[\s\.\:\-]*',
    # Markdown style: # Chapter 1, ## Глава 1
    r'(?:^|\n)\s*#{1,3}\s*(Глава|Chapter|ГЛАВА|CHAPTER)\s+(\d+|[IVXLCDM]+)',
    # Just numbers: 1., 2., etc. at line start
    r'(?:^|\n)\s*(\d+)\.\s+',
]


def roman_to_int(roman: str) -> int:
    """Convert Roman numeral to integer."""
    roman_values = {
        'I': 1, 'V': 5, 'X': 10, 'L': 50,
        'C': 100, 'D': 500, 'M': 1000
    }
    roman = roman.upper()
    total = 0
    prev = 0
    for char in reversed(roman):
        curr = roman_values.get(char, 0)
        if curr < prev:
            total -= curr
        else:
            total += curr
        prev = curr
    return total


def parse_chapter_number(s: str) -> int:
    """Parse chapter number from string (handles both Arabic and Roman numerals)."""
    s = s.strip()
    if s.isdigit():
        return int(s)
    # Try Roman numeral
    try:
        return roman_to_int(s)
    except:
        return 0


def find_chapters(text: str) -> List[Tuple[int, int, int]]:
    """
    Find all chapter positions in text.
    Returns list of (chapter_number, start_pos, end_pos).
    Filters out table of contents by checking if chapter has actual content.
    """
    chapters = []

    for pattern in CHAPTER_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            # Get chapter number from the match
            groups = match.groups()
            if len(groups) >= 2:
                chapter_num = parse_chapter_number(groups[1])
            else:
                chapter_num = parse_chapter_number(groups[0])

            if chapter_num > 0:
                chapters.append((chapter_num, match.start(), match.end()))

    # Sort by position
    chapters = sorted(chapters, key=lambda x: x[1])

    # Filter out TOC entries: keep only chapters that have substantial content
    # before the next chapter marker (or end of text)
    valid_chapters = []
    for i, (num, start, end) in enumerate(chapters):
        # Find next chapter position
        if i + 1 < len(chapters):
            next_start = chapters[i + 1][1]
        else:
            next_start = len(text)

        # Calculate content length between this chapter and next
        content = text[end:next_start].strip()

        # If content is substantial (>200 chars), this is a real chapter, not TOC
        if len(content) > 200:
            valid_chapters.append((num, start, end))

    # Remove duplicates - keep only the LAST occurrence of each chapter number
    # (first is usually TOC, last is the actual chapter)
    seen = {}
    for ch in valid_chapters:
        seen[ch[0]] = ch  # Later occurrence overwrites earlier

    return sorted(seen.values(), key=lambda x: x[1])


def extract_chapters(text: str, chapter_nums: List[int]) -> str:
    """Extract specified chapters from text."""
    chapters = find_chapters(text)

    if not chapters:
        print("Warning: No chapter markers found. Returning full text.", file=sys.stderr)
        return text

    # Build chapter boundaries
    chapter_bounds = {}
    for i, (num, start, _) in enumerate(chapters):
        # End is start of next chapter or end of text
        if i + 1 < len(chapters):
            end = chapters[i + 1][1]
        else:
            end = len(text)
        chapter_bounds[num] = (start, end)

    # Extract requested chapters
    extracted = []
    for num in sorted(chapter_nums):
        if num in chapter_bounds:
            start, end = chapter_bounds[num]
            extracted.append(text[start:end].strip())
        else:
            print(f"Warning: Chapter {num} not found. Available: {sorted(chapter_bounds.keys())}", file=sys.stderr)

    return '\n\n'.join(extracted)


def parse_chapter_arg(arg: str) -> List[int]:
    """
    Parse chapter argument into list of chapter numbers.
    Supports: "7", "7,8", "7-10", "7,8,10-12"
    """
    chapters = []
    parts = re.split(r'[,\s]+', arg)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Range: 7-10
        if '-' in part:
            try:
                start, end = part.split('-', 1)
                start, end = int(start), int(end)
                chapters.extend(range(start, end + 1))
            except ValueError:
                print(f"Warning: Invalid range '{part}'", file=sys.stderr)
        else:
            # Single number
            try:
                chapters.append(int(part))
            except ValueError:
                print(f"Warning: Invalid chapter number '{part}'", file=sys.stderr)

    return sorted(set(chapters))


def main():
    parser = argparse.ArgumentParser(
        description="Extract specific chapters from a book text file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s book.txt --chapters 7,8 --output chapters.md
  %(prog)s book.txt --chapters 1-5 --output first_five.md
  %(prog)s book.txt --chapters 7,8,10-12 --output selected.md
  %(prog)s book.txt --list  # List all found chapters
        """
    )

    parser.add_argument("input_file", help="Path to input text file")
    parser.add_argument("--chapters", "-c", help="Chapters to extract (e.g., '7,8' or '1-5')")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument("--list", "-l", action="store_true", help="List all chapters found in the book")

    args = parser.parse_args()

    # Read input file
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: File '{input_path}' not found.", file=sys.stderr)
        sys.exit(1)

    text = input_path.read_text(encoding='utf-8')

    # List chapters mode
    if args.list:
        chapters = find_chapters(text)
        if not chapters:
            print("No chapters found in the file.")
        else:
            print(f"Found {len(chapters)} chapters:")
            for num, start, _ in chapters:
                # Get preview of chapter start
                preview = text[start:start+100].replace('\n', ' ').strip()
                print(f"  Chapter {num}: {preview[:60]}...")
        sys.exit(0)

    # Extract mode
    if not args.chapters:
        print("Error: --chapters or --list required", file=sys.stderr)
        sys.exit(1)

    chapter_nums = parse_chapter_arg(args.chapters)
    if not chapter_nums:
        print("Error: No valid chapter numbers specified", file=sys.stderr)
        sys.exit(1)

    print(f"Extracting chapters: {chapter_nums}", file=sys.stderr)

    extracted = extract_chapters(text, chapter_nums)

    if not extracted:
        print("Error: No content extracted", file=sys.stderr)
        sys.exit(1)

    # Output
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(extracted, encoding='utf-8')
        print(f"Saved {len(extracted)} characters to {output_path}", file=sys.stderr)
    else:
        print(extracted)


if __name__ == "__main__":
    main()
