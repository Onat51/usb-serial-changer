#!/usr/bin/env python3
"""
USB Birim Seri Numara Değiştirici
Desteklenen dosya sistemleri: FAT12, FAT16, FAT32, NTFS, exFAT
⚠  Yönetici (Administrator) hakları ile çalıştırılmalıdır.
"""

import ctypes
import ctypes.wintypes as wintypes
import struct
import os
import sys
import random
import tkinter as tk
from tkinter import ttk, messagebox

# ════════════════════════════════════════════════════════════════
#  WINDOWS API SABİTLERİ & AYARLARI
# ════════════════════════════════════════════════════════════════

kernel32 = ctypes.windll.kernel32
shell32  = ctypes.windll.shell32

kernel32.CreateFileW.restype  = wintypes.HANDLE
kernel32.SetFilePointer.restype = wintypes.DWORD

GENERIC_READ          = 0x80000000
GENERIC_WRITE         = 0x40000000
FILE_SHARE_READ       = 0x00000001
FILE_SHARE_WRITE      = 0x00000002
OPEN_EXISTING         = 3
FILE_BEGIN            = 0
FSCTL_LOCK_VOLUME     = 0x00090018
FSCTL_UNLOCK_VOLUME   = 0x0009001C
FSCTL_DISMOUNT_VOLUME = 0x00090020
DRIVE_REMOVABLE       = 2
SECTOR                = 512
INVALID_HANDLE        = ctypes.c_void_p(-1).value


# ════════════════════════════════════════════════════════════════
#  YARDIMCI FONKSİYONLAR
# ════════════════════════════════════════════════════════════════

def is_admin() -> bool:
    """Yönetici hakları ile çalışıp çalışmadığını kontrol et."""
    try:
        return bool(shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate():
    """Uygulamayı yönetici olarak yeniden başlat."""
    if getattr(sys, "frozen", False):
        shell32.ShellExecuteW(None, "runas", sys.executable, "", None, 1)
    else:
        script = os.path.abspath(sys.argv[0])
        shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}"', None, 1
        )
    sys.exit(0)


def list_usb_drives():
    """Çıkarılabilir (removable) sürücüleri listele."""
    result = []
    mask = kernel32.GetLogicalDrives()
    for i in range(26):
        if mask & (1 << i):
            letter = chr(65 + i)
            if kernel32.GetDriveTypeW(f"{letter}:\\") == DRIVE_REMOVABLE:
                info = volume_info(letter)
                if info:
                    result.append((letter, info))
    return result


def volume_info(drive: str) -> dict | None:
    """Windows API ile birim bilgilerini oku."""
    vname  = ctypes.create_unicode_buffer(261)
    serial = wintypes.DWORD()
    maxlen = wintypes.DWORD()
    flags  = wintypes.DWORD()
    fsname = ctypes.create_unicode_buffer(261)

    ok = kernel32.GetVolumeInformationW(
        f"{drive}:\\", vname, 261,
        ctypes.byref(serial), ctypes.byref(maxlen),
        ctypes.byref(flags), fsname, 261,
    )
    if not ok:
        return None
    s = serial.value
    return {
        "label":      vname.value or "Etiketsiz",
        "serial":     s,
        "serial_str": f"{(s >> 16) & 0xFFFF:04X}-{s & 0xFFFF:04X}",
        "fs":         fsname.value,
    }


# ════════════════════════════════════════════════════════════════
#  DÜŞÜK SEVİYE DİSK I/O
# ════════════════════════════════════════════════════════════════

def _open_vol(drive: str, write: bool = False):
    access = GENERIC_READ | (GENERIC_WRITE if write else 0)
    h = kernel32.CreateFileW(
        f"\\\\.\\{drive}:", access,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None, OPEN_EXISTING, 0, None,
    )
    if h == INVALID_HANDLE:
        raise OSError(
            f"{drive}: sürücüsü açılamadı  (Windows hata kodu: {kernel32.GetLastError()})"
        )
    return h


def _seek(h, pos: int):
    kernel32.SetFilePointer(h, pos & 0xFFFFFFFF, None, FILE_BEGIN)


def _read(h, n: int) -> bytes:
    buf = ctypes.create_string_buffer(n)
    got = wintypes.DWORD()
    if not kernel32.ReadFile(h, buf, n, ctypes.byref(got), None):
        raise OSError(f"Okuma hatası  (kod: {kernel32.GetLastError()})")
    return buf.raw


def _write_raw(h, data: bytes):
    written = wintypes.DWORD()
    buf = ctypes.create_string_buffer(data)
    if not kernel32.WriteFile(h, buf, len(data), ctypes.byref(written), None):
        raise OSError(f"Yazma hatası  (kod: {kernel32.GetLastError()})")


def read_sectors(drive: str, start_sector: int, count: int) -> bytes:
    """Sektör oku (salt-okunur)."""
    h = _open_vol(drive)
    try:
        _seek(h, start_sector * SECTOR)
        return _read(h, count * SECTOR)
    finally:
        kernel32.CloseHandle(h)


def write_volume(drive: str, writes: list[tuple[int, bytes]]):
    """
    Birime yaz.  writes = [(offset_byte, veri), ...]
    Birimi kilitler → dismount eder → yazar → kilidi açar.
    """
    h = _open_vol(drive, write=True)
    ret = wintypes.DWORD()
    try:
        # — Kilitle —
        if not kernel32.DeviceIoControl(
            h, FSCTL_LOCK_VOLUME, None, 0, None, 0, ctypes.byref(ret), None
        ):
            raise OSError(
                "Hata birim kilitlenemedi. Sürücüyü kullanan tüm programları kapatın."
            )

        # — Dosya sistemini ayır —
        kernel32.DeviceIoControl(
            h, FSCTL_DISMOUNT_VOLUME, None, 0, None, 0, ctypes.byref(ret), None
        )

        # — Yaz —
        for offset, data in writes:
            _seek(h, offset)
            _write_raw(h, data)

        # — Kilidi aç —
        kernel32.DeviceIoControl(
            h, FSCTL_UNLOCK_VOLUME, None, 0, None, 0, ctypes.byref(ret), None
        )
    finally:
        kernel32.CloseHandle(h)


# ════════════════════════════════════════════════════════════════
#  DOSYA SİSTEMİ İŞLEMLERİ
# ════════════════════════════════════════════════════════════════

#  Boot sektöründe seri numaranın konumu  →  (offset, boyut)
SERIAL_MAP = {
    "FAT32": (67, 4),   # 0x43
    "FAT16": (39, 4),   # 0x27
    "FAT12": (39, 4),
    "FAT":   (39, 4),
    "NTFS":  (72, 8),   # 0x48  (64-bit; üst dword = 0 yapılır)
    "EXFAT": (100, 4),  # 0x64
}


def detect_fs(boot: bytes) -> str:
    """Boot sektöründen dosya sistemi türünü algıla."""
    if boot[3:11] == b"EXFAT   ":
        return "EXFAT"
    if boot[3:7] == b"NTFS":
        return "NTFS"
    if boot[82:87] == b"FAT32":
        return "FAT32"
    tag = boot[54:62].strip(b"\x00 ")
    if tag.startswith(b"FAT"):
        return tag.decode("ascii", errors="ignore").strip()
    return "UNKNOWN"


def exfat_checksum(region: bytearray) -> int:
    """exFAT boot bölgesi sağlama toplamı  (sektör 0-10)."""
    csum = 0
    for i in range(11 * SECTOR):
        if i in (106, 107, 112):          # VolumeFlags & PercentInUse atla
            continue
        csum = ((csum << 31) | (csum >> 1)) & 0xFFFFFFFF
        csum = (csum + region[i]) & 0xFFFFFFFF
    return csum


def change_serial(drive: str, new32: int) -> str:
    """
    Seri numarasını değiştir.
    drive  — sürücü harfi ('E' vb.)
    new32  — yeni 32-bit seri numarası
    Döndürür: dosya sistemi adı
    """
    boot = read_sectors(drive, 0, 1)
    fs   = detect_fs(boot)
    key  = fs.upper().replace(" ", "")

    if key not in SERIAL_MAP:
        raise ValueError(f"Desteklenmeyen dosya sistemi: {fs}")

    if key == "EXFAT":
        _change_exfat(drive, new32)
        return "exFAT"

    offset, size = SERIAL_MAP[key]
    data = bytearray(boot)

    if size == 4:
        data[offset : offset + 4] = struct.pack("<I", new32 & 0xFFFFFFFF)
    else:
        # NTFS — 8 bayt; üst dword 0 yapılır → görüntülenen = alt dword
        data[offset : offset + 8] = struct.pack("<Q", new32 & 0xFFFFFFFF)

    write_volume(drive, [(0, bytes(data))])
    return fs


def _change_exfat(drive: str, new32: int):
    """exFAT: ana + yedek boot bölgesini güncelle, checksum'ı yenile."""
    main   = bytearray(read_sectors(drive, 0, 12))
    backup = bytearray(read_sectors(drive, 12, 12))

    ser = struct.pack("<I", new32 & 0xFFFFFFFF)
    main[100:104]   = ser
    backup[100:104] = ser

    for region in (main, backup):
        cs = exfat_checksum(region)
        region[11 * SECTOR : 12 * SECTOR] = struct.pack("<I", cs) * (SECTOR // 4)

    write_volume(drive, [(0, bytes(main)), (12 * SECTOR, bytes(backup))])


# ════════════════════════════════════════════════════════════════
#  RENK PALETİ
# ════════════════════════════════════════════════════════════════

BG      = "#1a1b26"
BG2     = "#24283b"
FG      = "#c0caf5"
FG_DIM  = "#565f89"
ACCENT  = "#7aa2f7"
GREEN   = "#9ece6a"
RED     = "#f7768e"
YELLOW  = "#e0af68"
MAGENTA = "#bb9af7"


# ════════════════════════════════════════════════════════════════
#  ANA UYGULAMA  (Tkinter GUI)
# ════════════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("USB Birim Seri Numara Değiştirici")
        self.geometry("580x540")
        self.resizable(False, False)
        self.configure(bg=BG)

        self._drives: list = []
        self._sel = None

        self._setup_style()
        self._build_ui()
        self._refresh()

    # ── Ttk Stil ──────────────────────────────────────────────
    def _setup_style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(
            "TCombobox",
            fieldbackground="#1f2335",
            background="#414868",
            foreground=FG,
            arrowcolor=FG,
            selectbackground=ACCENT,
            selectforeground=BG,
            padding=6,
        )
        s.map(
            "TCombobox",
            fieldbackground=[("readonly", "#1f2335")],
            foreground=[("readonly", FG)],
        )

    # ── Yardımcı: LabelFrame ─────────────────────────────────
    def _frame(self, title: str) -> tk.LabelFrame:
        lf = tk.LabelFrame(
            self,
            text=f"  {title}  ",
            font=("Segoe UI", 10, "bold"),
            bg=BG2, fg=ACCENT,
            padx=14, pady=10,
            relief="groove", bd=1,
        )
        lf.pack(fill="x", padx=22, pady=6)
        return lf

    # ── Arayüz Oluştur ───────────────────────────────────────
    def _build_ui(self):
        # -------- Başlık --------
        tk.Label(
            self,
            text="🔌  USB Seri Numara Değiştirici",
            font=("Segoe UI", 17, "bold"),
            bg=BG, fg=FG,
        ).pack(pady=(18, 2))
        tk.Label(
            self,
            text="Volume Serial Number — birim seri numarasını değiştirir",
            font=("Segoe UI", 9),
            bg=BG, fg=FG_DIM,
        ).pack(pady=(0, 6))

        # -------- Sürücü Seçimi --------
        f1 = self._frame("Sürücü Seçimi")
        row1 = tk.Frame(f1, bg=BG2)
        row1.pack(fill="x")

        self._combo = ttk.Combobox(
            row1, state="readonly", width=48, font=("Segoe UI", 10)
        )
        self._combo.pack(side="left", fill="x", expand=True)
        self._combo.bind("<<ComboboxSelected>>", self._on_select)

        btn_ref = tk.Button(
            row1, text="⟳  Yenile", font=("Segoe UI", 10, "bold"),
            bg=ACCENT, fg=BG, activebackground="#5d8ae6",
            relief="flat", padx=10, command=self._refresh,
        )
        btn_ref.pack(side="right", padx=(10, 0))

        # -------- Bilgi --------
        f2 = self._frame("Sürücü Bilgileri")
        grid = tk.Frame(f2, bg=BG2)
        grid.pack(fill="x")

        self._lbl: dict[str, tk.Label] = {}
        rows = [
            ("label", "Birim Etiketi"),
            ("fs",    "Dosya Sistemi"),
            ("cur",   "Mevcut Seri No"),
        ]
        for i, (key, text) in enumerate(rows):
            tk.Label(
                grid, text=f"{text} :", font=("Segoe UI", 10),
                bg=BG2, fg=FG_DIM, anchor="w",
            ).grid(row=i, column=0, sticky="w", pady=3)

            is_serial = key == "cur"
            lbl = tk.Label(
                grid, text="—",
                font=("Consolas" if is_serial else "Segoe UI",
                      14 if is_serial else 10, "bold"),
                bg=BG2,
                fg=GREEN if is_serial else MAGENTA,
                anchor="w",
            )
            lbl.grid(row=i, column=1, sticky="w", padx=(14, 0), pady=3)
            self._lbl[key] = lbl

        # -------- Yeni Seri --------
        f3 = self._frame("Yeni Seri Numara")
        row2 = tk.Frame(f3, bg=BG2)
        row2.pack(fill="x")

        self._entry = tk.Entry(
            row2,
            font=("Consolas", 20),
            width=11, justify="center",
            bg="#1f2335", fg=RED,
            insertbackground=FG,
            relief="flat", bd=0,
            highlightthickness=2,
            highlightcolor=ACCENT,
            highlightbackground="#414868",
        )
        self._entry.pack(side="left", fill="x", expand=True, ipady=4)
        self._entry.insert(0, "XXXX-XXXX")
        self._entry.bind(
            "<FocusIn>",
            lambda _: (
                self._entry.delete(0, "end")
                if self._entry.get() == "XXXX-XXXX"
                else None
            ),
        )

        tk.Button(
            row2, text="🎲 Rastgele",
            font=("Segoe UI", 10, "bold"),
            bg=YELLOW, fg=BG, activebackground="#c9993b",
            relief="flat", padx=14,
            command=self._random,
        ).pack(side="right", padx=(12, 0))

        tk.Label(
            f3,
            text="Format:  XXXX-XXXX   (hexadecimal, örn: A1B2-C3D4)",
            font=("Segoe UI", 8), bg=BG2, fg=FG_DIM,
        ).pack(anchor="w", pady=(8, 0))

        # -------- Uygula Butonu --------
        tk.Button(
            self,
            text="✅   Seri Numarayı Değiştir",
            font=("Segoe UI", 14, "bold"),
            bg=GREEN, fg=BG,
            activebackground="#7ab85a",
            relief="flat", padx=20, pady=10,
            cursor="hand2",
            command=self._apply,
        ).pack(fill="x", padx=22, pady=(14, 8))

        # -------- Durum Çubuğu --------
        self._status = tk.StringVar(
            value="Hazır  —  USB bellek takın ve  ⟳ Yenile  butonuna basın."
        )
        tk.Label(
            self,
            textvariable=self._status,
            font=("Segoe UI", 8),
            bg="#16161e", fg=FG_DIM,
            anchor="w", padx=10, pady=4,
        ).pack(side="bottom", fill="x")

    # ── Mantık ────────────────────────────────────────────────
    def _refresh(self):
        self._drives = list_usb_drives()
        vals = [
            f"{lt}:   [{inf['fs']}]   {inf['label']}   ◆  {inf['serial_str']}"
            for lt, inf in self._drives
        ]
        self._combo["values"] = vals
        if vals:
            self._combo.current(0)
            self._on_select(None)
            self._status.set(f"{len(vals)} adet USB sürücü bulundu.")
        else:
            for v in self._lbl.values():
                v.config(text="—")
            self._sel = None
            self._status.set("Hiç USB sürücü bulunamadı.")

    def _on_select(self, _):
        idx = self._combo.current()
        if idx < 0 or idx >= len(self._drives):
            return
        letter, info = self._drives[idx]
        self._sel = (letter, info)
        self._lbl["label"].config(text=info["label"])
        self._lbl["fs"].config(text=info["fs"])
        self._lbl["cur"].config(text=info["serial_str"])

    def _random(self):
        v = random.randint(0, 0xFFFFFFFF)
        s = f"{(v >> 16) & 0xFFFF:04X}-{v & 0xFFFF:04X}"
        self._entry.delete(0, "end")
        self._entry.insert(0, s)

    def _parse(self) -> int:
        txt = self._entry.get().strip().upper().replace(" ", "")
        parts = txt.split("-")
        if len(parts) != 2:
            raise ValueError
        hi, lo = int(parts[0], 16), int(parts[1], 16)
        if hi > 0xFFFF or lo > 0xFFFF:
            raise ValueError
        return (hi << 16) | lo

    def _apply(self):
        if not self._sel:
            messagebox.showwarning("Uyarı", "Önce bir USB sürücü seçin!")
            return

        # Seri numarasını ayrıştır
        try:
            new_val = self._parse()
        except ValueError:
            messagebox.showerror(
                "Geçersiz Değer",
                "Seri numara formatı hatalı!\n\nDoğru format:  XXXX-XXXX  (hex)",
            )
            return

        letter, info = self._sel
        new_str = f"{(new_val >> 16) & 0xFFFF:04X}-{new_val & 0xFFFF:04X}"

        # Onay
        if not messagebox.askyesno(
            "Onay",
            f"Sürücü :           {letter}:\n"
            f"Dosya Sistemi :  {info['fs']}\n"
            f"Mevcut Seri :     {info['serial_str']}\n"
            f"Yeni Seri :         {new_str}\n\n"
            "Devam edilsin mi?",
            icon="warning",
        ):
            return

        # Uygula
        try:
            self._status.set("Seri numara değiştiriliyor …")
            self.update()

            fs = change_serial(letter, new_val)

            self._status.set(f"Başarılı!  Yeni seri: {new_str}")
            messagebox.showinfo(
                "Başarılı  ✅",
                f"Seri numara başarıyla değiştirildi!\n\n"
                f"Dosya Sistemi :  {fs}\n"
                f"Yeni Seri :         {new_str}\n\n"
                "USB belleği güvenli kaldırıp tekrar takın.",
            )
            self._refresh()

        except Exception as exc:
            self._status.set("Hata oluştu!")
            messagebox.showerror(
                "Hata  ❌",
                f"İşlem başarısız oldu:\n\n{exc}",
            )


# ════════════════════════════════════════════════════════════════
#  GİRİŞ NOKTASI
# ════════════════════════════════════════════════════════════════

def main():
    if not is_admin():
        elevate()          # Yönetici olarak yeniden başlat
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()