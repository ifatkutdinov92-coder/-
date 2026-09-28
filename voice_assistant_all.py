import sys
import os
import re
import json
import time
import sqlite3
import asyncio
import subprocess
import threading
import webbrowser
from datetime import datetime

# === ПРОВЕРКА ЗАВИСИМОСТЕЙ ===
def check_python():
    if sys.version_info < (3, 10):
        print("[-] Нужен Python 3.10 или выше")
        sys.exit(1)
    print(f"[+] Python {sys.version.split()[0]}")

def check_module(name, pip_name=None):
    try:
        __import__(name)
        print(f"[+] {name} OK")
        return True
    except ImportError:
        pkg = pip_name or name
        print(f"[-] {name} не установлен")
        print(f"    Установи: pip install {pkg}")
        return False

def check_ollama():
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
        if "llama3" in result.stdout:
            print("[+] Ollama + llama3 OK")
            return True
        else:
            print("[-] Модель llama3 не скачана")
            return False
    except Exception:
        print("[-] Ollama не установлен")
        return False

def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        print("[+] ffmpeg OK")
        return True
    except Exception:
        print("[-] ffmpeg не в PATH")
        return False

def check_all():
    print("=" * 60)
    print("VOICE ASSISTANT — ПРОВЕРКА")
    print("=" * 60)
    check_python()
    modules = [
        ("whisper", "openai-whisper"),
        ("ollama", "ollama"),
        ("pyautogui", "pyautogui"),
        ("sounddevice", "sounddevice"),
        ("soundfile", "soundfile"),
        ("numpy", "numpy"),
        ("edge_tts", "edge-tts"),
        ("librosa", "librosa"),
        ("customtkinter", "customtkinter"),
    ]
    all_ok = True
    for mod, pip in modules:
        if not check_module(mod, pip):
            all_ok = False
    if not check_ollama():
        all_ok = False
    if not check_ffmpeg():
        all_ok = False
    print("=" * 60)
    return all_ok


# === КОНФИГ ===
CONFIG_PATH = "config.json"

DEFAULT_CONFIG = {
    "assistant_name": "Voice Assistant",
    "whisper_model": "small",
    "ollama_model": "llama3",
    "tts_voice": "ru-RU-SvetlanaNeural",
    "record_seconds": 5,
    "mic_device": 1,
    "max_history": 5,
    "auto_listen": False,
    "log_to_db": True
}

def load_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
        return DEFAULT_CONFIG
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    for k, v in DEFAULT_CONFIG.items():
        if k not in cfg:
            cfg[k] = v
    return cfg

CONFIG = load_config()


# === ЛОГ В SQLITE ===
DB_PATH = "assistant_log.db"

def init_db():
    if not CONFIG.get("log_to_db", True):
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS dialogs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        user_text TEXT,
        assistant_text TEXT,
        command_done INTEGER
    )""")
    conn.commit()
    conn.close()

def log_dialog(user_text, assistant_text, command_done):
    if not CONFIG.get("log_to_db", True):
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO dialogs (created_at, user_text, assistant_text, command_done) VALUES (?,?,?,?)",
                  (datetime.now().isoformat(), user_text, assistant_text, int(command_done)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[-] Ошибка лога: {e}")


if __name__ == "__main__":
    if not check_all():
        print("[-] Не всё установлено. Исправь и запусти снова.")
        input("Enter...")
        sys.exit(1)
    print("[+] Всё готово. Запускаю GUI...")
    print("=" * 60)

    import whisper
    import ollama
    import pyautogui
    import sounddevice as sd
    import soundfile as sf
    import numpy as np
    import edge_tts
    import librosa
    import customtkinter as ctk

    init_db()

    WHISPER_MODEL = CONFIG["whisper_model"]
    OLLAMA_MODEL = CONFIG["ollama_model"]
    TTS_VOICE = CONFIG["tts_voice"]
    RECORD_SECONDS = CONFIG["record_seconds"]
    MIC_DEVICE = CONFIG["mic_device"]
    MAX_HISTORY = CONFIG["max_history"]
    SAMPLE_RATE = 16000
    RECORD_RATE = 48000
    TEMP_AUDIO = "voice_input.wav"
    TEMP_OUTPUT = "voice_output.mp3"

    print("[+] Загружаю Whisper...")
    whisper_model = whisper.load_model(WHISPER_MODEL)
    print("[+] Whisper загружен")

    history = []

    def record_audio(duration=RECORD_SECONDS):
        try:
            recording = sd.rec(int(duration * RECORD_RATE), samplerate=RECORD_RATE,
                               channels=1, dtype='float32', device=MIC_DEVICE)
            sd.wait()
            recording_16k = librosa.resample(recording.flatten(),
                                              orig_sr=RECORD_RATE,
                                              target_sr=SAMPLE_RATE)
            sf.write(TEMP_AUDIO, recording_16k, SAMPLE_RATE)
            return TEMP_AUDIO
        except Exception as e:
            print(f"[-] Ошибка записи: {e}")
            return None

    def speech_to_text(audio_path):
        result = whisper_model.transcribe(audio_path, language="ru")
        return result["text"].strip()

    async def text_to_speech(text, output=TEMP_OUTPUT):
        communicate = edge_tts.Communicate(text, TTS_VOICE)
        await communicate.save(output)
        return output

    def play_audio(path):
        try:
            subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                           timeout=30)
        except Exception as e:
            print(f"[-] Ошибка воспроизведения: {e}")

    def ask_llama(prompt):
        global history
        messages = [
            {
                'role': 'system',
                'content': (
                    "Ты — голосовой ассистент для управления ПК. "
                    "Отвечай кратко, 1-2 предложения. "
                    "Ты можешь открывать программы, искать в интернете, делать скриншоты."
                )
            }
        ]
        for h in history[-MAX_HISTORY:]:
            messages.append(h)
        messages.append({'role': 'user', 'content': prompt})

        response = ollama.chat(model=OLLAMA_MODEL, messages=messages)
        answer = response['message']['content']

        history.append({'role': 'user', 'content': prompt})
        history.append({'role': 'assistant', 'content': answer})
        if len(history) > MAX_HISTORY * 2:
            history = history[-MAX_HISTORY * 2:]

        return answer

    def execute_command(text):
        text_lower = text.lower()
        done = False
        result_msg = ""

        apps_map = {
            "хром": "chrome.exe", "chrome": "chrome.exe",
            "блокнот": "notepad.exe", "notepad": "notepad.exe",
            "калькулятор": "calc.exe", "проводник": "explorer.exe",
            "паинт": "mspaint.exe", "paint": "mspaint.exe",
            "дискорд": "discord.exe", "discord": "discord.exe",
            "телеграм": "telegram.exe", "telegram": "telegram.exe",
            "стим": "steam.exe", "steam": "steam.exe",
            "браузер": "chrome.exe", "ютуб": "chrome.exe",
        }

        m = re.search(r"(?:открой|запусти|включи|открыть|запустить)\s+([а-яa-z0-9\s]+)", text_lower)
        if m:
            app = m.group(1).strip().rstrip(".!?,")
            app_exe = apps_map.get(app, app)
            try:
                subprocess.Popen(app_exe, shell=True)
                done = True
                result_msg = f"Открываю {app}"
            except Exception as e:
                result_msg = f"Не смог открыть {app}: {e}"

        m = re.search(r"(?:найди|поищи|загугли)\s+(.+)", text_lower)
        if m:
            query = m.group(1).strip()
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            webbrowser.open(url)
            done = True
            result_msg = f"Ищу: {query}"

        if "напиши" in text_lower or "напечатай" in text_lower:
            m = re.search(r"(?:напиши|напечатай)\s+(.+)", text_lower)
            if m:
                txt = m.group(1)
                time.sleep(1)
                pyautogui.typewrite(txt, interval=0.05)
                done = True
                result_msg = f"Написал: {txt}"

        if "скриншот" in text_lower or "снимок экрана" in text_lower:
            try:
                img = pyautogui.screenshot()
                path = os.path.join(os.path.expanduser("~"), "Desktop", "screenshot.png")
                img.save(path)
                done = True
                result_msg = "Скриншот сохранён"
            except Exception as e:
                result_msg = f"Ошибка: {e}"

        if "громче" in text_lower:
            for _ in range(5):
                pyautogui.press('volumeup')
            done = True
            result_msg = "Сделал громче"

        if "тише" in text_lower:
            for _ in range(5):
                pyautogui.press('volumedown')
            done = True
            result_msg = "Сделал тише"

        if "закрой окно" in text_lower:
            pyautogui.hotkey('alt', 'f4')
            done = True
            result_msg = "Закрыл окно"

        if "выключи компьютер" in text_lower:
            subprocess.Popen("shutdown /s /t 30", shell=True)
            done = True
            result_msg = "Выключаю ПК через 30 секунд"

        if "ярче" in text_lower:
            for _ in range(5):
                pyautogui.press('brightnessup')
            done = True
            result_msg = "Сделал ярче"

        if "темнее" in text_lower:
            for _ in range(5):
                pyautogui.press('brightnessdown')
            done = True
            result_msg = "Сделал темнее"

        return done, result_msg

    class VoiceAssistantApp(ctk.CTk):
        def __init__(self):
            super().__init__()
            self.title(CONFIG["assistant_name"])
            self.geometry("700x750")
            self.resizable(False, False)

            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")

            self.avatar_frame = ctk.CTkFrame(self, fg_color="transparent")
            self.avatar_frame.pack(pady=20)

            self.avatar = ctk.CTkLabel(
                self.avatar_frame,
                text="🤖",
                font=("Segoe UI Emoji", 80),
                width=150, height=150,
                fg_color="#1f538d",
                corner_radius=75
            )
            self.avatar.pack()

            self.name_label = ctk.CTkLabel(
                self, text=CONFIG["assistant_name"],
                font=("Arial", 24, "bold")
            )
            self.name_label.pack(pady=5)

            self.status_label = ctk.CTkLabel(
                self, text="Нажми кнопку и говори",
                font=("Arial", 14),
                text_color="gray"
            )
            self.status_label.pack(pady=5)

            self.chat_frame = ctk.CTkScrollableFrame(self, width=650, height=350)
            self.chat_frame.pack(pady=10, padx=20, fill="both", expand=True)

            self.listen_btn = ctk.CTkButton(
                self,
                text="🎤 Говорить",
                font=("Arial", 18, "bold"),
                width=300, height=60,
                corner_radius=30,
                command=self.on_listen
            )
            self.listen_btn.pack(pady=20)

            self.add_message("Ассистент", "Привет! Нажми 'Говорить' и скажи что-нибудь.", "assistant")

        def add_message(self, sender, text, role):
            if role == "user":
                color = "#2b5278"
                anchor = "e"
            else:
                color = "#1f538d"
                anchor = "w"

            frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
            frame.pack(fill="x", pady=5)

            bubble = ctk.CTkLabel(
                frame,
                text=f"{sender}:\n{text}",
                font=("Arial", 13),
                wraplength=500,
                justify="left",
                fg_color=color,
                corner_radius=10,
                padx=10, pady=8
            )
            bubble.pack(anchor=anchor, padx=10)

            self.chat_frame._parent_canvas.yview_moveto(1.0)

        def on_listen(self):
            self.listen_btn.configure(state="disabled", text="🎤 Слушаю...")
            self.status_label.configure(text=f"Слушаю {RECORD_SECONDS} секунд...")
            threading.Thread(target=self.process_voice, daemon=True).start()

        def process_voice(self):
            try:
                audio = record_audio()
                if not audio:
                    self.after(0, lambda: self.status_label.configure(text="Ошибка записи"))
                    self.after(0, lambda: self.listen_btn.configure(state="normal", text="🎤 Говорить"))
                    return

                text = speech_to_text(audio)
                self.after(0, lambda: self.add_message("Ты", text, "user"))

                if not text or len(text) < 2:
                    self.after(0, lambda: self.status_label.configure(text="Не расслышал"))
                    self.after(0, lambda: self.listen_btn.configure(state="normal", text="🎤 Говорить"))
                    return

                done, cmd_msg = execute_command(text)
                answer = cmd_msg if done else ask_llama(text)

                log_dialog(text, answer, done)

                self.after(0, lambda: self.add_message("Ассистент", answer, "assistant"))
                self.after(0, lambda: self.status_label.configure(text="Готов"))

                out = asyncio.run(text_to_speech(answer))
                play_audio(out)

            except Exception as e:
                self.after(0, lambda: self.add_message("Ошибка", str(e), "assistant"))
            finally:
                self.after(0, lambda: self.listen_btn.configure(state="normal", text="🎤 Говорить"))

    app = VoiceAssistantApp()
    app.mainloop()