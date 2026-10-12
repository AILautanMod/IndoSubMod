"""Create Indonesian subtitles for a local video using Whisper and translation."""

from __future__ import annotations

import queue
import base64
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import threading
import time
import textwrap
import tkinter as tk
import urllib.error
import urllib.request
import webbrowser
import zlib
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from IndoSubMod_version import APP_VERSION

os.environ["HF_HUB_OFFLINE"] = "1"


VIDEO_TYPES = [
    ("Video files (Berkas video)", "*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.mpeg *.mpg *.wmv *.ts"),
    ("All files (Semua berkas)", "*.*"),
]

COLORS = {
    "background": "#050B11",
    "panel": "#0D1924",
    "panel_alt": "#122431",
    "border": "#263947",
    "cyan": "#00C8E8",
    "cyan_bright": "#13D9F4",
    "gold": "#F4B344",
    "silver": "#DCE5ED",
    "muted": "#A5B3C0",
    "ink": "#061118",
}


def timestamp(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def application_icon() -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return bundle_root / "IndoSubMod.ico"


def application_banner() -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return bundle_root / "IndoSubModBanner.png"


def application_logo() -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return bundle_root / "IndoSubModLogo.png"


def application_brand_logo() -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return bundle_root / "AILautanModBannerDisplay.png"


def show_themed_dialog(kind: str, title: str, message: str, **kwargs):
    parent = kwargs.get("parent")
    if parent is None:
        parent = next((widget for widget in tk._default_root.winfo_children() if isinstance(widget, tk.Tk)), tk._default_root) if tk._default_root else None
    if parent is None:
        return "ok"
    window = tk.Toplevel(parent)
    window.title(title)
    window.configure(background=COLORS["background"])
    window.resizable(False, False)
    window.transient(parent)
    icon = application_icon()
    if icon.is_file():
        try:
            window.iconbitmap(default=str(icon))
        except tk.TclError:
            pass
    accent = COLORS["gold"] if kind == "warning" else COLORS["cyan"]
    card = tk.Frame(window, background=COLORS["panel"], highlightthickness=1, highlightbackground=accent, padx=20, pady=16)
    card.pack(fill="both", expand=True, padx=12, pady=12)
    tk.Label(card, text="IndoSubMod  ✦  " + title, background=COLORS["panel"], foreground=accent, font=("Segoe UI", 13, "bold"), anchor="w").pack(fill="x", pady=(0, 12))
    tk.Label(card, text=message, background=COLORS["panel"], foreground=COLORS["silver"], font=("Segoe UI", 10), justify="left", anchor="w", wraplength=480).pack(fill="x")
    ttk.Button(card, text="OK  (Oke)", command=window.destroy, style="Accent.TButton").pack(anchor="e", pady=(18, 0))
    window.update_idletasks()
    window.geometry(f"{max(420, window.winfo_reqwidth())}x{window.winfo_reqheight()}+{parent.winfo_rootx() + max(0, (parent.winfo_width()-window.winfo_reqwidth())//2)}+{parent.winfo_rooty() + max(0, (parent.winfo_height()-window.winfo_reqheight())//2)}")
    window.grab_set()
    window.focus_force()
    window.wait_window()
    return "ok"


messagebox.showerror = lambda title, message, **kwargs: show_themed_dialog("error", title, message, **kwargs)
messagebox.showwarning = lambda title, message, **kwargs: show_themed_dialog("warning", title, message, **kwargs)
messagebox.showinfo = lambda title, message, **kwargs: show_themed_dialog("info", title, message, **kwargs)


def _srt_time_to_ass(value: str) -> str:
    match = re.fullmatch(r"\s*(\d{2}):(\d{2}):(\d{2})[,\.](\d{1,3})\s*", value)
    if not match:
        raise ValueError(f"Invalid SRT timestamp (Stempel waktu SRT tidak valid): {value}")
    hours, minutes, seconds, milliseconds = match.groups()
    centiseconds = int(milliseconds.ljust(3, "0")[:3]) // 10
    return f"{hours}:{minutes}:{seconds}.{centiseconds:02}"


SUBTITLE_SETTINGS_DEFAULTS = {
    "font_name": "Arial",
    "font_size": 48,
    "background_enabled": True,
    "background_opacity": 50,
    "max_chars_per_line": 42,
}


def subtitle_settings_path() -> Path:
    root = user_data_root()
    return root / "subtitle_settings.json"


def user_data_root() -> Path:
    local = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    root = local / "IndoSubMod"
    legacy = local / "IndoSub"
    root.mkdir(parents=True, exist_ok=True)
    for name in ("subtitle_settings.json", "feedback.json"):
        destination = root / name
        source = legacy / name
        if not destination.exists() and source.is_file():
            try:
                destination.write_bytes(source.read_bytes())
            except OSError:
                pass
    return root


def load_subtitle_settings() -> dict:
    settings = dict(SUBTITLE_SETTINGS_DEFAULTS)
    try:
        saved = json.loads(subtitle_settings_path().read_text(encoding="utf-8"))
        if isinstance(saved, dict):
            if saved.get("font_name") in ("Arial", "Segoe UI", "Tahoma", "Verdana"):
                settings["font_name"] = saved["font_name"]
            if isinstance(saved.get("background_enabled"), bool):
                settings["background_enabled"] = saved["background_enabled"]
            for key, low, high in (("font_size", 24, 80), ("background_opacity", 10, 90), ("max_chars_per_line", 24, 72)):
                try:
                    settings[key] = min(high, max(low, int(saved.get(key, settings[key]))))
                except (TypeError, ValueError):
                    pass
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return settings


def save_subtitle_settings(settings: dict) -> None:
    path = subtitle_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def srt_to_ass(source: Path, destination: Path) -> None:
    """Create an ASS subtitle track with a restrained translucent charcoal box."""
    raw = source.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    dialogue = []
    settings = load_subtitle_settings()
    wrap_width = settings["max_chars_per_line"]
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = block.splitlines()
        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        timing = re.match(r"\s*(\S+)\s+-->\s+(\S+)", lines[timing_index])
        if not timing:
            raise ValueError("Could not parse the SRT subtitle timestamp. (Stempel waktu subtitle SRT tidak dapat dibaca.)")
        start = _srt_time_to_ass(timing.group(1))
        end = _srt_time_to_ass(timing.group(2))
        text_lines = [line.strip() for line in lines[timing_index + 1:] if line.strip()]
        if not text_lines:
            continue
        # Prevent SRT text from being interpreted as ASS override commands.
        text = " ".join(text_lines)
        text = re.sub(r"<[^>]*>", "", text)
        # Replace ellipses with a single full stop so they never appear in the video.
        text = re.sub(r"(?:\.{2,}|…+)", ".", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = text.replace("\\", "／").replace("{", "｛").replace("}", "｝")
        wrapped_lines = []
        for line in text.splitlines():
            wrapped_lines.extend(textwrap.wrap(line, width=wrap_width, break_long_words=True, break_on_hyphens=False) or [""])
        text = "\\N".join(wrapped_lines)
        dialogue.append(f"Dialogue: 0,{start},{end},IndoSubMod,,0,0,0,,{text}")
    if not dialogue:
        raise ValueError("The SRT file contains no subtitle lines. (File SRT tidak berisi baris subtitle.)")
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: IndoSubMod,Arial,48,&H00FFFFFF,&H000000FF,&H80404040,&HFF000000,0,0,0,0,100,100,0,0,3,5,0,2,48,48,38,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    alpha = round(255 * (100 - settings["background_opacity"]) / 100)
    if settings["background_enabled"]:
        # BorderStyle 3 is the standard ASS opaque-box mode. Its box color is
        # taken from OutlineColour; BorderStyle 4 is a renderer-specific extension.
        outline_colour = f"&H{alpha:02X}404040"
        back_colour = "&HFF000000"
        border_style, outline = 3, 5
    else:
        outline_colour = "&H00101010"
        back_colour = "&HFF000000"
        border_style, outline = 1, 2
    style = f"Style: IndoSubMod,{settings['font_name']},{settings['font_size']},&H00FFFFFF,&H000000FF,{outline_colour},{back_colour},0,0,0,0,100,100,0,0,{border_style},{outline},0,2,48,48,38,1"
    header = header.replace("Style: IndoSubMod,Arial,48,&H00FFFFFF,&H000000FF,&H80404040,&HFF000000,0,0,0,0,100,100,0,0,3,5,0,2,48,48,38,1", style)
    destination.write_text(header + "\n".join(dialogue) + "\n", encoding="utf-8-sig", newline="\n")


def mux_subtitles(video: Path, subtitle: Path, output: Path, progress_callback=None, duration: float | None = None) -> None:
    """Copy streams into MKV and add a selectable Indonesian ASS track with a translucent backdrop."""
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    partial = output.with_name(output.stem + ".partial.mkv")
    styled_subtitle = output.with_name(output.stem + ".partial.ass")
    try:
        srt_to_ass(subtitle, styled_subtitle)
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-i", str(video), "-i", str(styled_subtitle),
            "-map", "0:v?", "-map", "0:a?", "-map", "1:0", "-c", "copy", "-c:s", "ass",
            "-map_metadata", "0", "-map_chapters", "0", "-progress", "pipe:1", "-nostats", str(partial),
        ]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        assert process.stdout is not None
        for line in process.stdout:
            if not progress_callback or not duration or duration <= 0:
                continue
            if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
                try:
                    microseconds = int(line.split("=", 1)[1])
                    progress_callback(min(1.0, max(0.0, microseconds / (duration * 1_000_000))))
                except (ValueError, ZeroDivisionError):
                    pass
            elif line.strip() == "progress=end":
                progress_callback(1.0)
        _stdout, stderr = process.communicate()
        if process.returncode:
            detail = (stderr or "").strip()[-1800:]
            raise RuntimeError(detail or f"FFmpeg exited with code {process.returncode}. (FFmpeg berhenti dengan kode {process.returncode}.)")
        if not partial.is_file() or partial.stat().st_size == 0:
            raise RuntimeError("FFmpeg did not create the output video. (FFmpeg tidak membuat video hasil.)")
        os.replace(partial, output)
    finally:
        partial.unlink(missing_ok=True)
        styled_subtitle.unlink(missing_ok=True)

FORMAL_CUES = re.compile(
    r"\b(sir|madam|mr\.?|mrs\.?|ms\.?|your honor|dear|hereby|pursuant|"
    r"official|regulation|policy|contract|we request|please be advised|"
    r"would you kindly|you are required)\b",
    re.IGNORECASE,
)
CASUAL_CUES = re.compile(
    r"\b(i'm|you're|we're|they're|that's|it's|don't|can't|won't|gonna|wanna|"
    r"gotta|hey|bro|dude|guys|yeah|nope|cool|buddy)\b",
    re.IGNORECASE,
)


def apply_register(english: str, indonesian: str, register: str) -> str:
    chosen = register
    if chosen == REGISTER_AUTO:
        if FORMAL_CUES.search(english):
            chosen = REGISTER_FORMAL
        elif CASUAL_CUES.search(english):
            chosen = REGISTER_FRIENDLY
        else:
            return indonesian

    replacements = (
        (("Anda", "kamu"), ("anda", "kamu"), ("Saya", "Aku"), ("saya", "aku"), ("Saudara", "kamu"), ("saudara", "kamu"))
        if chosen == REGISTER_FRIENDLY
        else (("kamu", "Anda"), ("Kamu", "Anda"), ("kau", "Anda"), ("Aku", "Saya"), ("aku", "saya"), ("gue", "saya"), ("gua", "saya"))
    )
    for old, new in replacements:
        indonesian = re.sub(rf"\b{re.escape(old)}\b", new, indonesian)
    return indonesian


def load_offline_translator():
    import argostranslate.translate

    languages = argostranslate.translate.get_installed_languages()
    english = next((language for language in languages if language.code == "en"), None)
    indonesian = next((language for language in languages if language.code == "id"), None)
    if english is None or indonesian is None:
        raise RuntimeError("The offline English-to-Indonesian model is missing. Run IndoSubModSetup.exe with internet access. (Model luring Inggris-ke-Indonesia tidak ditemukan. Jalankan IndoSubModSetup.exe dengan koneksi internet.)")
    translation = english.get_translation(indonesian)
    if translation is None:
        raise RuntimeError("The offline en → id model is not installed. Run IndoSubModSetup.exe with internet access. (Model luring en → id belum terpasang. Jalankan IndoSubModSetup.exe dengan koneksi internet.)")
    # Whisper already provides short subtitle-sized segments. Do not let Argos
    # lazily download a separate sentence-boundary model during offline use.
    class SubtitleSegmenter:
        @staticmethod
        def split_sentences(text: str) -> list[str]:
            return [text] if text.strip() else []

    segmenter = SubtitleSegmenter()
    seen: set[int] = set()

    def configure_segments(current):
        if id(current) in seen:
            return
        seen.add(id(current))
        if hasattr(current, "sentencizer"):
            current.sentencizer = segmenter
        for attribute in ("underlying", "t1", "t2"):
            child = getattr(current, attribute, None)
            if child is not None:
                configure_segments(child)

    configure_segments(translation)
    return translation


def ollama_is_installed() -> bool:
    if shutil.which("ollama") or shutil.which("ollama.exe"):
        return True
    local = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
    return any(path.is_file() for path in (
        local / "Programs" / "Ollama" / "ollama.exe",
        program_files / "Ollama" / "ollama.exe",
    ))


def ollama_prompt_choice_path() -> Path:
    return user_data_root() / "ollama_prompt_choice.txt"


def offline_translation_available() -> bool:
    try:
        import argostranslate.translate

        languages = argostranslate.translate.get_installed_languages()
        english = next((language for language in languages if language.code == "en"), None)
        indonesian = next((language for language in languages if language.code == "id"), None)
        return english is not None and indonesian is not None and english.get_translation(indonesian) is not None
    except Exception:
        return False


API_SERVICE = "IndoSubMod OpenAI API"
LEGACY_API_SERVICE = "IndoSub OpenAI API"
API_USER = "default"
GPT_MODEL = "gpt-6-astra"
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODE = "Your local model (Ollama) (Model lokal Anda (Ollama))"
GPT_MODE = "GPT online (GPT daring)"
ARGOS_MODE = "Offline (Argos) (Luring (Argos))"
MODE_LABELS = {
    ARGOS_MODE: "Offline (Argos) (Luring)",
    OLLAMA_MODE: "Local model (Ollama) (Model lokal)",
    GPT_MODE: "GPT online (Daring)",
}
MODE_INTERNAL_BY_LABEL = {label: mode for mode, label in MODE_LABELS.items()}
REGISTER_AUTO = "Automatic (Otomatis)"
REGISTER_FORMAL = "Formal (Resmi)"
REGISTER_FRIENDLY = "Friendly (Akrab)"
REVIEW_PLACEHOLDER = "[Needs review] (Perlu ditinjau)"


ENGLISH_UI = {
    "Готово к работе": "Ready", "Способ перевода на индонезийский:": "Indonesian translation method:",
    "Офлайн (Argos) · Своя локальная модель (Ollama) · GPT онлайн": "Offline (Argos) · Your local model (Ollama) · GPT online",
    "Ключ OpenAI API:": "OpenAI API key:", "Запомнить в Windows": "Remember in Windows", "Получить ключ": "Get API key",
    "Текст речи отправляется OpenAI; оплата API отдельная.": "Speech text is sent to OpenAI; API usage is billed separately.",
    "Локальная модель Ollama:": "Ollama local model:", "Найти модели": "Refresh models",
    "Работает локально на этом компьютере. Интернет и облачный API не используются; сначала запустите Ollama и загрузите модель.": "Runs locally on this computer. No internet or cloud API is used; start Ollama and download a model first.",
    "Видео:": "Video:", "Выбрать видео": "Choose video",
    "Поддерживаемые форматы: MP4, MKV, MOV, AVI, WebM, M4V, MPEG, MPG, WMV, TS.": "Supported formats: MP4, MKV, MOV, AVI, WebM, M4V, MPEG, MPG, WMV, TS.",
    "Стиль индонезийского:": "Indonesian style:", "Автоматический режим выбирает официальный или дружеский тон.": "Automatic mode chooses a formal or friendly tone.",
    "Исходное видео не меняется: создаётся отдельный MKV с дорожкой субтитров, без перекодирования видео и звука. Прототип предназначен только для тестирования и некоммерческого использования; права на видео остаются у правообладателей.": "The source video is unchanged: a separate MKV with subtitles is created without re-encoding video or audio. This prototype is for testing and non-commercial use only; video rights remain with their owners.",
    "Создать видео с субтитрами": "Create subtitled video", "Оценить перевод": "Review translation", "Настройки субтитров": "Subtitle settings", "Поддержать автора": "Support the creator",
    "Журнал обработки": "Processing log", "Локальные модели": "Local models", "Ollama недоступна": "Ollama is unavailable",
    "Видео не выбрано": "No video selected", "Выберите существующий видеофайл.": "Choose an existing video file.",
    "Нужен ключ OpenAI API": "OpenAI API key required", "Введите ключ для режима GPT онлайн.": "Enter an API key for GPT online mode.",
    "Выберите локальную модель": "Select a local model", "Нажмите «Найти модели» и выберите установленную модель Ollama.": "Select Refresh models and choose an installed Ollama model.",
    "Куда сохранить видео с субтитрами?": "Where should the subtitled video be saved?", "Видео Matroska с субтитрами": "Subtitled Matroska video",
    "Выберите другое имя": "Choose a different name", "Итоговый файл не может заменить исходное видео.": "The output file cannot overwrite the source video.",
    "Не удалось сохранить ключ": "Could not save the key", "Снимите отметку или выберите офлайн-режим.": "Clear the checkbox or choose offline mode.",
    "Подготовка обработки": "Preparing video", "Обработка видео": "Processing video",
    "Подготовка и загрузка модели Whisper": "Preparing and loading the Whisper model", "Загружаю офлайн-модель перевода en → id": "Loading the offline en → id translation model",
    "Распознаю речь и перевожу её на английский": "Recognizing speech and translating it into English", "Распознавание речи": "Speech recognition",
    "Распознавание и перевод речи на английский": "Recognizing speech and translating it into English",
    "Встраиваю индонезийские субтитры в видео без перекодирования": "Adding Indonesian subtitles without re-encoding the video", "Добавление субтитров в видео": "Adding subtitles to video",
    "Не удалось обновить дорожку субтитров в MKV.": "Could not update the subtitle track in the MKV.", "Видео не обновлено": "Video was not updated",
    "Не удалось создать субтитры": "Could not create subtitles", "Субтитры готовы": "Subtitles are ready", "Настройка субтитров": "Subtitle settings",
    "Внешний вид субтитров": "Subtitle appearance", "Изменения применятся к следующему созданному или обновлённому видео.": "Changes apply to the next video created or updated.",
    "Шрифт": "Font", "Размер текста": "Text size", "Символов в строке до переноса": "Characters per line before wrapping",
    "Без серого фона": "No gray background", "Непрозрачность серого фона": "Gray background opacity",
    "Не удалось сохранить настройки": "Could not save settings", "Отмена": "Cancel", "Сохранить": "Save",
    "Одобренные переводы и исправления сохраняются на этом компьютере.": "Approved translations and corrections are saved on this computer.",
    "Исправленный или подтверждённый вариант:": "Corrected or approved version:", "Встроенные субтитры в видео обновлены.": "Embedded video subtitles were updated.",
    "Обновляю субтитры в видео": "Updating video subtitles", "Выберите субтитр": "Select a subtitle", "Сначала выберите строку в списке.": "Select a row in the list first.",
    "Пустой перевод": "Translation is empty", "Введите текст на индонезийском языке.": "Enter the Indonesian text.", "Не удалось обновить SRT": "Could not update the SRT file",
    "Нет перевода для оценки": "No translation to review", "Выберите строку с переводом.": "Select a row that contains a translation.",
    "Хороший перевод": "Good translation", "Плохой перевод": "Poor translation", "Сохранить исправление": "Save correction", "Закрыть": "Close",
}


def bi(russian: str, indonesian: str) -> str:
    return f"{ENGLISH_UI.get(russian, russian)}\n({indonesian})"


def enable_clipboard_controls(widget) -> None:
    """Keep standard Windows clipboard shortcuts available and add a context menu."""
    menu = tk.Menu(widget, tearoff=False, background=COLORS["panel"], foreground=COLORS["silver"], activebackground=COLORS["cyan"], activeforeground=COLORS["ink"])
    for label, virtual_event in (("Cut (Potong)", "<<Cut>>"), ("Copy (Salin)", "<<Copy>>"), ("Paste (Tempel)", "<<Paste>>")):
        menu.add_command(label=label, command=lambda event=virtual_event: widget.event_generate(event))
    menu.add_separator()

    def select_all():
        if isinstance(widget, tk.Text):
            widget.tag_add("sel", "1.0", "end-1c")
        elif hasattr(widget, "selection_range"):
            widget.selection_range(0, "end")
        widget.focus_set()

    menu.add_command(label="Select all (Pilih semua)", command=select_all)

    def show_menu(event):
        widget.focus_set()
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    widget.bind("<Button-3>", show_menu, add="+")
    for sequence, virtual_event in (("<Control-x>", "<<Cut>>"), ("<Control-c>", "<<Copy>>"), ("<Control-v>", "<<Paste>>"), ("<Shift-Insert>", "<<Paste>>")):
        widget.bind(sequence, lambda _event, event=virtual_event: (widget.event_generate(event), "break")[1], add="+")
    widget.bind("<Control-a>", lambda _event: (select_all(), "break")[1], add="+")


def feedback_path() -> Path:
    return user_data_root() / "feedback.json"


def load_feedback() -> list[dict[str, str]]:
    try:
        data = json.loads(feedback_path().read_text(encoding="utf-8"))
        items = [item for item in data if isinstance(item, dict) and item.get("english") and item.get("indonesian")]
        legacy_registers = {"Автоматически": REGISTER_AUTO, "Официальный": REGISTER_FORMAL, "Дружеский": REGISTER_FRIENDLY}
        for item in items:
            if item.get("register") in legacy_registers:
                item["register"] = legacy_registers[item["register"]]
        return items
    except (OSError, json.JSONDecodeError, TypeError):
        return []


def save_feedback(items: list[dict[str, str]]) -> None:
    path = feedback_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(items[-5000:], ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def normalize_text(text: str) -> str:
    return re.sub(r"[^\w]+", " ", text.casefold(), flags=re.UNICODE).strip()


def find_learned_translation(english: str, examples: list[dict[str, str]], register: str) -> str | None:
    key = normalize_text(english)
    for item in reversed(examples):
        if item.get("quality", "good") == "good" and item.get("register") in (None, register) and normalize_text(item["english"]) == key:
            return item["indonesian"]
    return None


def is_rejected_translation(english: str, indonesian: str, examples: list[dict[str, str]], register: str) -> bool:
    source_key = normalize_text(english)
    target_key = normalize_text(indonesian)
    return any(
        item.get("quality") == "bad"
        and item.get("register") in (None, register)
        and normalize_text(item["english"]) == source_key
        and normalize_text(item["indonesian"]) == target_key
        for item in examples
    )


def relevant_examples(texts: list[str], examples: list[dict[str, str]], register: str, limit: int = 6) -> list[dict[str, str]]:
    wanted = set(re.findall(r"[a-z']+", " ".join(texts).casefold()))
    ranked = []
    seen = set()
    for item in examples:
        key = " ".join(item["english"].casefold().split())
        if key in seen or item.get("register") not in (None, register):
            continue
        seen.add(key)
        tokens = set(re.findall(r"[a-z']+", key))
        overlap = len(wanted & tokens) / max(1, len(wanted | tokens))
        ranked.append((overlap, item))
    return [item for score, item in sorted(ranked, key=lambda pair: pair[0], reverse=True)[:limit] if score > 0]


def get_saved_api_key() -> str:
    try:
        import keyring
        return keyring.get_password(API_SERVICE, API_USER) or keyring.get_password(LEGACY_API_SERVICE, API_USER) or ""
    except Exception:
        return ""


def build_translation_instructions(texts: list[str], register: str, examples: list[dict[str, str]] | None = None) -> str:
    style = {
        REGISTER_AUTO: "Choose formal Indonesian for official or professional speech and friendly conversational Indonesian for casual dialogue. Infer the register from context.",
        REGISTER_FORMAL: "Use standard, formal Bahasa Indonesia suitable for official or professional communication.",
        REGISTER_FRIENDLY: "Use natural, friendly, conversational Bahasa Indonesia suitable for dialogue between familiar people.",
    }[register]
    examples = examples or []
    good_examples = [item for item in examples if item.get("quality", "good") == "good"]
    bad_examples = [item for item in examples if item.get("quality") == "bad"]
    style_examples = relevant_examples(texts, good_examples, register)
    instructions = (
        "Translate each English subtitle segment into Indonesian. "
        "Keep the same number and order of segments; preserve meaning, names, tone, "
        f"and concise subtitle phrasing. {style}"
    )
    if style_examples:
        instructions += " Apply these user-approved translation examples as terminology and style guidance; translate new meanings faithfully rather than copying an unrelated example: " + json.dumps(
            [{"English": item["english"], "Indonesian": item["indonesian"]} for item in style_examples], ensure_ascii=False
        )
    rejected = relevant_examples(texts, bad_examples, register, limit=12)
    if rejected:
        instructions += " Never repeat these user-rejected English → Indonesian pairs. For the same English text, choose a genuinely different, faithful Indonesian translation: " + json.dumps(
            [{"English": item["english"], "Rejected Indonesian": item["indonesian"]} for item in rejected], ensure_ascii=False
        )
    return instructions


def _parse_translation_list(raw: str, expected_count: int) -> list[str]:
    try:
        translations = json.loads(raw)["translations"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError("GPT returned an unexpected response format. (GPT memberikan format respons yang tidak terduga.)") from exc
    if not isinstance(translations, list) or len(translations) != expected_count or not all(isinstance(x, str) and x.strip() for x in translations):
        raise RuntimeError("GPT returned an incorrect number of translations. (GPT memberikan jumlah terjemahan yang tidak sesuai.)")
    return [x.strip() for x in translations]


def list_ollama_models(timeout: float = 3.0) -> list[str]:
    """List models from the local Ollama service; this never contacts a remote host."""
    request = urllib.request.Request(OLLAMA_BASE_URL + "/api/tags", method="GET")
    try:
        # Bypass environment-configured HTTP proxies so private subtitle text and
        # local model traffic cannot accidentally be forwarded off this computer.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Could not connect to local Ollama. Start Ollama and download a model. (Tidak dapat terhubung ke Ollama lokal. Jalankan Ollama dan unduh model.)") from exc
    models = result.get("models", [])
    return [item["name"] for item in models if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"].strip()]


def translate_with_ollama(model_name: str, texts: list[str], register: str, examples: list[dict[str, str]] | None = None) -> list[str]:
    """Translate through the Ollama API bound to localhost only."""
    model_name = model_name.strip()
    if not model_name:
        raise RuntimeError("Enter a local Ollama model name, for example a model from the list. (Masukkan nama model Ollama lokal, misalnya model dari daftar.)")
    schema = {
        "type": "object",
        "properties": {"translations": {"type": "array", "items": {"type": "string"}}},
        "required": ["translations"],
        "additionalProperties": False,
    }
    body = {
        "model": model_name,
        "stream": False,
        "format": schema,
        "messages": [
            {"role": "system", "content": build_translation_instructions(texts, register, examples) + " Return only JSON matching the supplied schema."},
            {"role": "user", "content": json.dumps(texts, ensure_ascii=False)},
        ],
        "options": {"temperature": 0.2},
    }
    request = urllib.request.Request(
        OLLAMA_BASE_URL + "/api/chat",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"Local Ollama error ({exc.code}): {detail} (Kesalahan Ollama lokal.)") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Local Ollama did not return a translation. Check that its server is running. (Ollama lokal tidak memberikan terjemahan. Pastikan servernya berjalan.)") from exc
    content = result.get("message", {}).get("content", "")
    return _parse_translation_list(content, len(texts))


def translate_with_gpt(api_key: str, texts: list[str], register: str, examples: list[dict[str, str]] | None = None) -> list[str]:
    schema = {
        "type": "object",
        "properties": {"translations": {"type": "array", "items": {"type": "string"}}},
        "required": ["translations"],
        "additionalProperties": False,
    }
    instructions = build_translation_instructions(texts, register, examples)
    body = {
        "model": GPT_MODEL,
        "store": False,
        "instructions": instructions + " Return only the requested JSON.",
        "input": json.dumps(texts, ensure_ascii=False),
        "text": {"format": {"type": "json_schema", "name": "subtitle_translations", "strict": True, "schema": schema}},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"OpenAI API error ({exc.code}): {detail} (Kesalahan API OpenAI.)") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not connect to the OpenAI API: {exc.reason} (Tidak dapat terhubung ke API OpenAI.)") from exc
    output = "\n".join(
        part.get("text", "")
        for item in result.get("output", []) if item.get("type") == "message"
        for part in item.get("content", []) if part.get("type") == "output_text"
    )
    return _parse_translation_list(output, len(texts))


class IndoSubModApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"IndoSubMod {APP_VERSION} — Subtitles (Subtitle)")
        icon = application_icon()
        if icon.is_file():
            try:
                self.iconbitmap(default=str(icon))
            except tk.TclError:
                pass
        self.geometry("1000x900")
        self.minsize(900, 820)
        self.configure(background=COLORS["background"])
        self._rounded_button_images = []
        self._configure_style()
        self.path = tk.StringVar()
        self.register = tk.StringVar(value=REGISTER_AUTO)
        self.offline_available = offline_translation_available()
        default_mode = ARGOS_MODE if self.offline_available else GPT_MODE
        self.translation_mode = tk.StringVar(value=MODE_LABELS[default_mode])
        self.api_key = tk.StringVar(value=os.environ.get("OPENAI_API_KEY", ""))
        self.ollama_model = tk.StringVar(value=os.environ.get("INDOSUB_OLLAMA_MODEL", "qwen2.5:1.5b"))
        self.save_key = tk.BooleanVar(value=True)
        self.events: queue.Queue = queue.Queue()
        self.running = False
        self._button_animation_jobs = {}
        self._button_original_styles = {}
        self.processing_started = 0.0
        self.progress_percent = 0.0
        self.progress_target = 0.0
        self.progress_reported_value = 0.0
        self.progress_reported_at = 0.0
        self.progress_stage = bi("Готово к работе", "Siap digunakan")
        self.current_records: list[dict] = []
        self.current_output: Path | None = None
        self.current_video: Path | None = None
        self._build()
        self._configure_button_animations()
        self.after(150, self._poll)
        if not self.api_key.get():
            self.after(350, self._load_saved_api_key)
        self.after(600, self._offer_ollama_download)

    def _offer_ollama_download(self):
        choice_file = ollama_prompt_choice_path()
        try:
            if choice_file.is_file() and choice_file.read_text(encoding="utf-8").strip().lower() == "no":
                return
        except OSError:
            pass
        if ollama_is_installed():
            return

        dialog = tk.Toplevel(self)
        dialog.title("Optional local translation (Terjemahan lokal opsional)")
        dialog.configure(background=COLORS["background"])
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.attributes("-topmost", True)
        icon = application_icon()
        if icon.is_file():
            try:
                dialog.iconbitmap(default=str(icon))
            except tk.TclError:
                pass
        card = tk.Frame(dialog, background=COLORS["panel"], highlightthickness=1, highlightbackground=COLORS["gold"], padx=22, pady=18)
        card.pack(fill="both", expand=True, padx=12, pady=12)
        tk.Label(card, text="Would you like to download Ollama? (Ingin mengunduh Ollama?)", background=COLORS["panel"], foreground=COLORS["gold"], font=("Segoe UI", 13, "bold"), justify="left", wraplength=510).pack(fill="x", anchor="w", pady=(0, 12))
        message = (
            "Yes opens the official Ollama for Windows download page. You can install Ollama separately and then select a local model in IndoSubMod.\n"
            "No continues without opening the site; use Argos offline if installed, or GPT online.\n\n"
            "Ya membuka halaman resmi unduhan Ollama untuk Windows. Anda dapat memasang Ollama secara terpisah, lalu memilih model lokal di IndoSubMod.\n"
            "Tidak melanjutkan tanpa membuka situs; gunakan Argos luring jika tersedia atau GPT daring."
        )
        tk.Label(card, text=message, background=COLORS["panel"], foreground=COLORS["silver"], font=("Segoe UI", 10), justify="left", anchor="w", wraplength=510).pack(fill="x")
        buttons = tk.Frame(card, background=COLORS["panel"])
        buttons.pack(fill="x", pady=(18, 0))
        decision = {"open": None}

        def finish(open_page: bool):
            decision["open"] = open_page
            dialog.destroy()

        ttk.Button(buttons, text="No, continue (Tidak, lanjutkan)", command=lambda: finish(False), style="Secondary.TButton").pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Yes, open Ollama (Ya, buka Ollama)", command=lambda: finish(True), style="Accent.TButton").pack(side="right")
        dialog.protocol("WM_DELETE_WINDOW", lambda: finish(False))
        dialog.update_idletasks()
        width = max(560, dialog.winfo_reqwidth())
        height = dialog.winfo_reqheight()
        x = self.winfo_rootx() + max(0, (self.winfo_width() - width) // 2)
        y = self.winfo_rooty() + max(0, (self.winfo_height() - height) // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")
        dialog.focus_force()
        self.wait_window(dialog)

        if decision["open"]:
            try:
                if not webbrowser.open("https://ollama.com/download/windows", new=2):
                    raise RuntimeError("The default browser did not open the Ollama download page.")
            except Exception as exc:
                show_themed_dialog("error", "Could not open Ollama (Ollama tidak dapat dibuka)", f"Open https://ollama.com/download/windows manually.\n({exc})", parent=self)
        else:
            try:
                choice_file.write_text("no", encoding="utf-8")
            except OSError:
                pass

    def _configure_style(self):
        style = ttk.Style(self)
        self.option_add("*TCombobox*Listbox.background", COLORS["panel"])
        self.option_add("*TCombobox*Listbox.foreground", COLORS["silver"])
        self.option_add("*TCombobox*Listbox.selectBackground", COLORS["cyan"])
        self.option_add("*TCombobox*Listbox.selectForeground", COLORS["ink"])
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", font=("Trebuchet MS", 10), foreground=COLORS["silver"], background=COLORS["background"])
        style.configure("TFrame", background=COLORS["panel"])
        style.configure("Card.TLabel", background=COLORS["panel"], foreground=COLORS["silver"], font=("Trebuchet MS", 10))
        style.configure("TLabel", background=COLORS["panel"], foreground=COLORS["silver"], font=("Trebuchet MS", 10))
        style.configure("RootMuted.TLabel", background=COLORS["background"], foreground="#C3D0DC", font=("Trebuchet MS", 9))
        style.configure("Hero.TLabel", font=("Segoe UI", 18, "bold"), foreground=COLORS["silver"])
        style.configure("Muted.TLabel", background=COLORS["panel"], foreground="#BAC9D7", font=("Trebuchet MS", 9))
        style.configure("Accent.TLabel", foreground=COLORS["cyan"])
        style.configure("Gold.TLabel", foreground=COLORS["gold"])
        style.configure("Status.TLabel", foreground=COLORS["cyan"], font=("Segoe UI", 10, "bold"))
        self._configure_rounded_button_styles(style)
        style.configure("TButton", padding=(12, 8), background=COLORS["panel_alt"], foreground=COLORS["silver"], bordercolor=COLORS["border"], focuscolor=COLORS["cyan"], relief="flat")
        style.map("TButton", background=[("disabled", COLORS["panel"]), ("pressed", COLORS["cyan"]), ("active", COLORS["border"])], foreground=[("disabled", COLORS["muted"]), ("pressed", COLORS["ink"]), ("active", COLORS["silver"])])
        style.configure("Accent.TButton", padding=(16, 9), background=COLORS["gold"], foreground=COLORS["ink"], font=("Segoe UI", 10, "bold"), bordercolor=COLORS["gold"])
        style.map("Accent.TButton", background=[("disabled", COLORS["border"]), ("pressed", COLORS["cyan_bright"]), ("active", COLORS["cyan_bright"])], foreground=[("disabled", COLORS["muted"]), ("pressed", COLORS["ink"]), ("active", COLORS["ink"])])
        style.configure("Secondary.TButton", background=COLORS["panel_alt"], foreground=COLORS["silver"])
        style.map("Secondary.TButton", background=[("disabled", COLORS["panel"]), ("pressed", COLORS["cyan"]), ("active", COLORS["border"])], foreground=[("disabled", COLORS["muted"]), ("pressed", COLORS["ink"])])
        style.configure("Pressed.TButton", padding=(11, 7), background=COLORS["cyan"], foreground=COLORS["ink"], bordercolor=COLORS["cyan"])
        style.configure("Pressed.Accent.TButton", padding=(15, 8), background=COLORS["cyan_bright"], foreground=COLORS["ink"], bordercolor=COLORS["cyan_bright"], font=("Segoe UI", 10, "bold"))
        style.configure("Pressed.Secondary.TButton", padding=(11, 7), background=COLORS["cyan"], foreground=COLORS["ink"], bordercolor=COLORS["cyan"])
        style.configure("TEntry", padding=(8, 7), fieldbackground=COLORS["panel"], foreground=COLORS["silver"], bordercolor=COLORS["border"])
        style.configure("TCombobox", padding=(7, 6), fieldbackground=COLORS["panel"], background=COLORS["panel_alt"], foreground=COLORS["silver"], arrowcolor=COLORS["cyan"], bordercolor=COLORS["border"])
        style.map("TCombobox", fieldbackground=[("readonly", COLORS["panel"])], foreground=[("readonly", COLORS["silver"])], selectbackground=[("readonly", COLORS["panel"])], selectforeground=[("readonly", COLORS["silver"])])
        style.configure("TCheckbutton", background=COLORS["background"], foreground=COLORS["silver"])
        style.map("TCheckbutton", background=[("active", COLORS["background"])], foreground=[("active", COLORS["cyan"])])
        style.configure("TProgressbar", background=COLORS["cyan"], troughcolor=COLORS["panel"], bordercolor=COLORS["panel"])
        style.configure("Treeview", background=COLORS["panel"], fieldbackground=COLORS["panel"], foreground=COLORS["silver"], rowheight=30, bordercolor=COLORS["border"])
        style.map("Treeview", background=[("selected", COLORS["cyan"])], foreground=[("selected", COLORS["ink"])])
        style.configure("Treeview.Heading", background=COLORS["panel_alt"], foreground=COLORS["cyan"], font=("Segoe UI", 10, "bold"), padding=(8, 8))

    def _make_rounded_button_image(self, fill: str, outline: str, bottom: str | None = None) -> tk.PhotoImage:
        size, radius, border_width, samples = 32, 10.0, 1.5, 4
        fill_rgb = tuple(int(fill[index:index + 2], 16) for index in (1, 3, 5))
        bottom_rgb = tuple(int((bottom or fill)[index:index + 2], 16) for index in (1, 3, 5))
        edge_rgb = tuple(int(outline[index:index + 2], 16) for index in (1, 3, 5))
        raw = bytearray()
        for y in range(size):
            raw.append(0)
            for x in range(size):
                fill_count = edge_count = 0
                for sy in range(samples):
                    py = y + (sy + 0.5) / samples
                    for sx in range(samples):
                        px = x + (sx + 0.5) / samples
                        dx = abs(px - size / 2) - (size / 2 - radius)
                        dy = abs(py - size / 2) - (size / 2 - radius)
                        distance = math.hypot(max(dx, 0), max(dy, 0)) + min(max(dx, dy), 0) - radius
                        if distance <= -border_width:
                            fill_count += 1
                        elif distance <= 0:
                            edge_count += 1
                total = fill_count + edge_count
                if not total:
                    raw.extend((0, 0, 0, 0))
                    continue
                alpha = round(255 * total / (samples * samples))
                gradient = min(1.0, max(0.0, y / max(1, size - 1)))
                face_rgb = tuple(round(fill_rgb[i] * (1 - gradient) + bottom_rgb[i] * gradient) for i in range(3))
                rgb = tuple(round((face_rgb[i] * fill_count + edge_rgb[i] * edge_count) / total) for i in range(3))
                raw.extend((*rgb, alpha))

        def chunk(kind: bytes, data: bytes) -> bytes:
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

        png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">2I5B", size, size, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
        image = tk.PhotoImage(data=base64.b64encode(png))
        self._rounded_button_images.append(image)
        return image

    def _configure_rounded_button_styles(self, style):
        palettes = {
            "TButton": (COLORS["panel_alt"], COLORS["border"], COLORS["border"], COLORS["panel"]),
            "Accent.TButton": ("#FFE19E", "#FFF0CA", COLORS["cyan_bright"], COLORS["border"]),
            "Secondary.TButton": (COLORS["panel_alt"], COLORS["border"], COLORS["cyan"], COLORS["panel"]),
            "Pressed.TButton": (COLORS["cyan"], COLORS["cyan_bright"], COLORS["cyan_bright"], COLORS["panel"]),
            "Pressed.Accent.TButton": ("#FFEFB7", "#FFF6D8", COLORS["cyan"], COLORS["border"]),
            "Pressed.Secondary.TButton": (COLORS["cyan"], COLORS["cyan_bright"], COLORS["cyan_bright"], COLORS["panel"]),
        }
        inner = [("Button.padding", {"sticky": "nswe", "children": [("Button.label", {"sticky": "nswe"})]})]
        for button_style, (normal, active, pressed, disabled) in palettes.items():
            element = "IndoSubMod." + button_style.replace(".", "_") + ".border"
            image = self._make_rounded_button_image(normal, COLORS["border"], "#E48B2D" if "Accent" in button_style else None)
            active_image = self._make_rounded_button_image(active, COLORS["cyan"] if "Accent" not in button_style else "#F8A33B", "#F8A33B" if "Accent" in button_style else None)
            pressed_image = self._make_rounded_button_image(pressed, COLORS["cyan_bright"])
            disabled_image = self._make_rounded_button_image(disabled, COLORS["border"])
            style.element_create(element, "image", image, ("disabled", disabled_image), ("pressed", pressed_image), ("active", active_image), border=12, sticky="nsew")
            style.layout(button_style, [(element, {"sticky": "nswe", "children": inner})])

    def _configure_button_animations(self):
        self.bind_all("<ButtonPress-1>", self._animate_button_press, add="+")

    def _animate_button_press(self, event):
        button = event.widget
        if not isinstance(button, ttk.Button) or button.instate(["disabled"]):
            return
        original_style = self._button_original_styles.get(button, button.cget("style") or "TButton")
        pressed_style = "Pressed." + original_style
        try:
            pending = self._button_animation_jobs.pop(button, None)
            if pending:
                self.after_cancel(pending)
            self._button_original_styles[button] = original_style
            button.configure(style=pressed_style)

            def restore():
                self._button_animation_jobs.pop(button, None)
                self._button_original_styles.pop(button, None)
                try:
                    if button.winfo_exists():
                        button.configure(style=original_style)
                except tk.TclError:
                    pass

            self._button_animation_jobs[button] = self.after(130, restore)
        except tk.TclError:
            pass

    def _load_saved_api_key(self):
        if not self.api_key.get():
            saved = get_saved_api_key()
            if saved:
                self.api_key.set(saved)

    def _build(self):
        self.hero_canvas = tk.Canvas(self, height=150, background=COLORS["panel"], highlightthickness=1, highlightbackground=COLORS["cyan"])
        self.hero_canvas.pack(fill="x", padx=18, pady=(12, 6))
        self._draw_hero(self.hero_canvas, "Indonesian video subtitles", "Subtitle video Bahasa Indonesia", "Speech → English → Indonesian. (Ucapan → Inggris → Indonesia.)", use_brand_logo=True)

        mode_card = self._make_card()
        mode_card.pack(fill="x", padx=18, pady=3)
        row = ttk.Frame(mode_card)
        row.pack(fill="x", padx=10, pady=(8, 4))
        ttk.Label(row, text=bi("Способ перевода на индонезийский:", "Metode terjemahan ke bahasa Indonesia:"), style="Card.TLabel").pack(side="left")
        mode_values = tuple(MODE_LABELS[mode] for mode in ((ARGOS_MODE, OLLAMA_MODE, GPT_MODE) if self.offline_available else (OLLAMA_MODE, GPT_MODE)))
        self.mode_box = ttk.Combobox(row, textvariable=self.translation_mode, values=mode_values, state="readonly", width=32)
        self.mode_box.pack(side="left", padx=8)
        self.mode_box.bind("<<ComboboxSelected>>", self._mode_changed)
        mode_note = bi("Офлайн (Argos) · Своя локальная модель (Ollama) · GPT онлайн", "Luring (Argos) · Model lokal Anda (Ollama) · GPT daring")
        ttk.Label(mode_card, text=mode_note, style="Gold.TLabel", font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(0, 8))

        self.key_row = self._make_card()
        ttk.Label(self.key_row, text=bi("Ключ OpenAI API:", "Kunci OpenAI API:"), style="Card.TLabel").pack(side="left", padx=(10, 0))
        self.key_entry = ttk.Entry(self.key_row, textvariable=self.api_key, show="•")
        self.key_entry.pack(side="left", fill="x", expand=True, padx=8)
        enable_clipboard_controls(self.key_entry)
        ttk.Checkbutton(self.key_row, text=bi("Запомнить в Windows", "Simpan di Windows"), variable=self.save_key).pack(side="left")
        ttk.Button(self.key_row, text=bi("Получить ключ", "Dapatkan kunci"), command=lambda: webbrowser.open("https://platform.openai.com/api-keys")).pack(side="left", padx=(6, 0))
        self.key_note = ttk.Label(self, text=bi("Текст речи отправляется OpenAI; оплата API отдельная.", "Teks ucapan dikirim ke OpenAI; biaya API ditagihkan terpisah."), style="RootMuted.TLabel", wraplength=950)

        self.ollama_row = self._make_card()
        ttk.Label(self.ollama_row, text=bi("Локальная модель Ollama:", "Model lokal Ollama:"), style="Card.TLabel").pack(side="left", padx=(10, 0))
        self.ollama_model_box = ttk.Combobox(self.ollama_row, textvariable=self.ollama_model, state="normal", width=32)
        self.ollama_model_box.pack(side="left", fill="x", expand=True, padx=8)
        enable_clipboard_controls(self.ollama_model_box)
        ttk.Button(self.ollama_row, text=bi("Найти модели", "Cari model"), command=self._refresh_ollama_models).pack(side="left", padx=(0, 8))
        self.ollama_note = ttk.Label(self, text=bi("Работает локально на этом компьютере. Интернет и облачный API не используются; сначала запустите Ollama и загрузите модель.", "Berjalan secara lokal di komputer ini. Tidak memakai internet atau API cloud; jalankan Ollama dan unduh model terlebih dahulu."), style="RootMuted.TLabel", wraplength=990)

        self._video_row = self._make_card()
        self._video_row.pack(fill="x", padx=18, pady=3)
        video_row = ttk.Frame(self._video_row)
        video_row.pack(fill="x", padx=8, pady=6)
        ttk.Label(video_row, text=bi("Видео:", "Video:"), style="Card.TLabel").pack(side="left", padx=(0, 10))
        self.video_entry = ttk.Entry(video_row, textvariable=self.path)
        self.video_entry.pack(side="left", fill="x", expand=True)
        enable_clipboard_controls(self.video_entry)
        ttk.Button(video_row, text=bi("Выбрать видео", "Pilih video"), command=self._choose, style="Accent.TButton").pack(side="left", padx=(8, 0))
        ttk.Label(self._video_row, text=bi("Поддерживаемые форматы: MP4, MKV, MOV, AVI, WebM, M4V, MPEG, MPG, WMV, TS.", "Format yang didukung: MP4, MKV, MOV, AVI, WebM, M4V, MPEG, MPG, WMV, TS."), style="Muted.TLabel", wraplength=990).pack(anchor="w", padx=12, pady=(0, 8))

        style_card = self._make_card()
        style_card.pack(fill="x", padx=18, pady=3)
        row = ttk.Frame(style_card)
        row.pack(fill="x", padx=10, pady=(8, 3))
        ttk.Label(row, text=bi("Стиль индонезийского:", "Gaya bahasa Indonesia:"), style="Card.TLabel").pack(side="left")
        ttk.Combobox(row, textvariable=self.register, values=(REGISTER_AUTO, REGISTER_FORMAL, REGISTER_FRIENDLY), state="readonly", width=24).pack(side="left", padx=8)
        ttk.Label(row, text=bi("Автоматический режим выбирает официальный или дружеский тон.", "Mode otomatis memilih ragam resmi atau akrab."), style="Muted.TLabel", wraplength=500).pack(side="left", fill="x", expand=True)
        ttk.Label(style_card, text="Automatic (Otomatis) · Formal (Resmi) · Friendly (Akrab)", style="Gold.TLabel", font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(0, 8))

        action_card = self._make_card()
        action_card.pack(fill="x", padx=18, pady=3)
        ttk.Label(action_card, text=bi("Исходное видео не меняется: создаётся отдельный MKV с дорожкой субтитров, без перекодирования видео и звука. Прототип предназначен только для тестирования и некоммерческого использования; права на видео остаются у правообладателей.", "Video sumber tetap utuh: aplikasi membuat file MKV terpisah dengan trek subtitle tanpa mengodekan ulang video atau audio. Prototipe ini hanya untuk pengujian dan penggunaan nonkomersial; hak atas video tetap berada pada pemegang hak."), style="Muted.TLabel", wraplength=990).pack(anchor="w", padx=12, pady=(9, 5))
        action_row = ttk.Frame(action_card)
        action_row.pack(fill="x", padx=8, pady=(0, 8))
        self.start_button = ttk.Button(action_row, text=bi("Создать видео с субтитрами", "Buat video dengan subtitle"), command=self._start, style="Accent.TButton")
        self.start_button.pack(side="left", padx=4)
        self.feedback_button = ttk.Button(action_row, text=bi("Оценить перевод", "Nilai terjemahan"), command=self._open_feedback, state="disabled")
        self.feedback_button.pack(side="left", padx=4)
        self.subtitle_settings_button = ttk.Button(action_row, text=bi("Настройки субтитров", "Pengaturan subtitle"), command=self._open_subtitle_settings)
        self.subtitle_settings_button.pack(side="left", padx=4)
        self.support_button = ttk.Button(action_row, text=bi("Поддержать автора", "Dukung kreator"), command=lambda: webbrowser.open("https://buymeacoffee.com/ailautanmod"), style="Accent.TButton")
        self.support_button.pack(side="left", padx=4)

        status_card = self._make_card()
        status_card.pack(fill="both", expand=True, padx=18, pady=(3, 8))
        self.progress = tk.Canvas(status_card, height=22, background=COLORS["panel"], highlightthickness=0, bd=0)
        self.progress.pack(fill="x", padx=10, pady=(8, 3))
        self.progress.bind("<Configure>", lambda _event: self._draw_processing_progress())
        self.status = tk.StringVar(value=bi("Готово к работе", "Siap digunakan"))
        ttk.Label(status_card, textvariable=self.status, style="Status.TLabel", wraplength=980).pack(anchor="w", padx=12, pady=5)
        ttk.Label(status_card, text=bi("Журнал обработки", "Log pemrosesan"), style="Card.TLabel").pack(anchor="w", padx=12, pady=(5, 2))
        self.log = tk.Text(status_card, height=4, wrap="word", state="disabled", font=("Segoe UI", 9), background=COLORS["background"], foreground=COLORS["silver"], insertbackground=COLORS["cyan"], selectbackground=COLORS["cyan"], selectforeground=COLORS["ink"], relief="flat", padx=8, pady=6, highlightthickness=1, highlightbackground=COLORS["border"], highlightcolor=COLORS["cyan"])
        self.log.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self._mode_changed()

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds = max(0, int(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}" if hours else f"{minutes:02}:{seconds:02}"

    def _draw_processing_progress(self):
        if not hasattr(self, "progress") or not self.progress.winfo_exists():
            return
        width = max(2, self.progress.winfo_width())
        height = max(10, self.progress.winfo_height())
        self.progress.delete("all")
        self.progress.create_rectangle(2, 2, width - 2, height - 2, outline=COLORS["cyan"], width=1.5, fill=COLORS["background"])
        inner_left, inner_right = 5, width - 5
        usable = max(1, inner_right - inner_left)
        completed = int(usable * min(100.0, max(0.0, self.progress_percent)) / 100.0)
        if completed > 0:
            self.progress.create_rectangle(inner_left, 6, inner_left + completed, height - 6, outline="", fill=COLORS["cyan"])
    def _set_processing_progress(self, percent: float, stage: str, busy: bool = False):
        self.progress_target = max(self.progress_target, min(99.0, max(0.0, percent)))
        self.progress_reported_value = self.progress_target
        self.progress_reported_at = time.monotonic()
        self.progress_stage = stage
        self._update_processing_status()

    def _advance_processing_progress(self):
        if not self.running or not self.processing_started:
            return
        elapsed = max(0.0, time.monotonic() - self.processing_started)
        time_estimate = 99.5 * (1.0 - math.exp(-elapsed / 300.0))
        since_report = max(0.0, time.monotonic() - self.progress_reported_at) if self.progress_reported_at else 0.0
        phase_estimate = self.progress_reported_value + since_report * 0.35
        goal = min(99.5, max(self.progress_target, time_estimate, phase_estimate))
        gap = goal - self.progress_percent
        if gap > 0:
            self.progress_percent = min(goal, self.progress_percent + min(0.75, max(0.015, gap * 0.08)))
        self._draw_processing_progress()
        self._update_processing_status()

    def _update_processing_status(self):
        elapsed = max(0.0, time.monotonic() - self.processing_started) if self.processing_started else 0.0
        if self.progress_percent >= 8 and self.progress_percent < 100:
            eta = elapsed * (100.0 - self.progress_percent) / self.progress_percent
            remain_en = "about " + self._format_duration(eta)
            remain_id = "sekitar " + self._format_duration(eta)
        else:
            remain_en = "estimate available after the first stages"
            remain_id = "perkiraan muncul setelah tahap awal"
        detail = f"Processing progress (estimated): {self.progress_percent:.1f}% • elapsed: {self._format_duration(elapsed)} • remaining: {remain_en}\nProgres pemrosesan (perkiraan): {self.progress_percent:.1f}% • waktu: {self._format_duration(elapsed)} • tersisa: {remain_id}"
        self.status.set(f"{self.progress_stage}\n{detail}")

    def _make_card(self, parent=None):
        return tk.Frame(parent or self, background=COLORS["panel"], highlightthickness=1, highlightbackground=COLORS["border"], highlightcolor=COLORS["cyan"], padx=2, pady=2)

    def _draw_hero(self, canvas, title, translation, subtitle, use_brand_logo=False):
        banner_path = application_banner()
        try:
            canvas._banner_image = tk.PhotoImage(file=str(banner_path)).subsample(2, 2)
            canvas.create_image(0, 0, image=canvas._banner_image, anchor="nw")
        except (tk.TclError, OSError):
            canvas._banner_image = None
            canvas.configure(background=COLORS["panel"])
        canvas.create_rectangle(0, 0, 490, 150, fill=COLORS["background"], stipple="gray50", outline="")
        canvas.create_text(24, 34, text="IndoSubMod", anchor="w", fill="#F3F7FC", font=("Segoe UI", 28, "bold"))
        canvas.create_text(26, 70, text=title, anchor="w", fill=COLORS["gold"], font=("Segoe UI", 13, "bold"))
        canvas.create_text(26, 94, text=f"({translation})", anchor="w", fill=COLORS["silver"], font=("Segoe UI", 11))
        canvas.create_text(26, 124, text=subtitle, anchor="w", fill="#B8C9DC", font=("Segoe UI", 9))
        try:
            logo_path = application_brand_logo() if use_brand_logo else application_logo()
            canvas._logo_image = tk.PhotoImage(file=str(logo_path)) if use_brand_logo else tk.PhotoImage(file=str(logo_path)).subsample(8, 8)
            canvas.create_image(830, 74, image=canvas._logo_image, anchor="center")
        except (tk.TclError, OSError):
            canvas._logo_image = None

    def _mode_changed(self, _event=None):
        mode = MODE_INTERNAL_BY_LABEL.get(self.translation_mode.get(), self.translation_mode.get())
        if mode == GPT_MODE:
            self.key_row.pack(fill="x", padx=18, pady=5, before=self._video_row)
            self.key_note.pack(anchor="w", padx=18, pady=(0, 4), before=self._video_row)
        else:
            self.key_row.pack_forget()
            self.key_note.pack_forget()
        if mode == OLLAMA_MODE:
            self.ollama_row.pack(fill="x", padx=18, pady=5, before=self._video_row)
            self.ollama_note.pack(anchor="w", padx=18, pady=(0, 4), before=self._video_row)
        else:
            self.ollama_row.pack_forget()
            self.ollama_note.pack_forget()

    def _refresh_ollama_models(self):
        try:
            models = list_ollama_models()
            self.ollama_model_box.configure(values=models)
            if len(models) == 1:
                self.ollama_model.set(models[0])
            elif self.ollama_model.get() not in models and models:
                self.ollama_model.set(models[0])
            messagebox.showinfo(bi("Локальные модели", "Model lokal"), bi("Found models: " + str(len(models)), "Jumlah model ditemukan: " + str(len(models))))
        except Exception as exc:
            messagebox.showerror(bi("Ollama недоступна", "Ollama tidak tersedia"), bi(str(exc), str(exc)))

    def _choose(self):
        selected = filedialog.askopenfilename(title="Choose a video (Pilih video)", filetypes=VIDEO_TYPES)
        if selected:
            self.path.set(selected)

    def _start(self):
        video = Path(self.path.get().strip().strip('"'))
        if not video.is_file():
            messagebox.showerror(bi("Видео не выбрано", "Video belum dipilih"), bi("Выберите существующий видеофайл.", "Pilih file video yang tersedia."))
            return
        mode = MODE_INTERNAL_BY_LABEL.get(self.translation_mode.get(), self.translation_mode.get())
        api_key = self.api_key.get().strip()
        if mode == GPT_MODE and not api_key:
            messagebox.showerror(bi("Нужен ключ OpenAI API", "Kunci OpenAI API diperlukan"), bi("Введите ключ для режима GPT онлайн.", "Masukkan kunci untuk mode GPT daring."))
            return
        ollama_model = self.ollama_model.get().strip()
        if mode == OLLAMA_MODE and not ollama_model:
            messagebox.showerror(bi("Выберите локальную модель", "Pilih model lokal"), bi("Нажмите «Найти модели» и выберите установленную модель Ollama.", "Klik «Cari model» dan pilih model Ollama yang sudah terpasang."))
            return
        output_name = video.stem + ".id.mkv"
        selected_output = filedialog.asksaveasfilename(
            title=bi("Куда сохранить видео с субтитрами?", "Simpan video bersubtitle di mana?"),
            initialdir=str(video.parent),
            initialfile=output_name,
            defaultextension=".mkv",
            filetypes=[("Subtitled Matroska video (Video Matroska bersubtitel)", "*.mkv")],
        )
        if not selected_output:
            return
        output_video = Path(selected_output)
        if output_video.suffix.lower() != ".mkv":
            output_video = output_video.with_suffix(".mkv")
        try:
            if output_video.resolve() == video.resolve():
                messagebox.showerror(bi("Выберите другое имя", "Pilih nama file lain"), bi("Итоговый файл не может заменить исходное видео.", "File hasil tidak boleh menggantikan video sumber."))
                return
        except OSError:
            pass
        if mode == GPT_MODE and self.save_key.get():
            try:
                import keyring
                keyring.set_password(API_SERVICE, API_USER, api_key)
            except Exception as exc:
                messagebox.showerror(bi("Не удалось сохранить ключ", "Kunci gagal disimpan"), f"Windows credential storage is unavailable: {exc}\n(Penyimpanan kredensial Windows tidak tersedia: {exc})\n" + bi("Снимите отметку или выберите офлайн-режим.", "Hapus centang atau pilih mode luring."))
                return
        self.running = True
        self.start_button.configure(state="disabled")
        self.processing_started = time.monotonic()
        self.progress_percent = 0.0
        self.progress_target = 0.0
        self.progress_reported_value = 0.0
        self.progress_reported_at = self.processing_started
        self._set_processing_progress(1, bi("Подготовка обработки", "Menyiapkan pemrosesan"), True)
        self.status.set(bi("Обработка видео", "Memproses video"))
        worker = threading.Thread(target=self._process, args=(video, output_video, self.register.get(), mode, api_key, ollama_model), daemon=True)
        try:
            worker.start()
        except RuntimeError as exc:
            self.running = False
            self.start_button.configure(state="normal")
            self.status.set(bi("Не удалось запустить обработку", "Pemrosesan gagal dimulai"))
            messagebox.showerror(bi("Не удалось начать обработку", "Pemrosesan gagal dimulai"), str(exc))

    def _process(self, video: Path, output_video: Path, register: str, mode: str, api_key: str, ollama_model: str = ""):
        try:
            self.events.put(("log", f"Video: {video}\n(Video: {video})"))
            self.events.put(("progress", 2, bi("Подготовка и загрузка модели Whisper", "Menyiapkan dan memuat model Whisper"), True))
            from faster_whisper import WhisperModel

            translator = None
            if mode == ARGOS_MODE:
                self.events.put(("log", bi("Загружаю офлайн-модель перевода en → id", "Memuat model terjemahan luring en → id")))
                translator = load_offline_translator()
            elif mode == OLLAMA_MODE:
                self.events.put(("log", f"Translation uses the local Ollama model: {ollama_model}.\n(Terjemahan menggunakan model Ollama lokal: {ollama_model}.)"))
            model = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=min(8, max(1, os.cpu_count() or 4)))
            self.events.put(("log", bi("Распознаю речь и перевожу её на английский", "Mengenali ucapan dan menerjemahkannya ke bahasa Inggris")))
            self.events.put(("progress", 4, bi("Распознавание речи", "Mengenali ucapan"), True))
            segments, info = model.transcribe(str(video), task="translate", beam_size=5, vad_filter=True)
            output = output_video.with_suffix(".srt")
            recognized = []
            duration = float(getattr(info, "duration", 0) or 0)
            last_whisper_percent = -1
            for segment in segments:
                text = segment.text.strip()
                if text:
                    recognized.append((segment.start, segment.end, text))
                if duration > 0:
                    pct = 4.0 + 61.0 * min(1.0, max(0.0, float(segment.end) / duration))
                    if int(pct) > last_whisper_percent:
                        last_whisper_percent = int(pct)
                        self.events.put(("progress", pct, bi("Распознавание и перевод речи на английский", "Mengenali ucapan dan menerjemahkannya ke bahasa Inggris"), True))
            if not recognized:
                raise RuntimeError(bi("Speech could not be recognized in the video.", "Ucapan tidak dapat dikenali dalam video."))

            count = 0
            records: list[dict] = []
            examples = load_feedback()
            temporary_subtitle = output.with_name(output.stem + ".partial.srt")
            try:
                with temporary_subtitle.open("w", encoding="utf-8-sig", newline="\n") as stream:
                    for offset in range(0, len(recognized), 20):
                        batch = recognized[offset:offset + 20]
                        completed = offset + len(batch)
                        pct = 65.0 + 27.0 * completed / len(recognized)
                        stage = f"Translating into Indonesian: {completed}/{len(recognized)} segments\nMenerjemahkan ke bahasa Indonesia: {completed}/{len(recognized)} segmen"
                        english_batch = [item[2] for item in batch]
                        missing = [i for i, source in enumerate(english_batch) if find_learned_translation(source, examples, register) is None]
                        newly_translated: dict[int, str] = {}
                        if missing and mode == GPT_MODE:
                            translated = translate_with_gpt(api_key, [english_batch[i] for i in missing], register, examples)
                            newly_translated.update(zip(missing, translated))
                        elif missing and mode == OLLAMA_MODE:
                            translated = translate_with_ollama(ollama_model, [english_batch[i] for i in missing], register, examples)
                            newly_translated.update(zip(missing, translated))
                        elif missing:
                            for i in missing:
                                candidate = apply_register(english_batch[i], translator.translate(english_batch[i]), register)
                                newly_translated[i] = REVIEW_PLACEHOLDER if is_rejected_translation(english_batch[i], candidate, examples, register) else candidate
                        if mode in (GPT_MODE, OLLAMA_MODE):
                            for i, candidate in newly_translated.items():
                                if is_rejected_translation(english_batch[i], candidate, examples, register):
                                    newly_translated[i] = REVIEW_PLACEHOLDER
                        translations = [find_learned_translation(source, examples, register) or newly_translated[i] for i, source in enumerate(english_batch)]
                        for (start, end, _english), translated in zip(batch, translations):
                            count += 1
                            records.append({"start": start, "end": end, "english": _english, "indonesian": translated})
                            stream.write(f"{count}\n{timestamp(start)} --> {timestamp(end)}\n{translated}\n\n")
                        self.events.put(("progress", pct, stage, False))
                self.events.put(("log", bi("Встраиваю индонезийские субтитры в видео без перекодирования", "Menyematkan subtitle bahasa Indonesia tanpa mengodekan ulang video")))
                self.events.put(("progress", 92, bi("Добавление субтитров в видео", "Menambahkan subtitle ke video"), True))
                def report_mux(fraction: float):
                    self.events.put(("progress", 92.0 + 7.0 * fraction, bi("Добавление субтитров в видео", "Menambahkan subtitle ke video"), True))
                mux_subtitles(video, temporary_subtitle, output_video, report_mux, duration)
                os.replace(temporary_subtitle, output)
            finally:
                temporary_subtitle.unlink(missing_ok=True)
            provider_en = "Argos offline model" if mode == ARGOS_MODE else (f"local Ollama model: {ollama_model}" if mode == OLLAMA_MODE else "GPT online")
            provider_id = "model Argos luring" if mode == ARGOS_MODE else (f"model Ollama lokal: {ollama_model}" if mode == OLLAMA_MODE else "GPT daring")
            message = f"Done (Selesai): {output_video}\nSubtitle file (File subtitle): {output}\nSource language (Bahasa sumber): {info.language} ({info.language_probability:.0%}). Translation flow (Alur terjemahan): source language → English → Indonesian ({provider_en}; {provider_id}). The MKV has subtitles with a translucent gray background. (MKV berisi subtitle dengan latar abu-abu transparan.) The separate SRT is plain text. (File SRT terpisah berupa teks biasa.) Segments (Jumlah segmen): {count}."
            self.events.put(("done", message, (output, output_video, records, register)))
        except Exception as exc:
            self.events.put(("error", bi(f"{type(exc).__name__}: {exc}", f"{type(exc).__name__}: {exc}")))
        finally:
            self.events.put(("worker_exit",))

    def _poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                message = event[1] if len(event) > 1 else ""
                if kind == "log":
                    self.log.configure(state="normal")
                    self.log.insert("end", message + "\n")
                    self.log.see("end")
                    self.log.configure(state="disabled")
                elif kind == "progress":
                    self._set_processing_progress(event[1], event[2], event[3])
                elif kind == "status":
                    self.status.set(message)
                elif kind == "feedback_done":
                    self.status.set(message)
                elif kind == "feedback_error":
                    self.status.set(bi("Не удалось обновить дорожку субтитров в MKV.", "Trek subtitle MKV gagal diperbarui."))
                    messagebox.showerror(bi("Видео не обновлено", "Video gagal diperbarui"), message)
                elif kind == "worker_exit":
                    if self.running:
                        self.running = False
                        self.start_button.configure(state="normal")
                        self.status.set(bi("Обработка остановилась; можно повторить запуск.", "Pemrosesan berhenti; Anda dapat mencoba lagi."))
                        messagebox.showerror(bi("Обработка прервана", "Pemrosesan terhenti"), bi("Рабочий поток завершился без результата. Можно выбрать видео и повторить попытку.", "Proses kerja berhenti tanpa hasil. Pilih video dan coba lagi."))
                else:
                    self.running = False
                    if kind == "done":
                        self.progress_percent = 100.0
                        self._draw_processing_progress()
                    else:
                        self._draw_processing_progress()
                    self.start_button.configure(state="normal")
                    self.status.set(message)
                    if kind == "error":
                        messagebox.showerror(bi("Не удалось создать субтитры", "Subtitle gagal dibuat"), message)
                    else:
                        if len(event) > 2:
                            self.current_output, self.current_video, self.current_records, self.current_register = event[2]
                            self.feedback_button.configure(state="normal")
                        messagebox.showinfo(bi("Субтитры готовы", "Subtitle selesai"), message)
        except queue.Empty:
            pass
        if self.running:
            self._advance_processing_progress()
        self.after(150, self._poll)

    def _open_subtitle_settings(self):
        settings = load_subtitle_settings()
        window = tk.Toplevel(self)
        window.title(bi("Настройка субтитров", "Pengaturan subtitle"))
        window.transient(self)
        window.configure(background=COLORS["background"])
        window.resizable(False, False)
        window.geometry("640x840")
        window.minsize(640, 840)
        window.maxsize(640, 840)
        window.grab_set()
        ttk.Label(window, text=bi("Внешний вид субтитров", "Tampilan subtitle"), style="Hero.TLabel").pack(anchor="w", padx=22, pady=(18, 3))
        ttk.Label(window, text=bi("Изменения применятся к следующему созданному или обновлённому видео.", "Perubahan berlaku pada video yang dibuat atau diperbarui berikutnya."), style="Muted.TLabel", wraplength=580).pack(anchor="w", padx=22, pady=(0, 12))

        card = self._make_card(window)
        card.pack(fill="x", padx=18, pady=6)
        font_name = tk.StringVar(value=settings["font_name"])
        font_size = tk.IntVar(value=settings["font_size"])
        background_enabled = tk.BooleanVar(value=settings["background_enabled"])
        opacity = tk.IntVar(value=settings["background_opacity"])
        wrap_width = tk.IntVar(value=settings["max_chars_per_line"])

        font_row = ttk.Frame(card)
        font_row.pack(fill="x", padx=12, pady=(12, 8))
        ttk.Label(font_row, text=bi("Шрифт", "Font"), style="Card.TLabel").pack(anchor="w", pady=(0, 4))
        font_box = ttk.Combobox(font_row, textvariable=font_name, values=("Arial", "Segoe UI", "Tahoma", "Verdana"), state="readonly", width=18)
        font_box.pack(fill="x")

        size_row = ttk.Frame(card)
        size_row.pack(fill="x", padx=12, pady=8)
        ttk.Label(size_row, text=bi("Размер текста", "Ukuran teks"), style="Card.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Spinbox(size_row, from_=24, to=80, textvariable=font_size).pack(fill="x")

        wrap_row = ttk.Frame(card)
        wrap_row.pack(fill="x", padx=12, pady=8)
        ttk.Label(wrap_row, text=bi("Символов в строке до переноса", "Karakter per baris sebelum dilipat"), style="Card.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Spinbox(wrap_row, from_=24, to=72, textvariable=wrap_width).pack(fill="x")

        background_checkbox = ttk.Checkbutton(card, text=bi("Без серого фона", "Tanpa latar abu-abu"), variable=background_enabled)
        background_checkbox.pack(anchor="w", padx=12, pady=(8, 4))
        opacity_label = ttk.Label(card, text=bi("Непрозрачность серого фона", "Opasitas latar abu-abu"), style="Card.TLabel")
        opacity_label.pack(anchor="w", padx=12, pady=(6, 0))
        opacity_scale = tk.Scale(card, from_=10, to=90, orient="horizontal", variable=opacity, showvalue=True, resolution=5, background=COLORS["panel"], foreground=COLORS["silver"], troughcolor=COLORS["background"], activebackground=COLORS["cyan"], highlightthickness=0, bd=0, sliderlength=28, repeatdelay=300, repeatinterval=50)
        opacity_scale.pack(fill="x", padx=12, pady=(0, 10))

        preview = tk.Frame(window, background=COLORS["panel"], highlightthickness=1, highlightbackground=COLORS["border"], padx=18, pady=12)
        preview.pack(fill="x", padx=18, pady=8)
        preview_text = tk.Label(preview, text="Centered subtitle preview\nwith a gray background\n(Pratinjau subtitle dengan latar abu-abu)", background="#404040", foreground="#FFFFFF", font=(font_name.get(), min(28, font_size.get())), justify="center", padx=14, pady=7)
        preview_text.pack(anchor="center")

        def refresh_preview(*_args):
            try:
                preview_text.configure(font=(font_name.get(), min(28, max(12, int(font_size.get())))))
                opacity_value = min(90, max(10, int(opacity.get()))) / 100
                base = (13, 25, 36)
                gray = tuple(round(channel * opacity_value + background * (1 - opacity_value)) for channel, background in zip((64, 64, 64), base))
                preview_text.configure(background="#%02x%02x%02x" % gray if background_enabled.get() else COLORS["panel"])
            except (tk.TclError, ValueError):
                pass

        font_name.trace_add("write", refresh_preview)
        font_size.trace_add("write", refresh_preview)
        opacity.trace_add("write", refresh_preview)
        background_enabled.trace_add("write", refresh_preview)

        def update_background_controls():
            state = "normal" if background_enabled.get() else "disabled"
            opacity_scale.configure(state=state)
            opacity_label.configure(state=state)
            refresh_preview()

        background_checkbox.configure(command=update_background_controls)
        update_background_controls()
        buttons = ttk.Frame(window)
        buttons.pack(fill="x", padx=18, pady=(8, 18))

        def save():
            try:
                values = {
                    "font_name": font_name.get(),
                    "font_size": min(80, max(24, int(font_size.get()))),
                    "background_enabled": background_enabled.get(),
                    "background_opacity": min(90, max(10, int(opacity.get()))),
                    "max_chars_per_line": min(72, max(24, int(wrap_width.get()))),
                }
                save_subtitle_settings(values)
            except (OSError, ValueError, tk.TclError) as exc:
                messagebox.showerror(bi("Не удалось сохранить настройки", "Pengaturan gagal disimpan"), str(exc), parent=window)
                return
            window.destroy()

        ttk.Button(buttons, text=bi("Отмена", "Batal"), command=window.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text=bi("Сохранить", "Simpan"), command=save, style="Accent.TButton").pack(side="right")

    def _open_feedback(self):
        if not self.current_records or not self.current_output:
            return
        window = tk.Toplevel(self)
        window.title(f"IndoSubMod {APP_VERSION} — Feedback (Masukan)")
        icon = application_icon()
        if icon.is_file():
            try:
                window.iconbitmap(default=str(icon))
            except tk.TclError:
                pass
        window.geometry("1000x760")
        window.minsize(860, 620)
        window.configure(background=COLORS["background"])
        hero = tk.Canvas(window, height=180, background=COLORS["panel"], highlightthickness=1, highlightbackground=COLORS["gold"])
        hero.pack(fill="x", padx=14, pady=(14, 7))
        self._draw_hero(hero, "Review and correct translations", "Tinjau dan koreksi terjemahan", "Your feedback helps prevent repeated mistakes. (Masukan Anda membantu mencegah kesalahan berulang.)")
        ttk.Label(window, text=bi("Одобренные переводы и исправления сохраняются на этом компьютере.", "Terjemahan yang disetujui dan koreksi disimpan di komputer ini."), style="Muted.TLabel", wraplength=950).pack(anchor="w", padx=18, pady=5)
        table_card = self._make_card(window)
        table_card.pack(fill="both", expand=True, padx=14, pady=5)
        columns = ("n", "english", "indonesian")
        tree = ttk.Treeview(table_card, columns=columns, show="headings", selectmode="browse")
        tree.heading("n", text="#")
        tree.heading("english", text="English (Inggris)")
        tree.heading("indonesian", text="Indonesian (Bahasa Indonesia)")
        tree.column("n", width=45, stretch=False)
        tree.column("english", width=380)
        tree.column("indonesian", width=420)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        ids = []
        for index, record in enumerate(self.current_records):
            ids.append(tree.insert("", "end", values=(index + 1, record["english"], record["indonesian"])))
        edit_card = self._make_card(window)
        edit_card.pack(fill="x", padx=14, pady=5)
        ttk.Label(edit_card, text=bi("Исправленный или подтверждённый вариант:", "Versi yang dikoreksi atau disetujui:"), style="Card.TLabel").pack(anchor="w", padx=10, pady=(8, 2))
        edited = tk.Text(edit_card, height=3, wrap="word", font=("Segoe UI", 10), background=COLORS["background"], foreground=COLORS["silver"], insertbackground=COLORS["cyan"], selectbackground=COLORS["cyan"], selectforeground=COLORS["ink"], relief="flat", padx=10, pady=8, highlightthickness=1, highlightbackground=COLORS["border"], highlightcolor=COLORS["cyan"])
        edited.pack(fill="x", padx=10, pady=(0, 8))
        enable_clipboard_controls(edited)
        selected_index = {"value": None}

        def select_row(_event=None):
            selection = tree.selection()
            if not selection:
                selected_index["value"] = None
                return
            index = ids.index(selection[0])
            selected_index["value"] = index
            edited.delete("1.0", "end")
            edited.insert("1.0", self.current_records[index]["indonesian"])

        tree.bind("<<TreeviewSelect>>", select_row)

        def write_current_srt():
            with self.current_output.open("w", encoding="utf-8-sig", newline="\n") as stream:
                for number, item in enumerate(self.current_records, 1):
                    stream.write(f"{number}\n{timestamp(item['start'])} --> {timestamp(item['end'])}\n{item['indonesian']}\n\n")

        def refresh_video_track():
            if not self.current_video:
                return
            video_path = self.current_video
            subtitle_path = self.current_output

            def worker():
                try:
                    mux_subtitles(video_path, subtitle_path, video_path)
                except Exception as exc:
                    self.events.put(("feedback_error", str(exc)))
                else:
                    self.events.put(("feedback_done", bi("Встроенные субтитры в видео обновлены.", "Subtitle yang disematkan di video telah diperbarui.")))

            self.status.set(bi("Обновляю субтитры в видео", "Memperbarui subtitle di video"))
            threading.Thread(target=worker, daemon=True).start()

        def save_current(corrected: bool):
            index = selected_index["value"]
            if index is None:
                messagebox.showwarning(bi("Выберите субтитр", "Pilih subtitle"), bi("Сначала выберите строку в списке.", "Pilih satu baris dari daftar terlebih dahulu."), parent=window)
                return
            record = self.current_records[index]
            value = edited.get("1.0", "end-1c").strip() if corrected else record["indonesian"].strip()
            if not value:
                messagebox.showwarning(bi("Пустой перевод", "Terjemahan kosong"), bi("Введите текст на индонезийском языке.", "Masukkan teks dalam bahasa Indonesia."), parent=window)
                return
            record["indonesian"] = value
            tree.item(ids[index], values=(index + 1, record["english"], value))
            examples = load_feedback()
            key = normalize_text(record["english"])
            examples = [item for item in examples if not (item.get("quality", "good") == "good" and " ".join(item["english"].casefold().split()) == key)]
            examples.append({"english": record["english"], "indonesian": value, "register": self.current_register, "quality": "good"})
            save_feedback(examples)
            try:
                write_current_srt()
            except OSError as exc:
                messagebox.showerror(bi("Не удалось обновить SRT", "File SRT gagal diperbarui"), str(exc), parent=window)
                return
            refresh_video_track()

        def mark_bad():
            index = selected_index["value"]
            if index is None:
                messagebox.showwarning(bi("Выберите субтитр", "Pilih subtitle"), bi("Сначала выберите строку в списке.", "Pilih satu baris dari daftar terlebih dahulu."), parent=window)
                return
            record = self.current_records[index]
            bad_value = record["indonesian"].strip()
            if not bad_value or bad_value == REVIEW_PLACEHOLDER:
                messagebox.showwarning(bi("Нет перевода для оценки", "Tidak ada terjemahan untuk dinilai"), bi("Выберите строку с переводом.", "Pilih baris yang berisi terjemahan."), parent=window)
                return
            examples = load_feedback()
            key = normalize_text(record["english"])
            bad_key = normalize_text(bad_value)
            examples = [item for item in examples if not (
                item.get("quality", "good") == "good"
                and normalize_text(item["english"]) == key
                and normalize_text(item["indonesian"]) == bad_key
            )]
            if not any(item.get("quality") == "bad" and normalize_text(item["english"]) == key and normalize_text(item["indonesian"]) == bad_key for item in examples):
                examples.append({"english": record["english"], "indonesian": bad_value, "register": self.current_register, "quality": "bad"})
            save_feedback(examples)
            record["indonesian"] = REVIEW_PLACEHOLDER
            tree.item(ids[index], values=(index + 1, record["english"], REVIEW_PLACEHOLDER))
            edited.delete("1.0", "end")
            edited.insert("1.0", REVIEW_PLACEHOLDER)
            try:
                write_current_srt()
            except OSError as exc:
                messagebox.showerror(bi("Не удалось обновить SRT", "File SRT gagal diperbarui"), str(exc), parent=window)
                return
            refresh_video_track()

        buttons = ttk.Frame(window)
        buttons.pack(anchor="e", padx=14, pady=10)
        ttk.Button(buttons, text=bi("Хороший перевод", "Terjemahan bagus"), command=lambda: save_current(False), style="Secondary.TButton").pack(side="left", padx=4)
        ttk.Button(buttons, text=bi("Плохой перевод", "Terjemahan buruk"), command=mark_bad, style="Secondary.TButton").pack(side="left", padx=4)
        ttk.Button(buttons, text=bi("Сохранить исправление", "Simpan koreksi"), command=lambda: save_current(True), style="Accent.TButton").pack(side="left", padx=4)
        ttk.Button(buttons, text=bi("Закрыть", "Tutup"), command=window.destroy, style="Secondary.TButton").pack(side="left", padx=4)


if __name__ == "__main__":
    IndoSubModApp().mainloop()

