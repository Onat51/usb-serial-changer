# 🔌 USB Birim Seri Numara Değiştirici

**USB sürücülerin Volume Serial Number (Birim Seri Numarası) değerini kolayca değiştiren, Windows için geliştirilmiş grafiksel bir araç.**

---

## ✨ Özellikler

- 🖥️ **Grafiksel Arayüz** — Tkinter tabanlı, sade ve modern GUI
- 🗂️ **Çoklu Dosya Sistemi Desteği** — FAT12, FAT16, FAT32, NTFS, exFAT
- 🎲 **Rastgele Seri Üreteci** — Tek tuşla geçerli rastgele seri numarası oluşturur
- 🔍 **Otomatik Sürücü Tespiti** — Bağlı tüm çıkarılabilir (removable) sürücüleri listeler
- 🔒 **Güvenli Yazma** — Birim kilitleme → dismount → yazma → kilit açma sırası ile işlem yapar
- ✅ **exFAT Checksum Desteği** — Ana ve yedek boot bölgelerini otomatik günceller

---

## ⚙️ Gereksinimler

| Gereksinim | Açıklama |
|---|---|
| **İşletim Sistemi** | Windows 7 / 10 / 11 (64-bit önerilir) |
| **Python** | 3.10 veya üzeri |
| **Tkinter** | Python kurulumuna dahildir |
| **Yetki** | **Yönetici (Administrator) hakları zorunludur** |

> `ctypes` ve `struct` standart kütüphane modülleridir — ek paket kurulumu gerekmez.

---

## 🚀 Kurulum ve Kullanım

### 1. Depoyu klonlayın

```bash
git clone https://github.com/Onat51/usb-serial-changer.git
cd usb-serial-changer
```

### 2. Yönetici olarak çalıştırın

```bash
# Sağ tıklayıp "Yönetici olarak çalıştır" seçeneğini kullanın
# veya yönetici yetkili bir terminal açıp:
python usb_serial_changer.py
```

> ⚠️ Uygulama yönetici hakları olmadan başlatılırsa, otomatik olarak UAC yükseltme isteği açar.

### 3. Kullanım adımları

1. **Sürücü Seçimi** alanından USB sürücünüzü seçin
2. **⟳ Yenile** butonuna basarak sürücüleri güncelleyin
3. **Yeni Seri Numara** alanına `XXXX-XXXX` formatında bir değer girin  
   veya **🎲 Rastgele** butonunu kullanın
4. **✅ Seri Numarayı Değiştir** butonuna tıklayın
5. Onay penceresini onaylayın
6. İşlem sonrası USB belleği güvenle çıkarıp yeniden takın

---

## 📂 Desteklenen Dosya Sistemleri

| Dosya Sistemi | Boot Sektör Ofseti | Boyut |
|---|---|---|
| FAT12 | `0x27` (39) | 4 bayt |
| FAT16 | `0x27` (39) | 4 bayt |
| FAT32 | `0x43` (67) | 4 bayt |
| NTFS  | `0x48` (72) | 8 bayt (üst DWORD = 0) |
| exFAT | `0x64` (100) | 4 bayt + checksum yenileme |

---

## 🛠️ Teknik Detaylar

- Disk erişimi doğrudan **Windows Kernel32 API** (`CreateFileW`, `ReadFile`, `WriteFile`, `DeviceIoControl`) üzerinden yapılır
- `FSCTL_LOCK_VOLUME` → `FSCTL_DISMOUNT_VOLUME` → yazma → `FSCTL_UNLOCK_VOLUME` sırası izlenir
- exFAT'ta hem **ana** hem **yedek** boot bölgesi güncellenir; 11 sektörlük checksum otomatik hesaplanıp sektör 11'e yazılır
- Seri numara formatı: `XXXX-XXXX` (hexadecimal, toplam 32-bit)

---

## ⚠️ Uyarılar

- Bu araç düşük seviyeli disk yazma işlemi gerçekleştirir. **Veri kaybı riskine karşı önemli dosyalarınızı yedekleyin.**
- İşlem sırasında USB sürücüyü **çıkarmayın**.
- Sadece **çıkarılabilir (removable)** sürücüler listelenir; sabit diskler gösterilmez.
- Seri numara değişikliği bazı DRM veya lisans sistemlerini etkileyebilir.

---
