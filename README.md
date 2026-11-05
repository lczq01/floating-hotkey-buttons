# Floating Hotkey Buttons

[English](README.md) | [简体中文](README.zh-CN.md)

A Windows desktop utility that turns your frequently used keys — combos, function keys, special keys — into small floating buttons. Drag them anywhere, click to send the keystroke. Great for touch screens, pen tablets, one-handed use, or simply saving your fingers from awkward combos.

Built with Python + Tkinter standard library only. **Zero third-party dependencies** — no install needed.

## Features

- **Independent floating windows**: each button is a topmost, click-through-focus-free window that never steals input focus
- **Elegant transparency**: idle at 0.6 alpha, 0.95 on hover
- **Three gestures**:
  - Drag the body = move (release in place = click/send)
  - Drag the invisible bottom-right handle = resize (40×24 ~ 200×120, font auto-scales)
  - Right-click = menu (edit / add / delete / store to library / minimize / quit)
- **Two ways to bind keys**:
  - Record: click "Record" and press the key combo (captured via a low-level keyboard hook, immune to other apps' global hotkey interception)
  - Type it: enter `Ctrl+Shift+S`, `Enter`, `F5`, `←` etc. with instant validation
- **Button library**: right-click → "Store" tucks a button into the library icon at the bottom-right corner; restore it anytime with position/size/binding intact
- **Persistence**: all buttons (including stored ones) auto-save to `config.json` and survive restarts
- **Minimize**: collapse all buttons into a tiny dot at the bottom-right corner

## Getting Started

Requirements: Windows 10/11 + Python 3.8+ (standard library only)

```bat
pythonw vkb.py
```

Or simply double-click `启动悬浮键盘.bat` (launch script).

On first run a single "按钮1" button appears at screen center. Right-click it to edit the binding, or load 10 ready-made example buttons (copy / paste / cut / undo / enter / backspace / delete / F1 / F5).

## Configuration

`config.json` lives next to the script and is maintained automatically:

```json
{
  "buttons": [
    {
      "text": "复制",          // button label (≤6 chars)
      "mods": ["ctrl"],        // modifiers: ctrl / alt / shift
      "key": "c",              // main key (Tk keysym)
      "x": 1147, "y": 593,     // screen position
      "w": 60, "h": 36,        // button size
      "stored": false          // true = kept in the library
    }
  ]
}
```

## Known Limitations

- The Win key and Esc key cannot be bound
- Keystrokes cannot be sent to elevated (admin) windows
- While recording, all system key input is temporarily intercepted (Esc ends recording)

## Design Docs

- [悬浮式虚拟键盘 PRD V2.1](悬浮式虚拟键盘PRD-V2.1.md) (Chinese)
- [悬浮快捷键按钮 PRD V3](悬浮快捷键按钮PRD-V3.md) (Chinese)
