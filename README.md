# VanishCam — webcam vanish effects (now with Goku Instant Transmission, runs on Mac)

Video is processed on your computer. It is neither recorded nor sent anywhere. The preview window shows short tips (press `H` to hide them); the optional virtual camera always gets the clean video without any text.

Three effects:

| Mode | Gesture | What happens |
|---|---|---|
| **Goku** (Instant Transmission) | Index + middle finger **together**, touching your **forehead**, hold **1 s** | Energy flicker → your body snaps into a thin line of light → gone, with comic speed lines. Do it again to reappear (reverse effect). |
| **Normal Vanish** | V sign (index + middle apart) | You dissolve with a cyan edge over ~3.6 s |
| **Naruto Vanish** | Palms pressed together in front of the camera | Smoke puff + wooden log substitution |

## macOS — install as an app (recommended)

1. Install **Python 3.12** once from <https://www.python.org/downloads/macos/> (skip if you already have it).
2. In Finder, double-click **`Install VanishCam.command`** in this folder. A Terminal window shows the progress (first time ~2 min, needs internet). If macOS blocks it: right-click → **Open** → **Open**.
3. When it's done, **VanishCam** is in your **Applications** folder and opens automatically. From then on, open it like any app (Launchpad, Spotlight `Cmd+Space` → "VanishCam", or drag it into the Dock). No Terminal needed.
4. The first time, macOS asks to allow camera access for **VanishCam** → **OK**.
5. Pick an effect, step out of the frame while the background is captured, step back in. The window tells you what to do.

Where things live: the app is `/Applications/VanishCam.app`, its Python environment and downloaded models are in `~/Library/Application Support/VanishCam`, and the log is `~/Library/Logs/VanishCam.log`. After changing the code, run the installer again to update the app. To uninstall, delete the app and that Application Support folder.

## macOS — run from Terminal (for development)

1. **Python 3** must be installed. Easiest: download Python 3.12 from <https://www.python.org/downloads/macos/> (or `brew install python@3.12`).
2. In Finder, open this folder and **double-click `start_mac_goku.command`** (Goku straight away) or **`start_mac.command`** (menu with all three modes).
   - If macOS says it can't be opened because it's from an unidentified developer: right-click the file → **Open** → **Open**.
   - If it opens in a text editor instead, open **Terminal** and run:
     ```bash
     cd ~/Downloads/vanish_webcam-main
     chmod +x start_mac.command start_mac_goku.command
     ./start_mac_goku.command
     ```
3. The first launch installs the components into `.venv-mac` (needs internet once, 1–2 min) and downloads the MediaPipe models into `models/`.
4. macOS asks to let **Terminal** use the camera → click **OK**. If you clicked "Don't allow" (or the window stays black): **System Settings → Privacy & Security → Camera →** turn on **Terminal**, then start again.
5. **Click the video window once** so it receives your key presses.
6. **Step out of the frame for 4 seconds** while the background is captured (the Terminal counts down). Then step back in.

### Doing the Goku teleport


- Put your **index and middle fingers straight and together** (ring + pinky curled, like Goku) against your **forehead**, and hold still for **1 second**. A progress bar fills up in the window, then you teleport.
- To **come back**: lower your hand, then do the same gesture again for 1 second.
- Brief tracking glitches (< 0.3 s) don't reset the countdown; actually breaking the pose does.
- The Instant Transmission sound plays on both vanish and return. On first run it is downloaded from [myinstants](https://www.myinstants.com/en/instant/instant-transmission/) and saved as `assets/teleport.mp3`. To use a different sound, replace that file with any MP3. If it can't be downloaded, a built-in sound (`assets/teleport.wav`) is used.
- `V` / `R` also trigger vanish / reappear manually, handy for testing.
- Tips: good front lighting, face fully in frame, and a background that doesn't change (don't move the laptop after capturing it — press `SPACE` to recapture).
- Hold time can be changed: `./start_mac.command --mode goku --hold 0.6`

## Controls (all modes)

- `SPACE`: capture a new background (step out of the frame)
- `V`: vanish now · `R`: reappear
- `M`: back to the effect menu
- `H`: hide / show the tips in the window (hide them when capturing the window in OBS)
- `F`: toggle fullscreen
- `Q`, `ESC` or closing the window: quit

## Useful options

```bash
./start_mac.command --mode goku          # skip the menu (also: normal, naruto)
./start_mac.command --list-cameras       # show webcam numbers
./start_mac.command --camera 1           # use another webcam (e.g. if index 0 is your iPhone's Continuity Camera)
./start_mac.command --width 1280 --height 720
./start_mac.command --mode goku --gesture-debug   # prints hand/face detection status in Terminal
```

## Using it in Zoom / Meet / Discord / OBS (optional)

**Simplest:** press `H` to hide the tips, then in OBS add a **macOS Screen Capture / Window Capture** source, select the **VanishCam** window, then click **Start Virtual Camera** in OBS and pick "OBS Virtual Camera" in your call app.

**Direct virtual camera:** install OBS Studio 30+, open it once and click **Start Virtual Camera** (this installs the macOS camera extension; approve it in System Settings if asked), then **Stop Virtual Camera** and quit OBS. Now run `./start_mac.command --virtual-camera` — VanishCam sends its output to "OBS Virtual Camera".

## Troubleshooting (Mac)

- **"Webcam 0 not available"** → camera permission for Terminal (see step 4), or another app (FaceTime, Zoom, Photo Booth) is using the camera. Try `--list-cameras` and `--camera 1`.
- **Gesture never triggers** → run with `--gesture-debug`. `face=no` means the face isn't visible enough; `hands=0` means the hand isn't detected (more light, keep the hand inside the frame); `pose=False` with both found means the fingers aren't straight/together or not close enough to the forehead.
- **"Python quit unexpectedly" / "Check failed: service_ Service is unavailable"** → that is newer MediaPipe (0.10.30+) on Mac; this folder pins 0.10.21, which works. Delete `.venv-mac` and start again if you still see it.
- **Python version** → MediaPipe 0.10.21 needs Python 3.9–3.12 (3.12 recommended). The launcher picks one automatically.
- **Reset everything** → delete the `.venv-mac` folder and start again.

## Windows

The original Windows launchers are still here (`AVVIA_LOCALE.bat`, `AVVIA_OBS.bat`, `AVVIA_VIRTUAL.bat`), or run directly:

```powershell
py -3 -m venv .venv && .venv\Scripts\pip install -r requirements.txt pyvirtualcam
.venv\Scripts\python vanish_cam.py --mode goku
```

## Files

- `vanish_cam.py` — the app (menu, camera, background capture, all modes)
- `goku_effect.py` — Goku gesture detection, hold timer, teleport animation, teleport sound generator
- `naruto_effect.py` — Naruto smoke + log substitution
- `vanish_sound.py` — non-blocking sound playback (`afplay` on macOS)
- `hud.py` — on-screen tips in the preview window
- `macos_app.py` — Mac app niceties (Dock icon, window focus, quit on close)
- `Install VanishCam.command` — builds and installs `VanishCam.app`
- `launcher.c` — tiny compiled starter for the app (needed so macOS shows the camera permission pop-up for VanishCam)
- `hand_landmarker.task`, `face_landmarker.task` — MediaPipe models; `models/` gets the rest on first run
- `test_goku_effect.py` — tests: `.venv-mac/bin/python -m unittest test_goku_effect`

## Visual assets & credits

All effects are drawn in code — no anime frames or sprites are included. The wooden log (`assets/substitution_log.png`) is an original illustration; smoke and the Goku light/speed lines are procedural. Goku mode uses MediaPipe's Face Landmarker (forehead position) and Hand Landmarker (fingers).

Original VanishCam project: if you like it you can support the original author - https://github.com/Nicovic17
