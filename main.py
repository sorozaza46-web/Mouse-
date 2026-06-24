import time
import threading
import cv2
import numpy as np
import os
import sys
import customtkinter as ctk
import mss
from ultralytics import YOLO

# Oyun engelini aşmak için DirectInput ve Windows API kütüphaneleri
import pydirectinput
import win32gui
import win32con

# Pydirectinput fail-safe özelliğini kapatıyoruz
pydirectinput.FAILSAFE = False

# Global Kontroller
bot_calisiyor = False
baslat_durdur_tusu = "f6"
olta_at_tusu = "2"
balik_cek_tusu = "3"
secilen_bot_modu = "Otomatik (Yapay Zeka)"
elle_secilen_alan = None
hareket_hassasiyeti = 50

# Yapay Zeka Ayarları
MODEL_YOLU = "olta_modeli.pt"  
SABLON_YOLU = "klasik_olta.png" # Klasik olta resmi adı
GUVEN_ESIGI = 0.15             

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
    print(f"[UYARI] YOLO Modeli yüklenemedi, klasik resim araması kullanılacak: {e}")

# Klasik Olta Resmini Yüklüyoruz (Gri tonlamalı)
sablon_resim = cv2.imread(kaynak_yolu(SABLON_YOLU), cv2.IMREAD_GRAYSCALE)
if sablon_resim is None:
    print(f"[UYARI] {SABLON_YOLU} bulunamadı! Klasik arama modu çalışmayabilir.")

def oyuna_tus_gonder_directx(tus_str):
    try:
        tus_str = tus_str.lower()
        pydirectinput.press(tus_str)
        time.sleep(0.05)
    except Exception as e:
        print(f"[Tuş Hatası]: {e}")

def ekrana_anlik_kare_ciz(x1, y1, x2, y2):
    """Ekrana pencereleri engellemeden anlık kırmızı kare çizer."""
    hdc = win32gui.GetDC(0)
    renk = win32gui.RGB(255, 0, 0)
    kalem = win32gui.CreatePen(win32con.PS_SOLID, 3, renk)
    eski_kalem = win32gui.SelectObject(hdc, kalem)
    
    win32gui.MoveToEx(hdc, x1, y1)
    win32gui.LineTo(hdc, x2, y1)
    win32gui.LineTo(hdc, x2, y2)
    win32gui.LineTo(hdc, x1, y2)
    win32gui.LineTo(hdc, x1, y1)
        
    win32gui.SelectObject(hdc, eski_kalem)
    win32gui.DeleteObject(kalem)
    win32gui.ReleaseDC(0, hdc)

def ekrandan_elle_bolge_sec_buton(log_callback):
    global elle_secilen_alan
    log_callback("[!] Ekran alıntısı aktif! Fare ile olta bölgesini seçin ve ENTER'a basın.")
    time.sleep(0.5)
    
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
        elle_secilen_alan = {"top": ust, "left": sol, "width": genislik, "height": yukseklik}
        log_callback(f"[+] Manuel bölge kaydedildi! Koordinat: X={sol}, Y={ust}")
    else:
        log_callback("[-] Seçim iptal edildi.")

def ekranda_oltayi_hibrit_ara(img):
    """Önce YOLO ile arar, bulamazsa klasik resim (şablon) ile arayıp koordinat döner."""
    # 1. Yöntem: Yapay Zeka (YOLOv8)
    if yolo_aktif:
        sonuclar = model.predict(source=img, conf=GUVEN_ESIGI, verbose=False)
        for sonuc in sonuclar:
            for kutu in sonuc.boxes:
                x1, y1, x2, y2 = map(int, kutu.xyxy[0].tolist())
                return {"top": y1 - 5, "left": x1 - 5, "width": (x2 - x1) + 10, "height": (y2 - y1) + 10, "coords": (x1, y1, x2, y2)}
                
    # 2. Yöntem: Klasik Resim Eşleştirme (Template Matching)
    if sablon_resim is not None:
        gri_ekran = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(gri_ekran, sablon_resim, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        
        if max_val > 0.65: # %65 benzerlik eşiği
            sol, ust = max_loc
            h, w = sablon_resim.shape
            x2, y2 = sol + w, ust + h
            return {"top": ust - 5, "left": sol - 5, "width": w + 10, "height": h + 10, "coords": (sol, ust, x2, y2)}
            
    return None

def balik_botu_dongusu(log_callback):
    global bot_calisiyor
    log_callback("[+] Bot Başlatıldı! Lütfen oyuna geçiş yapın.")
    time.sleep(1.5)
    
    with mss.mss() as sct:
        ekran_boyutu = sct.monitors[1]
        
        while bot_calisiyor:
            log_callback(f"[+] Olta Atılıyor... Tuş: {olta_at_tusu}")
            oyuna_tus_gonder_directx(olta_at_tusu)
            
            time.sleep(3.8) # Oltanın suya düşme süresi
            if not bot_calisiyor: break

            olta_alani = None
            eski_kare = None
            hareket_bekleme_baslangic = time.time()
            balik_yakalandi = False

            log_callback("[*] Olta aranıyor ve dinamik takibe alınıyor...")

            # 30 saniye boyunca balık vurana kadar döngü
            while bot_calisiyor and (time.time() - hareket_bekleme_baslangic < 30):
                # Ekranı anlık yakala
                ekran = sct.grab(ekran_boyutu)
                img = np.array(ekran)
                img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

                if secilen_bot_modu == "Manuel (Ben Seçeceğim)":
                    if elle_secilen_alan is None:
                        log_callback("[-] HATA: Manuel alan seçilmedi!")
                        bot_calisiyor = False
                        break
                    olta_alani = elle_secilen_alan
                    # Manuel modda da ekrana yeşil/kırmızı sabit kare çizebiliriz
                    ekrana_anlik_kare_ciz(olta_alani["left"], olta_alani["top"], olta_alani["left"]+olta_alani["width"], olta_alani["top"]+olta_alani["height"])
                else:
                    # OTOMATİK MOD: Her an tarar ve bulduğu yeri hep kare içinde tutar
                    bulunan = ekranda_oltayi_hibrit_ara(img_bgr)
                    if bulunan:
                        olta_alani = {"top": bulunan["top"], "left": bulunan["left"], "width": bulunan["width"], "height": bulunan["height"]}
                        # Kırmızı kareyi ekranda CANLI tutuyoruz
                        cx1, cy1, cx2, cy2 = bulunan["coords"]
                        ekrana_anlik_kare_ciz(cx1, cy1, cx2, cy2)
                    else:
                        # Eğer o anlık kare kaçtıysa eski alanı koru veya aramaya devam et
                        pass

                # Eğer bir olta alanı hedeflendiyse pikselsel değişim (hareket) kontrolü yap
                if olta_alani:
                    anlik_bölge = sct.grab(olta_alani)
                    yeni_kare = cv2.cvtColor(np.array(anlik_bölge), cv2.COLOR_BGRA2GRAY)

                    if eski_kare is not None:
                        fark = cv2.absdiff(eski_kare, yeni_kare)
                        hareket_miktari = np.sum(fark > 30)

                        if hareket_miktari > hareket_hassasiyeti: 
                            log_callback(f"[!] BALIK VURDU! Çekiliyor... Tuş: {balik_cek_tusu}")
                            oyuna_tus_gonder_directx(balik_cek_tusu)
                            balik_yakalandi = True
                            time.sleep(3.0) # Çekme animasyonu beklesi
                            break

                    eski_kare = yeni_kare
                
                time.sleep(0.03) # Ultra hızlı tarama döngü gecikmesi

            if not balik_yakalandi and bot_calisiyor:
                log_callback("[-] Süre doldu veya olta kayboldu, tazeleniyor...")
            
            # Ekranı temizlemek için Windows pencere yenileme tetiklemesi
            win32gui.InvalidateRect(0, None, True)
            time.sleep(1.0)

class BotArayuz(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Nostale Sürekli Çerçeveli Bot v8.5")
        self.geometry("460x550") 
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        
        self.lbl_baslik = ctk.CTkLabel(self, text="Nostale Canlı Takip & Hibrit Balık Botu", font=("Arial", 15, "bold"))
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

        self.lbl_has = ctk.CTkLabel(self.frame_ayarlar, text="Algılama Hassasiyeti:", font=("Arial", 12))
        self.lbl_has.grid(row=3, column=0, padx=15, pady=6, sticky="w")
        self.ent_has = ctk.CTkEntry(self.frame_ayarlar, width=120)
        self.ent_has.insert(0, str(hareket_hassasiyeti))
        self.ent_has.grid(row=3, column=1, padx=15, pady=6)

        self.lbl_mod = ctk.CTkLabel(self.frame_ayarlar, text="Çalışma Seçeneği:", font=("Arial", 12, "bold"))
        self.lbl_mod.grid(row=4, column=0, padx=15, pady=6, sticky="w")
        self.cmb_mod = ctk.CTkComboBox(self.frame_ayarlar, values=["Otomatik (Yapay Zeka)", "Manuel (Ben Seçeceğim)"], width=160)
        self.cmb_mod.set(secilen_bot_modu)
        self.cmb_mod.grid(row=4, column=1, padx=15, pady=6)

        self.lbl_manuel_text = ctk.CTkLabel(self.frame_ayarlar, text="Manuel Alan Ayarı:", font=("Arial", 12))
        self.lbl_manuel_text.grid(row=5, column=0, padx=15, pady=6, sticky="w")
        self.btn_elle_sec = ctk.CTkButton(self.frame_ayarlar, text="Olta Bölgesini Elle Seç", fg_color="#2b8a3e", hover_color="#237032", width=140, font=("Arial", 11, "bold"), command=self.elle_secim_tetikle)
        self.btn_elle_sec.grid(row=5, column=1, padx=15, pady=6)
        
        self.btn_kaydet = ctk.CTkButton(self, text="Ayarları Kaydet ve Sistemi Aktif Et", font=("Arial", 12, "bold"), command=self.ayarlari_uygula)
        self.btn_kaydet.pack(pady=10)
        
        self.txt_log = ctk.CTkTextbox(self, height=130, width=420, font=("Consolas", 11))
        self.txt_log.pack(pady=5, padx=20)
        
        import keyboard
        keyboard.unhook_all()
        keyboard.add_hotkey(baslat_durdur_tusu.lower(), self.tetikleyici)
        self.log_yaz("[*] Sürekli kare çizimi modu aktif. 'klasik_olta.png' resmini koymayı unutmayın.")
        
    def log_yaz(self, mesaj):
        self.txt_log.insert("end", mesaj + "\n")
        self.txt_log.see("end")
        
    def elle_secim_tetikle(self):
        threading.Thread(target=ekrandan_elle_bolge_sec_buton, args=(self.log_yaz,), daemon=True).start()

    def ayarlari_uygula(self):
        global baslat_durdur_tusu, olta_at_tusu, balik_cek_tusu, secilen_bot_modu, hareket_hassasiyeti
        baslat_durdur_tusu = self.ent_bd.get().lower()
        olta_at_tusu = self.ent_olta.get()
        balik_cek_tusu = self.ent_cek.get()
        secilen_bot_modu = self.cmb_mod.get()
        try:
            hareket_hassasiyeti = int(self.ent_has.get())
        except:
            hareket_hassasiyeti = 50
        
        import keyboard
        keyboard.unhook_all()
        keyboard.add_hotkey(baslat_durdur_tusu, self.tetikleyici)
        self.log_yaz(f"[+] Ayarlar Kaydedildi! Kısayol: '{baslat_durdur_tusu.upper()}'")

    def tetikleyici(self):
        global bot_calisiyor
        if not bot_calisiyor:
            bot_calisiyor = True
            threading.Thread(target=balik_botu_dongusu, args=(self.log_yaz,), daemon=True).start()
        else:
            bot_calisiyor = False
            win32gui.InvalidateRect(0, None, True) # Kareyi temizle
            self.log_yaz("[-] Bot durduruldu.")

if __name__ == "__main__":
    app = BotArayuz()
    app.mainloop()
        
