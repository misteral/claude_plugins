#!/usr/bin/env python3
"""
Convert Markdown files to audiobooks using Qwen3-TTS (local, MLX optimized for Apple Silicon).
"""
import os
import sys
import argparse
import tempfile
import subprocess
import shutil
from pathlib import Path
from typing import List
import re

from tqdm import tqdm


# Available Qwen3-TTS models on HuggingFace (MLX format)
# CustomVoice models have preset voices; VoiceDesign allows text description of voice
MODELS = {
    # Lite models (0.6B) - faster, less RAM
    'lite': 'mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit',     # ~1GB RAM, good quality
    'lite-fast': 'mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-4bit', # ~0.5GB RAM, faster

    # Pro models (1.7B) - better quality
    'pro': 'mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit',      # ~2GB RAM, great quality
    'pro-hq': 'mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-bf16',   # ~4GB RAM, best quality

    # VoiceDesign - describe voice with text
    'design': 'mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit',   # ~2GB RAM
}

DEFAULT_MODEL = 'lite'
DEFAULT_MAX_CHARS = 500  # Qwen works better with shorter chunks
SAMPLE_RATE = 24000

# Available voices for CustomVoice models
VOICES = {
    # English speakers (best for Russian/European languages)
    'Ryan': 'Dynamic male voice with strong rhythmic drive (English)',
    'Aiden': 'Sunny American male voice with clear midrange (English)',
    # Chinese speakers
    'Vivian': 'Bright, slightly edgy young female voice (Chinese)',
    'Serena': 'Warm, gentle young female voice (Chinese)',
    'Uncle_Fu': 'Seasoned male voice with low, mellow timbre (Chinese)',
    'Dylan': 'Youthful Beijing male voice (Chinese)',
    'Eric': 'Lively Chengdu male voice (Chinese/Sichuan)',
    # Asian speakers
    'Ono_Anna': 'Playful Japanese female voice (Japanese)',
    'Sohee': 'Warm Korean female voice (Korean)',
}
DEFAULT_VOICE = 'Aiden'

# Preset voice descriptions for VoiceDesign model (Russian audiobooks)
VOICE_PRESETS = {
    'ru-male': 'Мужской голос средних лет, глубокий баритон, спокойный и профессиональный, как диктор аудиокниг. Четкая дикция, размеренный темп.',
    'ru-female': 'Женский голос, мягкий и теплый, приятный тембр. Читает спокойно и выразительно, как профессиональный диктор аудиокниг.',
    'ru-young-male': 'Молодой мужской голос, энергичный но не торопливый, четкая дикция, подходит для современной литературы.',
    'ru-narrator': 'Глубокий мужской голос рассказчика, с легкой хрипотцой, задумчивый тон, идеален для художественной литературы.',
    'en-narrator': 'Deep male narrator voice, calm and professional, perfect for audiobooks. Clear pronunciation, measured pace.',
    'en-female': 'Warm female voice, gentle and soothing, like a bedtime storyteller. Clear and expressive.',
}


def split_text_smart(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> List[str]:
    """Split text into chunks on sentence boundaries."""
    chunks = []

    # Split by sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    current_chunk = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(current_chunk) + len(sentence) + 1 > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def clean_text_for_tts(text: str) -> str:
    """Clean text for TTS processing."""
    # Remove markdown headers
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
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


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
    finally:
        Path(filelist_path).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description="Convert Markdown to audiobook using Qwen3-TTS (local, MLX).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  %(prog)s book.md
  %(prog)s book.md --model pro --voice Ryan
  %(prog)s book.md --model design --voice-preset ru-male
  %(prog)s book.md --model design -i "Глубокий мужской голос, спокойный диктор"
  %(prog)s book.md --ref-audio my_voice.wav

Models:
  lite:      0.6B 8bit, ~1GB RAM (default, CustomVoice)
  lite-fast: 0.6B 4bit, ~0.5GB RAM (CustomVoice)
  pro:       1.7B 8bit, ~2GB RAM (CustomVoice, better quality)
  pro-hq:    1.7B bf16, ~4GB RAM (CustomVoice, best quality)
  design:    1.7B VoiceDesign (describe voice with text, best for Russian)

Voices (for CustomVoice models: lite, pro):
  English: Ryan, Aiden
  Chinese: Vivian, Serena, Uncle_Fu, Dylan, Eric
  Asian: Ono_Anna (Japanese), Sohee (Korean)

Voice Presets (for VoiceDesign model: design):
  ru-male:       Мужской голос, глубокий баритон, диктор аудиокниг
  ru-female:     Женский голос, мягкий и теплый
  ru-young-male: Молодой мужской голос, энергичный
  ru-narrator:   Глубокий голос рассказчика с хрипотцой
  en-narrator:   Deep male narrator, calm and professional
  en-female:     Warm female storyteller voice

Requirements:
  - Apple Silicon Mac (M1/M2/M3/M4)
  - ffmpeg for merging audio
        """
    )

    parser.add_argument("input_file", help="Path to input Markdown file")
    parser.add_argument(
        "--model", "-m",
        default=DEFAULT_MODEL,
        choices=list(MODELS.keys()),
        help=f"Model size. Default: {DEFAULT_MODEL}"
    )
    parser.add_argument(
        "--voice", "-v",
        default=DEFAULT_VOICE,
        choices=list(VOICES.keys()),
        help=f"Voice/speaker name. Default: {DEFAULT_VOICE}"
    )
    parser.add_argument(
        "--instruct", "-i",
        default="",
        help="Emotion/style instruction or voice description for 'design' model"
    )
    parser.add_argument(
        "--voice-preset", "-p",
        choices=list(VOICE_PRESETS.keys()),
        help="Preset voice description for 'design' model (ru-male, ru-female, etc.)"
    )
    parser.add_argument(
        "--ref-audio",
        help="Reference audio for voice cloning (5-10 sec WAV)"
    )
    parser.add_argument(
        "--ref-text",
        help="Transcript of reference audio (optional, auto-transcribed if not provided)"
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Speech speed (0.5-2.0). Default: 1.0"
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

    # Validate input
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: File '{input_path}' not found.", file=sys.stderr)
        sys.exit(1)

    # Import mlx_audio here to show helpful error if not installed
    try:
        from mlx_audio.tts.utils import load_model
        from mlx_audio.tts.generate import generate_audio
    except ImportError:
        print("Error: mlx-audio not installed. Run: uv add mlx-audio", file=sys.stderr)
        sys.exit(1)

    # Determine voice/instruct settings
    is_design_model = args.model == 'design'

    if is_design_model:
        # VoiceDesign model uses instruct for voice description
        if args.voice_preset:
            voice_instruct = VOICE_PRESETS[args.voice_preset]
            print(f"Using voice preset: {args.voice_preset}")
        elif args.instruct:
            voice_instruct = args.instruct
        else:
            voice_instruct = VOICE_PRESETS['ru-male']  # default
            print(f"Using default voice preset: ru-male")
        voice_name = None
    else:
        # CustomVoice model uses preset voices
        voice_name = args.voice
        voice_instruct = args.instruct if args.instruct else None

    # Load model
    model_name = MODELS[args.model]
    print(f"Loading model: {model_name}")
    model = load_model(model_name)

    # Read and split text
    print(f"Reading: {input_path}")
    text = input_path.read_text(encoding="utf-8")
    text = clean_text_for_tts(text)

    if not text:
        print("Error: Input file is empty.", file=sys.stderr)
        sys.exit(1)

    print(f"Splitting into chunks (max {args.max_chars} chars)...")
    chunks = split_text_smart(text, max_chars=args.max_chars)
    print(f"Created {len(chunks)} chunks")

    # Output path
    output_path = Path(args.output) if args.output else input_path.parent / f"{input_path.stem}_audiobook.mp3"

    # Process chunks
    temp_dir = tempfile.mkdtemp(prefix="qwen_tts_")
    temp_files = []

    try:
        if is_design_model:
            print(f"\nGenerating audio (model: {args.model}, speed: {args.speed})...")
            print(f"Voice description: {voice_instruct[:80]}...")
        else:
            print(f"\nGenerating audio (model: {args.model}, voice: {voice_name}, speed: {args.speed})...")

        for i, chunk in enumerate(tqdm(chunks, desc="Processing", unit="chunk")):
            chunk_prefix = f"{temp_dir}/chunk_{i:04d}"

            # Generate audio
            gen_kwargs = {
                'model': model,
                'text': chunk,
                'speed': args.speed,
                'ref_audio': args.ref_audio,
                'ref_text': args.ref_text,
                'file_prefix': chunk_prefix,
                'audio_format': 'wav',
                'verbose': False,
            }

            if is_design_model:
                gen_kwargs['instruct'] = voice_instruct
            else:
                gen_kwargs['voice'] = voice_name
                if voice_instruct:
                    gen_kwargs['instruct'] = voice_instruct

            generate_audio(**gen_kwargs)

            # Find generated file
            wav_file = Path(f"{chunk_prefix}_000.wav")
            if not wav_file.exists():
                wav_file = Path(f"{chunk_prefix}.wav")
            if not wav_file.exists():
                # Try to find any wav file with this prefix
                wav_files = list(Path(temp_dir).glob(f"chunk_{i:04d}*.wav"))
                if wav_files:
                    wav_file = wav_files[0]
                else:
                    print(f"Warning: No audio generated for chunk {i}", file=sys.stderr)
                    continue

            temp_files.append(wav_file)

        if not temp_files:
            print("Error: No audio files generated", file=sys.stderr)
            sys.exit(1)

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
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
