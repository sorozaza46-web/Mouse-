import time
import threading
import keyboard
import pyautogui
import cv2
import numpy as np
import os
import sys
import customtkinter as ctk

# Global Kontroller
bot_calisiyor = False
baslat_durdur_tusu = "f6"
olta_at_tusu = "2"
balik_cek_tusu = "3"

def kaynak_yolu(goreli_yol):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, goreli_yol)

# Şablon Listesi (İstediğin kadar olta ekleyebilirsin)
SABLONLAR = ["olta_sablonu.png", "olta_sablonu2.png"]
SABLON_YOLLARI = [kaynak_yolu(s) for s in SABLONLAR]

def ekranda_oltayi_ara():
    ekran = pyautogui.screenshot()
    ekran_cv = cv2.cvtColor(np.array(ekran), cv2.COLOR_RGB2GRAY)
    
    # Tüm tanımlı olta şablonlarını sırayla tara
    for yol in SABLON_YOLLARI:
        if not os.path.exists(yol):
            continue
            
        sablon_img = cv2.imread(yol, cv2.IMREAD_GRAYSCALE)
        sablon_h, sablon_w = sablon_img.shape
        
        sonuc = cv2.matchTemplate(ekran_cv, sablon_img, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(sonuc)
        
        # %65 eşleşme toleransı
        if max_val >= 0.65:
            sol_ust = max_loc
            # Hangi şablonla eşleştiğini bulduk, onun boyutlarına göre bölge dönüyoruz
            return (sol_ust[0] - 10, sol_ust[1] - 10, sablon_w + 20, sablon_h + 20)
            
    return None

def balik_botu_dongusu(log_callback):
    global bot_calisiyor
    log_callback("[+] Bot başlatıldı! Oyuna odaklanın.")
    
    pyautogui.press(olta_at_tusu)
    time.sleep(2.5)

    # Çoklu şablon kontrolüyle oltayı ara
    olta_alani = ekranda_oltayi_ara()
    if not olta_alani:
        log_callback("[!] Olta ekranda bulunamadı! (Şablon 1 ve 2 kontrol edildi)")
        bot_calisiyor = False
        return

    log_callback(f"[+] Olta tespit edildi, kilitlendi: {olta_alani[:2]}")
    
    ilk_ekran = pyautogui.screenshot(region=olta_alani)
    eski_kare = cv2.cvtColor(np.array(ilk_ekran), cv2.COLOR_RGB2GRAY)

    while bot_calisiyor:
        anlik_ekran = pyautogui.screenshot(region=olta_alani)
        yeni_kare = cv2.cvtColor(np.array(anlik_ekran), cv2.COLOR_RGB2GRAY)

        fark = cv2.absdiff(eski_kare, yeni_kare)
        hareket_miktari = np.sum(fark > 30)

        if hareket_miktari > 120: 
            log_callback("[!] Balık vurdu! Çekiliyor...")
            pyautogui.press(balik_cek_tusu)
            time.sleep(2.0)
            
            if not bot_calisiyor: break
            
            log_callback("[+] Yeniden olta atılıyor...")
            pyautogui.press(olta_at_tusu)
            time.sleep(2.5)
            
            olta_alani = ekranda_oltayi_ara()
            if not olta_alani: 
                log_callback("[-] Olta gözden kayboldu.")
                bot_calisiyor = False
                break
                
            ilk_ekran = pyautogui.screenshot(region=olta_alani)
            yeni_kare = cv2.cvtColor(np.array(ilk_ekran), cv2.COLOR_RGB2GRAY)

        eski_kare = yeni_kare
        time.sleep(0.04)

class BotArayuz(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Nostale Balık Botu v3.5 (Çoklu Şablon)")
        self.geometry("460x420")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.lbl_baslik = ctk.CTkLabel(self, text="Nostale Balık Botu", font=("Arial", 18, "bold"))
        self.lbl_baslik.pack(pady=15)
        
        self.frame_ayarlar = ctk.CTkFrame(self)
        self.frame_ayarlar.pack(pady=10, padx=20, fill="x")
        
        self.lbl_bd = ctk.CTkLabel(self.frame_ayarlar, text="Başlat/Durdur Tuşu:", font=("Arial", 12))
        self.lbl_bd.grid(row=0, column=0, padx=15, pady=8, sticky="w")
        self.ent_bd = ctk.CTkEntry(self.frame_ayarlar, width=120)
        self.ent_bd.insert(0, baslat_durdur_tusu.upper())
        self.ent_bd.grid(row=0, column=1, padx=15, pady=8)
        
        self.lbl_olta = ctk.CTkLabel(self.frame_ayarlar, text="Olta Atma Tuşu (Oyun İçi):", font=("Arial", 12))
        self.lbl_olta.grid(row=1, column=0, padx=15, pady=8, sticky="w")
        self.ent_olta = ctk.CTkEntry(self.frame_ayarlar, width=120)
        self.ent_olta.insert(0, olta_at_tusu)
        self.ent_olta.grid(row=1, column=1, padx=15, pady=8)
        
        self.lbl_cek = ctk.CTkLabel(self.frame_ayarlar, text="Balık Çekme Tuşu (Oyun İçi):", font=("Arial", 12))
        self.lbl_cek.grid(row=2, column=0, padx=15, pady=8, sticky="w")
        self.ent_cek = ctk.CTkEntry(self.frame_ayarlar, width=120)
        self.ent_cek.insert(0, balik_cek_tusu)
        self.ent_cek.grid(row=2, column=1, padx=15, pady=8)
        
        self.btn_kaydet = ctk.CTkButton(self, text="Ayarları Kaydet ve Kısayolu Dinle", font=("Arial", 12, "bold"), command=self.ayarlari_uygula)
        self.btn_kaydet.pack(pady=10)
        
        self.txt_log = ctk.CTkTextbox(self, height=130, width=420, font=("Consolas", 11))
        self.txt_log.pack(pady=10, padx=20)
        self.log_yaz("[*] Menü hazır. Çift olta algılama modu aktif.")
        
    def log_yaz(self, mesaj):
        self.txt_log.insert("end", mesaj + "\n")
        self.txt_log.see("end")
        
    def ayarlari_uygula(self):
        global baslat_durdur_tusu, olta_at_tusu, balik_cek_tusu
        baslat_durdur_tusu = self.ent_bd.get().lower()
        olta_at_tusu = self.ent_olta.get()
        balik_cek_tusu = self.ent_cek.get()
        
        keyboard.unhook_all()
        keyboard.add_hotkey(baslat_durdur_tusu, self.tetikleyici)
        self.log_yaz(f"[+] Kısayol '{baslat_durdur_tusu.upper()}' dinleniyor...")

    def tetikleyici(self):
        global bot_calisiyor
        if not bot_calisiyor:
            bot_calisiyor = True
            threading.Thread(target=balik_botu_dongusu, args=(self.log_yaz,), daemon=True).start()
        else:
            bot_calisiyor = False
            self.log_yaz("[-] Bot durduruldu.")

if __name__ == "__main__":
    app = BotArayuz()
    app.mainloop()
    
