#!/usr/bin/env python3
"""Piko 1.6 Runtime: GUI, Web, Game Development and Network/Ping helpers."""
from __future__ import annotations

import logging
import platform
import subprocess
import time
import urllib.request
import tkinter as tk
from pathlib import Path
from typing import Any, Callable

LOGGER = logging.getLogger("piko.runtime")

__all__ = [
    # GUI
    "gui_pencere", "gui_yazi", "gui_giris", "gui_al", "gui_buton", "gui_mesaj", "gui_goster",
    # Web
    "web_proje", "web_html", "web_css", "web_js", "web_onizle",
    # Ağ ve Ping (YENİ)
    "ag_ping", "internet_var_mi",
    # Oyun Geliştirme (YENİ)
    "oyun_pencere", "oyun_temizle", "oyun_ciz_kare", "oyun_ciz_yazi", 
    "oyun_tus_basildi_mi", "oyun_baslat",
]

# --- AĞ VE PİNG ÖZELLİKLERİ ---
def ag_ping(adres: str) -> float:
    """Belirtilen adrese ping atar ve milisaniye (ms) cinsinden gecikme süresini döndürür."""
    param = "-n" if platform.system().lower() == "windows" else "-c"
    command = ["ping", param, "1", str(adres)]
    try:
        baslangic = time.time()
        sonuc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
        bitis = time.time()
        if sonuc.returncode == 0:
            return round((bitis - baslangic) * 1000, 2)
        return -1.0
    except Exception:
        return -1.0

def internet_var_mi() -> bool:
    """Genel bir web sitesine bağlanarak internet bağlantısını test eder."""
    try:
        urllib.request.urlopen("https://www.google.com", timeout=2)
        return True
    except Exception:
        return False


# --- OYUN GELİŞTİRME MOTORU ---
class _GameState:
    def __init__(self) -> None:
        self.root: tk.Tk | None = None
        self.canvas: tk.Canvas | None = None
        self.keys: set[str] = set()

_GAME = _GameState()

def oyun_pencere(baslik: str = "Piko Oyun", genislik: int = 800, yukseklik: int = 600) -> None:
    """Oyun için özel bir grafik tuvali (canvas) penceresi açar."""
    if _GAME.root is not None:
        try:
            _GAME.root.destroy()
        except Exception:
            pass
    _GAME.root = tk.Tk()
    _GAME.root.title(str(baslik))
    _GAME.canvas = tk.Canvas(_GAME.root, width=int(genislik), height=int(yukseklik), bg="black")
    _GAME.canvas.pack(fill="both", expand=True)
    
    # Klavye tuş dinleyicileri
    _GAME.root.bind("<KeyPress>", lambda e: _GAME.keys.add(e.keysym.lower()))
    _GAME.root.bind("<KeyRelease>", lambda e: _GAME.keys.discard(e.keysym.lower()))
    LOGGER.debug("Oyun penceresi oluşturuldu.")

def oyun_temizle() -> None:
    """Her karede (frame) ekranı temizler."""
    if _GAME.canvas:
        _GAME.canvas.delete("all")

def oyun_ciz_kare(x: float, y: float, genislik: float, yukseklik: float, renk: str = "white") -> None:
    """Oyun ekranına renkli bir kare/dikdörtgen çizer."""
    if _GAME.canvas:
        _GAME.canvas.create_rectangle(x, y, x + genislik, y + yukseklik, fill=renk, outline=renk)

def oyun_ciz_yazi(metin: str, x: float, y: float, renk: str = "white") -> None:
    """Oyun ekranına yazı yazar (Skor, Can vb. için)."""
    if _GAME.canvas:
        _GAME.canvas.create_text(x, y, text=str(metin), fill=str(renk), anchor="nw", font=("Arial", 14, "bold"))

def oyun_tus_basildi_mi(tus: str) -> bool:
    """Belirli bir tuşa basılıp basılmadığını kontrol eder (Örn: 'space', 'left', 'right', 'w', 'a', 's', 'd')."""
    return str(tus).lower() in _GAME.keys

def oyun_baslat(guncelleme_fonksiyonu: Callable[[], Any], fps: int = 60) -> None:
    """Oyun döngüsünü (Game Loop) başlatır."""
    gecikme = max(10, int(1000 / max(1, int(fps))))
    
    def dongu() -> None:
        try:
            if callable(guncelleme_fonksiyonu):
                guncelleme_fonksiyonu()
        except Exception as exc:
            LOGGER.exception("Oyun döngü hatası")
            print(f"Oyun Hatası: {exc}")
        if _GAME.root:
            _GAME.root.after(gecikme, dongu)

    if _GAME.root:
        _GAME.root.after(10, dongu)
        _GAME.root.mainloop()

# (Eski GUI ve Web fonksiyonları aynen korunur...)
class _GuiState:
    def __init__(self) -> None:
        self.root: Any = None
        self.entries: dict[str, Any] = {}
    def require_root(self) -> Any:
        if self.root is None:
            raise RuntimeError("Önce gui_pencere(...) komutunu kullanmalısın.")
        return self.root

_GUI = _GuiState()
_WEB_PROJECT: Path | None = None

def gui_pencere(baslik: str = "Piko Uygulamasi", genislik: int = 640, yukseklik: int = 420) -> None:
    if _GUI.root is not None:
        try: _GUI.root.destroy()
        except Exception: pass
    _GUI.root = tk.Tk()
    _GUI.root.title(str(baslik))
    _GUI.root.geometry(f"{max(240, int(genislik))}x{max(160, int(yukseklik))}")
    _GUI.entries.clear()

def gui_yazi(metin: Any, x: int = 20, y: int = 20) -> Any:
    root = _GUI.require_root()
    widget = tk.Label(root, text=str(metin), anchor="w")
    widget.place(x=int(x), y=int(y))
    return widget

def gui_giris(ad: str, x: int = 20, y: int = 60, genislik: int = 24) -> Any:
    root = _GUI.require_root()
    widget = tk.Entry(root, width=max(4, int(genislik)))
    widget.place(x=int(x), y=int(y))
    _GUI.entries[str(ad)] = widget
    return widget

def gui_al(ad: str) -> str:
    if str(ad) not in _GUI.entries:
        raise KeyError(f"'{ad}' adında bir giriş alanı yok.")
    return _GUI.entries[str(ad)].get()

def gui_buton(metin: str, x: int = 20, y: int = 100, komut: Callable[[], Any] | None = None) -> Any:
    from tkinter import messagebox
    root = _GUI.require_root()
    def safe_callback() -> None:
        try:
            if callable(komut): komut()
        except Exception as exc:
            messagebox.showerror("Piko Hatasi", f"{type(exc).__name__}: {exc}")
    widget = tk.Button(root, text=str(metin), command=safe_callback)
    widget.place(x=int(x), y=int(y))
    return widget

def gui_mesaj(baslik: str, metin: str) -> None:
    from tkinter import messagebox
    _GUI.require_root()
    messagebox.showinfo(str(baslik), str(metin))

def gui_goster() -> None:
    root = _GUI.require_root()
    root.mainloop()

def web_proje(ad: str) -> str:
    global _WEB_PROJECT
    base = (Path.cwd() / "piko_web_projects").resolve()
    base.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() else "_" for c in ad)
    target = (base / slug).resolve()
    target.mkdir(parents=True, exist_ok=True)
    (target / "index.html").write_text("<h1>Merhaba Piko Web</h1>", encoding="utf-8")
    _WEB_PROJECT = target
    return str(target)

def web_html(kod: str) -> str:
    path = (_WEB_PROJECT or Path.cwd()) / "index.html"
    path.write_text(str(kod), encoding="utf-8")
    return str(path)

def web_css(kod: str) -> str:
    path = (_WEB_PROJECT or Path.cwd()) / "style.css"
    path.write_text(str(kod), encoding="utf-8")
    return str(path)

def web_js(kod: str) -> str:
    path = (_WEB_PROJECT or Path.cwd()) / "app.js"
    path.write_text(str(kod), encoding="utf-8")
    return str(path)

def web_onizle(port: int = 8000) -> None:
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
    import webbrowser
    project = _WEB_PROJECT or Path.cwd()
    server = ThreadingHTTPServer(("127.0.0.1", int(port)), partial(SimpleHTTPRequestHandler, directory=str(project)))
    url = f"http://127.0.0.1:{port}/"
    print(f"Web önizleme: {url}")
    webbrowser.open(url)
    server.serve_forever()