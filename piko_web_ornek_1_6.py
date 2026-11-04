# Piko 1.6 runtime baglantisi
from piko_runtime_1_6 import web_css, web_html, web_js, web_onizle, web_proje

# program "Piko 1.6 Web Ornegi"

web_proje("ilk_sitem")
web_html("<!doctype html><html lang='tr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Piko</title><link rel='stylesheet' href='style.css'></head><body><h1>Merhaba Piko!</h1><p>Bu site Piko ile olusturuldu.</p><button onclick='selam()'>Tikla</button><script src='app.js'></script></body></html>")
web_css("body { font-family: Arial, sans-serif; margin: 3rem; background: #f3f6ff; } h1 { color: #3155a6; } button { padding: 10px 16px; }")
web_js("function selam() { alert('Piko calisiyor!'); }")
# web_onizle(8000) komutunu calistirmak yerel onizleme sunucusunu baslatir.
