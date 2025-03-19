#!/usr/bin/env python3
import sys
import os
import json
import time
import wave
import re
import tempfile
import threading
import logging
import io
from contextlib import contextmanager, suppress, redirect_stdout, redirect_stderr
from pathlib import Path

import pyaudio
import pygame
import openai
import whisper
from TTS.api import TTS
import torch
import enchant

from PyQt6.QtGui import QTextCursor, QFont, QColor, QTextCharFormat, QSyntaxHighlighter, QIcon
from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QPlainTextEdit, QDialog,
    QLabel, QSpinBox, QComboBox, QFormLayout, QDialogButtonBox, QMenu, QTextEdit, QColorDialog, QGroupBox, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal, pyqtSlot

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Определяем корневую директорию скрипта и пути к файлам настроек/истории
ROOT_DIR = Path(__file__).parent.resolve()
HISTORY_FILE = ROOT_DIR / "conversation_history.json"
SETTINGS_FILE = ROOT_DIR / "settings.json"
MESSAGE_COUNTER_FILE = ROOT_DIR / "message_counter.json"


def load_settings() -> dict:
    """Загружает настройки из файла или возвращает настройки по умолчанию."""
    default_settings = {
        "text_size": 14,
        "tts_model": "tts_models/multilingual/multi-dataset/xtts_v2",
        "whisper_model": "large-v3-turbo",
        "summary_interval": 10,
        "colors": {
            "text_input_bg": "#2F2F2F",
            "text_input_text": "#FFFFFF",
            "chat_bg": "#2F2F2F",
            "chat_text": "#FFFFFF",
            "system_log_bg": "#1F1F1F",
            "system_log_text": "#FFA500",
            "button_bg": "#333333",
            "button_text": "orange",
            "button_hover_color": "#444444",
            "panel_bg": "#3F3F3F",
            "window_bg": "#2F2F2F",
            "system_label_color": "#AAAAAA",
            "system_content_color": "#FFFFFF",
            "user_label_color": "#008080",
            "user_content_color": "#ADD8E6",
            "assistant_label_color": "#9B59B6",
            "assistant_content_color": "#FFA500",
            "scrollbar_handle_color": "#888888",
            "scrollbar_track_color": "#444444"
        }
    }
    if SETTINGS_FILE.exists():
        try:
            with SETTINGS_FILE.open("r", encoding="utf-8") as f:
                settings = json.load(f)
            # Обеспечиваем наличие всех ключей цветов
            settings.setdefault("colors", {})
            for key, val in default_settings["colors"].items():
                settings["colors"].setdefault(key, val)
            logging.info("Настройки успешно загружены")
            return settings
        except Exception:
            logging.exception("Ошибка загрузки настроек:")
    return default_settings


def save_settings(settings: dict) -> None:
    """Сохраняет настройки в файл."""
    try:
        with SETTINGS_FILE.open("w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        logging.info("Настройки сохранены")
    except Exception:
        logging.exception("Ошибка сохранения настроек:")


# --- Подсветчик орфографических ошибок с подчеркиванием ---
class SpellCheckHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        try:
            self.dictionary = enchant.Dict("ru_RU")
        except enchant.errors.DictNotFoundError:
            logging.error("Словарь для ru_RU не найден. Проверьте установку pyenchant и наличие соответствующего словаря.")
            self.dictionary = None
        self.error_format = QTextCharFormat()
        self.error_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
        self.error_format.setUnderlineColor(QColor("red"))

    def highlightBlock(self, text):
        if not self.dictionary:
            return
        for match in re.finditer(r'\b\w+\b', text):
            word = match.group()
            if not self.dictionary.check(word):
                self.setFormat(match.start(), match.end() - match.start(), self.error_format)


# --- QPlainTextEdit с поддержкой исправления ошибок ---
class SpellCheckTextEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighter = SpellCheckHighlighter(self.document())

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        cursor = self.cursorForPosition(event.position().toPoint())
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        word = cursor.selectedText()
        if word and self.highlighter.dictionary and not self.highlighter.dictionary.check(word):
            suggestions = self.highlighter.dictionary.suggest(word)
            if suggestions:
                menu = QMenu(self)
                for suggestion in suggestions[:5]:
                    menu.addAction(suggestion)
                action = menu.exec(event.globalPosition().toPoint())
                if action:
                    cursor.insertText(action.text())


# --- Worker для динамической озвучки ответа ассистента ---
class AssistantMessageWorker(QObject):
    appendChar = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, text: str, backend: "VoiceAssistantBackend") -> None:
        super().__init__()
        self.text = text.strip()
        self.backend = backend

    def run(self) -> None:
        self.text = re.sub(r"(?<=\d)\.(?=\d)", ",", self.text)

        # Разбиваем текст на предложения по знакам препинания
        parts = re.split(r'(?<=[.!?])\s+', self.text)
        for i, part in enumerate(parts):
            if not part:
                continue
            original_part = part
            if self.backend.stop_event.is_set():
                self.backend.tts_channel.stop()
                for ch in original_part:
                    self.appendChar.emit("&nbsp;" if ch == " " else ch)
                    time.sleep(0.005)
                for later_part in parts[i + 1:]:
                    if later_part.strip():
                        self.appendChar.emit("<br>")
                        for ch in later_part:
                            self.appendChar.emit("&nbsp;" if ch == " " else ch)
                            time.sleep(0.005)
                self.finished.emit()
                return

            # Оставляем только нужные символы, не меняя знаков препинания
            normalized_part = re.sub(r"[^a-zA-Zа-яА-ЯёЁ0-9 ,!?;:+=%'/-]", "", part).rstrip(" ,!?;:")
            if not normalized_part.strip():
                self.appendChar.emit("<br>" + original_part)
                continue

            max_words = 350
            words_norm = normalized_part.split()
            words_orig = original_part.split()
            if len(words_norm) > max_words:
                normalized_chunks = [" ".join(words_norm[j:j + max_words]) for j in range(0, len(words_norm), max_words)]
                original_chunks = [" ".join(words_orig[j:j + max_words]) for j in range(0, len(words_orig), max_words)]
            else:
                normalized_chunks = [normalized_part]
                original_chunks = [original_part]

            for norm_chunk, orig_chunk in zip(normalized_chunks, original_chunks):
                temp_wav = None
                try:
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
                        temp_wav = tmp_wav.name
                    # Перенаправляем вывод для TTS
                    with self.backend._suppress_output():
                        self.backend.tts_model.tts_to_file(
                            text=norm_chunk,
                            speaker_wav=str(ROOT_DIR / "speaker.wav"),
                            language="ru",
                            file_path=temp_wav,
                            temperature=0.85,
                            split_sentences=False
                        )
                    try:
                        sound = pygame.mixer.Sound(temp_wav)
                        duration = sound.get_length()
                        delay_per_char = duration / len(norm_chunk) if norm_chunk else duration
                        self.backend.tts_channel.play(sound)
                    except Exception:
                        logging.exception("Ошибка во время воспроизведения звука:")
                        delay_per_char = 0.04

                    for ch in orig_chunk:
                        self.appendChar.emit("&nbsp;" if ch == " " else ch)
                        time.sleep(delay_per_char)
                except Exception:
                    logging.exception("Ошибка во время синтеза TTS:")
                finally:
                    if temp_wav is not None:
                        with suppress(Exception):
                            os.remove(temp_wav)
            if i < len(parts) - 1:
                self.appendChar.emit("<br>")
        self.finished.emit()


# --- Логика голосового ассистента ---
class VoiceAssistantBackend:
    SOUND_FILES = {
        "system_ready": ROOT_DIR / "system_ready.mp3",
        "recording": ROOT_DIR / "recording.mp3",
        "stop_recording": ROOT_DIR / "stop_recording.mp3",
        "assistant_message": ROOT_DIR / "assistant_message.mp3",
        "stop_generation": ROOT_DIR / "stop_generation.mp3",
        "termination": ROOT_DIR / "termination.mp3",
        "input": ROOT_DIR / "input.mp3"
    }

    def __init__(self, settings: dict) -> None:
        self.settings = settings
        self.conversation_history = []
        self._load_history()
        self.stop_event = threading.Event()
        self.cancel_record_flag = False
        self.mouse_stop_flag = False
        self.recording_in_progress = False
        self.summary_interval = self.settings.get("summary_interval", 10)
        self.message_count = self._load_message_count()

        pygame.mixer.init()
        pygame.mixer.set_num_channels(8)
        self.tts_channel = pygame.mixer.Channel(1)
        self.audio = pyaudio.PyAudio()
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.rate = 22050
        self.chunk = 1024

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logging.info(f"Используем устройство: {self.device.upper()}")

        try:
            self.tts_model = TTS(model_name=self.settings.get("tts_model", "tts_models/multilingual/multi-dataset/xtts_v2")).to(self.device)
        except Exception:
            logging.exception("Ошибка загрузки TTS модели:")
            raise

        try:
            self.whisper_model = whisper.load_model(self.settings.get("whisper_model", "large-v3-turbo"))
        except Exception:
            logging.exception("Ошибка загрузки модели Whisper:")
            raise

        openai.api_base = "http://localhost:1234/v1"
        openai.api_key = "not-needed"
        self.input_enabled = True

    @contextmanager
    def _suppress_output(self):
        # Используем современные контекстные менеджеры для перенаправления stdout/stderr
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            yield

    def _load_history(self) -> None:
        if HISTORY_FILE.exists():
            try:
                with HISTORY_FILE.open("r", encoding="utf-8") as f:
                    self.conversation_history = json.load(f)
                logging.info("История диалога загружена")
            except Exception:
                logging.exception("Ошибка загрузки истории:")
                self.conversation_history = []
        else:
            self.conversation_history = []

    def _save_history(self) -> None:
        try:
            history_json = json.dumps(self.conversation_history, ensure_ascii=False, indent=2)
            max_size = 200 * 1024
            while len(history_json.encode('utf-8')) > max_size and self.conversation_history:
                self.conversation_history.pop(0)
                history_json = json.dumps(self.conversation_history, ensure_ascii=False, indent=2)
            with HISTORY_FILE.open("w", encoding="utf-8") as f:
                f.write(history_json)
            logging.info("История диалога сохранена")
        except Exception:
            logging.exception("Ошибка сохранения истории:")

    def _load_message_count(self) -> int:
        if MESSAGE_COUNTER_FILE.exists():
            try:
                with MESSAGE_COUNTER_FILE.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                logging.info("Счетчик сообщений загружен")
                return data.get("message_count", 0)
            except Exception:
                logging.exception("Ошибка загрузки счетчика сообщений:")
        return 0

    def _save_message_count(self) -> None:
        try:
            with MESSAGE_COUNTER_FILE.open("w", encoding="utf-8") as f:
                json.dump({"message_count": self.message_count}, f, ensure_ascii=False, indent=2)
            logging.info("Счетчик сообщений сохранен")
        except Exception:
            logging.exception("Ошибка сохранения счетчика сообщений:")

    def _play_sound(self, sound_key: str) -> None:
        sound_path = self.SOUND_FILES.get(sound_key)
        if sound_path and sound_path.exists():
            try:
                sound = pygame.mixer.Sound(str(sound_path))
                sound.play()
            except Exception:
                logging.exception(f"Ошибка воспроизведения звука {sound_path}:")
        else:
            logging.warning(f"Звуковой файл для ключа '{sound_key}' не найден.")

    def record_audio(self, filename: str = "temp_audio.wav", max_duration: int = None) -> str:
        try:
            stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk
            )
        except Exception:
            logging.exception("Ошибка открытия аудиопотока:")
            return ""

        self._play_sound("recording")
        frames = []
        self.cancel_record_flag = False
        self.mouse_stop_flag = False
        start_time = time.time()

        try:
            while (max_duration is None) or (time.time() - start_time < max_duration):
                try:
                    data = stream.read(self.chunk, exception_on_overflow=False)
                except Exception:
                    logging.exception("Ошибка чтения аудио:")
                    break
                frames.append(data)
                if self.cancel_record_flag:
                    self._play_sound("stop_generation")
                    break
                if self.mouse_stop_flag:
                    self._play_sound("stop_recording")
                    break
        finally:
            stream.stop_stream()
            stream.close()

        if self.cancel_record_flag:
            return ""
        try:
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(self.audio_format))
                wf.setframerate(self.rate)
                wf.writeframes(b''.join(frames))
            return filename
        except Exception:
            logging.exception("Ошибка записи аудиофайла:")
            return ""

    def record_voice_sample(self) -> None:
        audio_file = self.record_audio("speaker.wav")
        if audio_file:
            logging.info("Голосовой образец обновлен")
        else:
            logging.info("Запись голосового образца отменена")

    def transcribe_audio(self, filename: str) -> str:
        try:
            result = self.whisper_model.transcribe(filename, language="ru", task="transcribe")
            return result.get("text", "")
        except Exception:
            logging.exception("Ошибка транскрипции:")
            return ""

    def generate_reply(self, user_message: str) -> str:
        self.conversation_history.append({"role": "user", "content": user_message})
        self.message_count += 1
        self._save_message_count()
        self._save_history()
        try:
            response = openai.ChatCompletion.create(
                model="local-model",
                messages=self.conversation_history
            )
            reply = response.choices[0].message.content.strip() if response.choices else "Пустой ответ."
        except Exception:
            logging.exception("Ошибка генерации ответа:")
            reply = "Ошибка генерации ответа."
        self.conversation_history.append({"role": "assistant", "content": reply})
        self._save_history()

        if self.message_count >= self.summary_interval:
            self.generate_summary()
            self.message_count = 0
            self._save_message_count()
        return reply

    def generate_summary(self) -> None:
        summary_prompt = (
"Создай сжатое структурированное резюме всей ключевой информации обо мне, которое будет служить тебе в качестве долговременной памяти, следуя нижеприведенному шаблону: "
"1. Обо мне: имя, возраст, профессия, интересы, хобби, достижения, цели, ключевые черты характера. "
"2. Семья: члены семьи, имена, возраст, важные детали, события и воспоминания. "
"3. Друзья, близкие, важные знакомые: имена, возраст, важные события и детали, ключевые моменты общения. "
"4. Эмоции: значимые эмоции и чувства, связанные с важными событиями. "
"5. Разговоры: ключевые темы обсуждений, важные моменты и детали, общие выводы. "
"6. Указания и предпочтения: особые инструкции, предпочтения, любимые вещи. "
"7. Ценности и убеждения: важные принципы, взгляды и убеждения. "
       )
        self.conversation_history.append({"role": "user", "content": summary_prompt})
        self._save_history()
        try:
            response = openai.ChatCompletion.create(
                model="local-model",
                messages=self.conversation_history
            )
            summary = response.choices[0].message.content.strip() if response.choices else ""
            if summary:
                self.conversation_history.append({"role": "assistant", "content": summary})
                self._save_history()
                logging.info("Резюме успешно сгенерировано")
        except Exception:
            logging.exception("Ошибка генерации резюме:")

    def stop_generation(self) -> None:
        self.stop_event.set()
        self._play_sound("stop_generation")

    def cancel_recording(self) -> None:
        self.cancel_record_flag = True

    def mouse_stop_recording(self) -> None:
        self.mouse_stop_flag = True

# --- Окно настроек ---
class SettingsWindow(QDialog):
    def __init__(self, parent=None, current_text_size: int = 14,
                 current_tts: str = "tts_models/multilingual/multi-dataset/xtts_v2",
                 current_whisper: str = "large-v3-turbo",
                 current_summary_interval: int = 10,
                 current_colors: dict = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.resize(750, 400)
        self.setStyleSheet(f"font-size: {current_text_size}px;")
        
        main_layout = QVBoxLayout(self)
        groups_layout = QHBoxLayout()
        
        general_group = QGroupBox("Общие настройки")
        general_layout = QFormLayout()
        self.text_size_spin = QSpinBox()
        self.text_size_spin.setRange(10, 30)
        self.text_size_spin.setValue(current_text_size)
        general_layout.addRow(QLabel("Размер текста:"), self.text_size_spin)

        self.tts_combo = QComboBox()
        self.tts_combo.addItems([
            "tts_models/multilingual/multi-dataset/xtts_v2",
            "tts_models/en/ljspeech/tacotron2-DDC"
        ])
        self.tts_combo.setCurrentText(current_tts)
        general_layout.addRow(QLabel("Модель синтеза речи:"), self.tts_combo)

        self.whisper_combo = QComboBox()
        self.whisper_combo.addItems(["tiny", "base", "small", "medium", "large-v3-turbo"])
        self.whisper_combo.setCurrentText(current_whisper)
        general_layout.addRow(QLabel("Модель распознавания:"), self.whisper_combo)

        self.summary_spin = QSpinBox()
        self.summary_spin.setRange(1, 1000)
        self.summary_spin.setValue(current_summary_interval)
        general_layout.addRow(QLabel("Сообщений до резюме:"), self.summary_spin)
        general_group.setLayout(general_layout)
        
        colors_group = QGroupBox("Цветовые настройки")
        colors_layout = QGridLayout()
        self.colors = {}
        defaults = {
            "text_input_bg": "#2F2F2F",
            "text_input_text": "#FFFFFF",
            "chat_bg": "#2F2F2F",
            "chat_text": "#FFFFFF",
            "system_log_bg": "#1F1F1F",
            "system_log_text": "#FFA500",
            "button_bg": "#333333",
            "button_text": "orange",
            "button_hover_color": "#444444",
            "panel_bg": "#3F3F3F",
            "window_bg": "#2F2F2F",
            "system_label_color": "#AAAAAA",
            "system_content_color": "#FFFFFF",
            "user_label_color": "#008080",
            "user_content_color": "#ADD8E6",
            "assistant_label_color": "#9B59B6",
            "assistant_content_color": "#FFA500",
            "scrollbar_handle_color": "#888888",
            "scrollbar_track_color": "#444444"
        }
        if current_colors is None:
            current_colors = defaults
        for key, default in defaults.items():
            self.colors[key] = current_colors.get(key, default)

        self.color_buttons = {}
        color_options = [
            ("Фон поля ввода", "text_input_bg"),
            ("Цвет текста поля ввода", "text_input_text"),
            ("Фон области чата", "chat_bg"),
            ("Фон системного лога", "system_log_bg"),
            ("Цвет текста системного лога", "system_log_text"),
            ("Фон кнопок", "button_bg"),
            ("Цвет текста кнопок", "button_text"),
            ("Цвет выделения кнопок", "button_hover_color"),
            ("Фон панелей", "panel_bg"),
            ("Фон основного окна", "window_bg"),
            ("Цвет метки 'Система:'", "system_label_color"),
            ("Цвет текста 'Система:'", "system_content_color"),
            ("Цвет метки 'Пользователь:'", "user_label_color"),
            ("Цвет текста 'Пользователь:'", "user_content_color"),
            ("Цвет метки 'Ассистент:'", "assistant_label_color"),
            ("Цвет текста 'Ассистент:'", "chat_text"),
            ("Цвет ползунка", "scrollbar_handle_color"),
            ("Цвет трека", "scrollbar_track_color")
        ]
        row = 0
        for label_text, key in color_options:
            lbl = QLabel(label_text + ":")
            btn = QPushButton()
            btn.setStyleSheet(f"background-color: {self.colors[key]};")
            btn.setFixedWidth(80)
            btn.clicked.connect(lambda _, k=key, b=btn: self.choose_color(k, b))
            self.color_buttons[key] = btn
            colors_layout.addWidget(lbl, row, 0)
            colors_layout.addWidget(btn, row, 1)
            row += 1
        colors_group.setLayout(colors_layout)
        
        groups_layout.addWidget(general_group)
        groups_layout.addWidget(colors_group)
        main_layout.addLayout(groups_layout)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        main_layout.addWidget(self.buttons)

    def choose_color(self, key: str, button: QPushButton) -> None:
        color = QColorDialog.getColor(QColor(self.colors[key]), self, "Выберите цвет")
        if color.isValid():
            self.colors[key] = color.name()
            button.setStyleSheet(f"background-color: {color.name()};")

    def get_settings(self) -> dict:
        return {
            "text_size": self.text_size_spin.value(),
            "tts_model": self.tts_combo.currentText(),
            "whisper_model": self.whisper_combo.currentText(),
            "summary_interval": self.summary_spin.value(),
            "colors": self.colors
        }


# --- Главное окно приложения ---
class VoiceAssistantUI(QWidget):
    replyReady = pyqtSignal(str)
    transcribedTextReady = pyqtSignal(str)

    def __init__(self, settings: dict) -> None:
        super().__init__()
        self.settings = settings
        self.current_text_size = self.settings.get("text_size", 14)
        self.setWindowIcon(QIcon(str(ROOT_DIR / "LM Studio Голосовой диалог.ico")))
        self.backend = VoiceAssistantBackend(self.settings)
        self.replyReady.connect(self.start_assistant_message_worker)
        self.transcribedTextReady.connect(self.append_user_message)
        self.synthesis_active = False
        self.init_ui()
        self.update_system_message("Готов к работе!")

    def init_ui(self) -> None:
        scrollbar_handle_color = self.settings["colors"].get("scrollbar_handle_color", "#888888")
        scrollbar_track_color = self.settings["colors"].get("scrollbar_track_color", "#444444")
        window_bg = self.settings["colors"].get("window_bg", "#2F2F2F")
        self.setStyleSheet(f"background-color: {window_bg};")
        self.setWindowTitle("LM Studio Голосовой Диалог")
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Панель ввода текста
        self.input_panel = QWidget()
        panel_bg = self.settings["colors"].get("panel_bg", "#3F3F3F")
        self.input_panel.setStyleSheet(f"background-color: {panel_bg}; border-radius: 15px;")
        input_layout = QVBoxLayout(self.input_panel)
        input_layout.setContentsMargins(15, 15, 15, 15)
        input_layout.setSpacing(10)

        self.text_input = SpellCheckTextEdit()
        text_input_bg = self.settings["colors"].get("text_input_bg", "#2F2F2F")
        text_input_text = self.settings["colors"].get("text_input_text", "#FFFFFF")
        self.text_input.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {text_input_bg};
                color: {text_input_text};
                border-radius: 15px;
                padding: 8px;
                font-size: {self.current_text_size}px;
                font-family: Arial, sans-serif;
            }}
            QPlainTextEdit QScrollBar:vertical {{
                background: {scrollbar_track_color};
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }}
            QPlainTextEdit QScrollBar::handle:vertical {{
                background: {scrollbar_handle_color};
                border-radius: 5px;
                min-height: 20px;
            }}
            QPlainTextEdit QScrollBar::handle:vertical:hover {{
                background: #aaaaaa;
            }}
            QPlainTextEdit QScrollBar::add-line:vertical,
            QPlainTextEdit QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QPlainTextEdit QScrollBar::add-page:vertical,
            QPlainTextEdit QScrollBar::sub-page:vertical {{
                background: {scrollbar_track_color};
                border-radius: 5px;
            }}
        """)
        self.text_input.setPlaceholderText("Введите текст здесь...")
        input_layout.addWidget(self.text_input)

        self.btn_send_text = QPushButton("Отправить")
        self.style_round_button(self.btn_send_text)
        self.btn_send_text.clicked.connect(self.on_send_text)
        input_layout.addWidget(self.btn_send_text)
        self.input_panel.setFixedWidth(220)
        main_layout.addWidget(self.input_panel)

        # Панель чата
        self.chat_panel = QWidget()
        self.chat_panel.setStyleSheet(f"background-color: {panel_bg}; border-radius: 15px;")
        chat_layout = QVBoxLayout(self.chat_panel)
        chat_layout.setContentsMargins(15, 15, 15, 15)
        chat_layout.setSpacing(10)

        self.chat_edit = QTextEdit()
        self.chat_edit.setReadOnly(True)
        chat_bg = self.settings["colors"].get("chat_bg", "#2F2F2F")
        chat_text = self.settings["colors"].get("chat_text", "#FFFFFF")
        self.chat_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {chat_bg};
                border-radius: 15px;
                padding: 8px;
                color: {chat_text};
                font-size: {self.current_text_size}px;
                font-family: Arial, sans-serif;
            }}
            QTextEdit QScrollBar:vertical {{
                background: {scrollbar_track_color};
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }}
            QTextEdit QScrollBar::handle:vertical {{
                background: {scrollbar_handle_color};
                border-radius: 5px;
                min-height: 20px;
            }}
            QTextEdit QScrollBar::handle:vertical:hover {{
                background: #aaaaaa;
            }}
            QTextEdit QScrollBar::add-line:vertical,
            QTextEdit QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QTextEdit QScrollBar::add-page:vertical,
            QTextEdit QScrollBar::sub-page:vertical {{
                background: {scrollbar_track_color};
                border-radius: 5px;
            }}
        """)
        chat_layout.addWidget(self.chat_edit, stretch=3)

        self.system_log = QTextEdit()
        self.system_log.setReadOnly(True)
        system_log_bg = self.settings["colors"].get("system_log_bg", "#1F1F1F")
        system_log_text = self.settings["colors"].get("system_log_text", "#FFA500")
        self.system_log.setStyleSheet(f"""
            QTextEdit {{
                background-color: {system_log_bg};
                border-radius: 15px;
                padding: 8px;
                color: {system_log_text};
                font-size: {self.current_text_size}px;
                font-family: Arial, sans-serif;
            }}
            QTextEdit::selection {{
                background-color: #444444;
                color: {system_log_text};
            }}
        """)
        self.system_log.setFixedHeight(80)
        chat_layout.addWidget(self.system_log, stretch=0)
        main_layout.addWidget(self.chat_panel, stretch=1)

        # Панель с кнопками
        self.button_panel = QWidget()
        self.button_panel.setStyleSheet(f"background-color: {panel_bg}; border-radius: 15px;")
        btn_layout = QVBoxLayout(self.button_panel)
        btn_layout.setContentsMargins(15, 15, 15, 15)
        btn_layout.setSpacing(10)

        self.btn_record = QPushButton("Запись аудио")
        self.style_round_button(self.btn_record)
        self.btn_record.clicked.connect(self.on_record_audio)
        btn_layout.addWidget(self.btn_record)

        self.btn_stop_record = QPushButton("Остановить запись")
        self.style_round_button(self.btn_stop_record)
        self.btn_stop_record.clicked.connect(self.on_stop_recording)
        btn_layout.addWidget(self.btn_stop_record)

        self.btn_cancel = QPushButton("Отменить запись")
        self.style_round_button(self.btn_cancel)
        self.btn_cancel.clicked.connect(self.on_cancel_recording)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_voice = QPushButton("Голосовой образец")
        self.style_round_button(self.btn_voice)
        self.btn_voice.clicked.connect(self.on_record_voice_sample)
        btn_layout.addWidget(self.btn_voice)

        self.btn_stop_gen = QPushButton("Остановить озвучку")
        self.style_round_button(self.btn_stop_gen)
        self.btn_stop_gen.clicked.connect(self.on_stop_generation)
        btn_layout.addWidget(self.btn_stop_gen)

        self.btn_settings = QPushButton("Настройки")
        self.style_round_button(self.btn_settings)
        self.btn_settings.clicked.connect(self.open_settings)
        btn_layout.addWidget(self.btn_settings)

        self.button_panel.setFixedWidth(220)
        main_layout.addWidget(self.button_panel)

        self.setLayout(main_layout)
        self.resize(1000, 600)

    def style_round_button(self, btn: QPushButton) -> None:
        btn.setToolTip(btn.text())
        button_bg = self.settings["colors"].get("button_bg", "#333333")
        button_text = self.settings["colors"].get("button_text", "orange")
        button_hover = self.settings["colors"].get("button_hover_color", "#444444")
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {button_bg};
                color: {button_text};
                border: 2px solid {button_bg};
                border-radius: 15px;
                padding: 8px;
                font-size: {self.current_text_size}px;
                font-family: Arial, sans-serif;
            }}
            QPushButton:hover {{
                background-color: {button_hover};
            }}
        """)

    def update_all_button_styles(self) -> None:
        self.style_round_button(self.btn_send_text)
        for btn in [self.btn_record, self.btn_stop_record, self.btn_cancel, self.btn_voice, self.btn_stop_gen, self.btn_settings]:
            self.style_round_button(btn)

    def apply_styles(self) -> None:
        """Обновляет стили для всех виджетов на основе текущих настроек."""
        scrollbar_handle_color = self.settings["colors"].get("scrollbar_handle_color", "#888888")
        scrollbar_track_color = self.settings["colors"].get("scrollbar_track_color", "#444444")
        text_input_bg = self.settings["colors"].get("text_input_bg", "#2F2F2F")
        text_input_text = self.settings["colors"].get("text_input_text", "#FFFFFF")
        chat_bg = self.settings["colors"].get("chat_bg", "#2F2F2F")
        chat_text = self.settings["colors"].get("chat_text", "#FFFFFF")
        system_log_bg = self.settings["colors"].get("system_log_bg", "#1F1F1F")
        system_log_text = self.settings["colors"].get("system_log_text", "#FFA500")
        panel_bg = self.settings["colors"].get("panel_bg", "#3F3F3F")

        # Обновляем стили текстового ввода
        self.text_input.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {text_input_bg};
                color: {text_input_text};
                border-radius: 15px;
                padding: 8px;
                font-size: {self.current_text_size}px;
                font-family: Arial, sans-serif;
            }}
            QPlainTextEdit QScrollBar:vertical {{
                background: {scrollbar_track_color};
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }}
            QPlainTextEdit QScrollBar::handle:vertical {{
                background: {scrollbar_handle_color};
                border-radius: 5px;
                min-height: 20px;
            }}
            QPlainTextEdit QScrollBar::handle:vertical:hover {{
                background: #aaaaaa;
            }}
            QPlainTextEdit QScrollBar::add-line:vertical,
            QPlainTextEdit QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QPlainTextEdit QScrollBar::add-page:vertical,
            QPlainTextEdit QScrollBar::sub-page:vertical {{
                background: {scrollbar_track_color};
                border-radius: 5px;
            }}
        """)
        # Обновляем стили области чата
        self.chat_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {chat_bg};
                border-radius: 15px;
                padding: 8px;
                color: {chat_text};
                font-size: {self.current_text_size}px;
                font-family: Arial, sans-serif;
            }}
            QTextEdit QScrollBar:vertical {{
                background: {scrollbar_track_color};
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }}
            QTextEdit QScrollBar::handle:vertical {{
                background: {scrollbar_handle_color};
                border-radius: 5px;
                min-height: 20px;
            }}
            QTextEdit QScrollBar::handle:vertical:hover {{
                background: #aaaaaa;
            }}
            QTextEdit QScrollBar::add-line:vertical,
            QTextEdit QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QTextEdit QScrollBar::add-page:vertical,
            QTextEdit QScrollBar::sub-page:vertical {{
                background: {scrollbar_track_color};
                border-radius: 5px;
            }}
        """)
        self.system_log.setStyleSheet(f"""
            QTextEdit {{
                background-color: {system_log_bg};
                border-radius: 15px;
                padding: 8px;
                color: {system_log_text};
                font-size: {self.current_text_size}px;
                font-family: Arial, sans-serif;
            }}
            QTextEdit::selection {{
                background-color: #444444;
                color: {system_log_text};
            }}
        """)
        self.input_panel.setStyleSheet(f"background-color: {panel_bg}; border-radius: 15px;")
        self.chat_panel.setStyleSheet(f"background-color: {panel_bg}; border-radius: 15px;")
        self.button_panel.setStyleSheet(f"background-color: {panel_bg}; border-radius: 15px;")
        self.update_all_button_styles()

    @pyqtSlot(str)
    def append_user_message(self, text: str) -> None:
        user_label_color = self.settings["colors"].get("user_label_color", "#008080")
        user_content_color = self.settings["colors"].get("user_content_color", "#ADD8E6")
        self.chat_edit.append(f"<p><b style='color: {user_label_color};'>Пользователь:</b> <span style='color: {user_content_color};'>{text}</span></p>")
        self.chat_edit.verticalScrollBar().setValue(self.chat_edit.verticalScrollBar().maximum())

    def update_system_message(self, text: str) -> None:
        system_label_color = self.settings["colors"].get("system_label_color", "#AAAAAA")
        system_content_color = self.settings["colors"].get("system_content_color", "#FFFFFF")
        self.system_log.setHtml(f"<p><b style='color: {system_label_color};'>Система:</b> <span style='color: {system_content_color};'>{text}</span></p>")
        self.system_log.verticalScrollBar().setValue(self.system_log.verticalScrollBar().maximum())
        if text == "Готов к работе!":
            self.backend._play_sound("system_ready")

    @pyqtSlot(str)
    def start_assistant_message_worker(self, text: str) -> None:
        self.backend.stop_event.clear()
        self.synthesis_active = True
        self.text_input.setEnabled(False)
        self.btn_record.setEnabled(False)
        self.btn_send_text.setEnabled(False)  # Отключаем кнопку "Отправить"

        self.chat_edit.append("")
        cursor = self.chat_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        assistant_label_color = self.settings["colors"].get("assistant_label_color", "#9B59B6")
        assistant_content_color = self.settings["colors"].get("assistant_content_color", "#FFA500")
        cursor.insertHtml(f"<p><b style='color: {assistant_label_color};'>Ассистент:</b> <span style='color: {assistant_content_color};'>")
        self.chat_edit.setTextCursor(cursor)
        self.update_system_message("Идет озвучка")

        self.worker_thread = QThread()
        self.worker = AssistantMessageWorker(text, self.backend)
        self.worker.moveToThread(self.worker_thread)
        self.worker.appendChar.connect(self.on_update_assistant_text)
        self.worker.finished.connect(self.on_assistant_message_finished)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.started.connect(self.worker.run)
        self.worker_thread.start()

    @pyqtSlot(str)
    def on_update_assistant_text(self, ch: str) -> None:
        cursor = self.chat_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(ch)
        self.chat_edit.setTextCursor(cursor)
        self.chat_edit.verticalScrollBar().setValue(self.chat_edit.verticalScrollBar().maximum())

    @pyqtSlot()
    def on_assistant_message_finished(self) -> None:
        cursor = self.chat_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml("</span></p>")
        self.chat_edit.setTextCursor(cursor)
        self.update_system_message("Готов к работе!")
        self.backend.input_enabled = True
        self.backend.stop_event.clear()
        self.synthesis_active = False
        self.text_input.setEnabled(True)
        self.btn_record.setEnabled(True)
        self.btn_send_text.setEnabled(True)  # Разблокируем кнопку "Отправить"
        self.chat_edit.verticalScrollBar().setValue(self.chat_edit.verticalScrollBar().maximum())

    def on_send_text(self) -> None:
        if not self.backend.input_enabled:
            self.update_system_message("Ожидайте окончания озвучки!")
            return
        user_text = self.text_input.toPlainText().strip()
        if not user_text:
            return
        self.text_input.setEnabled(False)
        self.btn_record.setEnabled(False)
        self.btn_send_text.setEnabled(False)  # Отключаем кнопку "Отправить" при отправке
        self.backend._play_sound("input")
        self.append_user_message(user_text)
        self.text_input.clear()
        self.backend.input_enabled = False
        threading.Thread(target=lambda: self.process_lm_input(user_text), daemon=True).start()

    def process_lm_input(self, input_text: str) -> None:
        reply = self.backend.generate_reply(input_text)
        self._play_assistant_sound("assistant_message")
        self.replyReady.emit(reply)

    def _play_assistant_sound(self, key: str) -> None:
        self.backend._play_sound(key)

    def on_record_audio(self) -> None:
        if not self.backend.input_enabled or self.backend.recording_in_progress:
            self.update_system_message("Ожидайте окончания озвучки или запись уже идет!")
            return
        if self.synthesis_active:
            self.update_system_message("Ожидайте окончания озвучки!")
            return
        self.update_system_message("Идет запись, говорите...")
        self.backend.recording_in_progress = True
        self.text_input.setEnabled(False)
        self.btn_record.setEnabled(False)
        self.btn_send_text.setEnabled(False)  # Отключаем кнопку "Отправить" при записи

        def record_thread() -> None:
            audio_file = self.backend.record_audio(max_duration=None)
            if audio_file:
                text = self.backend.transcribe_audio(audio_file)
                if text:
                    self.transcribedTextReady.emit(text)
                    self.process_lm_input(text)
                with suppress(Exception):
                    os.remove(audio_file)
            else:
                # Если запись не удалась, разблокируем все элементы ввода
                self.text_input.setEnabled(True)
                self.btn_record.setEnabled(True)
                self.btn_send_text.setEnabled(True)
            self.backend.recording_in_progress = False

        threading.Thread(target=record_thread, daemon=True).start()

    def on_stop_recording(self) -> None:
        if not self.backend.input_enabled:
            self.update_system_message("Ожидайте окончания озвучки!")
            return
        self.update_system_message("Запись остановлена.")
        self.backend.mouse_stop_recording()

    def on_cancel_recording(self) -> None:
        if not self.backend.input_enabled:
            self.update_system_message("Ожидайте окончания озвучки!")
            return
        self.update_system_message("Запись отменена.")
        self.backend.cancel_recording()

    def on_record_voice_sample(self) -> None:
        if not self.backend.input_enabled:
            self.update_system_message("Ожидайте окончания озвучки!")
            return
        self.update_system_message("Запись голосового образца началась...")
        threading.Thread(target=self.backend.record_voice_sample, daemon=True).start()

    def on_stop_generation(self) -> None:
        if not self.synthesis_active:
            self.update_system_message("Нет активной озвучки для остановки.")
            return
        self.update_system_message("Озвучка остановлена.")
        self.backend.stop_generation()
        # Ввод (и кнопка "Отправить") будут активированы в on_assistant_message_finished после завершения озвучки.

    def open_settings(self) -> None:
        settings_dialog = SettingsWindow(
            self,
            current_text_size=self.current_text_size,
            current_tts=self.settings.get("tts_model", "tts_models/multilingual/multi-dataset/xtts_v2"),
            current_whisper=self.settings.get("whisper_model", "large-v3-turbo"),
            current_summary_interval=self.settings.get("summary_interval", 10),
            current_colors=self.settings.get("colors", {})
        )
        if settings_dialog.exec() == QDialog.DialogCode.Accepted:
            new_settings = settings_dialog.get_settings()
            self.current_text_size = new_settings["text_size"]
            self.settings.update(new_settings)
            save_settings(self.settings)
            QApplication.instance().setFont(QFont("Arial", self.current_text_size))
            self.apply_styles()
            self.update_system_message("Некоторые изменения настроек будут применены после перезапуска приложения.")


def main() -> None:
    settings = load_settings()
    app = QApplication(sys.argv)
    app.setFont(QFont("Arial", settings.get("text_size", 14)))
    app.setStyleSheet("QToolTip { font-size: 12px; }")
    ui = VoiceAssistantUI(settings)
    ui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()