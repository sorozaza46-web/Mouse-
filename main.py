import time
import threading
import keyboard
import pyautogui
import cv2
import numpy as np
import os
import sys
import customtkinter as ctk
import mss
from ultralytics import YOLO

# Global Kontroller
bot_calisiyor = False
baslat_durdur_tusu = "f6"
olta_at_tusu = "2"
balik_cek_tusu = "3"

# Yapay Zeka Ayarları
MODEL_YOLU = "olta_modeli.pt"  # Eğittiğin model dosyasının adı
GUVEN_ESIGI = 0.50             # %50 ve üzeri benzerlikte oltayı kabul et

def kaynak_yolu(goreli_yol):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, goreli_yol)

# Yapay Zeka Modelini Yüklüyoruz
try:
    model = YOLO(kaynak_yolu(MODEL_YOLU))
    yolo_aktif = True
except Exception as e:
    yolo_aktif = False
    print(f"[HATA] Model yüklenemedi! {MODEL_YOLU} dosyasını kodun yanına attığından emin ol: {e}")

def ekranda_oltayi_yolo_ile_ara():
    """Tüm ekranı saliseler içinde yakalar ve YOLOv8 ile oltanın yerini tespit eder."""
    with mss.mss() as sct:
        # Birinci monitörün tüm ekranını yakala
        ekran_boyutu = sct.monitors[1]
        ekran = sct.grab(ekran_boyutu)
        
        # Görüntüyü YOLO'nun anlayacağı formata çevir
        img = np.array(ekran)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
        # Yapay zekadan tahmin iste
        sonuclar = model.predict(source=img, conf=GUVEN_ESIGI, verbose=False)
        
        for sonuc in sonuclar:
            kutular = sonuc.boxes
            for kutu in kutular:
                # Koordinatları al (Sol üst ve Sağ alt köşe)
                x1, y1, x2, y2 = kutu.xyxy[0].tolist()
                
                # Oltanın bulunduğu bölgeyi (Genişlik ve Yükseklik olarak) hesapla
                sol = int(x1)
                ust = int(y1)
                genislik = int(x2 - x1)
                yukseklik = int(y2 - y1)
                
                # Tolerans payı ekleyerek bölgeyi döndür
                return (sol - 10, ust - 10, genislik + 20, yukseklik + 20)
                
    return None

def balik_botu_dongusu(log_callback):
    global bot_calisiyor
    
    if not yolo_aktif:
        log_callback("[!] HATA: Yapay zeka modeli yüklü değil! Bot başlatılamadı.")
        bot_calisiyor = False
        return

    log_callback("[+] Yapay Zeka Botu Başlatıldı! Oyuna odaklanın.")
    
    log_callback("[+] İlk olta atılıyor...")
    pyautogui.press(olta_at_tusu)
    time.sleep(2.5)

    # Yapay zeka ile oltayı ara
    olta_alani = ekranda_oltayi_yolo_ile_ara()
    if not olta_alani:
        log_callback("[!] Olta ekranda bulunamadı! Yapay zeka göremiyor.")
        bot_calisiyor = False
        return

    log_callback(f"[+] Yapay Zeka oltaya kilitlendi! Koordinat: {olta_alani[:2]}")
    
    # Kilitlenilen alanın ilk halini hafızaya al (Hareket takibi için)
    ilk_ekran = pyautogui.screenshot(region=olta_alani)
    eski_kare = cv2.cvtColor(np.array(ilk_ekran), cv2.COLOR_RGB2GRAY)

    while bot_calisiyor:
        # Sadece oltanın olduğu küçük bölgeyi izle (Hız ve performans için)
        anlik_ekran = pyautogui.screenshot(region=olta_alani)
        yeni_kare = cv2.cvtColor(np.array(anlik_ekran), cv2.COLOR_RGB2GRAY)

        # İki kare arasındaki piksel farklarını hesapla (Balık vurma/hareket algılama)
        fark = cv2.absdiff(eski_kare, yeni_kare)
        hareket_miktari = np.sum(fark > 30)

        if hareket_miktari > 120: 
            log_callback("[!] Yapay Zeka Hareketi Yakaladı! Balık vurdu, çekiliyor...")
            pyautogui.press(balik_cek_tusu)
            time.sleep(2.0)
            
            if not bot_calisiyor: 
                break
            
            log_callback("[+] Yeniden olta atılıyor...")
            pyautogui.press(olta_at_tusu)
            time.sleep(2.5)
            
            # Yeni atılan oltanın yerini yapay zeka ile tekrar tara
            olta_alani = ekranda_oltayi_yolo_ile_ara()
            if not olta_alani: 
                log_callback("[-] Olta gözden kayboldu veya yapay zeka kaçırdı.")
                bot_calisiyor = False
                break
                
            ilk_ekran = pyautogui.screenshot(region=olta_alani)
            yeni_kare = cv2.cvtColor(np.array(ilk_ekran), cv2.COLOR_RGB2GRAY)

        eski_kare = yeni_kare
        time.sleep(0.04)

class BotArayuz(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Nostale Yapay Zeka Balık Botu v4.0")
        self.geometry("460x420")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.lbl_baslik = ctk.CTkLabel(self, text="Nostale Yapay Zeka Botu", font=("Arial", 18, "bold"))
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
        
        if yolo_aktif:
            self.log_yaz("[*] Menü hazır. [YOLOv Durumu: AKTİF] Model yüklendi.")
        else:
            self.log_yaz("[!] Menü hazır fakat 'olta_modeli.pt' bulunamadı!")
        
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
        
