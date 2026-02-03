#!/usr/bin/env python3
"""
Convert Markdown files to audiobooks using Google Gemini TTS API.
Splits large texts into chunks, processes them, and merges into a single MP3.
"""
import os
import sys
import argparse
import tempfile
import subprocess
import wave
import struct
from pathlib import Path
from typing import List
import re

from google import genai
from google.genai import types
from tqdm import tqdm


# Available Gemini TTS voices
VOICES = [
    'Puck',      # Upbeat
    'Charon',    # Informative
    'Kore',      # Firm
    'Fenrir',    # Excitable
    'Aoede',     # Breezy
    'Leda',      # Youthful
    'Orus',      # Firm
    'Zephyr',    # Bright
]

# Default settings
DEFAULT_VOICE = 'Kore'
DEFAULT_MODEL = 'gemini-2.5-flash-preview-tts'
# Gemini disconnects on large requests, need smaller chunks with retries
# Each chunk produces ~1-2 min of audio at normal speech rate
DEFAULT_MAX_CHARS = 5000  # ~1-2 min of audio per chunk
MAX_RETRIES = 3
SAMPLE_RATE = 24000


def split_text_smart(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> List[str]:
    """
    Split text into chunks that don't exceed max_chars characters.
    Tries to split on paragraph boundaries.
    """
    chunks = []
    paragraphs = re.split(r'\n\n+', text)
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(para) > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            # Split by sentences
            sentences = re.split(r'([.!?]+\s+)', para)
            for i in range(0, len(sentences), 2):
                sentence = sentences[i]
                if i + 1 < len(sentences):
                    sentence += sentences[i + 1]

                if len(current_chunk) + len(sentence) > max_chars:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence
                else:
                    current_chunk += sentence
        else:
            if len(current_chunk) + len(para) + 2 > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def clean_text_for_tts(text: str) -> str:
    """Clean text for TTS processing."""
    # Remove markdown headers but keep text
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    # Remove bold/italic
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
    text = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', text)
    # Remove links
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove code blocks
    text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
    text = re.sub(r'`[^`]+`', '', text)
    # Remove footnotes
    text = re.sub(r'\[\d+\]', '', text)
    return text.strip()


def text_to_audio_chunk(
    client: genai.Client,
    text: str,
    voice: str,
    model: str,
    retries: int = MAX_RETRIES
) -> bytes:
    """
    Convert text chunk to audio using Gemini TTS.
    Returns PCM audio bytes. Includes retry logic for disconnections.
    """
    import time

    clean_text = clean_text_for_tts(text)
    if not clean_text:
        # Return 0.5 second of silence
        return b'\x00\x00' * (SAMPLE_RATE // 2)

    last_error = None
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=clean_text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice,
                            )
                        )
                    ),
                )
            )
            # Extract audio data from response
            audio_data = response.candidates[0].content.parts[0].inline_data.data
            return audio_data
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                wait_time = (attempt + 1) * 5  # 5, 10, 15 seconds
                print(f"\n  Retry {attempt + 1}/{retries} after {wait_time}s: {e}")
                time.sleep(wait_time)

    raise last_error


def save_pcm_to_wav(pcm_data: bytes, wav_path: Path, sample_rate: int = SAMPLE_RATE):
    """Save raw PCM data to WAV file."""
    with wave.open(str(wav_path), 'wb') as wav_file:
        wav_file.setnchannels(1)  # mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)


def merge_audio_files(audio_files: List[Path], output_path: Path) -> None:
    """Merge multiple WAV files into one MP3 using ffmpeg."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        filelist_path = f.name
        for audio_file in audio_files:
            f.write(f"file '{audio_file.absolute()}'\n")

    try:
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', filelist_path,
            '-c:a', 'libmp3lame',
            '-q:a', '2',
            '-y',
            str(output_path)
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
        description="Convert Markdown to audiobook using Google Gemini TTS.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  %(prog)s book.md
  %(prog)s book.md --voice Puck
  %(prog)s book.md --model gemini-2.5-pro-preview-tts

Available voices: {', '.join(VOICES)}

Requirements:
  - GOOGLE_API_KEY environment variable
  - ffmpeg for merging audio
        """
    )

    parser.add_argument("input_file", help="Path to input Markdown file")
    parser.add_argument(
        "--voice", "-v",
        default=DEFAULT_VOICE,
        help=f"Voice name. Default: {DEFAULT_VOICE}"
    )
    parser.add_argument(
        "--model", "-m",
        default=DEFAULT_MODEL,
        help=f"Model name. Default: {DEFAULT_MODEL}"
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help=f"Max characters per chunk. Default: {DEFAULT_MAX_CHARS}"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path. Default: <input>_audiobook.mp3"
    )

    args = parser.parse_args()

    # Check API key (try multiple env var names)
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_GEMINI_API")
    if not api_key:
        print("Error: GOOGLE_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    # Validate input
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: File '{input_path}' not found.", file=sys.stderr)
        sys.exit(1)

    # Create client
    client = genai.Client(api_key=api_key)

    # Read and split text
    print(f"Reading: {input_path}")
    text = input_path.read_text(encoding="utf-8")

    if not text.strip():
        print("Error: Input file is empty.", file=sys.stderr)
        sys.exit(1)

    print(f"Splitting into chunks (max {args.max_chars} chars)...")
    chunks = split_text_smart(text, max_chars=args.max_chars)
    print(f"Created {len(chunks)} chunks")

    # Output path
    output_path = Path(args.output) if args.output else input_path.parent / f"{input_path.stem}_audiobook.mp3"

    # Process chunks
    temp_dir = tempfile.mkdtemp(prefix="gemini_tts_")
    temp_files = []

    try:
        print(f"\nGenerating audio (voice: {args.voice}, model: {args.model})...")

        for i, chunk in enumerate(tqdm(chunks, desc="Processing", unit="chunk")):
            temp_file = Path(temp_dir) / f"chunk_{i:04d}.wav"

            # Generate audio
            pcm_data = text_to_audio_chunk(
                client=client,
                text=chunk,
                voice=args.voice,
                model=args.model
            )

            # Save as WAV
            save_pcm_to_wav(pcm_data, temp_file)
            temp_files.append(temp_file)

        # Merge
        print(f"\nMerging {len(temp_files)} chunks...")
        merge_audio_files(temp_files, output_path)

        print(f"\nSuccess! Saved to: {output_path}")
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"File size: {size_mb:.2f} MB")

    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        for f in temp_files:
            f.unlink(missing_ok=True)
        Path(temp_dir).rmdir()


if __name__ == "__main__":
    main()
