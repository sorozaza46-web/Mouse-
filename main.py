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

# Windows API kütüphaneleri (Ekran üzeri kırmızı çizim için)
import win32gui
import win32con

# Global Kontroller
bot_calisiyor = False
baslat_durdur_tusu = "f6"
olta_at_tusu = "2"
balik_cek_tusu = "3"
secilen_bot_modu = "Otomatik (Yapay Zeka)" # Varsayılan Mod
elle_secilen_alan = None # Butonla seçilen koordinatları tutar

# Yapay Zeka Ayarları
MODEL_YOLU = "olta_modeli.pt"  
GUVEN_ESIGI = 0.25             

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
    print(f"[HATA] Model yüklenemedi! {MODEL_YOLU} dosyasını kontrol et: {e}")

def oyuna_tus_gonder(tus):
    """Oyunların algılaması için tuşa 100ms boyunca basılı tutup bırakır."""
    try:
        keyboard.press(tus)
        time.sleep(0.1)  
        keyboard.release(tus)
    except Exception as e:
        print(f"[Tuş Hatası]: {e}")

def ekrana_kirmizi_kare_ciz(x1, y1, x2, y2, sure=0.8):
    """Doğrudan Windows ekranının üzerine kırmızı bir çerçeve çizer."""
    hdc = win32gui.GetDC(0)
    renk = win32gui.RGB(255, 0, 0)
    kalem = win32gui.CreatePen(win32con.PS_SOLID, 3, renk)
    eski_kalem = win32gui.SelectObject(hdc, kalem)
    
    baslangic = time.time()
    while time.time() - baslangic < sure:
        win32gui.MoveToEx(hdc, x1, y1)
        win32gui.LineTo(hdc, x2, y1)
        win32gui.LineTo(hdc, x2, y2)
        win32gui.LineTo(hdc, x1, y2)
        win32gui.LineTo(hdc, x1, y1)
        time.sleep(0.05)
        
    win32gui.SelectObject(hdc, eski_kalem)
    win32gui.DeleteObject(kalem)
    win32gui.ReleaseDC(0, hdc)
    win32gui.InvalidateRect(0, (x1-5, y1-5, x2+5, y2+5), True)

def ekrandan_elle_bolge_sec_buton(log_callback):
    """Menüdeki yeşil butona basıldığında ekran alıntısı gibi bölge seçtirir."""
    global elle_secilen_alan
    log_callback("[!] Ekran alıntısı aktif! Fare ile olta bölgesini seçin ve ENTER'a basın.")
    
    time.sleep(0.5) # Oyuna geçiş için ufak es
    
    with mss.mss() as sct:
        ekran_boyutu = sct.monitors[1]
        ekran = sct.grab(ekran_boyutu)
        img = np.array(ekran)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    
    cv2.namedWindow("Olta Bolgesi Secim Ekrani", cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty("Olta Bolgesi Secim Ekrani", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    
    r = cv2.selectROI("Olta Bolgesi Secim Ekrani", img, fromCenter=False, showCrosshair=True)
    cv2.destroyWindow("Olta Bolgesi Secim Ekrani")
    
    if r[2] > 0 and r[3] > 0:
        sol, ust, genislik, yukseklik = map(int, r)
        elle_secilen_alan = (sol, ust, genislik, yukseklik)
        log_callback(f"[+] Manuel bölge kaydedildi! Koordinat: {elle_secilen_alan[:2]}")
        threading.Thread(target=ekrana_kirmizi_kare_ciz, args=(sol, ust, sol+genislik, ust+yukseklik, 1.0), daemon=True).start()
    else:
        log_callback("[-] Seçim iptal edildi veya geçersiz bölge.")

def ekranda_oltayi_yolo_ile_ara(log_callback):
    """Ekranı tarar, oltayı bulursa doğrudan ekrana kırmızı kare çizip koordinat döner."""
    olta_koordinati = None
    
    with mss.mss() as sct:
        ekran_boyutu = sct.monitors[1]
        baslangic_zamani = time.time()
        log_callback("[*] Ekran üzerinde yapay zekayla olta aranıyor...")
        
        while time.time() - baslangic_zamani < 5.0:
            ekran = sct.grab(ekran_boyutu)
            img = np.array(ekran)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            sonuclar = model.predict(source=img, conf=GUVEN_ESIGI, verbose=False)
            bulundu = False
            
            for sonuc in sonuclar:
                kutular = sonuc.boxes
                for kutu in kutular:
                    x1, y1, x2, y2 = map(int, kutu.xyxy[0].tolist())
                    
                    threading.Thread(target=ekrana_kirmizi_kare_ciz, args=(x1, y1, x2, y2, 0.8), daemon=True).start()
                    
                    sol = x1 - 10
                    ust = y1 - 10
                    genislik = (x2 - x1) + 20
                    yukseklik = (y2 - y1) + 20
                    olta_koordinati = (sol, ust, genislik, yukseklik)
                    bulundu = True
                    break
                if bulundu: break
                
            if bulundu:
                break
            time.sleep(0.1)
            
    return olta_koordinati

def balik_botu_dongusu(log_callback):
    global bot_calisiyor
    
    if secilen_bot_modu == "Otomatik (Yapay Zeka)" and not yolo_aktif:
        log_callback("[!] HATA: Yapay zeka modeli yüklü değil! Modu değiştirin.")
        bot_calisiyor = False
        return

    log_callback(f"[+] Bot Başlatıldı! Aktif Seçenek: {secilen_bot_modu}")
    time.sleep(1.0)
    
    while bot_calisiyor:
        log_callback(f"[+] Olta Atılıyor... Tuş: {olta_at_tusu}")
        oyuna_tus_gonder(olta_at_tusu)
        
        time.sleep(3.5) 

        if not bot_calisiyor: break

        olta_alani = None

        # 2 SEÇENEKLİ İŞLEYİŞ KONTROLÜ
        if secilen_bot_modu == "Manuel (Ben Seçeceğim)":
            if elle_secilen_alan is None:
                log_callback("[-] HATA: Manuel modu seçtiniz ama yeşil butondan yer belirlemediniz! Bot durduruldu.")
                bot_calisiyor = False
                break
            log_callback("[+] Önceden el ile seçtiğiniz sabit bölgeye kilitleniliyor...")
            olta_alani = elle_secilen_alan
        else:
            # Otomatik Yapay Zeka Modu
            olta_alani = ekranda_oltayi_yolo_ile_ara(log_callback)
            if not olta_alani:
                log_callback("[-] Otomatik modda olta bulunamadı! Yeniden deneniyor...")
                time.sleep(1.0)
                continue

        log_callback(f"[+] Bölge takibi aktifleşti: {olta_alani[:2]}")
        
        try:
            ilk_ekran = pyautogui.screenshot(region=olta_alani)
            eski_kare = cv2.cvtColor(np.array(ilk_ekran), cv2.COLOR_RGB2GRAY)
        except Exception:
            continue

        hareket_bekleme_baslangic = time.time()
        balik_yakalandi = False

        # 30 saniye boyunca hareket izleme döngüsü
        while bot_calisiyor and (time.time() - hareket_bekleme_baslangic < 30):
            try:
                anlik_ekran = pyautogui.screenshot(region=olta_alani)
                yeni_kare = cv2.cvtColor(np.array(anlik_ekran), cv2.COLOR_RGB2GRAY)
            except Exception:
                break

            fark = cv2.absdiff(eski_kare, yeni_kare)
            hareket_miktari = np.sum(fark > 30)

            if hareket_miktari > 80: 
                log_callback("[!] BALIK VURDU! Çekiliyor...")
                oyuna_tus_gonder(balik_cek_tusu)
                balik_yakalandi = True
                time.sleep(2.5) 
                break

            eski_kare = yeni_kare
            time.sleep(0.05)

        if not balik_yakalandi and bot_calisiyor:
            log_callback("[-] Süre doldu, olta yenileniyor...")
            
        time.sleep(1.0)

class BotArayuz(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Nostale Yapay Zeka Balık Botu v7.5")
        self.geometry("460x520") 
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        
        self.lbl_baslik = ctk.CTkLabel(self, text="Nostale Hibrit Balık Botu", font=("Arial", 16, "bold"))
        self.lbl_baslik.pack(pady=12)
        
        self.frame_ayarlar = ctk.CTkFrame(self)
        self.frame_ayarlar.pack(pady=5, padx=20, fill="x")
        
        self.lbl_bd = ctk.CTkLabel(self.frame_ayarlar, text="Başlat/Durdur Tuşu:", font=("Arial", 12))
        self.lbl_bd.grid(row=0, column=0, padx=15, pady=6, sticky="w")
        self.ent_bd = ctk.CTkEntry(self.frame_ayarlar, width=120)
        self.ent_bd.insert(0, baslat_durdur_tusu.upper())
        self.ent_bd.grid(row=0, column=1, padx=15, pady=6)
        
        self.lbl_olta = ctk.CTkLabel(self.frame_ayarlar, text="Olta Atma Tuşu:", font=("Arial", 12))
        self.lbl_olta.grid(row=1, column=0, padx=15, pady=6, sticky="w")
        self.ent_olta = ctk.CTkEntry(self.frame_ayarlar, width=120)
        self.ent_olta.insert(0, olta_at_tusu)
        self.ent_olta.grid(row=1, column=1, padx=15, pady=6)
        
        self.lbl_cek = ctk.CTkLabel(self.frame_ayarlar, text="Balık Çekme Tuşu:", font=("Arial", 12))
        self.lbl_cek.grid(row=2, column=0, padx=15, pady=6, sticky="w")
        self.ent_cek = ctk.CTkEntry(self.frame_ayarlar, width=120)
        self.ent_cek.insert(0, balik_cek_tusu)
        self.ent_cek.grid(row=2, column=1, padx=15, pady=6)

        # 2 Seçenekli Mod Kısmı
        self.lbl_mod = ctk.CTkLabel(self.frame_ayarlar, text="Çalışma Seçeneği:", font=("Arial", 12, "bold"))
        self.lbl_mod.grid(row=3, column=0, padx=15, pady=6, sticky="w")
        self.cmb_mod = ctk.CTkComboBox(self.frame_ayarlar, values=["Otomatik (Yapay Zeka)", "Manuel (Ben Seçeceğim)"], width=160)
        self.cmb_mod.set(secilen_bot_modu)
        self.cmb_mod.grid(row=3, column=1, padx=15, pady=6)

        # Manuel Seçim için Yeşil Ekstra Buton
        self.lbl_manuel_text = ctk.CTkLabel(self.frame_ayarlar, text="Manuel Alan Ayarı:", font=("Arial", 12))
        self.lbl_manuel_text.grid(row=4, column=0, padx=15, pady=6, sticky="w")
        self.btn_elle_sec = ctk.CTkButton(self.frame_ayarlar, text="Olta Bölgesini Elle Seç", fg_color="#2b8a3e", hover_color="#237032", width=140, font=("Arial", 11, "bold"), command=self.elle_secim_tetikle)
        self.btn_elle_sec.grid(row=4, column=1, padx=15, pady=6)
        
        self.btn_kaydet = ctk.CTkButton(self, text="Ayarları Kaydet ve Kısayolu Aktif Et", font=("Arial", 12, "bold"), command=self.ayarlari_uygula)
        self.btn_kaydet.pack(pady=10)
        
        self.txt_log = ctk.CTkTextbox(self, height=130, width=420, font=("Consolas", 11))
        self.txt_log.pack(pady=5, padx=20)
        
        self.log_yaz("[*] Sistem Hazır. Seçeneğinizi belirleyip 'Ayarları Kaydet' butonuna basın.")
        
    def log_yaz(self, mesaj):
        self.txt_log.insert("end", mesaj + "\n")
        self.txt_log.see("end")
        
    def elle_secim_tetikle(self):
        threading.Thread(target=ekrandan_elle_bolge_sec_buton, args=(self.log_yaz,), daemon=True).start()

    def ayarlari_uygula(self):
        global baslat_durdur_tusu, olta_at_tusu, balik_cek_tusu, secilen_bot_modu
        baslat_durdur_tusu = self.ent_bd.get().lower()
        olta_at_tusu = self.ent_olta.get()
        balik_cek_tusu = self.ent_cek.get()
        secilen_bot_modu = self.cmb_mod.get()
        
        keyboard.unhook_all()
        keyboard.add_hotkey(baslat_durdur_tusu, self.tetikleyici)
        self.log_yaz(f"[+] Ayarlar Güncellendi! Seçenek: {secilen_bot_modu} | Kısayol: '{baslat_durdur_tusu.upper()}'")

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
            
