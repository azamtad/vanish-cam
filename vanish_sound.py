"""Play short effect sounds without blocking the video loop.

macOS: uses the built-in ``afplay`` command (nothing to install).
Windows/Linux: uses pygame if installed, otherwise ``ffplay``.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path


SOUND_PATH = Path(__file__).resolve().parent / "assets" / "vanish.MP3"


class VanishSound:
    def __init__(self, path: Path = SOUND_PATH):
        if not path.is_file():
            raise RuntimeError(f"Sound file not found: {path}")
        self.path = path
        self.process: subprocess.Popen | None = None
        self.command: list[str] | None = None
        self.sound = None
        self.mixer = None
        self.owns_mixer = False

        afplay = shutil.which("afplay") if platform.system() == "Darwin" else None
        if afplay is not None:
            self.command = [afplay, str(path)]
            return

        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        try:
            from pygame import mixer
        except ImportError:
            ffplay = shutil.which("ffplay")
            if ffplay is None:
                raise RuntimeError(
                    f"To play {path.name} install pygame (pip install pygame) or ffplay."
                )
            self.command = [ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet", "-i", str(path)]
            return

        self.mixer = mixer
        self.owns_mixer = mixer.get_init() is None
        try:
            if self.owns_mixer:
                mixer.init(frequency=44100, size=-16, channels=2, buffer=256)
            self.sound = mixer.Sound(str(path))  # Decode once, before opening the webcam.
        except Exception as error:
            if self.owns_mixer:
                mixer.quit()
            raise RuntimeError(f"Could not open {path.name}: {error}") from error

    def play(self) -> None:
        if self.command is not None:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
            try:
                self.process = subprocess.Popen(
                    self.command,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except OSError as error:
                print(f"[Sound] Could not play {self.path.name}: {error}")
            return
        self.sound.stop()
        self.sound.play()

    def close(self) -> None:
        if self.command is not None:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
            return
        if self.owns_mixer and self.mixer is not None:
            self.mixer.quit()
            self.owns_mixer = False
