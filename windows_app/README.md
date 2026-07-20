# Magic 1v1 for Windows

This folder builds the same Python rules and web interface as the macOS app
into a self-contained Windows application. Players do not need Python.

## Supported release target

- 64-bit Windows 10 and Windows 11
- Windows 11 on ARM through Microsoft's x64 application emulation
- Microsoft Edge WebView2 Runtime, included with Windows 11 and almost all
  supported Windows 10 installations

Windows 7, Windows 8, 32-bit Windows, and native Windows ARM64 are not release
targets because the current Python and embedded browser runtimes no longer
provide a dependable modern environment for them.

If Windows reports that WebView2 is missing, install Microsoft's current
Evergreen WebView2 Runtime and reopen the game.

## Build on Windows

Install 64-bit Python 3.11, including the Python Launcher, then double-click
`build_windows.bat`. The script creates:

```text
dist\windows\Magic 1v1\Magic 1v1.exe
dist\windows\Magic 1v1 Windows x64.zip
```

Keep the complete `Magic 1v1` folder together. Distribute the generated ZIP,
not the executable by itself, because the adjacent runtime files are required.

## Automated cloud build

The repository workflow at `.github/workflows/build-windows.yml` performs the
same build on a genuine Windows runner and uploads the portable ZIP as an
artifact. Start it from the GitHub Actions page using **Run workflow**.
