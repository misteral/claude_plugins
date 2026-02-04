#!/usr/bin/env python3
"""
Convert Markdown files to audiobooks using Gemini TTS via Vertex AI.
High-quality audiobook narration with professional voice prompts.
"""

import argparse
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

from google import genai
from google.genai import types
from tqdm import tqdm

# Vertex AI configuration
PROJECT_ID = "key-partition-407406"
LOCATION = "us-central1"

# Default settings
VOICE = "Despina"  # Warm, intimate narration style
DEFAULT_MODEL = "gemini-2.5-pro-tts"
DEFAULT_MAX_CHARS = 1500  # Smaller chunks for better quality

# Professional audiobook narrator prompt
AUDIOBOOK_PROMPT = """You are an audiobook narrator. Read the following text aloud.

## Voice Profile: "The Companion Voice"

### Environment
A warm, intimate space where stories come alive. The acoustic environment is natural and close—like someone reading from a comfortable armchair. The voice fills the room without overwhelming it, creating presence and connection.

### Approach
- Pacing: Steady, unhurried rhythm. Let sentences breathe. Pause naturally at paragraph breaks and scene transitions.
- Tone: Warm, conversational, and engaging—like a trusted friend telling a story they love.
- Breathing: Natural and relaxed. Breaths are gentle transitions, not dramatic punctuation.
- Consonants: Soft, clear articulation. Intelligible without being percussive or harsh.
- Dynamics: Subtle variations in energy to match the narrative mood, never jarring shifts.

### Reading Style
- Narration: Grounded, present, and flowing. Maintain consistent energy across long passages.
- Dialogue: Light characterization through tone and pace, not dramatic voice acting. Keep it natural.
- Emotional moments: Honor the emotion without overselling. Trust the words.
- Technical or dense passages: Slow slightly, maintain clarity, guide the listener through.

### Goal
The listener should forget they're hearing a voice and simply experience the story. Consistency is paramount—the voice should feel like the same person from chapter one to the final page.

---

Text to read:
"""


def split_text_smart(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> List[str]:
    """Split text into chunks on paragraph boundaries."""
    chunks = []
    paragraphs = re.split(r"\n\n+", text)
    current_chunk = ""
    current_chars = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_chars = len(para)

        if para_chars > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
                current_chars = 0

            sentences = re.split(r"([.!?]+\s+)", para)
            for i in range(0, len(sentences), 2):
                sentence = sentences[i]
                if i + 1 < len(sentences):
                    sentence += sentences[i + 1]

                sent_chars = len(sentence)
                if current_chars + sent_chars > max_chars:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence
                    current_chars = sent_chars
                else:
                    current_chunk += sentence
                    current_chars += sent_chars
        else:
            if current_chars + para_chars > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para
                current_chars = para_chars
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                    current_chars += 2 + para_chars
                else:
                    current_chunk = para
                    current_chars = para_chars

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def clean_text_for_tts(text: str) -> str:
    """Remove markdown formatting for cleaner TTS output."""
    # Remove code blocks
    text = re.sub(r"```[^`]*```", "", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]+`", "", text)
    # Remove links but keep text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove images
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", "", text)
    # Remove footnotes
    text = re.sub(r"\[\d+\]", "", text)
    # Remove markdown headers but keep text
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    # Remove bold/italic
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)
    text = re.sub(r"_{1,2}([^_]+)_{1,2}", r"\1", text)
    return text.strip()


def parse_audio_mime_type(mime_type: str) -> dict:
    """Parse bits per sample and rate from audio MIME type."""
    bits_per_sample = 16
    rate = 24000

    parts = mime_type.split(";")
    for param in parts:
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate = int(param.split("=", 1)[1])
            except (ValueError, IndexError):
                pass
        elif param.startswith("audio/L"):
            try:
                bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError):
                pass

    return {"bits_per_sample": bits_per_sample, "rate": rate}


def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Convert raw audio data to WAV format."""
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        chunk_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return header + audio_data


def text_to_audio_chunk(client: genai.Client, text: str, model: str) -> bytes:
    """Convert text chunk to audio using Gemini TTS with streaming."""
    clean_text = clean_text_for_tts(text)
    if not clean_text:
        return b""

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=f"{AUDIOBOOK_PROMPT}{clean_text}"),
            ],
        ),
    ]

    config = types.GenerateContentConfig(
        temperature=1,
        response_modalities=["audio"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE)
            )
        ),
    )

    audio_data = b""
    mime_type = None
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=config,
    ):
        if (
            chunk.candidates is None
            or chunk.candidates[0].content is None
            or chunk.candidates[0].content.parts is None
        ):
            continue

        part = chunk.candidates[0].content.parts[0]
        if part.inline_data and part.inline_data.data:
            audio_data += part.inline_data.data
            if mime_type is None:
                mime_type = part.inline_data.mime_type

    if audio_data:
        return convert_to_wav(audio_data, mime_type or "audio/L16;rate=24000")
    return b""


def merge_audio_ffmpeg(audio_files: List[Path], output_path: Path) -> None:
    """Merge multiple audio files using ffmpeg."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        filelist_path = f.name
        for audio_file in audio_files:
            f.write(f"file '{audio_file.absolute()}'\n")

    try:
        cmd = [
            "ffmpeg",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            filelist_path,
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            "-y",
            str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg failed: {e.stderr}") from e
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found. Install: brew install ffmpeg")
    finally:
        Path(filelist_path).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description="Convert Markdown to audiobook using Gemini TTS (Vertex AI).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s book.md
  %(prog)s book.md --model gemini-2.5-flash-preview-tts

Requirements:
  - Google Cloud authentication (gcloud auth application-default login)
  - ffmpeg for merging audio
        """,
    )

    parser.add_argument("input_file", help="Path to input Markdown file")
    parser.add_argument(
        "--model",
        "-m",
        default=DEFAULT_MODEL,
        help=f"Model name. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help=f"Max characters per chunk. Default: {DEFAULT_MAX_CHARS}",
    )
    parser.add_argument(
        "--output", "-o", help="Output file path. Default: <input>_audiobook.mp3"
    )

    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: File '{input_path}' not found.", file=sys.stderr)
        sys.exit(1)

    # Create Vertex AI client
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

    print(f"Reading file: {input_path}")
    text = input_path.read_text(encoding="utf-8")

    if not text.strip():
        print("Error: Input file is empty.", file=sys.stderr)
        sys.exit(1)

    print(f"Splitting text into chunks (max {args.max_chars} chars)...")
    chunks = split_text_smart(text, max_chars=args.max_chars)
    print(f"Created {len(chunks)} chunks")

    # Save chunks to tmp folder for debugging
    chunks_dir = input_path.parent / "tmp"
    chunks_dir.mkdir(exist_ok=True)
    for i, chunk in enumerate(chunks):
        chunk_file = chunks_dir / f"chunk_{i:04d}.txt"
        chunk_file.write_text(chunk, encoding="utf-8")
    print(f"Chunks saved to: {chunks_dir}")

    output_path = (
        Path(args.output)
        if args.output
        else input_path.parent / f"{input_path.stem}_audiobook.mp3"
    )

    temp_dir = tempfile.mkdtemp(prefix="gemini_audiobook_")
    temp_files = []

    try:
        print(f"\nGenerating audio (voice: {VOICE}, model: {args.model})...")

        for i, chunk in enumerate(tqdm(chunks, desc="Processing", unit="chunk")):
            temp_file = Path(temp_dir) / f"chunk_{i:04d}.wav"
            audio_bytes = text_to_audio_chunk(client, chunk, args.model)

            if audio_bytes:
                temp_file.write_bytes(audio_bytes)
                temp_files.append(temp_file)

        if not temp_files:
            print("Error: No audio generated.", file=sys.stderr)
            sys.exit(1)

        print(f"\nMerging {len(temp_files)} chunks...")
        merge_audio_ffmpeg(temp_files, output_path)

        print(f"\nDone! Saved to: {output_path}")
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"File size: {size_mb:.2f} MB")

    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        for temp_file in temp_files:
            temp_file.unlink(missing_ok=True)
        Path(temp_dir).rmdir()


if __name__ == "__main__":
    main()
