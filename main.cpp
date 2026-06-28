#include <wx/wx.h>
#include <wx/thread.h>
#include <opencv2/opencv.hpp>
#include <windows.h>
#include <iostream>
#include <string>
#include <vector>
#include <chrono>
#include <thread>
#include <atomic>

// OpenCV ad alanı
using namespace cv;
using namespace std;

// Bot Çalışma Event Tanımı
wxDEFINE_EVENT(wxEVT_BOT_LOG, wxThreadEvent);

class FishingBotThread : public wxThread {
public:
    FishingBotThread(wxEvtHandler* handler, double conf, double delay)
        : wxThread(wxTHREAD_JOINABLE), m_handler(handler), m_confidence(conf), m_delay(delay), m_running(true) {}

    void Stop() { m_running = false; }

private:
    wxEvtHandler* m_handler;
    double m_confidence;
    double m_delay;
    std::atomic<bool> m_running;

    void Log(const wxString& msg) {
        wxThreadEvent* event = new wxThreadEvent(wxEVT_BOT_LOG);
        event->SetString(msg);
        m_handler->QueueEvent(event);
    }

    // Windows API ile Sağ Tıklama Simülasyonu
    void RightClick() {
        INPUT input = { 0 };
        input.type = INPUT_MOUSE;
        input.mi.dwFlags = MOUSEEVENTF_RIGHTDOWN;
        SendInput(1, &input, sizeof(INPUT));
        
        ZeroMemory(&input, sizeof(INPUT));
        input.type = INPUT_MOUSE;
        input.mi.dwFlags = MOUSEEVENTF_RIGHTUP;
        SendInput(1, &input, sizeof(INPUT));
    }

    // Windows Masaüstü Ekranını Yakalama (Hızlı Ekran Görüntüsü)
    Mat CaptureScreen() {
        HWND hwndDesktop = GetDesktopWindow();
        HDC hdcDesktop = GetDC(hwndDesktop);
        HDC hdcMem = CreateCompatibleDC(hdcDesktop);

        int width = GetSystemMetrics(SM_CXSCREEN);
        int height = GetSystemMetrics(SM_CYSCREEN);

        HBITMAP hBitmap = CreateCompatibleBitmap(hdcDesktop, width, height);
        SelectObject(hdcMem, hBitmap);

        BitBlt(hdcMem, 0, 0, width, height, hdcDesktop, 0, 0, SRCCOPY);

        BITMAPINFOHEADER bi;
        bi.biSize = sizeof(BITMAPINFOHEADER);
        bi.biWidth = width;
        bi.biHeight = -height; // Üstten alta doğru tarama için negatif
        bi.biPlanes = 1;
        bi.biBitCount = 24;
        bi.biCompression = BI_RGB;

        Mat mat(height, width, CV_8UC3);
        GetDIBits(hdcDesktop, hBitmap, 0, height, mat.data, (BITMAPINFO*)&bi, DIB_RGB_COLORS);

        DeleteObject(hBitmap);
        DeleteDC(hdcMem);
        ReleaseDC(hwndDesktop, hdcDesktop);

        return mat;
    }

    virtual ExitCode Entry() override {
        Log("Bot başlatılıyor... Kütüphaneler yükleniyor.");

        // YOLO Modelini Yükle (ONNX formatına çevrilmiş olmalıdır)
        dnn::Net net;
        try {
            net = dnn::readNetFromONNX("best.onnx");
            net.setPreferableBackend(dnn::DNN_BACKEND_OPENCV);
            net.setPreferableTarget(dnn::DNN_TARGET_CPU);
        } catch (const cv::Exception& e) {
            Log("❌ Hata: 'best.onnx' modeli yüklenemedi!");
            return (ExitCode)0;
        }

        // Şablon Resmi Yükle (Template Matching için)
        Mat template_img = imread("mantar.png", IMREAD_COLOR);
        if (template_img.empty()) {
            Log("⚠️ Uyarı: 'mantar.png' bulunamadı. Sadece Yapay Zeka kullanılacak.");
        }

        Log("Bot Aktif! Durdurmak için 'Durdur' butonuna basın.");
        auto last_log_time = std::chrono::steady_clock::now();

        while (m_running) {
            Mat screen = CaptureScreen();
            int h = screen.rows;
            int w = screen.cols;

            bool found = false;
            int mantar_x = 0, mantar_y = 0, mantar_w = 0, mantar_h = 0;

            // ---- YÖNTEM 1: YOLOv8 Nesne Algılama ----
            Mat blob = dnn::blobFromImage(screen, 1.0 / 255.0, Size(640, 640), Scalar(), true, false);
            net.setInput(blob);
            vector<Mat> outputs;
            net.forward(outputs, net.getUnconnectedOutLayersNames());

            // Çıktıları Ayrıştır (YOLOv8 formatı: [1, 5, 8400])
            float* data = (float*)outputs[0].data;
            int rows = outputs[0].size[2]; // 8400 aday
            
            float max_conf = 0;
            int best_box_idx = -1;

            for (int i = 0; i < rows; ++i) {
                float confidence = data[4 * rows + i]; // İlk 4 eleman x,y,w,h. 5. eleman sınıf skoru
                if (confidence > m_confidence && confidence > max_conf) {
                    max_conf = confidence;
                    best_box_idx = i;
                }
            }

            if (best_box_idx != -1) {
                float x = data[0 * rows + best_box_idx];
                float y = data[1 * rows + best_box_idx];
                float width = data[2 * rows + best_box_idx];
                float height = data[3 * rows + best_box_idx];

                // Çözünürlüğü ölçeklendir
                mantar_x = static_cast<int>((x - width / 2) * w / 640.0);
                mantar_y = static_cast<int>((y - height / 2) * h / 640.0);
                mantar_w = static_cast<int>(width * w / 640.0);
                mantar_h = static_cast<int>(height * h / 640.0);
                found = true;
            }

            // ---- YÖNTEM 2: Şablon Eşleştirme (Geri Çekilme Mekanizması) ----
            if (!found && !template_img.empty()) {
                Mat result;
                matchTemplate(screen, template_img, result, TM_CCOEFF_NORMED);
                double minVal, maxVal;
                Point minLoc, maxLoc;
                minMaxLoc(result, &minVal, &maxVal, &minLoc, &maxLoc);

                if (maxVal > 0.65) {
                    mantar_x = maxLoc.x;
                    mantar_y = maxLoc.y;
                    mantar_w = template_img.cols;
                    mantar_h = template_img.rows;
                    found = true;
                }
            }

            // ---- SU PARÇACIĞI ANALİZİ VE BALIK TUTMA ----
            if (found) {
                int padding = 40;
                int roi_y1 = max(0, mantar_y - padding);
                int roi_y2 = min(h, mantar_y + mantar_h + padding);
                int roi_x1 = max(0, mantar_x - padding);
                int roi_x2 = min(w, mantar_x + mantar_w + padding);

                if (roi_x2 > roi_x1 && roi_y2 > roi_y1) {
                    Mat roi = screen(Range(roi_y1, roi_y2), Range(roi_x1, roi_x2));
                    
                    Mat hsv;
                    cvtColor(roi, hsv, COLOR_BGR2HSV);

                    // Beyaz su kabarcığı/partikül filtresi
                    Mat mask;
                    Scalar lower_particle(0, 0, 180);
                    Scalar upper_particle(180, 60, 255);
                    inRange(hsv, lower_particle, upper_particle, mask);

                    int particle_count = countNonZero(mask);

                    if (particle_count > 10) {
                        Log("🐟 Balık yakalandı! Yoğunluk: " + std::to_string(particle_count));
                        RightClick();
                        
                        std::this_thread::sleep_for(std::chrono::milliseconds(static_cast<int>(m_delay * 1000)));
                        if (!m_running) break;

                        Log("Olta suya geri fırlatılıyor...");
                        RightClick();
                        std::this_thread::sleep_for(std::chrono::seconds(3));
                    }
                }
            } else {
                auto now = std::chrono::steady_clock::now();
                if (std::chrono::duration_cast<std::chrono::seconds>(now - last_log_time).count() > 2) {
                    Log("⚠️ Mantar bulunamadı, bekleniyor...");
                    last_log_time = now;
                }
            }

            std::this_thread::sleep_for(std::chrono::milliseconds(100)); // CPU yorulmasın
        }

        Log("Bot durduruldu.");
        return (ExitCode)0;
    }
};

// ---- GUI ARAYÜZ SINIFI (wxWidgets) ----
class FishingBotGui : public wxFrame {
public:
    FishingBotGui() : wxFrame(NULL, wxID_ANY, "SonOyuncu Balık Tutma Botu v4 (C++ Hibrit)", wxDefaultPosition, wxSize(500, 550), wxDEFAULT_FRAME_STYLE & ~(wxRESIZE_BORDER | wxMAXIMIZE_BOX)) {
        SetBackgroundColour(wxColour(30, 30, 30)); // Dark Theme

        wxBoxSizer* mainSizer = new wxBoxSizer(wxVERTICAL);

        // Başlık
        wxStaticText* title = new wxStaticText(this, wxID_ANY, "Minecraft Hibrit Balık Botu");
        title->SetForegroundColour(*wxWHITE);
        title->SetFont(wxFont(16, wxFONTFAMILY_DEFAULT, wxFONTSTYLE_NORMAL, wxFONTWEIGHT_BOLD));
        mainSizer->Add(title, 0, wxALIGN_CENTER | wxALL, 15);

        // Slider Alanları
        wxStaticText* confLabel = new wxStaticText(this, wxID_ANY, "Güven Oranı (Confidence): 0.30");
        confLabel->SetForegroundColour(*wxWHITE);
        mainSizer->Add(confLabel, 0, wxLEFT | wxRIGHT, 20);

        m_confSlider = new wxSlider(this, wxID_ANY, 30, 10, 90, wxDefaultPosition, wxDefaultSize, wxSL_HORIZONTAL);
        mainSizer->Add(m_confSlider, 0, wxEXPAND | wxLEFT | wxRIGHT | wxBOTTOM, 20);

        wxStaticText* delayLabel = new wxStaticText(this, wxID_ANY, "Tıklama Gecikmesi (Saniye): 1.0");
        delayLabel->SetForegroundColour(*wxWHITE);
        mainSizer->Add(delayLabel, 0, wxLEFT | wxRIGHT, 20);

        m_delaySlider = new wxSlider(this, wxID_ANY, 10, 1, 50, wxDefaultPosition, wxDefaultSize, wxSL_HORIZONTAL);
        mainSizer->Add(m_delaySlider, 0, wxEXPAND | wxLEFT | wxRIGHT | wxBOTTOM, 20);

        // Butonlar
        wxBoxSizer* btnSizer = new wxBoxSizer(wxHORIZONTAL);
        m_btnStart = new wxButton(this, wxID_ANY, "Botu Başlat");
        m_btnStop = new wxButton(this, wxID_ANY, "Durdur");
        m_btnStop->Enable(false);

        btnSizer->Add(m_btnStart, 1, wxALL, 5);
        btnSizer->Add(m_btnStop, 1, wxALL, 5);
        mainSizer->Add(btnSizer, 0, wxALIGN_CENTER | wxLEFT | wxRIGHT, 15);

        // Log Alanı
        m_logText = new wxTextCtrl(this, wxID_ANY, "", wxDefaultPosition, wxSize(-1, 200), wxTE_MULTILINE | wxTE_READONLY | wxTE_RICH);
        m_logText->SetBackgroundColour(wxColour(45, 45, 45));
        m_logText->SetForegroundColour(wxColour(0, 255, 0)); // Yeşil terminal yazısı
        mainSizer->Add(m_logText, 1, wxEXPAND | wxALL, 20);

        SetSizer(mainSizer);

        // Event Bindings
        m_btnStart->Bind(wxEVT_BUTTON, &FishingBotGui::OnStart, this);
        m_btnStop->Bind(wxEVT_BUTTON, &FishingBotGui::OnStop, this);
        m_confSlider->Bind(wxEVT_SLIDER, [=](wxCommandEvent&) {
            confLabel->SetLabel(wxString::Format("Güven Oranı (Confidence): %.2f", m_confSlider->GetValue() / 100.0));
        });
        m_delaySlider->Bind(wxEVT_SLIDER, [=](wxCommandEvent&) {
            delayLabel->SetLabel(wxString::Format("Tıklama Gecikmesi (Saniye): %.1f", m_delaySlider->GetValue() / 10.0));
        });
        Bind(wxEVT_BOT_LOG, &FishingBotGui::OnLogMessage, this);
    }

private:
    wxSlider* m_confSlider;
    wxSlider* m_delaySlider;
    wxButton* m_btnStart;
    wxButton* m_btnStop;
    wxTextCtrl* m_logText;
    FishingBotThread* m_botThread = nullptr;

    void OnStart(wxCommandEvent& event) {
        double conf = m_confSlider->GetValue() / 100.0;
        double delay = m_delaySlider->GetValue() / 10.0;

        m_botThread = new FishingBotThread(this, conf, delay);
        if (m_botThread->Run() == wxTHREAD_NO_ERROR) {
            m_btnStart->Enable(false);
            m_btnStop->Enable(true);
        }
    }

    void OnStop(wxCommandEvent& event) {
        if (m_botThread) {
            m_botThread->Stop();
            m_botThread->Wait();
            delete m_botThread;
            m_botThread = nullptr;
        }
        m_btnStart->Enable(true);
        m_btnStop->Enable(false);
    }

    void OnLogMessage(wxThreadEvent& event) {
        m_logText->AppendText(event.GetString() + "\n");
    }
};

class FishingBotApp : public wxApp {
public:
    virtual bool OnInit() {
        FishingBotGui* frame = new FishingBotGui();
        frame->Show(true);
        return true;
    }
};

wxIMPLEMENT_APP(FishingBotApp);
