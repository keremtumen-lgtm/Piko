# Piko 1.6 runtime baglantisi
from piko_runtime_1_6 import gui_al, gui_buton, gui_giris, gui_goster, gui_mesaj, gui_pencere, gui_yazi

# program "Piko 1.6 GUI Ornegi"

def selamla():
    isim = gui_al("isim")
    gui_mesaj("Piko", "Merhaba " + isim + "!")

gui_pencere("Piko GUI", 520, 320)
gui_yazi("Piko 1.6 ile ilk arayuzum", 20, 20)
gui_yazi("Adin:", 20, 65)
gui_giris("isim", 20, 95, 28)
gui_buton("Selamla", 20, 140, selamla)
gui_goster()
