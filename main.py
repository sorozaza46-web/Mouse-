import time
import threading
import cv2
import numpy as np
import os
import sys
import customtkinter as ctk
import tkinter as tk
import mss
from ultralytics import YOLO

# Sürücü düzeyinde tuş ve Windows API bileşenleri
import pydirectinput
import win32gui
import win32con
import win32api

pydirectinput.FAILSAFE = False

# Global Kontroller
bot_calisiyor = False
baslat_durdur_tusu = "f6"
olta_at_tusu = "2"
balik_cek_tusu = "3"
hareket_hassasiyeti = 50

# Katman/Çerçeve Global Değişkenleri
overlay_pencere = None
canvas = None
mevcut_kare_id = None

# Algılama Ayarları
MODEL_YOLU = "olta_modeli.pt"  
SABLON_YOLU = "klasik_olta.png" 
GUVEN_ESIGI = 0.15             

def kaynak_yolu(goreli_yol):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, goreli_yol)

# YOLOv8 Yüklemesi
try:
    model = YOLO(kaynak_yolu(MODEL_YOLU))
    yolo_aktif = True
except Exception as e:
    yolo_aktif = False

# ORB Hazırlığı
orb = cv2.ORB_create(nfeatures=500)
sablon_bgr = cv2.imread(kaynak_yolu(SABLON_YOLU))
if sablon_bgr is not None:
    sablon_gri = cv2.cvtColor(sablon_bgr, cv2.COLOR_BGR2GRAY)
    kp_sablon, des_sablon = orb.detectAndCompute(sablon_gri, None)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
else:
    des_sablon = None

def oyuna_tus_gonder_directx(tus_str):
    try:
        pydirectinput.press(tus_str.lower())
        time.sleep(0.05)
    except Exception as e:
        print(f"[Tuş Hatası]: {e}")

# --- HER KOŞULDA ÇİZEN HAYALET KATMAN SİSTEMİ ---
def hayalet_katman_olustur():
    global overlay_pencere, canvas
    overlay_pencere = tk.Tk()
    overlay_pencere.title("HayaletKare")
    
    # Ekran boyutlarını al ve pencereyi kapla
    ekran_w = overlay_pencere.winfo_screenwidth()
    ekran_h = overlay_pencere.winfo_screenheight()
    overlay_pencere.geometry(f"{ekran_w}x{ekran_h}+0+0")
    
    # Kenarlıkları kaldır, arka planı mor yap (Mor rengi şeffaf ilan edeceğiz)
    overlay_pencere.overrideredirect(True)
    overlay_pencere.config(bg="purple")
    overlay_pencere.attributes("-topmost", True)
    
    # Windows API ile mor rengi tamamen şeffaf yap ve tıklamaları arkaya geçir (Click-Through)
    hwnd = win32gui.GetParent(overlay_pencere.winfo_id())
    istil = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, istil | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT)
    overlay_pencere.attributes("-transparentcolor", "purple")
    
    canvas = tk.Canvas(overlay_pencere, width=ekran_w, height=ekran_h, bg="purple", highlightthickness=0)
    canvas.pack()
    overlay_pencere.mainloop()

def hayalet_kare_ciz(x1, y1, x2, y2):
    """Gelişmiş hayalet katman üzerinde her koşulda en üstte duran kırmızı kare çizer."""
    global canvas, mevcut_kare_id, overlay_pencere
    if canvas and overlay_pencere:
        try:
            # Önceki kareyi temizle (Ekranda çorba olmasın diye)
            if mevcut_kare_id:
                canvas.delete(mevcut_kare_id)
            # Yeni kareyi çiz (Kırmızı, 3 piksel kalınlıkta)
            mevcut_kare_id = canvas.create_rectangle(x1, y1, x2, y2, outline="red", width=3)
            overlay_pencere.update_idletasks()
            overlay_pencere.update()
        except:
            pass

def hayalet_kare_temizle():
    global canvas, mevcut_kare_id
    if canvas and mevcut_kare_id:
        try:
            canvas.delete(mevcut_kare_id)
            mevcut_kare_id = None
        except:
            pass

def ekranda_oltayi_gelismis_ara(img_bgr):
    if yolo_aktif:
        sonuclar = model.predict(source=img_bgr, conf=GUVEN_ESIGI, verbose=False)
        for sonuc in sonuclar:
            for kutu in sonuc.boxes:
                x1, y1, x2, y2 = map(int, kutu.xyxy[0].tolist())
                return {"top": y1 - 10, "left": x1 - 10, "width": (x2 - x1) + 20, "height": (y2 - y1) + 20, "coords": (x1, y1, x2, y2)}

    img_gri = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    if des_sablon is not None:
        kp_sahne, des_sahne = orb.detectAndCompute(img_gri, None)
        if des_sahne is not None:
            eslesmeler = bf.match(des_sablon, des_sahne)
            eslesmeler = sorted(eslesmeler, key=lambda x: x.distance)
            if len(eslesmeler) > 4:
                noktalar = [kp_sahne[m.trainIdx].pt for m in eslesmeler[:10]]
                noktalar = np.array(noktalar)
                x_min, y_min = np.min(noktalar, axis=0)
                x_max, y_max = np.max(noktalar, axis=0)
                if 10 < (x_max - x_min) < 150 and 10 < (y_max - y_min) < 150:
                    return {
                        "top": int(y_min) - 15, "left": int(x_min) - 15,
                        "width": int(x_max - x_min) + 30, "height": int(y_max - y_min) + 30,
                        "coords": (int(x_min), int(y_min), int(x_max), int(y_max))
                    }

    parlaklik_filtresi = cv2.threshold(img_gri, 200, 255, cv2.THRESH_BINARY)[1]
    kenarlar = cv2.Canny(parlaklik_filtresi, 50, 150)
    cizgiler = cv2.HoughLinesP(kenarlar, 1, np.pi/180, threshold=20, minLineLength=15, maxLineGap=5)
    
    if cizgiler is not None:
        for cizgi in cizgiler:
            x1, y1, x2, y2 = cizgi[0]
            if abs(x2 - x1) < abs(y2 - y1) * 2: 
                return {
                    "top": min(y1, y2) - 20, "left": min(x1, x2) - 20,
                    "width": abs(x2 - x1) + 40, "height": abs(y2 - y1) + 40,
                    "coords": (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                }
    return None

def balik_botu_dongusu(log_callback):
    global bot_calisiyor
    log_callback("[+] Ultra Otonom Yıkılmaz Motor Aktif!")
    time.sleep(1.0)
    
    with mss.mss() as sct:
        ekran_boyutu = sct.monitors[1]
        
        while bot_calisiyor:
            ilk_ekran_yakala = sct.grab(ekran_boyutu)
            ref_img = cv2.cvtColor(np.array(ilk_ekran_yakala), cv2.COLOR_BGRA2GRAY)
            
            log_callback(f"[+] Olta Atılıyor... Tuş: {olta_at_tusu}")
            oyuna_tus_gonder_directx(olta_at_tusu)
            
            hareket_alani_koordinati = None
            hareket_baslangic = time.time()
            
            while time.time() - hareket_baslangic < 1.8:
                anlik_ekran = sct.grab(ekran_boyutu)
                anlik_img = cv2.cvtColor(np.array(anlik_ekran), cv2.COLOR_BGRA2GRAY)
                fark = cv2.absdiff(ref_img, anlik_img)
                _, esik_fark = cv2.threshold(fark, 35, 255, cv2.THRESH_BINARY)
                
                konturlar, _ = cv2.findContours(esik_fark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for kontur in konturlar:
                    if 30 < cv2.contourArea(kontur) < 600:
                        x, y, w, h = cv2.boundingRect(kontur)
                        if 0.2 < (y / ekran_boyutu["height"]) < 0.8:
                            hareket_alani_koordinati = {"top": y - 40, "left": x - 40, "width": w + 80, "height": h + 80}
                            break
                if hareket_alani_koordinati: break
                time.sleep(0.05)

            time.sleep(2.0)
            if not bot_calisiyor: break

            olta_alani = None
            eski_kare = None
            hareket_bekleme_baslangic = time.time()
            balik_yakalandi = False

            while bot_calisiyor and (time.time() - hareket_bekleme_baslangic < 30):
                ekran = sct.grab(ekran_boyutu)
                img = np.array(ekran)
                img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

                tarama_alani = img_bgr
                b_offset_x, b_offset_y = 0, 0
                if hareket_alani_koordinati:
                    top, left = hareket_alani_koordinati["top"], hareket_alani_koordinati["left"]
                    wd, hg = hareket_alani_koordinati["width"], hareket_alani_koordinati["height"]
                    if top > 0 and left > 0 and (top+hg) < ekran_boyutu["height"] and (left+wd) < ekran_boyutu["width"]:
                        tarama_alani = img_bgr[top:top+hg, left:left+wd]
                        b_offset_x, b_offset_y = left, top

                bulunan = ekranda_oltayi_gelismis_ara(tarama_alani)
                
                if bulunan:
                    olta_alani = {
                        "top": bulunan["top"] + b_offset_y, 
                        "left": bulunan["left"] + b_offset_x, 
                        "width": bulunan["width"], 
                        "height": bulunan["height"]
                    }
                    cx1, cy1, cx2, cy2 = bulunan["coords"]
                    # YENİ SİSTEM: Hayalet katmana çiziyoruz (Her koşulda en üstte parlar!)
                    hayalet_kare_ciz(cx1 + b_offset_x, cy1 + b_offset_y, cx2 + b_offset_x, cy2 + b_offset_y)

                if olta_alani:
                    try:
                        anlik_bölge = sct.grab(olta_alani)
                        yeni_kare = cv2.cvtColor(np.array(anlik_bölge), cv2.COLOR_BGRA2GRAY)

                        if eski_kare is not None:
                            fark = cv2.absdiff(eski_kare, yeni_kare)
                            hareket_miktari = np.sum(fark > 30)

                            if hareket_miktari > hareket_hassasiyeti: 
                                log_callback(f"[!] BALIK VURDU! Çekiliyor...")
                                oyuna_tus_gonder_directx(balik_cek_tusu)
                                balik_yakalandi = True
                                time.sleep(3.0)
                                break
                        eski_kare = yeni_kare
                    except:
                        pass
                time.sleep(0.03)

            if not balik_yakalandi and bot_calisiyor:
                log_callback("[-] Olta tazeleniyor...")
            
            hayalet_kare_temizle()
            time.sleep(1.0)

class BotArayuz(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Nostale Absolute Overlays v9.5")
        self.geometry("460x480") 
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        
        self.lbl_baslik = ctk.CTkLabel(self, text="Nostale Her Koşulda Çizen Otonom Bot", font=("Arial", 15, "bold"))
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
        
        self.btn_kaydet = ctk.CTkButton(self, text="Ayarları Kaydet ve Botu Hazırla", font=("Arial", 12, "bold"), command=self.ayarlari_uygula)
        self.btn_kaydet.pack(pady=12)
        
        self.txt_log = ctk.CTkTextbox(self, height=130, width=420, font=("Consolas", 11))
        self.txt_log.pack(pady=5, padx=20)
        
        import keyboard
        keyboard.unhook_all()
        keyboard.add_hotkey(baslat_durdur_tusu.lower(), self.tetikleyici)
        
        # Hayalet Katmanı arka planda sonsuz döngüde açıyoruz
        threading.Thread(target=hayalet_katman_olustur, daemon=True).start()
        self.log_yaz("[+] Çizim katmanı mor şeffaflıkla kilitlendi. Her modda çizer!")
        
    def log_yaz(self, mesaj):
        self.txt_log.insert("end", mesaj + "\n")
        self.txt_log.see("end")

    def ayarlari_uygula(self):
        global baslat_durdur_tusu, olta_at_tusu, balik_cek_tusu, hareket_hassasiyeti
        baslat_durdur_tusu = self.ent_bd.get().lower()
        olta_at_tusu = self.ent_olta.get()
        balik_cek_tusu = self.ent_cek.get()
        try: hareket_hassasiyeti = int(self.ent_has.get())
        except: hareket_hassasiyeti = 50
        
        import keyboard
        keyboard.unhook_all()
        keyboard.add_hotkey(baslat_durdur_tusu, self.tetikleyici)
        self.log_yaz(f"[+] Sistem Katmanı Sıkılaştırıldı! Tuş: '{baslat_durdur_tusu.upper()}'")

    def tetikleyici(self):
        global bot_calisiyor
        if not bot_calisiyor:
            bot_calisiyor = True
            threading.Thread(target=balik_botu_dongusu, args=(self.log_yaz,), daemon=True).start()
        else:
            bot_calisiyor = False
            hayalet_kare_temizle()
            self.log_yaz("[-] Bot durduruldu.")

if __name__ == "__main__":
    app = BotArayuz()
    app.mainloop()
        
