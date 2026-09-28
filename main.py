import sys
import os
import subprocess

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
            print("    Установи: ollama pull llama3")
            return False
    except FileNotFoundError:
        print("[-] Ollama не установлен")
        print("    Скачай: https://ollama.com")
        return False
    except Exception as e:
        print(f"[-] Ollama: {e}")
        return False

def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        print("[+] ffmpeg OK")
        return True
    except FileNotFoundError:
        print("[-] ffmpeg не в PATH")
        return False

def main():
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
    if not all_ok:
        print("[-] Не всё установлено. Исправь и запусти снова.")
        input("Enter чтобы выйти...")
        sys.exit(1)

    print("[+] Всё готово. Запускаю GUI...")
    print("=" * 60)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    gui_path = os.path.join(script_dir, "voice_assistant_gui.py")

    if not os.path.exists(gui_path):
        print(f"[-] Не найден {gui_path}")
        input("Enter...")
        sys.exit(1)

    subprocess.run([sys.executable, gui_path])


if __name__ == "__main__":
    main()