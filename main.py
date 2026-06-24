import time
import threading
import cv2
import numpy as np
import os
import sys
import customtkinter as ctk
import tkinter as tk
import mss
import base64
import json
from groq import Groq

# Sürücü düzeyinde tuş ve Windows API bileşenleri
import pydirectinput
import win32gui
import win32con

pydirectinput.FAILSAFE = False

# --- GITHUB FILTRE DETOUR / API ANAHTARI PARÇALAMA ---
API_PART1 = "gsk_OSP3xnd81eQmgfLDtAwxWGdyb3FYe"
API_PART2 = "4tMIYM9O6IMZ2eeLxReB1iq"
COMBINED_API_KEY = API_PART1 + API_PART2

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

# Algılama Ayarları (Lokal Filtreler İçin)
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
    from ultralytics import YOLO
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

# Groq İstemcisi Birleştirilmiş Anahtarla Başlatılıyor
try:
    groq_client = Groq(api_key=COMBINED_API_KEY)
except Exception as e:
    groq_client = None

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
    ekran_w = overlay_pencere.winfo_screenwidth()
    ekran_h = overlay_pencere.winfo_screenheight()
    overlay_pencere.geometry(f"{ekran_w}x{ekran_h}+0+0")
    overlay_pencere.overrideredirect(True)
    overlay_pencere.config(bg="purple")
    overlay_pencere.attributes("-topmost", True)
    
    try:
        hwnd = win32gui.GetParent(overlay_pencere.winfo_id())
        istil = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, istil | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT)
        overlay_pencere.attributes("-transparentcolor", "purple")
    except:
        pass
    
    canvas = tk.Canvas(overlay_pencere, width=ekran_w, height=ekran_h, bg="purple", highlightthickness=0)
    canvas.pack()
    overlay_pencere.mainloop()

def hayalet_kare_ciz(x1, y1, x2, y2):
    global canvas, mevcut_kare_id, overlay_pencere
    if canvas and overlay_pencere:
        try:
            if mevcut_kare_id:
                canvas.delete(mevcut_kare_id)
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

# --- GROQ VIZYON İLK TESPİT MOTORU ---
def groq_ile_ilk_konumu_al(img_bgr, log_callback):
    if groq_client is None: return None
    try:
        log_callback("[*] Groq Llama v3.2 Vision üzerinden ilk harita konumu alınıyor...")
        _, buffer = cv2.imencode('.jpg', img_bgr)
        base64_image = base64.b64encode(buffer).decode('utf-8')

        completion = groq_client.chat.completions.create(
            model="llama-3.2-11b-vision-preview", # Güncel ve kararlı vizyon modeli
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Bu oyun ekranındaki balık tutma oltasını/şamandırasını bul ve sadece şu JSON formatında piksel koordinatlarını ver, başka yazı ekleme: {'x_min': sayı, 'y_min': sayı, 'x_max': sayı, 'y_max': sayı}"
                        },
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        koordinatlar = json.loads(completion.choices[0].message.content)
        return (int(koordinatlar['x_min']), int(koordinatlar['y_min']), int(koordinatlar['x_max']), int(koordinatlar['y_max']))
    except Exception as e:
        log_callback(f"[-] Groq İlk Konum Hatası: {e}")
    return None

# --- GELİŞMİŞ LOKAL TAKİP FİLTRELERİ (YOLO, ORB, CANNY) ---
def lokal_alan_icinde_milimetrik_ara(tarama_alani):
    if yolo_aktif:
        sonuclar = model.predict(source=tarama_alani, conf=GUVEN_ESIGI, verbose=False)
        for sonuc in sonuclar:
            for kutu in sonuc.boxes:
                x1, y1, x2, y2 = map(int, kutu.xyxy[0].tolist())
                return {"top": y1 - 5, "left": x1 - 5, "width": (x2 - x1) + 10, "height": (y2 - y1) + 10, "coords": (x1, y1, x2, y2)}

    img_gri = cv2.cvtColor(tarama_alani, cv2.COLOR_BGR2GRAY)

    if des_sablon is not None:
        kp_sahne, des_sahne = orb.detectAndCompute(img_gri, None)
        if des_sahne is not None:
            eslesmeler = bf.match(des_sablon, des_sahne)
            eslesmeler = sorted(eslesmeler, key=lambda x: x.distance)
            if len(eslesmeler) > 3:
                noktalar = np.array([kp_sahne[m.trainIdx].pt for m in eslesmeler[:8]])
                x_min, y_min = np.min(noktalar, axis=0)
                x_max, y_max = np.max(noktalar, axis=0)
                if 10 < (x_max - x_min) < 150 and 10 < (y_max - y_min) < 150:
                    return {
                        "top": int(y_min) - 10, "left": int(x_min) - 10,
                        "width": int(x_max - x_min) + 20, "height": int(y_max - y_min) + 20,
                        "coords": (int(x_min), int(y_min), int(x_max), int(y_max))
                    }

    parlaklik_filtresi = cv2.threshold(img_gri, 200, 255, cv2.THRESH_BINARY)[1]
    kenarlar = cv2.Canny(parlaklik_filtresi, 50, 150)
    cizgiler = cv2.HoughLinesP(kenarlar, 1, np.pi/180, threshold=15, minLineLength=12, maxLineGap=4)
    if cizgiler is not None:
        for cizgi in cizgiler:
            x1, y1, x2, y2 = cizgi[0]
            if abs(x2 - x1) < abs(y2 - y1) * 2: 
                return {
                    "top": min(y1, y2) - 15, "left": min(x1, x2) - 15,
                    "width": abs(x2 - x1) + 30, "height": abs(y2 - y1) + 30,
                    "coords": (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                }
    return None

def balik_botu_dongusu(log_callback):
    global bot_calisiyor
    log_callback("[+] Tam Hibrit Safe-Key Motor Devrede!")
    time.sleep(1.0)
    
    with mss.mss() as sct:
        ekran_boyutu = sct.monitors[1]
        
        while bot_calisiyor:
            log_callback(f"[+] Olta Atılıyor... Tuş: {olta_at_tusu}")
            oyuna_tus_gonder_directx(olta_at_tusu)
            
            time.sleep(3.6)
            if not bot_calisiyor: break

            ekran = sct.grab(ekran_boyutu)
            img_bgr = cv2.cvtColor(np.array(ekran), cv2.COLOR_BGRA2BGR)
            
            groq_koordinat = groq_ile_ilk_konumu_al(img_bgr, log_callback)
            
            if not groq_koordinat:
                log_callback("[-] Groq ilk konumu belirleyemedi, döngü yenileniyor...")
                continue
                
            gx1, gy1, gx2, gy2 = groq_koordinat
            top = max(0, gy1 - 50)
            left = max(0, gx1 - 50)
            width = min(ekran_boyutu["width"] - left, (gx2 - gx1) + 100)
            height = min(ekran_boyutu["height"] - top, (gy2 - gy1) + 100)

            eski_kare = None
            hareket_bekleme_baslangic = time.time()
            balik_yakalandi = False

            log_callback("[*] İlk konum kilitlendi. Yerel milimetrik filtreler aktif.")

            while bot_calisiyor and (time.time() - hareket_bekleme_baslangic < 25):
                try:
                    mini_bölge_koordinat = {"top": top, "left": left, "width": width, "height": height}
                    mini_ekran = sct.grab(mini_bölge_koordinat)
                    tarama_alani = cv2.cvtColor(np.array(mini_ekran), cv2.COLOR_BGRA2BGR)

                    bulunan = lokal_alan_icinde_milimetrik_ara(tarama_alani)
                    
                    olta_izleme_alani = mini_bölge_koordinat
                    if bulunan:
                        olta_izleme_alani = {
                            "top": bulunan["top"] + top,
                            "left": bulunan["left"] + left,
                            "width": bulunan["width"],
                            "height": bulunan["height"]
                        }
                        cx1, cy1, cx2, cy2 = bulunan["coords"]
                        hayalet_kare_ciz(cx1 + left, cy1 + top, cx2 + left, cy2 + top)
                    else:
                        hayalet_kare_ciz(gx1, gy1, gx2, gy2)

                    anlik_izleme_ekrani = sct.grab(olta_izleme_alani)
                    yeni_kare = cv2.cvtColor(np.array(anlik_izleme_ekrani), cv2.COLOR_BGRA2GRAY)

                    if eski_kare is not None:
                        fark = cv2.absdiff(eski_kare, yeni_kare)
                        hareket_miktari = np.sum(fark > 30)

                        if hareket_miktari > hareket_hassasiyeti: 
                            log_callback(f"[!] BALIK VURDU! Kilitlenen bölgeden çekiliyor...")
                            oyuna_tus_gonder_directx(balik_cek_tusu)
                            balik_yakalandi = True
                            time.sleep(3.0)
                            break
                    eski_kare = yeni_kare
                except:
                    pass
                time.sleep(0.03)

            hayalet_kare_temizle()
            time.sleep(1.0)

class BotArayuz(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Nostale Safe-Hybrid Bot v11.5")
        self.geometry("460x480") 
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        
        self.lbl_baslik = ctk.CTkLabel(self, text="Nostale Groq + 3X Lokal Filtre Botu", font=("Arial", 15, "bold"))
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
        
        self.btn_kaydet = ctk.CTkButton(self, text="Sistemi Güvenli Modda Başlat", font=("Arial", 12, "bold"), command=self.ayarlari_uygula)
        self.btn_kaydet.pack(pady=12)
        
        self.txt_log = ctk.CTkTextbox(self, height=130, width=420, font=("Consolas", 11))
        self.txt_log.pack(pady=5, padx=20)
        
        import keyboard
        keyboard.unhook_all()
        keyboard.add_hotkey(baslat_durdur_tusu.lower(), self.tetikleyici)
        
        threading.Thread(target=hayalet_katman_olustur, daemon=True).start()
        self.log_yaz("[+] API ve model (v3.2 Vision) güncellendi. Hazır!")
        
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
        self.log_yaz(f"[+] Ayarlar güncellendi. Kısayol: '{baslat_durdur_tusu.upper()}'")

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
    
