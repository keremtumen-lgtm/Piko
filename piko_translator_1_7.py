#!/usr/bin/env python3
"""Piko Translator 1.7 - GUI, web, game, network and expanded standard library.

Piko 1.7 still translates Piko to Python. The 2.x series is planned to start
replacing this backend with a Piko parser, bytecode and virtual machine.

Usage:
    python piko_translator_1_7.py --gui
    python piko_translator_1_7.py example.piko --show
    python piko_translator_1_7.py example.piko --scan --debug
    python piko_translator_1_7.py example.piko --run --debug
"""
from __future__ import annotations

import argparse
import ast
import logging
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

VERSION = "1.7"
IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
TRACE_LEVEL = 5
logging.addLevelName(TRACE_LEVEL, "TRACE")
LOGGER = logging.getLogger("piko")
LOGGER.propagate = False

WORD_MAP: dict[str, str] = {
    "ve": "and", "veya": "or", "degil": "not",
    "dogru": "True", "yanlis": "False", "yok": "None",
    "bitir": "break", "devam": "continue", "gec": "pass",
}
CALL_MAP: dict[str, str] = {
    "yaz": "print", "sor": "input",
    "demet": "tuple", "kume": "set",
    "sayi": "int", "ondalik": "float", "metin": "str",
    "liste": "list", "sozluk": "dict", "mantik": "bool",
    "uzunluk": "len", "aralik": "range", "toplam": "sum",
    "en_buyuk": "max", "en_kucuk": "min", "mutlak": "abs",
    "yuvarla": "round", "sirala": "sorted", "tip": "type",
    "numaralandir": "enumerate", "hepsi": "all", "herhangi": "any",
    "birlestir": "zip", "ters_cevir": "reversed", "us": "pow",
    "karakter": "chr", "ascii_kodu": "ord",
    # Piko GUI API
    "gui_pencere": "gui_pencere", "gui_yazi": "gui_yazi",
    "gui_giris": "gui_giris", "gui_al": "gui_al",
    "gui_buton": "gui_buton", "gui_mesaj": "gui_mesaj",
    "gui_goster": "gui_goster",
    # Piko web API
    "web_proje": "web_proje", "web_html": "web_html",
    "web_css": "web_css", "web_js": "web_js",
    "web_onizle": "web_onizle",
    # Piko network diagnostics
    "ag_ping": "ag_ping", "internet_var_mi": "internet_var_mi",
    # Piko game development API
    "oyun_pencere": "oyun_pencere", "oyun_temizle": "oyun_temizle",
    "oyun_ciz_kare": "oyun_ciz_kare", "oyun_ciz_yazi": "oyun_ciz_yazi",
    "oyun_tus_basildi_mi": "oyun_tus_basildi_mi", "oyun_baslat": "oyun_baslat",
    # Piko 1.7 string helpers
    "metin_buyut": "metin_buyut", "metin_kucult": "metin_kucult",
    "metin_kirp": "metin_kirp", "metin_bol": "metin_bol",
    "metin_degistir": "metin_degistir", "metin_bul": "metin_bul",
    "metin_baslar": "metin_baslar", "metin_biter": "metin_biter",
    # Piko 1.7 list and dictionary helpers
    "liste_ekle": "liste_ekle", "liste_cikar": "liste_cikar",
    "liste_kopyala": "liste_kopyala", "liste_sirala": "liste_sirala",
    "liste_ters": "liste_ters", "sozluk_al": "sozluk_al",
    "sozluk_anahtarlar": "sozluk_anahtarlar", "sozluk_degerler": "sozluk_degerler",
    "sozluk_sil": "sozluk_sil", "sozluk_var_mi": "sozluk_var_mi",
    # Piko 1.7 math, random and date helpers
    "karekok": "karekok", "sinus": "sinus", "kosinus": "kosinus",
    "faktoriyel": "faktoriyel", "taban": "taban", "tavan": "tavan",
    "rastgele_sayi": "rastgele_sayi", "rastgele_sec": "rastgele_sec",
    "simdi": "simdi",
}
RUNTIME_CALLS = {
    "gui_pencere", "gui_yazi", "gui_giris", "gui_al", "gui_buton",
    "gui_mesaj", "gui_goster", "web_proje", "web_html", "web_css",
    "web_js", "web_onizle",
    "ag_ping", "internet_var_mi",
    "oyun_pencere", "oyun_temizle", "oyun_ciz_kare", "oyun_ciz_yazi",
    "oyun_tus_basildi_mi", "oyun_baslat",
    "metin_buyut", "metin_kucult", "metin_kirp", "metin_bol",
    "metin_degistir", "metin_bul", "metin_baslar", "metin_biter",
    "liste_ekle", "liste_cikar", "liste_kopyala", "liste_sirala", "liste_ters",
    "sozluk_al", "sozluk_anahtarlar", "sozluk_degerler", "sozluk_sil", "sozluk_var_mi",
    "karekok", "sinus", "kosinus", "faktoriyel", "taban", "tavan",
    "rastgele_sayi", "rastgele_sec", "simdi",
}
SAFE_IMPORTS = {"math", "random", "statistics", "json", "datetime", "decimal", "fractions", "re", "string", "collections", "itertools"}
SAFE_BUILTINS = {
    "print", "input", "int", "float", "str", "bool", "list", "dict", "tuple",
    "set", "len", "range", "sum", "max", "min", "abs", "round", "sorted",
    "type", "enumerate", "all", "any", "zip", "reversed", "pow", "chr", "ord", "tuple", "set",
    "Exception", "ValueError", "TypeError", "ZeroDivisionError", "IndexError",
    "KeyError", "NameError", "RuntimeError", "isinstance",
}
FORBIDDEN_NAMES = {
    "open", "eval", "exec", "compile", "__import__", "globals", "locals",
    "vars", "getattr", "setattr", "delattr", "breakpoint", "help", "dir",
    "memoryview", "classmethod", "staticmethod", "property", "super",
}


class DebugQueueHandler(logging.Handler):
    def __init__(self, target: queue.Queue[str]) -> None:
        super().__init__(TRACE_LEVEL)
        self.target = target
        self.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.target.put_nowait(self.format(record))
        except Exception:
            self.handleError(record)


def configure_logging(level: int = logging.WARNING, log_file: str | None = None,
                      extra_handlers: list[logging.Handler] | None = None) -> None:
    for handler in list(LOGGER.handlers):
        LOGGER.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    LOGGER.setLevel(level)
    formatter = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S")
    if level <= logging.DEBUG:
        stream = logging.StreamHandler()
        stream.setLevel(level)
        stream.setFormatter(formatter)
        LOGGER.addHandler(stream)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(TRACE_LEVEL)
        file_handler.setFormatter(formatter)
        LOGGER.addHandler(file_handler)
    for handler in extra_handlers or []:
        LOGGER.addHandler(handler)
    LOGGER.debug("Piko Translator %s debug sistemi baslatildi.", VERSION)
    LOGGER.debug("Python surumu: %s", sys.version.replace("\n", " "))
    LOGGER.debug("Calisma dizini: %s", Path.cwd())


def replace_words_outside_strings(source_line: str) -> str:
    """Translate keywords and function names outside strings and comments."""
    result: list[str] = []
    i = 0
    quote: str | None = None
    escaped = False
    while i < len(source_line):
        char = source_line[i]
        if quote is not None:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            i += 1
            continue
        if char == "#":
            result.append(source_line[i:])
            break
        if char in ("'", '"'):
            quote = char
            result.append(char)
            i += 1
            continue
        match = re.match(IDENT, source_line[i:])
        if match:
            word = match.group(0)
            end = i + len(word)
            if word in WORD_MAP:
                replacement = WORD_MAP[word]
            elif word in CALL_MAP and source_line[end:].lstrip().startswith("("):
                replacement = CALL_MAP[word]
            else:
                replacement = word
            result.append(replacement)
            LOGGER.log(TRACE_LEVEL, "TOKEN line-fragment=%r -> %r", word, replacement)
            i = end
            continue
        result.append(char)
        i += 1
    return "".join(result)


def _parse_function_args(raw: str) -> str:
    """Accept fonk add(a, b), fonk add a b, and default values."""
    raw = raw.strip()
    if raw.startswith("(") and raw.endswith(")"):
        depth = 0
        quote: str | None = None
        escaped = False
        encloses_all = True
        for index, char in enumerate(raw):
            if quote is not None:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                continue
            if char in ("'", '"'):
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0 and index != len(raw) - 1:
                    encloses_all = False
                    break
        if encloses_all and depth == 0:
            raw = raw[1:-1].strip()
    if not raw:
        return ""
    parts: list[str] = []
    buffer: list[str] = []
    depth = 0
    quote: str | None = None
    escaped = False
    def save() -> None:
        token = "".join(buffer).strip()
        if token:
            parts.append(token)
    for char in raw:
        if quote is not None:
            buffer.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            buffer.append(char)
        elif char in "([{":
            depth += 1
            buffer.append(char)
        elif char in ")]}":
            depth = max(0, depth - 1)
            buffer.append(char)
        elif depth == 0 and (char.isspace() or char == ","):
            save()
            buffer = []
        else:
            buffer.append(char)
    save()
    normalized: list[str] = []
    index = 0
    while index < len(parts):
        if index + 2 < len(parts) and parts[index + 1] == "=":
            normalized.append(parts[index] + "=" + parts[index + 2])
            index += 3
        else:
            normalized.append(parts[index])
            index += 1
    return ", ".join(replace_words_outside_strings(part) for part in normalized)


def translate_line(line: str, line_number: int) -> str:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        LOGGER.log(TRACE_LEVEL, "LINE %d unchanged (blank/comment)", line_number)
        return line
    indent = line[:len(line) - len(line.lstrip())]
    if re.match(r'^\s*program\s+["\'].*["\']\s*$', line):
        LOGGER.debug("LINE %d: program header", line_number)
        return f"{indent}# {stripped}"
    match = re.match(rf"^(\s*)ice_al\s+({IDENT})(?:\s+(?:olarak|as)\s+({IDENT}))?\s*$", line)
    if match:
        prefix, module, alias = match.groups()
        LOGGER.debug("LINE %d: import %s", line_number, module)
        return f"{prefix}import {module}" + (f" as {alias}" if alias else "")
    for pattern, keyword in [
        (r"^(\s*)eger\s+(.+):\s*$", "if"),
        (r"^(\s*)yada\s+(.+):\s*$", "elif"),
        (r"^(\s*)iken\s+(.+):\s*$", "while"),
    ]:
        match = re.match(pattern, line)
        if match:
            prefix, expression = match.groups()
            translated = replace_words_outside_strings(expression)
            LOGGER.debug("LINE %d: condition -> %s", line_number, keyword)
            return f"{prefix}{keyword} {translated}:"
    if re.match(r"^\s*degilse\s*:\s*$", line):
        LOGGER.debug("LINE %d: else", line_number)
        return f"{indent}else:"
    match = re.match(r"^(\s*)tekrar\s+(.+):\s*$", line)
    if match:
        prefix, count = match.groups()
        LOGGER.debug("LINE %d: repeat loop", line_number)
        return f"{prefix}for _piko_{line_number} in range({replace_words_outside_strings(count)}):"
    match = re.match(rf"^(\s*)her\s+({IDENT})\s+icinde\s+(.+):\s*$", line)
    if match:
        prefix, item, collection = match.groups()
        LOGGER.debug("LINE %d: collection loop item=%s", line_number, item)
        return f"{prefix}for {item} in {replace_words_outside_strings(collection)}:"
    match = re.match(rf"^(\s*)fonk\s+({IDENT})\s*(.*):\s*$", line)
    if match:
        prefix, function_name, raw_args = match.groups()
        args = _parse_function_args(raw_args)
        LOGGER.debug("LINE %d: function %s(%s)", line_number, function_name, args)
        return f"{prefix}def {function_name}({args}):"
    match = re.match(r"^(\s*)ver(?:\s+(.+))?$", line)
    if match:
        prefix, value = match.groups()
        LOGGER.debug("LINE %d: return", line_number)
        return f"{prefix}return {replace_words_outside_strings(value)}" if value else f"{prefix}return"
    if re.match(r"^\s*dene\s*:\s*$", line):
        LOGGER.debug("LINE %d: try", line_number)
        return f"{indent}try:"
    match = re.match(rf"^(\s*)yakala\s+({IDENT})(?:(?:\s+olarak|\s+as)\s+({IDENT}))?\s*:\s*$", line)
    if match:
        prefix, exception, alias = match.groups()
        LOGGER.debug("LINE %d: except %s", line_number, exception)
        return f"{prefix}except {exception}" + (f" as {alias}" if alias else "") + ":"
    if re.match(r"^\s*yakala\s*:\s*$", line):
        LOGGER.debug("LINE %d: except Exception", line_number)
        return f"{indent}except Exception:"
    if re.match(r"^\s*sonunda\s*:\s*$", line):
        LOGGER.debug("LINE %d: finally", line_number)
        return f"{indent}finally:"
    translated = replace_words_outside_strings(line)
    LOGGER.log(TRACE_LEVEL, "LINE %d: %r -> %r", line_number, line, translated)
    return translated


def translate(source: str) -> str:
    LOGGER.info("Ceviri basladi: %d karakter, %d satir", len(source), len(source.splitlines()))
    lines: list[str] = []
    for number, line in enumerate(source.splitlines(), start=1):
        LOGGER.log(TRACE_LEVEL, "SOURCE %04d | %s", number, line)
        translated = translate_line(line, number)
        LOGGER.log(TRACE_LEVEL, "OUTPUT %04d | %s", number, translated)
        lines.append(translated)
    result = "\n".join(lines)
    if result and not result.endswith("\n"):
        result += "\n"
    LOGGER.info("Ceviri tamamlandi: %d Python satiri", len(lines))
    return result


class FirewallVisitor(ast.NodeVisitor):
    """Static language-level checks; deliberately not advertised as an OS sandbox."""
    def __init__(self) -> None:
        self.issues: list[str] = []
        self.warnings: list[str] = []
        self.imports: set[str] = set()
        self.calls: set[str] = set()
        self.functions: set[str] = set()
        self.function_definitions: list[str] = []
        self.warnings: list[str] = []

    def issue(self, node: ast.AST, message: str) -> None:
        line = getattr(node, "lineno", "?")
        self.issues.append(f"Satir {line}: {message}")
        LOGGER.warning("FIREWALL BLOCK line=%s: %s", line, message)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            self.imports.add(alias.name)
            if root not in SAFE_IMPORTS:
                self.issue(node, f"'{alias.name}' modulune izin verilmiyor.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        self.imports.add(module)
        if module.split(".")[0] not in SAFE_IMPORTS:
            self.issue(node, f"'{module}' modulunden ice aktarma yasak.")
        if any(alias.name == "*" for alias in node.names):
            self.issue(node, "Toplu import (*) kullanilamaz.")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            name = node.func.id
            self.calls.add(name)
            if name in FORBIDDEN_NAMES:
                self.issue(node, f"'{name}()' guvenlik duvari tarafindan engellendi.")
        elif isinstance(node.func, ast.Attribute):
            self.calls.add(node.func.attr)
            if node.func.attr in {"__subclasses__", "__globals__", "__code__", "__closure__", "mro", "maketrans"}:
                self.issue(node, f"{node.func.attr}() guvenlik nedeniyle engellendi.")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in FORBIDDEN_NAMES:
            self.issue(node, f"'{node.id}' adi kullanilamaz.")
        if node.id.startswith("__"):
            self.issue(node, "Cift alt cizgili ozel isimler kullanilamaz.")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("_"):
            self.issue(node, "Ozel/dunder nesne ozelliklerine erisim engellendi.")
        if node.attr in {"system", "popen", "spawn", "fork", "execv", "execve", "urlopen", "connect", "bind", "listen", "__subclasses__", "__globals__", "__code__", "__closure__", "mro", "rmtree", "remove", "unlink"}:
            self.issue(node, f"'{node.attr}' ozelligine erisim engellendi.")
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name in self.functions:
            self.warnings.append(f"Ayni isimli fonksiyon birden fazla tanimlanmis: {node.name} (satir {node.lineno}).")
        self.functions.add(node.name)
        self.function_definitions.append(node.name)
        if len(node.body) > 50:
            self.warnings.append(f"{node.name} fonksiyonu uzun ({len(node.body)} ust seviye ifade); parcalamayi dusunebilirsin.")
        if node.name.startswith("__"):
            self.issue(node, "Ozel isimle fonksiyon tanimlanamaz.")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.issue(node, "Piko 1.7'te sinif tanimlama henuz acik degil.")

    def visit_Global(self, node: ast.Global) -> None:
        self.issue(node, "global bildirimi Piko 1.7'te desteklenmiyor.")

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.issue(node, "nonlocal bildirimi Piko 1.7'te desteklenmiyor.")


def firewall_check(python_code: str) -> tuple[list[str], dict[str, Any]]:
    LOGGER.info("Guvenlik duvari taramasi basladi.")
    if len(python_code) > 250_000:
        LOGGER.warning("FIREWALL BLOCK: source exceeds 250 KB limit")
        return ["Program 250 KB sinirini asti; guvenlik icin tarama durduruldu."], {
            "functions": [], "calls": [], "imports": [], "warnings": [],
            "metrics": {"lines": len(python_code.splitlines()), "ast_nodes": 0,
                        "functions": 0, "loops": 0, "conditions": 0,
                        "calls": 0, "assignments": 0},
        }
    try:
        tree = ast.parse(python_code)
    except SyntaxError as exc:
        issue = [f"Python sozdizimi hatasi, satir {exc.lineno}: {exc.msg}"]
        return issue, {"functions": [], "calls": [], "imports": []}
    visitor = FirewallVisitor()
    visitor.visit(tree)
    nodes = list(ast.walk(tree))
    if len(nodes) > 20_000:
        visitor.issues.append("AST dugum sayisi 20.000 sinirini asti.")
    report = {
        "functions": sorted(visitor.functions),
        "calls": sorted(visitor.calls),
        "imports": sorted(visitor.imports),
        "warnings": visitor.warnings,
        "metrics": {
            "lines": len(python_code.splitlines()),
            "ast_nodes": len(nodes),
            "functions": sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in nodes),
            "loops": sum(isinstance(node, (ast.For, ast.AsyncFor, ast.While)) for node in nodes),
            "conditions": sum(isinstance(node, ast.If) for node in nodes),
            "calls": sum(isinstance(node, ast.Call) for node in nodes),
            "assignments": sum(isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)) for node in nodes),
        },
    }
    LOGGER.info("Guvenlik taramasi bitti: %d engel, %d fonksiyon, %d cagri.",
                len(visitor.issues), len(visitor.functions), len(visitor.calls))
    return visitor.issues, report


def runtime_prelude(python_code: str) -> str:
    used = sorted(name for name in RUNTIME_CALLS if re.search(rf"\b{re.escape(name)}\s*\(", python_code))
    if not used:
        return ""
    imports = ", ".join(used)
    return f"# Piko {VERSION} runtime baglantisi\nfrom piko_runtime_1_7 import {imports}\n\n"


def prepare_python(source: str) -> tuple[str, str, list[str], dict[str, Any]]:
    body = translate(source)
    issues, report = firewall_check(body)
    full_code = runtime_prelude(body) + body
    LOGGER.debug("Python cikti uzunlugu: %d karakter", len(full_code))
    return body, full_code, issues, report


def format_scan_report(report: dict[str, Any], issues: list[str]) -> str:
    lines = ["PIKO FONKSIYON TARAMASI", "=" * 36]
    for label, key in [("Tanimli fonksiyonlar", "functions"), ("Kullanilan cagrilar", "calls"), ("Icer aktarmalar", "imports")]:
        items = report.get(key, [])
        lines.append(f"{label} ({len(items)}):")
        lines.extend(f"  - {item}" for item in items) if items else lines.append("  - Yok")
    lines.append("")
    lines.append("PIKO GUVENLIK DUVARI")
    lines.append("=" * 36)
    if issues:
        lines.extend(f"[ENGELLENDI] {issue}" for issue in issues)
    else:
        lines.append("[OK] Bilinen tehlikeli yapilar bulunmadi.")
    warnings = report.get("warnings", [])
    lines.append("")
    lines.append(f"KALITE UYARILARI ({len(warnings)}):")
    lines.extend(f"[UYARI] {warning}" for warning in warnings) if warnings else lines.append("  - Uyari yok")
    metrics = report.get("metrics", {})
    if metrics:
        lines.append("")
        lines.append("KOD METRIKLERI:")
        for key, label in [("lines", "Satir"), ("ast_nodes", "AST dugumu"), ("functions", "Fonksiyon"), ("loops", "Dongu"), ("conditions", "Kosul"), ("calls", "Fonksiyon cagrisi"), ("assignments", "Atama")]:
            lines.append(f"  {label}: {metrics.get(key, 0)}")
    lines.append("Not: Bu statik kontrol tam bir isletim sistemi sandbox'i degildir.")
    return "\n".join(lines)


def copy_runtime_if_needed(python_code: str, output_dir: Path) -> None:
    if not runtime_prelude(python_code):
        return
    source_runtime = Path(__file__).resolve().with_name("piko_runtime_1_7.py")
    if not source_runtime.is_file():
        raise FileNotFoundError("piko_runtime_1_7.py bulunamadi; runtime dosyasini translator yanina koy.")
    destination = output_dir / "piko_runtime_1_7.py"
    if source_runtime.resolve() != destination.resolve():
        shutil.copy2(source_runtime, destination)
        LOGGER.debug("Runtime dosyasi kopyalandi: %s", destination)


def run_generated(output_path: Path, source: str, timeout: float = 8.0) -> int:
    """Run generated program in a child process after static checks."""
    has_long_lived_ui = any(token in source for token in ("gui_goster(", "web_onizle(", "oyun_baslat("))
    command = [sys.executable, str(output_path)]
    LOGGER.info("Alt surec baslatiliyor: %s", command)
    try:
        if has_long_lived_ui:
            LOGGER.info("GUI/web programi acik kalacak; kapatmak icin penceresini durdur.")
            completed = subprocess.run(command, cwd=str(output_path.parent), check=False)
        else:
            completed = subprocess.run(command, cwd=str(output_path.parent), timeout=timeout, check=False)
        LOGGER.info("Program bitti: exit_code=%s", completed.returncode)
        return int(completed.returncode)
    except subprocess.TimeoutExpired:
        LOGGER.error("Program %s saniyelik calisma sinirini asti.", timeout)
        print(f"Piko durduruldu: program {timeout} saniye icinde bitmedi.", file=sys.stderr)
        return 124
    except OSError as exc:
        LOGGER.exception("Alt surec baslatilamadi.")
        print(f"Calistirma hatasi: {exc}", file=sys.stderr)
        return 1



def run_self_tests() -> int:
    """Run focused regression tests for translation, scanning and firewall rules."""
    tests: list[tuple[str, Any]] = []
    tests.append(("Piko print command", lambda: "print(\"Merhaba\")" in translate('yaz("Merhaba")')))
    tests.append(("String contents stay unchanged", lambda: 'print("degil ve yaz")' in translate('yaz("degil ve yaz")')))
    tests.append(("Comments stay unchanged", lambda: "# eger degilse yaz" in translate("# eger degilse yaz")))
    tests.append(("Condition translation", lambda: "if True:" in translate("eger dogru:")))
    tests.append(("Function parameter parsing", lambda: "def topla(a, b):" in translate("fonk topla(a, b):")))
    tests.append(("GUI runtime imports", lambda: "from piko_runtime_1_7 import gui_pencere" in (runtime_prelude(translate('gui_pencere("Test", 400, 300)')))))
    tests.append(("Web runtime imports", lambda: "web_proje" in runtime_prelude(translate('web_proje("site")'))))
    tests.append(("Ping runtime import", lambda: "ag_ping" in runtime_prelude(translate('ag_ping("example.com")'))))
    tests.append(("Internet check runtime import", lambda: "internet_var_mi" in runtime_prelude(translate('internet_var_mi()'))))
    tests.append(("Game runtime import", lambda: "oyun_baslat" in runtime_prelude(translate('oyun_baslat(guncelle)'))))
    tests.append(("Runtime module imports", lambda: __import__("piko_runtime_1_7").ag_ping is not None))
    def ping_rejects_url_input() -> bool:
        runtime = __import__("piko_runtime_1_7")
        try:
            runtime.ag_ping("https://example.com")
        except ValueError:
            return True
        return False
    tests.append(("Ping rejects URL-shaped input", ping_rejects_url_input))
    def game_key_state_works() -> bool:
        runtime = __import__("piko_runtime_1_7")
        runtime._GAME.keys.add("space")
        result = runtime.oyun_tus_basildi_mi("SPACE")
        runtime._GAME.keys.clear()
        return result
    tests.append(("Game key-state helper", game_key_state_works))
    def web_helpers_write_project_files() -> bool:
        import tempfile
        runtime = __import__("piko_runtime_1_7")
        old_cwd = Path.cwd()
        try:
            with tempfile.TemporaryDirectory(prefix="piko16_") as temp_dir:
                os.chdir(temp_dir)
                runtime.web_proje("test_site")
                runtime.web_html("<h1>test</h1>")
                runtime.web_css("h1 { color: blue; }")
                runtime.web_js("console.log('test');")
                project = Path(temp_dir) / "piko_web_projects" / "test_site"
                return all((project / name).is_file() for name in ("index.html", "style.css", "app.js"))
        finally:
            os.chdir(old_cwd)
            runtime._WEB_PROJECT = None
    tests.append(("Web helpers create project files", web_helpers_write_project_files))
    tests.append(("Firewall blocks os import", lambda: bool(firewall_check("import os")[0])))
    tests.append(("Firewall blocks eval", lambda: bool(firewall_check("eval('1 + 1')")[0])))
    def function_scan() -> bool:
        _, report = firewall_check(translate("fonk selam():\n    yaz(\"hi\")"))
        return "selam" in report["functions"]
    tests.append(("Function scanner finds functions", function_scan))
    def translated_code_compiles() -> bool:
        body = translate("fonk kare(x):\n    ver x * x\nyaz(kare(4))")
        compile(body, "<piko-self-test>", "exec")
        return True
    tests.append(("Translated code compiles", translated_code_compiles))
    # Piko 1.7 standard-library regression tests
    tests.append(("Tuple and set constructors", lambda: "tuple((1, 2))" in translate("demet((1, 2))") and "set([1, 2])" in translate("kume([1, 2])")))
    tests.append(("String helper runtime import", lambda: "metin_bol" in runtime_prelude(translate('metin_bol("a,b", ",")'))))
    tests.append(("List helper runtime import", lambda: "liste_ekle" in runtime_prelude(translate("liste_ekle(veriler, 3)"))))
    tests.append(("Dictionary helper runtime import", lambda: "sozluk_al" in runtime_prelude(translate('sozluk_al(veri, "ad")'))))
    tests.append(("Math helper runtime import", lambda: "karekok" in runtime_prelude(translate("karekok(81)"))))
    tests.append(("Runtime 1.7 imports", lambda: __import__("piko_runtime_1_7").metin_buyut("piko") == "PIKO"))
    tests.append(("List helpers work", lambda: __import__("piko_runtime_1_7").liste_ekle([1], 2) == [1, 2]))
    tests.append(("Dictionary helpers work", lambda: __import__("piko_runtime_1_7").sozluk_al({"x": 4}, "x") == 4))
    tests.append(("Math helpers work", lambda: __import__("piko_runtime_1_7").karekok(81) == 9))
    tests.append(("Firewall blocks dunder introspection", lambda: bool(firewall_check("x.__class__.__mro__")[0])))
    tests.append(("Metrics are reported", lambda: "metrics" in firewall_check(translate("fonk x():\n    ver 1\n"))[1]))
    tests.append(("Text replacement helper", lambda: __import__("piko_runtime_1_7").metin_degistir("piko 1.6", "1.6", "1.7") == "piko 1.7"))
    tests.append(("Text split helper", lambda: __import__("piko_runtime_1_7").metin_bol("a,b", ",") == ["a", "b"]))
    tests.append(("List pop helper", lambda: (__import__("piko_runtime_1_7").liste_cikar([7, 8], 0) == 7)))
    tests.append(("Dictionary delete helper", lambda: __import__("piko_runtime_1_7").sozluk_sil({"a": 1}, "a") is True))
    tests.append(("Factorial helper", lambda: __import__("piko_runtime_1_7").faktoriyel(5) == 120))
    tests.append(("Firewall blocks subprocess import", lambda: bool(firewall_check("import subprocess")[0])))
    tests.append(("Firewall allows math import", lambda: not firewall_check("import math")[0]))
    passed = 0
    print(f"Piko {VERSION} SELF-TEST\n" + "=" * 38)
    for label, test in tests:
        try:
            result = bool(test())
        except Exception as exc:
            result = False
            LOGGER.exception("SELF-TEST exception: %s", label)
            print(f"[FAIL] {label}: {type(exc).__name__}: {exc}")
        else:
            print(f"[{ 'OK' if result else 'FAIL' }] {label}")
        passed += int(result)
    print("-" * 38)
    print(f"Sonuc: {passed}/{len(tests)} test basarili")
    return 0 if passed == len(tests) else 1

def launch_ide() -> int:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError:
        print("GUI acilamadi: Python kurulumunda Tkinter bulunamadi.", file=sys.stderr)
        return 1

    root = tk.Tk()
    root.title(f"Piko IDE {VERSION}")
    root.geometry("1100x780")
    root.minsize(780, 560)
    log_queue: queue.Queue[str] = queue.Queue()
    queue_handler = DebugQueueHandler(log_queue)
    configure_logging(logging.DEBUG, "piko_debug.log", [queue_handler])
    current_file: dict[str, Path | None] = {"path": None}

    toolbar = ttk.Frame(root, padding=6)
    toolbar.pack(fill="x")
    status = tk.StringVar(value="Hazir | Piko 1.7")
    ttk.Label(root, textvariable=status, anchor="w", padding=(8, 4)).pack(side="bottom", fill="x")

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=6, pady=4)
    editor_tab = ttk.Frame(notebook)
    python_tab = ttk.Frame(notebook)
    debug_tab = ttk.Frame(notebook)
    notebook.add(editor_tab, text="Piko Editor")
    notebook.add(python_tab, text="Python Ciktisi")
    notebook.add(debug_tab, text="Debug / Guvenlik")

    editor = tk.Text(editor_tab, wrap="none", undo=True, font=("Consolas", 11), tabs=(32,))
    editor.pack(fill="both", expand=True)
    python_output = tk.Text(python_tab, wrap="none", font=("Consolas", 10))
    python_output.pack(fill="both", expand=True)
    debug_output = tk.Text(debug_tab, wrap="none", font=("Consolas", 9), state="disabled")
    debug_output.pack(fill="both", expand=True)
    editor.insert("1.0", '''program "Piko GUI Ornegi"

fonk selamla():
    gui_mesaj("Piko", "Merhaba! GUI butonu calisti.")

gui_pencere("Piko Uygulamam", 520, 300)
gui_yazi("Piko ile ilk penceren!", 20, 20)
gui_buton("Tikla", 20, 65, selamla)
gui_goster()
''')

    def log_to_debug(message: str) -> None:
        debug_output.configure(state="normal")
        debug_output.insert("end", message + "\n")
        debug_output.see("end")
        debug_output.configure(state="disabled")

    def drain_logs() -> None:
        try:
            while True:
                log_to_debug(log_queue.get_nowait())
        except queue.Empty:
            pass
        root.after(100, drain_logs)

    def get_source() -> str:
        return editor.get("1.0", "end-1c")

    def save_file() -> bool:
        path = current_file["path"]
        if path is None:
            chosen = filedialog.asksaveasfilename(
                defaultextension=".piko", filetypes=[("Piko dosyasi", "*.piko"), ("Tum dosyalar", "*.*")]
            )
            if not chosen:
                return False
            path = Path(chosen)
            current_file["path"] = path
        try:
            path.write_text(get_source(), encoding="utf-8")
            root.title(f"Piko IDE {VERSION} - {path.name}")
            status.set(f"Kaydedildi: {path}")
            LOGGER.info("Dosya kaydedildi: %s", path)
            return True
        except OSError as exc:
            messagebox.showerror("Kaydetme hatasi", str(exc))
            LOGGER.exception("Dosya kaydedilemedi.")
            return False

    def open_file() -> None:
        chosen = filedialog.askopenfilename(filetypes=[("Piko dosyasi", "*.piko"), ("Tum dosyalar", "*.*")])
        if not chosen:
            return
        path = Path(chosen)
        try:
            editor.delete("1.0", "end")
            editor.insert("1.0", path.read_text(encoding="utf-8"))
            current_file["path"] = path
            root.title(f"Piko IDE {VERSION} - {path.name}")
            status.set(f"Acildi: {path}")
            LOGGER.info("Dosya acildi: %s", path)
        except (OSError, UnicodeDecodeError) as exc:
            messagebox.showerror("Dosya acma hatasi", str(exc))
            LOGGER.exception("Dosya acilamadi.")

    def translate_current() -> tuple[Path | None, str, list[str], dict[str, Any]]:
        source = get_source()
        body, full, issues, report = prepare_python(source)
        python_output.delete("1.0", "end")
        python_output.insert("1.0", full)
        notebook.select(python_tab)
        LOGGER.info("IDE ceviri butonu kullanildi.")
        LOGGER.debug("Tarama ozeti: functions=%d calls=%d imports=%d", len(report["functions"]), len(report["calls"]), len(report["imports"]))
        return current_file["path"], full, issues, report

    def translate_button() -> None:
        try:
            _, _, issues, report = translate_current()
            log_to_debug(format_scan_report(report, issues))
            status.set("Ceviri tamamlandi" if not issues else f"Guvenlik duvari {len(issues)} sorun buldu")
            if issues:
                messagebox.showwarning("Piko Guvenlik Duvari", "Program calistirilmayacak. Debug sekmesindeki engelleri incele.")
        except Exception as exc:
            LOGGER.exception("Ceviri sirasinda beklenmeyen hata.")
            messagebox.showerror("Ceviri hatasi", str(exc))

    def scan_button() -> None:
        try:
            _, _, issues, report = translate_current()
            log_to_debug(format_scan_report(report, issues))
            notebook.select(debug_tab)
            status.set("Fonksiyon ve guvenlik taramasi tamamlandi")
        except Exception:
            LOGGER.exception("Tarama hatasi.")

    def run_button() -> None:
        if not save_file():
            return
        path = current_file["path"]
        assert path is not None
        try:
            _, full, issues, report = translate_current()
            log_to_debug(format_scan_report(report, issues))
            if issues:
                messagebox.showerror("Guvenlik duvari", "Riskli kod engellendi. Program calistirilmadi.")
                status.set("Calistirma engellendi")
                return
            output_path = path.with_suffix(".py")
            output_path.write_text(full, encoding="utf-8")
            copy_runtime_if_needed(full, output_path.parent)
            script = Path(__file__).resolve()
            command = [sys.executable, str(script), str(path), "--run", "--debug"]
            LOGGER.info("IDE run komutu: %s", command)
            status.set("Program alt surecte calisiyor...")
            def worker() -> None:
                try:
                    process = subprocess.Popen(
                        command, cwd=str(path.parent), stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace"
                    )
                    assert process.stdout is not None
                    for output_line in process.stdout:
                        log_queue.put("RUN | " + output_line.rstrip())
                    return_code = process.wait()
                    log_queue.put(f"RUN | Program kapandi (kod={return_code})")
                except Exception as exc:
                    log_queue.put(f"RUN | Baslatma hatasi: {exc}")
                    LOGGER.exception("IDE program calistirma hatasi.")
                root.after(0, lambda: status.set("Program kapandi"))
            threading.Thread(target=worker, daemon=True).start()
            notebook.select(debug_tab)
        except Exception as exc:
            LOGGER.exception("IDE calistirma islemi basarisiz.")
            messagebox.showerror("Calistirma hatasi", str(exc))

    def new_file() -> None:
        if messagebox.askyesno("Yeni dosya", "Editor icerigi temizlensin mi?"):
            editor.delete("1.0", "end")
            current_file["path"] = None
            root.title(f"Piko IDE {VERSION} - Yeni dosya")
            status.set("Yeni dosya")

    def show_help() -> None:
        messagebox.showinfo("Piko 1.7 Komutlari",
            "Kosullar: eger / yada / degilse\nDongu: iken / tekrar / her oge icinde liste\n"
            "Fonksiyon: fonk ad(a, b): / ver deger\nGUI: gui_pencere, gui_yazi, gui_giris, gui_al, gui_buton, gui_mesaj, gui_goster\n"
            "Web: web_proje, web_html, web_css, web_js, web_onizle\n"
            "Oyun: oyun_pencere, oyun_temizle, oyun_ciz_kare, oyun_ciz_yazi, oyun_tus_basildi_mi, oyun_baslat\n"
            "Ag: ag_ping, internet_var_mi\n"
            "1.7: metin/liste/sozluk/matematik/rastgele/zaman yardimcilari. Debug: piko_debug.log.")

    buttons = [
        ("Yeni", new_file), ("Ac", open_file), ("Kaydet", save_file),
        ("Cevir", translate_button), ("Fonksiyon Tara", scan_button),
        ("Calistir", run_button), ("Yardim", show_help),
    ]
    for label, callback in buttons:
        ttk.Button(toolbar, text=label, command=callback).pack(side="left", padx=3)
    LOGGER.info("Piko IDE acildi.")
    root.after(100, drain_logs)
    root.mainloop()
    LOGGER.info("Piko IDE kapatildi.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"Piko Translator {VERSION}: GUI, web, games, network diagnostics, function scan and debug tools.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Ornekler:\n  python piko_translator_1_7.py --gui\n  python piko_translator_1_7.py ornek.piko --scan --debug\n  python piko_translator_1_7.py ornek.piko --run --trace",
    )
    parser.add_argument("file", nargs="?", help="Cevirilecek .piko dosyasi")
    parser.add_argument("--gui", action="store_true", help="Piko grafik editorunu ac")
    parser.add_argument("--run", action="store_true", help="Guvenlik taramasindan sonra calistir")
    parser.add_argument("--show", action="store_true", help="Python ciktisini ekrana yaz")
    parser.add_argument("--scan", action="store_true", help="Fonksiyonlari ve guvenlik kurallarini tara")
    parser.add_argument("--self-test", action="store_true", help="Cevirici ve guvenlik testlerini calistir")
    parser.add_argument("--dil", "--language", action="store_true", help="Piko komutlarini goster")
    parser.add_argument("--debug", action="store_true", help="Ayrintili debug kaydi ac")
    parser.add_argument("--trace", action="store_true", help="Satir/token seviyesinde cok ayrintili trace ac")
    parser.add_argument("--json-report", metavar="DOSYA", help="Fonksiyon, guvenlik ve metrik raporunu JSON olarak kaydet")
    parser.add_argument("--debug-file", default="piko_debug.log", help="Debug log dosyasi (varsayilan: piko_debug.log)")
    args = parser.parse_args()

    log_level = TRACE_LEVEL if args.trace else (logging.DEBUG if args.debug else logging.WARNING)
    log_file = args.debug_file if (args.debug or args.trace) else None
    configure_logging(log_level, log_file)
    LOGGER.debug("CLI argumanlari: %r", vars(args))

    if args.gui:
        return launch_ide()
    if args.self_test:
        return run_self_tests()
    if args.dil:
        print("""Piko 1.7 - Turkce ASCII komutlari
  eger / yada / degilse / iken
  tekrar N: / her oge icinde liste:
  fonk ad(a, b): / ver deger
  dene: / yakala: / sonunda:
  yaz(...) / sor(...) / sayi(...) / metin(...)
  gui_pencere(...) / gui_yazi(...) / gui_giris(...) / gui_buton(...) / gui_goster()
  web_proje(...) / web_html(...) / web_css(...) / web_js(...) / web_onizle(8000)
  oyun_pencere(...) / oyun_temizle() / oyun_ciz_kare(...) / oyun_ciz_yazi(...)
  oyun_tus_basildi_mi(...) / oyun_baslat(guncelle, 60)
  ag_ping("example.com") / internet_var_mi()
  Metin: metin_buyut, metin_kucult, metin_kirp, metin_bol, metin_degistir, metin_bul
  Liste: liste_ekle, liste_cikar, liste_kopyala, liste_sirala, liste_ters
  Sozluk: sozluk_al, sozluk_anahtarlar, sozluk_degerler, sozluk_sil, sozluk_var_mi
  Matematik: karekok, sinus, kosinus, faktoriyel, taban, tavan
  Rastgele/zaman: rastgele_sayi, rastgele_sec, simdi
  Demet/kume: demet(...), kume(...)
  debug: --debug | token/line trace: --trace | function scan: --scan
  JSON raporu: --json-report rapor.json
  Guvenlik: --run oncesi AST tabanli guvenlik taramasi yapilir.""")
        return 0
    if not args.file:
        return launch_ide()

    source_path = Path(args.file).expanduser()
    LOGGER.info("Girdi dosyasi: %s", source_path)
    if not source_path.is_file():
        print(f"Hata: Dosya bulunamadi: {source_path}", file=sys.stderr)
        LOGGER.error("Girdi dosyasi bulunamadi.")
        return 1
    try:
        source = source_path.read_text(encoding="utf-8")
        body, python_code, issues, report = prepare_python(source)
    except (UnicodeDecodeError, OSError) as exc:
        print(f"Hata: Dosya okunamadi: {exc}", file=sys.stderr)
        LOGGER.exception("Dosya okuma hatasi.")
        return 1

    if args.json_report:
        report_payload = {"version": VERSION, "issues": issues, **report}
        try:
            Path(args.json_report).write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"JSON raporu kaydedildi: {args.json_report}")
        except OSError as exc:
            print(f"JSON raporu yazilamadi: {exc}", file=sys.stderr)
            return 1
    if args.scan:
        print(format_scan_report(report, issues))
    if issues:
        print("\nPiko Guvenlik Duvari programi engelledi:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        if args.run:
            LOGGER.error("Program guvenlik duvari nedeniyle calistirilmadi.")
            return 2

    if args.scan and not args.run and not args.show:
        if issues:
            return 2
        try:
            compile(python_code, str(source_path), "exec")
        except SyntaxError as exc:
            print(f"Piko yazim hatasi, satir {exc.lineno}: {exc.msg}", file=sys.stderr)
            return 1
        LOGGER.info("Tarama-only modu: cikti dosyasi olusturulmadi.")
        return 0

    if args.show:
        print(python_code, end="")
        return 0

    try:
        compile(python_code, str(source_path), "exec")
        LOGGER.info("Derleme kontrolu basarili.")
    except SyntaxError as exc:
        print(f"Piko yazim hatasi, satir {exc.lineno}: {exc.msg}", file=sys.stderr)
        LOGGER.exception("Python sozdizimi kontrolu basarisiz.")
        return 1

    output_path = source_path.with_suffix(".py")
    try:
        output_path.write_text(python_code, encoding="utf-8")
        copy_runtime_if_needed(body, output_path.parent)
        LOGGER.info("Python ciktisi yazildi: %s", output_path)
    except OSError as exc:
        print(f"Cikti dosyasi yazilamadi: {exc}", file=sys.stderr)
        LOGGER.exception("Cikti yazma hatasi.")
        return 1

    if args.run:
        print(f"--- {source_path.name} Piko {VERSION} ile calisiyor ---")
        return run_generated(output_path, source, timeout=8.0)
    if not args.scan:
        print(f"Ceviri tamamlandi: {output_path}")
    if args.debug or args.trace:
        print(f"Debug kaydi: {Path(args.debug_file).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
