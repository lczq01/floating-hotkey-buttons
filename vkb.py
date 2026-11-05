# -*- coding: utf-8 -*-
"""悬浮快捷键按钮 V1（依据 PRD V3.1 · 独立小窗形态）
出厂单个「按钮1」，右键菜单完成全部管理：编辑/新增按钮/删除/收入库/最小化/退出全部。
每个按钮是独立的置顶不夺焦小窗：闲置半透明 0.6、悬停 0.95，
主体拖动=移动、原地松开=点击发送按键、右下角隐形手柄拖动=缩放。
按钮库：右键收入库，右下角库图标取出/删除存件。
运行: pythonw vkb.py
"""
import ctypes
import json
import os
import tkinter as tk
from ctypes import wintypes
from tkinter import messagebox

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

user32 = ctypes.windll.user32

# ---------------- Win32 按键模拟 ----------------
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
ULONG_PTR = ctypes.c_size_t

WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
GWL_EXSTYLE = -20


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]
    _anonymous_ = ("_u",)
    _fields_ = [("type", wintypes.DWORD), ("_u", _U)]


MOD_VK = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10}
MOD_ORDER = ["ctrl", "alt", "shift"]
MOD_NAME = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift"}

SPECIAL_KEYS = {
    "Return": (0x0D, "回车", False), "BackSpace": (0x08, "退格", False),
    "Tab": (0x09, "Tab", False), "Delete": (0x2E, "Del", True),
    "space": (0x20, "空格", False), "Home": (0x24, "Home", True),
    "End": (0x23, "End", True), "Prior": (0x21, "PgUp", True),
    "Next": (0x22, "PgDn", True), "Left": (0x25, "←", True),
    "Up": (0x26, "↑", True), "Right": (0x27, "→", True),
    "Down": (0x28, "↓", True), "Insert": (0x2D, "Ins", True),
    "Print": (0x2C, "PrtSc", False), "Pause": (0x13, "Pause", False),
    "Caps_Lock": (0x14, "CapsLk", False),
}
MODIFIER_KEYSYMS = {"Shift_L", "Shift_R", "Control_L", "Control_R",
                    "Alt_L", "Alt_R", "Meta_L", "Meta_R", "Win_L", "Win_R"}

# ---------------- 低层键盘钩子（录制用，抢在全局热键拦截之前捕获按键） ----------------
WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
LLRESULT = ctypes.c_ssize_t
LLHOOKPROC = ctypes.WINFUNCTYPE(LLRESULT, ctypes.c_int, wintypes.WPARAM,
                                wintypes.LPARAM)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


# 修饰键 VK（按下时只记录状态，不当功能键）
VK_MODIFIERS = {0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5}
VK_WIN = {0x5B, 0x5C}

VK_TO_KEYSYM = {v[0]: k for k, v in SPECIAL_KEYS.items()}
for _i in range(1, 13):
    VK_TO_KEYSYM[0x6F + _i] = f"F{_i}"
for _i in range(26):
    VK_TO_KEYSYM[0x41 + _i] = chr(ord("a") + _i)
for _i in range(10):
    VK_TO_KEYSYM[0x30 + _i] = str(_i)
VK_TO_KEYSYM.update({0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-",
                     0xBE: ".", 0xBF: "/", 0xC0: "`", 0xDB: "[",
                     0xDC: "\\", 0xDD: "]", 0xDE: "'"})


def keysym_info(ks):
    if ks in SPECIAL_KEYS:
        return SPECIAL_KEYS[ks]
    if ks.startswith("F") and ks[1:].isdigit() and 1 <= int(ks[1:]) <= 12:
        n = int(ks[1:])
        return (0x6F + n, ks, False)
    if len(ks) == 1:
        c = ks.upper()
        if c.isdigit():
            return (ord(c), c, False)
        if "A" <= c <= "Z":
            return (ord(c), c, False)
        r = user32.VkKeyScanW(ord(ks))
        if r != -1:
            return (r & 0xFF, ks, False)
    return None


def binding_display(b):
    mods = "+".join(MOD_NAME[m] for m in MOD_ORDER if m in b.get("mods", []))
    info = keysym_info(b["key"]) if b.get("key") else None
    if not info:
        return "（未绑定）"
    key_disp = info[1]
    return (mods + " + " + key_disp) if mods else key_disp


# 文字输入支持：中文/英文键名 → Tk keysym
CN_KEY_NAMES = {
    "回车": "Return", "退格": "BackSpace", "空格": "space", "删除": "Delete",
    "tab": "Tab", "home": "Home", "end": "End",
    "pgup": "Prior", "pgdn": "Next", "上翻": "Prior", "下翻": "Next",
    "上": "Up", "下": "Down", "左": "Left", "右": "Right",
    "↑": "Up", "↓": "Down", "←": "Left", "→": "Right",
    "插入": "Insert", "ins": "Insert", "prtsc": "Print", "printscreen": "Print",
    "pause": "Pause", "capslock": "Caps_Lock", "capslk": "Caps_Lock",
}


def parse_binding(text):
    """解析 "Ctrl+Shift+S" / "回车" / "F5" 等文字为 {"mods": [...], "key": ks}。"""
    parts = [p.strip() for p in text.split("+") if p.strip()]
    if not parts:
        return None
    mods = []
    for p in parts[:-1]:
        m = p.lower()
        if m in MOD_VK and m not in mods:
            mods.append(m)
        else:
            return None
    raw = parts[-1].lower()
    ks = CN_KEY_NAMES.get(raw)
    if ks is None and raw not in CN_KEY_NAMES:
        for cand in (raw, raw.capitalize()):  # return→Return, f5→F5, a→a
            if keysym_info(cand):
                ks = cand
                break
    if ks is None or keysym_info(ks) is None:
        return None
    return {"mods": mods, "key": ks}


def press_combo(mods, keysym):
    info = keysym_info(keysym)
    if not info:
        return False
    vk, _, ext = info
    seq = [(MOD_VK[m], False, False) for m in MOD_ORDER if m in mods]
    seq.append((vk, False, ext))
    seq.append((vk, True, ext))
    seq += [(MOD_VK[m], True, False) for m in reversed(MOD_ORDER) if m in mods]
    arr = (INPUT * len(seq))()
    for i, (v, up, e) in enumerate(seq):
        flags = (KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if e else 0)
        arr[i].type = INPUT_KEYBOARD
        arr[i].ki = KEYBDINPUT(v, 0, flags, 0, 0)
    n = user32.SendInput(len(seq), arr, ctypes.sizeof(INPUT))
    if n != len(seq):
        print(f"[vkb] SendInput 失败: 注入 {n}/{len(seq)}", flush=True)
    return n == len(seq)


def set_noactivate(win):
    win.update_idletasks()
    hwnd = win.winfo_id()
    while True:
        p = user32.GetParent(hwnd)
        if not p:
            break
        hwnd = p
    getter = getattr(user32, "GetWindowLongPtrW", None)
    setter = getattr(user32, "SetWindowLongPtrW", None)
    style_flags = WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
    if getter and setter:
        setter(hwnd, GWL_EXSTYLE, getter(hwnd, GWL_EXSTYLE) | style_flags)
    else:
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                              user32.GetWindowLongW(hwnd, GWL_EXSTYLE) | style_flags)


def clamp(v, lo, hi):
    return max(lo, min(v, hi))


# ---------------- 配置 ----------------
W_MIN, W_MAX, H_MIN, H_MAX = 40, 200, 24, 120   # V3.1: 最小 40x24
DEFAULT_W, DEFAULT_H = 96, 36
ALPHA_IDLE, ALPHA_HOVER = 0.6, 0.95             # V3.1: 闲置 0.6 / 悬停 0.95
GRIP_SIZE = 12                                   # 隐形缩放手柄热区
FONT_MIN, FONT_MAX = 7, 26                       # V3.1: 字号下限 7
FACTORY_TEXT = "按钮1"

EXAMPLES = [
    ("复制", ["ctrl"], "c"), ("粘贴", ["ctrl"], "v"), ("剪切", ["ctrl"], "x"),
    ("全选", ["ctrl"], "a"), ("撤销", ["ctrl"], "z"), ("回车", [], "Return"),
    ("退格", [], "BackSpace"), ("删除", [], "Delete"), ("F1", [], "F1"),
    ("F5", [], "F5"),
]


def load_config():
    """返回按钮列表（含 stored 标记）。损坏/缺失回退 []（由调用方补出厂按钮）。"""
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            d = json.load(f)
        btns = d.get("buttons") if isinstance(d, dict) else None
        if not isinstance(btns, list):
            return []
        clean = []
        for b in btns:
            if not (isinstance(b, dict) and "text" in b):
                continue
            key = b.get("key")
            if key is not None and keysym_info(key) is None:
                continue
            clean.append({
                "text": str(b["text"])[:6],
                "mods": [m for m in b.get("mods", []) if m in MOD_VK],
                "key": key,
                "x": b.get("x") if isinstance(b.get("x"), int) else None,
                "y": b.get("y") if isinstance(b.get("y"), int) else None,
                "w": clamp(int(b.get("w") or DEFAULT_W), W_MIN, W_MAX),
                "h": clamp(int(b.get("h") or DEFAULT_H), H_MIN, H_MAX),
                "stored": bool(b.get("stored")),
            })
        return clean
    except Exception:
        return []


# ---------------- 编辑对话框（可激活窗口，用于按键录制） ----------------
class EditDialog(tk.Toplevel):
    BG = "#2b2f36"
    FG = "#e8eaed"

    def __init__(self, data=None, on_save=None, show_examples=False,
                 on_examples=None):
        super().__init__()
        self.title("编辑按钮")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(bg=self.BG)
        self.on_save = on_save
        self.on_examples = on_examples
        self.result = dict(data) if data and data.get("key") else None
        self.recording = False
        self._hook = None
        self._hook_proc = None

        top = tk.Frame(self, bg=self.BG)
        top.pack(fill="x", padx=12, pady=(12, 4))
        tk.Label(top, text="显示文字", bg=self.BG, fg=self.FG).pack(side="left")
        vcmd = (self.register(lambda s: len(s) <= 6), "%P")
        self.ent = tk.Entry(top, width=10, validate="key", validatecommand=vcmd,
                            relief="flat", bg="#3a4048", fg=self.FG,
                            insertbackground=self.FG)
        self.ent.pack(side="left", padx=8)
        if data:
            self.ent.insert(0, data["text"])

        mid = tk.Frame(self, bg=self.BG)
        mid.pack(fill="x", padx=12, pady=4)
        tk.Label(mid, text="绑定按键", bg=self.BG, fg=self.FG).pack(side="left")
        self.lbl = tk.Label(mid, text="", bg="#3a4048", fg=self.FG, width=16,
                            relief="flat", padx=6, pady=3)
        self.lbl.pack(side="left", padx=8)
        self.btn_rec = tk.Button(mid, text="录制", width=6, relief="flat",
                                 bg="#4a525c", fg=self.FG,
                                 command=self.toggle_record)
        self.btn_rec.pack(side="left")
        tk.Button(mid, text="清除", width=6, relief="flat", bg="#4a525c",
                  fg=self.FG, command=self.clear_binding).pack(side="left", padx=(4, 0))

        # 文字输入定义：Ctrl+C / 回车 / F5 等，即时校验
        mid2 = tk.Frame(self, bg=self.BG)
        mid2.pack(fill="x", padx=12, pady=4)
        tk.Label(mid2, text="文字输入", bg=self.BG, fg=self.FG).pack(side="left")
        self.ent_key = tk.Entry(mid2, width=16, relief="flat", bg="#3a4048",
                                fg=self.FG, insertbackground=self.FG)
        self.ent_key.pack(side="left", padx=8)
        self.ent_key.bind("<KeyRelease>", self.on_text)

        self.hint = tk.Label(self, text="点「录制」后按键，或在下方输入如 Ctrl+C / 回车 / F5",
                             bg=self.BG, fg="#8a919c")
        self.hint.pack(fill="x", padx=12)

        bottom = tk.Frame(self, bg=self.BG)
        bottom.pack(fill="x", padx=12, pady=(6, 12))
        tk.Button(bottom, text="保存", width=8, relief="flat", bg="#2d7d46",
                  fg="white", command=self.save).pack(side="right")
        tk.Button(bottom, text="取消", width=8, relief="flat", bg="#4a525c",
                  fg=self.FG, command=self.destroy).pack(side="right", padx=(0, 6))
        if show_examples:
            tk.Button(bottom, text="加载示例", width=10, relief="flat",
                      bg="#8ab4f8", fg="#1f2328",
                      command=self.load_examples).pack(side="left")

        self.bind("<KeyPress>", self.on_key)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.refresh()
        self._center()
        self.ent.focus_set()

    def destroy(self):
        self._remove_hook()
        super().destroy()

    def _center(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    def refresh(self):
        self.lbl.config(
            text=binding_display({"mods": self.result["mods"], "key": self.result["key"]})
            if self.result else "（未绑定）")
        self.btn_rec.config(text="取消" if self.recording else "录制")
        state = "disabled" if self.recording else "normal"
        self.ent.config(state=state)
        self.ent_key.config(state=state)

    def set_key_text(self, s):
        """回填文字输入框（程序写入不触发 KeyRelease）。"""
        self.ent_key.delete(0, "end")
        self.ent_key.insert(0, s)

    def on_text(self, e):
        if self.recording:
            return
        text = self.ent_key.get().strip()
        if not text:
            self.hint.config(text="点「录制」后按键，或输入如 Ctrl+C / 回车 / F5",
                             fg="#8a919c")
            return
        b = parse_binding(text)
        if b:
            self.result = b
            self.hint.config(text="已识别：" + binding_display(b), fg="#5cb86a")
        else:
            self.hint.config(text="无法识别，格式如 Ctrl+Shift+S / 回车 / F5",
                             fg="#e06c5a")
        self.refresh()

    def toggle_record(self):
        self.recording = not self.recording
        if self.recording:
            self.hint.config(text="按下按键…（Esc 结束录制）", fg="#e8b34c")
            self.focus_force()
            self._install_hook()
        else:
            self._stop_recording("点击「录制」后按下要绑定的按键", "#8a919c")
        self.refresh()

    # ---- 低层钩子录制：其他软件的全局热键拦不住它 ----
    def _install_hook(self):
        self._hook_proc = LLHOOKPROC(self._hook_cb)
        h = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._hook_proc, None, 0)
        if not h:
            # 钩子安装失败 → 退回 Tk 焦点捕获（on_key 仍有效）
            self._hook = None
            self.hint.config(text="按下按键…（若被其他软件拦截请换用组合键）",
                             fg="#e8b34c")
        else:
            self._hook = h

    def _remove_hook(self):
        if self._hook:
            user32.UnhookWindowsHookEx(self._hook)
            self._hook = None
        self._hook_proc = None

    def _hook_cb(self, nCode, wparam, lparam):
        try:
            if nCode == HC_ACTION and wparam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                vk = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)
                                 ).contents.vkCode
                self.after_idle(self._hook_handle_key, vk)
                return 1  # 吞掉按键，防止其他软件的全局热键被触发
            return user32.CallNextHookEx(0, nCode, wparam, lparam)
        except Exception:
            return user32.CallNextHookEx(0, nCode, wparam, lparam)

    def _hook_handle_key(self, vk):
        if not self.recording:
            return
        if vk == 0x1B:  # Esc 结束录制
            self._stop_recording("已结束录制", "#8a919c")
            self.refresh()
            return
        if vk in VK_WIN:
            self.hint.config(text="不支持绑定 Win 键", fg="#e06c5a")
            return
        if vk in VK_MODIFIERS:
            return
        mods = []
        g = user32.GetAsyncKeyState
        if g(0x11) & 0x8000:
            mods.append("ctrl")
        if g(0x12) & 0x8000:
            mods.append("alt")
        if g(0x10) & 0x8000:
            mods.append("shift")
        ks = VK_TO_KEYSYM.get(vk)
        if ks is None or keysym_info(ks) is None:
            self.hint.config(text="无法识别该按键，换一个试试", fg="#e06c5a")
            return
        self.result = {"mods": mods, "key": ks}
        self.set_key_text(binding_display(self.result))
        self._stop_recording("已捕获：" + binding_display(self.result), "#5cb86a")
        self.refresh()

    def _stop_recording(self, text, color):
        self.recording = False
        self._remove_hook()
        self.hint.config(text=text, fg=color)

    def clear_binding(self):
        self.result = None
        self.ent_key.delete(0, "end")
        self.hint.config(text="点「录制」后按键，或输入如 Ctrl+C / 回车 / F5", fg="#8a919c")
        self.refresh()

    def load_examples(self):
        if self.on_examples and messagebox.askyesno(
                "加载示例", "将生成 10 个常用按键按钮（未绑定的当前按钮会被移除），继续？",
                parent=self):
            self.on_examples()
            self.destroy()

    def on_key(self, e):
        if not self.recording:
            return
        if self._hook:  # 钩子模式下按键已由钩子处理
            return
        if e.keysym == "Escape":
            self.recording = False
            self.hint.config(text="已结束录制", fg="#8a919c")
            self.refresh()
            return
        if e.keysym in MODIFIER_KEYSYMS:
            return
        # GetAsyncKeyState 读物理状态，规避 tk e.state 误报（如 F1 带出 Alt）
        g = user32.GetAsyncKeyState
        if (g(0x5B) & 0x8000) or (g(0x5C) & 0x8000):
            self.hint.config(text="不支持绑定 Win 键", fg="#e06c5a")
            return
        mods = []
        if g(0x11) & 0x8000:
            mods.append("ctrl")
        if g(0x12) & 0x8000:
            mods.append("alt")
        if g(0x10) & 0x8000:
            mods.append("shift")
        if keysym_info(e.keysym) is None:
            self.hint.config(text="无法识别该按键，换一个试试", fg="#e06c5a")
            return
        self.result = {"mods": mods, "key": e.keysym}
        self.recording = False
        self.set_key_text(binding_display(self.result))
        self.hint.config(text="已捕获：" + binding_display(self.result), fg="#5cb86a")
        self.refresh()

    def save(self):
        if not self.result:
            messagebox.showwarning("提示", "请先录制要绑定的按键", parent=self)
            return
        text = self.ent.get().strip()
        if not text:
            info = keysym_info(self.result["key"])
            text = info[1] if info else "按钮"
        if self.on_save:
            self.on_save({"text": text, "mods": self.result["mods"],
                          "key": self.result["key"]})
        self.destroy()


# ---------------- 独立按钮小窗 ----------------
class ButtonWin:
    BG = "#2b2f36"
    FG = "#e8eaed"
    BTN = "#3a4048"
    BTN_ACTIVE = "#556070"
    MOVE_THRESHOLD = 5  # px，超过则判定为拖动

    def __init__(self, app, data):
        self.app = app
        self.data = data
        self.win = tk.Toplevel(app.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", ALPHA_IDLE)
        self.win.configure(bg=self.BG)
        self.lbl = tk.Label(self.win, text=data["text"], bg=self.BTN, fg=self.FG,
                            padx=6, pady=2)
        self.lbl.pack(fill="both", expand=True)
        # V3.1: 隐形缩放手柄——与按钮同色不可见，悬停该角落显示缩放光标
        self.grip = tk.Label(self.win, text="", bg=self.BTN,
                             cursor="size_nw_se")
        self.grip.place(relx=1.0, rely=1.0, anchor="se",
                        width=GRIP_SIZE, height=GRIP_SIZE)
        # 三手势：主体拖=移动 / 手柄拖=缩放 / 原地松开=点击发送
        self.lbl.bind("<Button-1>", self._press)
        self.lbl.bind("<B1-Motion>", self._motion)
        self.lbl.bind("<ButtonRelease-1>", self._release)
        self.lbl.bind("<Button-3>", self._menu)
        self.grip.bind("<Button-1>", self._rs_press)
        self.grip.bind("<B1-Motion>", self._rs_motion)
        self.grip.bind("<ButtonRelease-1>", lambda e: self.app.save())
        # V3.1: 透明度 闲置 0.6 / 悬停 0.95
        self.win.bind("<Enter>", lambda e: self.win.attributes("-alpha", ALPHA_HOVER))
        self.win.bind("<Leave>", lambda e: self.win.attributes("-alpha", ALPHA_IDLE))
        self.apply_geometry()
        self.win.update()
        set_noactivate(self.win)

    def apply_geometry(self):
        d = self.data
        d["w"] = clamp(d["w"], W_MIN, W_MAX)
        d["h"] = clamp(d["h"], H_MIN, H_MAX)
        self.win.geometry(f"{d['w']}x{d['h']}+{d['x']}+{d['y']}")
        font = max(FONT_MIN, min(FONT_MAX,
                                 int(d["h"] * 0.45), int(d["w"] * 0.35)))
        self.lbl.config(text=d["text"], font=("", font))

    # ---- 移动 / 点击 ----
    def _press(self, e):
        self._sx, self._sy = e.x_root, e.y_root
        self._ox, self._oy = self.data["x"], self.data["y"]
        self._moved = False

    def _motion(self, e):
        dx, dy = e.x_root - self._sx, e.y_root - self._sy
        if not self._moved and abs(dx) + abs(dy) > self.MOVE_THRESHOLD:
            self._moved = True
        if self._moved:
            self.data["x"] = self._ox + dx
            self.data["y"] = self._oy + dy
            self.win.geometry(f"+{self.data['x']}+{self.data['y']}")

    def _release(self, e):
        if self._moved:
            self.app.save()
        else:
            self.send()

    # ---- 缩放 ----
    def _rs_press(self, e):
        self._rw, self._rh = self.data["w"], self.data["h"]
        self._rx, self._ry = e.x_root, e.y_root

    def _rs_motion(self, e):
        self.data["w"] = clamp(self._rw + (e.x_root - self._rx), W_MIN, W_MAX)
        self.data["h"] = clamp(self._rh + (e.y_root - self._ry), H_MIN, H_MAX)
        self.apply_geometry()

    # ---- 发送 ----
    def send(self):
        d = self.data
        if not d.get("key"):  # 未绑定按钮：点击直接进编辑
            self.edit()
            return
        if press_combo(d["mods"], d["key"]):
            self.lbl.config(bg=self.BTN_ACTIVE)
            self.lbl.after(120, lambda: self.lbl.config(bg=self.BTN))
        else:
            messagebox.showwarning("提示", f"按键无法识别：{d['key']}")

    # ---- 右键菜单 ----
    def _menu(self, e):
        m = tk.Menu(self.win, tearoff=0)
        m.add_command(label="编辑", command=self.edit)
        m.add_command(label="新增按钮",
                      command=lambda: self.app.add_button(near=self.data))
        m.add_command(label="删除", command=self.delete)
        m.add_command(label="收入库", command=self.store)
        m.add_separator()
        m.add_command(label="最小化", command=self.app.minimize_all)
        m.add_command(label="退出全部", command=self.app.quit)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()  # 释放独占抓取，点菜单外任意处即可关闭

    def edit(self):
        EditDialog(self.data, on_save=self._on_saved,
                   show_examples=self.app.is_factory(self),
                   on_examples=self.app.load_examples)

    def _on_saved(self, d):
        self.data.update(d)
        self.apply_geometry()
        self.app.save()

    def delete(self):
        if not messagebox.askyesno("确认删除",
                                   f"确定删除按钮「{self.data['text']}」？"):
            return
        self.app.remove(self)

    def store(self):
        self.app.store_button(self)


# ---------------- 按钮库图标与列表 ----------------
class LibraryIcon:
    """桌面右下角库图标：空库半隐、有存件常显，点击弹出存件列表。"""

    SIZE = 28

    def __init__(self, app):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="#2b2f36")
        self.lbl = tk.Label(self.win, text="库", bg="#2b2f36", fg="#e8eaed",
                            font=("", 11))
        self.lbl.pack(fill="both", expand=True)
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.x, self.y = sw - 56, sh - 150   # 与最小化圆点（右下更低处）错开
        self.win.geometry(f"{self.SIZE}x{self.SIZE}+{self.x}+{self.y}")
        self.lbl.bind("<Button-1>", self._open)
        self.win.bind("<Enter>", lambda e: self.win.attributes("-alpha", 0.95))
        self.win.bind("<Leave>", lambda e: self.refresh())
        self.win.update()
        set_noactivate(self.win)
        self.refresh()

    def refresh(self):
        """空库半隐（0.35）、有存件常显（0.9）。"""
        self.win.attributes("-alpha", 0.9 if self.app.stored else 0.35)

    def _open(self, e):
        self.app.open_library()


class LibraryList(tk.Toplevel):
    """存件列表（普通可激活窗口）：点项取出，亦可删除存件。"""

    BG = "#2b2f36"
    FG = "#e8eaed"

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.title("按钮库")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(bg=self.BG)
        self.body = tk.Frame(self, bg=self.BG)
        self.body.pack(fill="both", expand=True, padx=10, pady=10)
        self.refresh()

    def refresh(self):
        for w in self.body.winfo_children():
            w.destroy()
        if not self.app.stored:
            tk.Label(self.body, text="库为空", bg=self.BG, fg="#8a919c",
                     padx=16, pady=8).pack()
        else:
            for d in list(self.app.stored):
                row = tk.Frame(self.body, bg=self.BG)
                row.pack(fill="x", pady=2)
                binding = binding_display(d)
                tk.Button(row, text=f"{d['text']}（{binding}）取回", anchor="w",
                          relief="flat", bg="#3a4048", fg=self.FG,
                          padx=8, pady=3,
                          command=lambda d=d: self.app.restore_button(d)
                          ).pack(side="left", fill="x", expand=True)
                tk.Button(row, text="删除", relief="flat", bg="#5a3634",
                          fg=self.FG, padx=8, pady=3,
                          command=lambda d=d: self.delete_stored(d)
                          ).pack(side="left", padx=(6, 0))
        self.update_idletasks()
        self.geometry(f"+{self.app.lib.x - self.winfo_reqwidth() - 8} "
                      f"+{self.app.lib.y}")

    def delete_stored(self, d):
        if messagebox.askyesno("确认删除",
                               f"确定删除库中的「{d['text']}」？", parent=self):
            self.app.remove_stored(d)


# ---------------- 应用 ----------------
class App:
    def __init__(self):
        self.btns = []
        self.stored = []
        self.dot = None
        self.lib = None
        self.lib_list = None
        self.root = tk.Tk()
        self.root.withdraw()
        data_list = load_config()
        # 修复：按 stored 标记分流，入库按钮不再回流到桌面
        self.stored, visible = [], []
        for d in data_list:
            (self.stored if d.pop("stored", False) else visible).append(d)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        if not visible:  # 出厂状态：单个「按钮1」（库存不影响出厂按钮）
            visible = [{"text": FACTORY_TEXT, "mods": [], "key": None,
                        "x": (sw - DEFAULT_W) // 2, "y": (sh - DEFAULT_H) // 2,
                        "w": DEFAULT_W, "h": DEFAULT_H}]
        else:  # 迁移：无坐标的按钮平铺摆放并做屏内校验
            bx, by = int(sw * 0.6), int(sh * 0.25)
            for b in visible:
                if b["x"] is None:
                    b["x"], b["y"] = bx, by
                    bx += b["w"] + 8
                    if bx > sw - b["w"] - 20:
                        bx, by = int(sw * 0.6), by + b["h"] + 8
                b["x"] = clamp(b["x"], -b["w"] + 40, sw - 40)
                b["y"] = clamp(b["y"], -b["h"] + 40, sh - 40)
        for d in visible:
            self.btns.append(ButtonWin(self, d))
        self.lib = LibraryIcon(self)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.mainloop()

    def is_factory(self, bw):
        """出厂态：只有一个按钮且未绑定过，此时编辑框提供"加载示例" """
        return (len(self.btns) == 1 and self.btns[0] is bw
                and not bw.data.get("key")
                and bw.data["text"] == FACTORY_TEXT)

    def add_button(self, near=None):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        if near:
            x, y = near["x"] + 30, near["y"] + 30
        else:
            x, y = sw // 2, sh // 2
        x = clamp(x, 10, sw - DEFAULT_W - 10)
        y = clamp(y, 10, sh - DEFAULT_H - 10)
        d = {"text": FACTORY_TEXT, "mods": [], "key": None,
             "x": x, "y": y, "w": DEFAULT_W, "h": DEFAULT_H}
        bw = ButtonWin(self, d)
        self.btns.append(bw)
        bw.edit()
        self.save()

    def remove(self, bw):
        self.btns.remove(bw)
        bw.win.destroy()
        if not self.btns:  # 删到最后一个 → 程序退出，下次回出厂态
            self.quit()
        else:
            self.save()

    # ---- 按钮库 ----
    def store_button(self, bw):
        """收入库：从桌面消失，位置/大小/绑定全部保留。"""
        self.btns.remove(bw)
        bw.win.destroy()
        bw.data["stored"] = True
        self.stored.append(bw.data)
        self.save()
        self.lib.refresh()
        if self.lib_list:
            self.lib_list.refresh()

    def restore_button(self, d):
        """取出：出现在库图标旁偏移处，越界回屏内。"""
        self.stored.remove(d)
        d["stored"] = False
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        d["x"] = clamp(self.lib.x - d["w"] - 8, 10, sw - d["w"] - 10)
        d["y"] = clamp(self.lib.y, 10, sh - d["h"] - 10)
        self.btns.append(ButtonWin(self, d))
        self.save()
        self.lib.refresh()
        if self.lib_list:
            if self.stored:
                self.lib_list.refresh()
            else:
                self.close_library()

    def remove_stored(self, d):
        self.stored.remove(d)
        self.save()
        self.lib.refresh()
        if self.lib_list:
            if self.stored:
                self.lib_list.refresh()
            else:
                self.close_library()

    def open_library(self):
        if self.lib_list:
            self.lib_list.lift()
            return
        self.lib_list = LibraryList(self)
        self.lib_list.protocol("WM_DELETE_WINDOW", self.close_library)

    def close_library(self):
        if self.lib_list:
            self.lib_list.destroy()
            self.lib_list = None

    def load_examples(self):
        # 出厂按钮无绑定 → 移除，生成 10 个示例
        if self.btns and self.is_factory(self.btns[0]):
            self.btns[0].win.destroy()
            self.btns.clear()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        bx, by = (sw - 3 * (DEFAULT_W + 8)) // 2, (sh - 2 * (DEFAULT_H + 8)) // 2
        for i, (t, mods, key) in enumerate(EXAMPLES):
            r, c = divmod(i, 3)
            d = {"text": t, "mods": mods, "key": key,
                 "x": bx + c * (DEFAULT_W + 8), "y": by + r * (DEFAULT_H + 8),
                 "w": DEFAULT_W, "h": DEFAULT_H}
            self.btns.append(ButtonWin(self, d))
        self.save()

    def minimize_all(self):
        self.save()
        self.close_library()
        for b in self.btns:
            b.win.withdraw()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.dot = tk.Toplevel(self.root)
        self.dot.overrideredirect(True)
        self.dot.attributes("-topmost", True)
        self.dot.attributes("-alpha", 0.8)
        self.dot.geometry(f"30x30+{sw - 56}+{sh - 112}")
        tk.Label(self.dot, text="＋", bg="#2b2f36", fg="#e8eaed",
                 font=("", 13)).pack(fill="both", expand=True)
        self.dot.bind("<Button-1>", lambda e: self.restore_all())
        self.dot.update()
        set_noactivate(self.dot)

    def restore_all(self):
        if self.dot:
            self.dot.destroy()
            self.dot = None
        for b in self.btns:
            b.win.deiconify()

    def quit(self):
        self.save()
        self.root.destroy()

    def save(self):
        try:
            items = [b.data for b in self.btns]
            items += [dict(d, stored=True) for d in self.stored]
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"buttons": items}, f, ensure_ascii=False, indent=2)
        except OSError:
            pass


if __name__ == "__main__":
    App()
