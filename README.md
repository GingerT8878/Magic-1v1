# Magic 1v1 pt2

<!-- This file documents architecture, development startup, packaging, and the
     purpose of each editable source file. Generated build output is omitted. -->

The web version keeps all game rules in Python. Flask sends the Python game state to the HTML interface, and JavaScript only handles button presses, API requests, and graphics.

## Run the game

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 app.py
```

Open `http://127.0.0.1:5050` in a browser.

## Build the Windows app

Windows packaging files live in `windows_app`. A genuine `.exe` must be
compiled on Windows because PyInstaller is not a cross-compiler. On a Windows
computer, double-click `windows_app\build_windows.bat`. Alternatively, run the
included GitHub Actions workflow on a Windows cloud runner.

The output is a self-contained 64-bit Windows 10/11 application and portable
ZIP; players do not need Python installed.

After the project is pushed to GitHub, open the repository's **Actions** tab,
choose **Build Windows app**, and select **Run workflow**. When the run finishes,
download the `Magic-1v1-Windows-x64` artifact and extract the ZIP before opening
`Magic 1v1.exe`. Keep the extracted application folder together.

## Files

- `game_engine.py`: Python combat rules, state, items, spells, and bot.
- `app.py`: Flask routes connecting Python to the browser.
- `templates/index.html`: interface structure.
- `static/styles.css`: interface appearance.
- `static/app.js`: API calls and canvas graphics only.
