# Piko 1.6 runtime baglantisi
from piko_runtime_1_6 import ag_ping, internet_var_mi

# program "Piko 1.6 Ag Kontrolu"

# Yalnizca kendi aginda veya kontrol etme iznin olan adresleri test et.
print("Internet var mi?", internet_var_mi())
print("example.com ping (ms):", ag_ping("example.com"))
