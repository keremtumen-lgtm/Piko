#!/usr/bin/env python3
"""Piko 1.8 Runtime: GUI, web, game and basic network diagnostics.

The web preview binds to 127.0.0.1 only. ag_ping runs one bounded ping
request to a validated hostname or IP address. This runtime is not a sandbox.
"""
from __future__ import annotations

import ipaddress
import logging
import math
import random
from datetime import datetime
import platform
import re
import subprocess
import time
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

try:  # Keep non-GUI helpers usable on Python installs without Tk support.
    import tkinter as tk
    from tkinter import messagebox
except ImportError:  # pragma: no cover - depends on the user's Python build
    tk = None  # type: ignore[assignment]
    messagebox = None  # type: ignore[assignment]

LOGGER = logging.getLogger("piko.runtime")

__all__ = [
    "gui_pencere", "gui_yazi", "gui_giris", "gui_al", "gui_buton", "gui_mesaj", "gui_goster",
    "web_proje", "web_html", "web_css", "web_js", "web_onizle",
    "ag_ping", "internet_var_mi",
    "oyun_pencere", "oyun_temizle", "oyun_ciz_kare", "oyun_ciz_yazi",
    "oyun_tus_basildi_mi", "oyun_baslat",
    "metin_buyut", "metin_kucult", "metin_kirp", "metin_bol",
    "metin_degistir", "metin_bul", "metin_baslar", "metin_biter",
    "liste_ekle", "liste_cikar", "liste_kopyala", "liste_sirala", "liste_ters",
    "sozluk_al", "sozluk_anahtarlar", "sozluk_degerler", "sozluk_sil", "sozluk_var_mi",
    "karekok", "sinus", "kosinus", "faktoriyel", "taban", "tavan",
    "rastgele_sayi", "rastgele_sec", "simdi", "sinif_adi",
]


def _require_tk() -> Any:
    if tk is None:
        raise RuntimeError("Bu Python kurulumunda Tk GUI destegi bulunamadi.")
    return tk


# ---------------------------------------------------------------------------
# Basic network diagnostics
# ---------------------------------------------------------------------------
_HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def _validate_host(address: str) -> str:
    host = str(address).strip()
    if not host or len(host) > 253 or any(ch in host for ch in "/\\\0 \t\r\n"):
        raise ValueError("Gecersiz adres. IP adresi veya alan adi gir.")
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    if host.endswith("."):
        host = host[:-1]
    labels = host.split(".")
    if not labels or any(not _HOST_LABEL.fullmatch(label) for label in labels):
        raise ValueError("Gecersiz alan adi.")
    return host


def ag_ping(adres: str) -> float:
    """Send one ping with a short timeout; return milliseconds or -1.0.

    Only a hostname or IP address is accepted. No shell is used.
    """
    host = _validate_host(adres)
    system = platform.system().lower()
    if system == "windows":
        command = ["ping", "-n", "1", "-w", "2000", host]
    elif system == "darwin":
        command = ["ping", "-c", "1", host]
    else:
        command = ["ping", "-c", "1", "-W", "2", host]
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=3.0,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        LOGGER.debug("Ping failed for %s: %s", host, exc)
        return -1.0
    if result.returncode != 0:
        return -1.0
    return round((time.monotonic() - started) * 1000.0, 2)


def internet_var_mi() -> bool:
    """Check internet access with a short HTTPS request."""
    request = urllib.request.Request(
        "https://www.google.com/generate_204",
        headers={"User-Agent": "Piko/1.8 connectivity-check"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=2.5) as response:
            return 200 <= int(response.status) < 500
    except Exception as exc:
        LOGGER.debug("Internet check failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# GUI helpers
# ---------------------------------------------------------------------------
class _GuiState:
    def __init__(self) -> None:
        self.root: Any = None
        self.entries: dict[str, Any] = {}

    def require_root(self) -> Any:
        if self.root is None:
            raise RuntimeError("Once gui_pencere(...) komutunu kullanmalisin.")
        return self.root


_GUI = _GuiState()


def gui_pencere(baslik: str = "Piko Uygulamasi", genislik: int = 640, yukseklik: int = 420) -> None:
    ui = _require_tk()
    if _GUI.root is not None:
        try:
            _GUI.root.destroy()
        except Exception:
            pass
    _GUI.root = ui.Tk()
    _GUI.root.title(str(baslik))
    _GUI.root.geometry(f"{max(240, int(genislik))}x{max(160, int(yukseklik))}")
    _GUI.entries.clear()
    LOGGER.debug("GUI window created: %s", baslik)


def gui_yazi(metin: Any, x: int = 20, y: int = 20) -> Any:
    ui = _require_tk()
    root = _GUI.require_root()
    widget = ui.Label(root, text=str(metin), anchor="w")
    widget.place(x=int(x), y=int(y))
    return widget


def gui_giris(ad: str, x: int = 20, y: int = 60, genislik: int = 24) -> Any:
    ui = _require_tk()
    root = _GUI.require_root()
    widget = ui.Entry(root, width=max(4, int(genislik)))
    widget.place(x=int(x), y=int(y))
    _GUI.entries[str(ad)] = widget
    return widget


def gui_al(ad: str) -> str:
    key = str(ad)
    if key not in _GUI.entries:
        raise KeyError(f"'{key}' adinda bir giris alani yok.")
    return str(_GUI.entries[key].get())


def gui_buton(
    metin: str,
    x: int = 20,
    y: int = 100,
    komut: Callable[[], Any] | None = None,
) -> Any:
    ui = _require_tk()
    root = _GUI.require_root()

    def safe_callback() -> None:
        try:
            if callable(komut):
                komut()
        except Exception as exc:
            if messagebox is not None:
                messagebox.showerror("Piko Hatasi", f"{type(exc).__name__}: {exc}")
            LOGGER.exception("GUI button callback failed")

    widget = ui.Button(root, text=str(metin), command=safe_callback)
    widget.place(x=int(x), y=int(y))
    return widget


def gui_mesaj(baslik: str, metin: str) -> None:
    _require_tk()
    _GUI.require_root()
    if messagebox is None:
        raise RuntimeError("Tk messagebox destegi bulunamadi.")
    messagebox.showinfo(str(baslik), str(metin))


def gui_goster() -> None:
    _GUI.require_root().mainloop()


# ---------------------------------------------------------------------------
# Game helpers
# ---------------------------------------------------------------------------
class _GameState:
    def __init__(self) -> None:
        self.root: Any = None
        self.canvas: Any = None
        self.keys: set[str] = set()
        self.running = False


_GAME = _GameState()


def oyun_pencere(baslik: str = "Piko Oyun", genislik: int = 800, yukseklik: int = 600) -> None:
    ui = _require_tk()
    if _GAME.root is not None:
        try:
            _GAME.root.destroy()
        except Exception:
            pass
    _GAME.keys.clear()
    _GAME.root = ui.Tk()
    _GAME.root.title(str(baslik))
    _GAME.canvas = ui.Canvas(
        _GAME.root,
        width=max(160, int(genislik)),
        height=max(120, int(yukseklik)),
        bg="black",
        highlightthickness=0,
    )
    _GAME.canvas.pack(fill="both", expand=True)
    _GAME.root.bind("<KeyPress>", lambda event: _GAME.keys.add(str(event.keysym).lower()))
    _GAME.root.bind("<KeyRelease>", lambda event: _GAME.keys.discard(str(event.keysym).lower()))
    _GAME.root.focus_force()
    LOGGER.debug("Game window created: %s", baslik)


def oyun_temizle() -> None:
    if _GAME.canvas is not None:
        _GAME.canvas.delete("all")


def oyun_ciz_kare(x: float, y: float, genislik: float, yukseklik: float, renk: str = "white") -> None:
    if _GAME.canvas is not None:
        _GAME.canvas.create_rectangle(
            float(x), float(y), float(x) + float(genislik), float(y) + float(yukseklik),
            fill=str(renk), outline=str(renk),
        )


def oyun_ciz_yazi(metin: str, x: float, y: float, renk: str = "white") -> None:
    if _GAME.canvas is not None:
        _GAME.canvas.create_text(
            float(x), float(y), text=str(metin), fill=str(renk),
            anchor="nw", font=("Arial", 14, "bold"),
        )


def oyun_tus_basildi_mi(tus: str) -> bool:
    return str(tus).lower() in _GAME.keys


def oyun_baslat(guncelleme_fonksiyonu: Callable[[], Any], fps: int = 60) -> None:
    if _GAME.root is None or _GAME.canvas is None:
        raise RuntimeError("Once oyun_pencere(...) komutunu kullanmalisin.")
    if not callable(guncelleme_fonksiyonu):
        raise TypeError("oyun_baslat icin bir fonksiyon vermelisin.")
    frame_rate = max(1, min(240, int(fps)))
    delay_ms = max(1, round(1000 / frame_rate))
    _GAME.running = True

    def loop() -> None:
        if not _GAME.running or _GAME.root is None:
            return
        try:
            guncelleme_fonksiyonu()
        except Exception:
            _GAME.running = False
            LOGGER.exception("Game loop callback failed")
            if messagebox is not None:
                messagebox.showerror("Piko Oyun Hatasi", "Oyun dongusunde hata olustu. piko_debug.log dosyasini kontrol et.")
            return
        try:
            _GAME.root.after(delay_ms, loop)
        except Exception:
            _GAME.running = False

    _GAME.root.protocol("WM_DELETE_WINDOW", _stop_game)
    _GAME.root.after(10, loop)
    _GAME.root.mainloop()


def _stop_game() -> None:
    _GAME.running = False
    if _GAME.root is not None:
        try:
            _GAME.root.destroy()
        finally:
            _GAME.root = None
            _GAME.canvas = None
            _GAME.keys.clear()


# ---------------------------------------------------------------------------
# Local web project helpers
# ---------------------------------------------------------------------------
_WEB_PROJECT: Path | None = None


def web_proje(ad: str) -> str:
    global _WEB_PROJECT
    raw_name = str(ad).strip()
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", raw_name).strip("_-")[:64]
    if not slug:
        raise ValueError("Web proje adi en az bir harf veya rakam icermeli.")
    base = (Path.cwd() / "piko_web_projects").resolve()
    base.mkdir(parents=True, exist_ok=True)
    target = (base / slug).resolve()
    if target.parent != base:
        raise ValueError("Gecersiz proje yolu.")
    target.mkdir(parents=True, exist_ok=True)
    (target / "index.html").write_text(
        '<!doctype html>\n<html lang="tr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<link rel="stylesheet" href="style.css"></head>'
        '<body><h1>Merhaba Piko Web</h1><script src="app.js"></script></body></html>\n',
        encoding="utf-8",
    )
    (target / "style.css").write_text("body { font-family: sans-serif; padding: 2rem; }\n", encoding="utf-8")
    (target / "app.js").write_text("console.log('Piko Web hazir');\n", encoding="utf-8")
    _WEB_PROJECT = target
    LOGGER.info("Web project created: %s", target)
    return str(target)


def _web_file(filename: str) -> Path:
    if _WEB_PROJECT is None:
        raise RuntimeError("Once web_proje('proje_adi') komutunu kullanmalisin.")
    return _WEB_PROJECT / filename


def web_html(kod: str) -> str:
    path = _web_file("index.html")
    path.write_text(str(kod), encoding="utf-8")
    return str(path)


def web_css(kod: str) -> str:
    path = _web_file("style.css")
    path.write_text(str(kod), encoding="utf-8")
    return str(path)


def web_js(kod: str) -> str:
    path = _web_file("app.js")
    path.write_text(str(kod), encoding="utf-8")
    return str(path)


def web_onizle(port: int = 8000) -> None:
    if _WEB_PROJECT is None:
        raise RuntimeError("Once web_proje('proje_adi') komutunu kullanmalisin.")
    port_number = int(port)
    if not 1024 <= port_number <= 65535:
        raise ValueError("Port 1024 ile 65535 arasinda olmali.")
    import webbrowser

    handler = partial(SimpleHTTPRequestHandler, directory=str(_WEB_PROJECT))
    server = ThreadingHTTPServer(("127.0.0.1", port_number), handler)
    server.daemon_threads = True
    url = f"http://127.0.0.1:{port_number}/"
    print(f"Piko Web onizleme: {url}")
    LOGGER.info("Local web preview started: %s", url)
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Web preview interrupted by user")
    finally:
        server.server_close()
        LOGGER.info("Web preview stopped")


# ---------------------------------------------------------------------------
# Piko 1.8 standard library: text, list, dictionary, math, random and time
# ---------------------------------------------------------------------------
def metin_buyut(metin: Any) -> str:
    """Metni buyuk harfe donusturur."""
    return str(metin).upper()


def metin_kucult(metin: Any) -> str:
    """Metni kucuk harfe donusturur."""
    return str(metin).lower()


def metin_kirp(metin: Any) -> str:
    """Metnin basindaki ve sonundaki bosluklari temizler."""
    return str(metin).strip()


def metin_bol(metin: Any, ayirac: str | None = None) -> list[str]:
    """Metni ayiraca gore parcalara ayirir."""
    if ayirac is not None and not isinstance(ayirac, str):
        raise TypeError("metin_bol ayirac degeri metin veya yok olmali.")
    return str(metin).split(ayirac)


def metin_degistir(metin: Any, eski: str, yeni: str, adet: int = -1) -> str:
    """Metindeki bir parcayi yenisiyle degistirir."""
    return str(metin).replace(str(eski), str(yeni), int(adet))


def metin_bul(metin: Any, aranan: str) -> int:
    """Aranan metnin ilk konumunu verir; bulunamazsa -1 dondurur."""
    return str(metin).find(str(aranan))


def metin_baslar(metin: Any, onek: str) -> bool:
    return str(metin).startswith(str(onek))


def metin_biter(metin: Any, sonek: str) -> bool:
    return str(metin).endswith(str(sonek))


def liste_ekle(liste_degeri: list[Any], oge: Any) -> list[Any]:
    """Listeye oge ekler ve ayni listeyi dondurur."""
    if not isinstance(liste_degeri, list):
        raise TypeError("liste_ekle ilk parametre olarak liste bekler.")
    liste_degeri.append(oge)
    return liste_degeri


def liste_cikar(liste_degeri: list[Any], indeks: int = -1) -> Any:
    """Listeden belirtilen indeksteki ogeyi cikarip dondurur."""
    if not isinstance(liste_degeri, list):
        raise TypeError("liste_cikar ilk parametre olarak liste bekler.")
    return liste_degeri.pop(int(indeks))


def liste_kopyala(liste_degeri: list[Any]) -> list[Any]:
    if not isinstance(liste_degeri, list):
        raise TypeError("liste_kopyala liste bekler.")
    return liste_degeri.copy()


def liste_sirala(liste_degeri: Any, ters: bool = False) -> list[Any]:
    return sorted(liste_degeri, reverse=bool(ters))


def liste_ters(liste_degeri: Any) -> list[Any]:
    return list(reversed(liste_degeri))


def sozluk_al(sozluk_degeri: dict[Any, Any], anahtar: Any, varsayilan: Any = None) -> Any:
    if not isinstance(sozluk_degeri, dict):
        raise TypeError("sozluk_al ilk parametre olarak sozluk bekler.")
    return sozluk_degeri.get(anahtar, varsayilan)


def sozluk_anahtarlar(sozluk_degeri: dict[Any, Any]) -> list[Any]:
    if not isinstance(sozluk_degeri, dict):
        raise TypeError("sozluk_anahtarlar sozluk bekler.")
    return list(sozluk_degeri.keys())


def sozluk_degerler(sozluk_degeri: dict[Any, Any]) -> list[Any]:
    if not isinstance(sozluk_degeri, dict):
        raise TypeError("sozluk_degerler sozluk bekler.")
    return list(sozluk_degeri.values())


def sozluk_sil(sozluk_degeri: dict[Any, Any], anahtar: Any) -> bool:
    if not isinstance(sozluk_degeri, dict):
        raise TypeError("sozluk_sil sozluk bekler.")
    return sozluk_degeri.pop(anahtar, _MISSING) is not _MISSING


_MISSING = object()


def sozluk_var_mi(sozluk_degeri: dict[Any, Any], anahtar: Any) -> bool:
    if not isinstance(sozluk_degeri, dict):
        raise TypeError("sozluk_var_mi sozluk bekler.")
    return anahtar in sozluk_degeri


def karekok(sayi: float) -> float:
    return math.sqrt(float(sayi))


def sinus(radyan: float) -> float:
    """Sinus; aci radyan cinsindendir."""
    return math.sin(float(radyan))


def kosinus(radyan: float) -> float:
    """Kosinus; aci radyan cinsindendir."""
    return math.cos(float(radyan))


def faktoriyel(sayi: int) -> int:
    numeric = float(sayi)
    if not math.isfinite(numeric) or numeric < 0 or not numeric.is_integer():
        raise ValueError("faktoriyel negatif olmayan tam sayi bekler.")
    return math.factorial(int(numeric))


def taban(sayi: float) -> int:
    return math.floor(float(sayi))


def tavan(sayi: float) -> int:
    return math.ceil(float(sayi))


def rastgele_sayi(en_az: int, en_cok: int) -> int:
    low, high = int(en_az), int(en_cok)
    if low > high:
        raise ValueError("rastgele_sayi icin ilk sinir ikinci sinirdan buyuk olamaz.")
    return random.randint(low, high)


def rastgele_sec(ogeler: Any) -> Any:
    if not ogeler:
        raise IndexError("rastgele_sec bos koleksiyondan oge secemez.")
    return random.choice(ogeler)


def simdi() -> str:
    """Yerel tarih ve saati ISO 8601 metni olarak dondurur."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Piko 1.8 object helpers
# ---------------------------------------------------------------------------
def sinif_adi(nesne: Any) -> str:
    """Return the runtime class name of an object."""
    return type(nesne).__name__
