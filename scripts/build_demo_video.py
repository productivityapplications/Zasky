"""Build the <=180-second local protocol/transcript demo video.

The video is intentionally honest: it renders the real model/tool/approval
transcript, not a fabricated Discord UI. Audio is generated locally with
espeak-ng; no paid TTS or external media service is used.
"""

from __future__ import annotations

import subprocess
import textwrap
import wave
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "demo"
BUILD = OUT / "build"
WIDTH, HEIGHT = 1280, 720
BG = (13, 17, 23)
PANEL = (22, 27, 34)
WHITE = (240, 246, 252)
MUTED = (139, 148, 158)
GREEN = (126, 231, 135)
BLUE = (121, 192, 255)
YELLOW = (240, 200, 105)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


@dataclass(frozen=True)
class Slide:
    kicker: str
    title: str
    lines: tuple[str, ...]
    narration: str
    accent: tuple[int, int, int] = GREEN
    footer: str = "SYNTHETIC DATA · LOCAL STAGING · DISCORD UI NOT CAPTURED"


SLIDES: tuple[Slide, ...] = (
    Slide(
        "SINGLE-OWNER PLANNING AGENT",
        "ZASKY",
        ("It makes coming back cheap.", "Local protocol/transcript demo"),
        "This is Zasky. A personal planning agent that lives in a private chat "
        "room. It doesn't give me discipline. It makes coming back cheap.",
        GREEN,
    ),
    Slide(
        "THE PLAN HAS A SPINE",
        "Year → month → week → day",
        (
            "Year goals with evidence of done.",
            "Monthly commitments I name.",
            "An approved week pool, then one day.",
            "No invented tasks. I name the work.",
        ),
        "The plan has a spine: year goals, monthly commitments, an approved "
        "week pool, and one day. Zasky never invents tasks. I name the work; "
        "the application does the arithmetic.",
        BLUE,
    ),
    Slide(
        "FRIDAY, 6 NOVEMBER",
        "One must. Two should.",
        (
            "MUST    Record the demo narration — 45 min",
            "SHOULD  Capture the recovery transcript — 60 min",
            "Latest wake 08:30 · first required start 09:00",
            "65% capacity · protected slack",
        ),
        "On Friday, the plan has one must and two should tasks. The app shows "
        "the latest wake time from my preparation buffer. The day is small "
        "enough to start.",
        GREEN,
    ),
    Slide(
        "THE DAY BREAKS",
        "“Back. A two-hour call ran over.”",
        (
            "It is 4pm.",
            "The expensive part is reconstructing what mattered.",
            "Zasky already has the approved week pool.",
        ),
        "Then the day breaks. I say: back, a two-hour call ran over, it's 4pm. "
        "I don't rebuild the list from scratch. Zasky already has the approved "
        "week pool.",
        YELLOW,
    ),
    Slide(
        "RECOVERY PROPOSAL",
        "Keep what fits. Move the rest.",
        (
            "KEEP  16:00–16:45  Record the demo narration",
            "KEEP  16:45–17:45  Capture the recovery transcript",
            "KEEP  19:40–20:10  Review the release checklist",
            "MOVE  three tasks to Saturday — same week",
            "",
            "Week holds: 270 min work vs 1,066 min remaining budget",
        ),
        "Zasky reads the approved week pool and proposes a recovery. It keeps "
        "what still fits, moves the rest within the same week, preserves fixed "
        "events, and reports that the week holds with 270 minutes of work "
        "against a 1,066 minute remaining budget.",
        GREEN,
    ),
    Slide(
        "NOTHING CHANGES UNTIL APPROVAL",
        "The owner controls the commit.",
        (
            "Proposal ZK-EZK9",
            "Owner: approve ZK-EZK9",
            "",
            "The deterministic parser checks owner, room, code, expiry and",
            "every expected revision. The model cannot approve itself.",
        ),
        "Nothing changes until I approve. I send approve, with the proposal "
        "code. The deterministic parser commits the plan. The model cannot "
        "approve itself.",
        BLUE,
    ),
    Slide(
        "THE PLAN HOLDS",
        "Facts. Arithmetic. A next action.",
        (
            "Friday: 3 tasks · Saturday: 3 tasks",
            "Remaining work: 270 minutes",
            "The commitments are still mine.",
            "Zasky just made the return path short.",
        ),
        "Now the day is workable again. I ask what's left this week and get a "
        "short, evidence-backed answer. The commitments are still mine.",
        GREEN,
    ),
    Slide(
        "HONEST BOUNDARY",
        "What this demo is — and is not",
        (
            "Real model: openai/gpt-4o-mini via OpenRouter",
            "Seven strict tools + deterministic approval",
            "Synthetic data only",
            "No Discord screen capture; Switch transport runs separately",
        ),
        "This demo is a local protocol transcript, not a Discord screen capture. "
        "It uses synthetic data and the real OpenRouter model. The Switch "
        "transport is running separately.",
        YELLOW,
        "LOCAL PROTOCOL/TRANSCRIPT DEMO · REAL MODEL + TOOLS · SYNTHETIC DATA",
    ),
    Slide(
        "ZASKY",
        "It makes coming back cheap.",
        ("Synthetic demo · local staging · <=180 seconds",),
        "Zasky doesn't give me discipline. It makes coming back cheap.",
        GREEN,
    ),
)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size=size)


def wrap(text: str, max_chars: int) -> list[str]:
    return textwrap.wrap(text, width=max_chars, break_long_words=False) or [""]


def render_slide(slide: Slide, index: int) -> Path:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (48, 48, WIDTH - 48, HEIGHT - 72),
        radius=22,
        fill=PANEL,
        outline=(41, 48, 58),
        width=2,
    )
    draw.rectangle((48, 48, 60, HEIGHT - 72), fill=slide.accent)
    draw.text((92, 88), slide.kicker, font=font(18, True), fill=slide.accent)
    title_size = 58 if index in (0, 8) else 42
    title = slide.title
    y = 130
    for line in wrap(title, 38 if title_size >= 50 else 54):
        draw.text((92, y), line, font=font(title_size, True), fill=WHITE)
        y += title_size + 10
    y += 18
    for line in slide.lines:
        if not line:
            y += 22
            continue
        wrapped = wrap(line, 72)
        for part in wrapped:
            color = MUTED if line.startswith("MOVE") else WHITE
            draw.text((92, y), part, font=font(24), fill=color)
            y += 34
        y += 8
    draw.line((92, HEIGHT - 112, WIDTH - 92, HEIGHT - 112), fill=(41, 48, 58), width=1)
    draw.text((92, HEIGHT - 96), slide.footer, font=font(15), fill=MUTED)
    page = f"{index + 1:02d}/{len(SLIDES):02d}"
    draw.text(
        (WIDTH - 150, HEIGHT - 96),
        page,
        font=font(15, True),
        fill=slide.accent,
    )
    path = BUILD / f"slide-{index:02d}.png"
    image.save(path)
    return path


def synth_audio(slide: Slide, index: int) -> Path:
    path = BUILD / f"slide-{index:02d}.wav"
    subprocess.run(
        [
            "espeak-ng",
            "-v",
            "en-us",
            "-s",
            "155",
            "-p",
            "45",
            "-w",
            str(path),
            slide.narration,
        ],
        check=True,
        capture_output=True,
    )
    return path


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate()
        return frames / float(rate)


def render_segment(image: Path, audio: Path, duration: float, index: int) -> Path:
    path = BUILD / f"segment-{index:02d}.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-framerate",
            "30",
            "-i",
            str(image),
            "-i",
            str(audio),
            "-t",
            f"{duration:.2f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    segments: list[Path] = []
    script_lines = [
        "# Zasky local protocol/transcript demo",
        "",
        "Synthetic data only. Model: openai/gpt-4o-mini via OpenRouter.",
        "",
    ]
    total = 0.0
    for index, slide in enumerate(SLIDES):
        image = render_slide(slide, index)
        audio = synth_audio(slide, index)
        duration = wav_duration(audio) + 0.8
        segment = render_segment(image, audio, duration, index)
        segments.append(segment)
        total += duration
        script_lines.append(f"## {index + 1:02d} — {slide.title}")
        script_lines.append("")
        script_lines.append(slide.narration)
        script_lines.append("")

    concat = BUILD / "concat.txt"
    concat.write_text(
        "\n".join(f"file '{segment.resolve()}'" for segment in segments) + "\n",
        encoding="utf-8",
    )
    final = OUT / "zasky-demo.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(final),
        ],
        check=True,
        capture_output=True,
    )
    (OUT / "narration-script.md").write_text(
        "\n".join(script_lines).strip() + "\n", encoding="utf-8"
    )
    print(f"rendered {final} ({total:.1f}s planned, {len(SLIDES)} slides)")


if __name__ == "__main__":
    main()
