# 🔧 Hata Ayıklama ve Sorun Giderme Kılavuzu

## ✅ Düzeltilen Hatalar (v1.1)

### Slider TypeError Hatası - ÇÖZÜLDÜ ✅
**Hata Mesajı:**
```
TypeError: '>' not supported between instances of 'str' and 'int'
```

**Neden Oldu:**
- CTkSlider widget'ları `StringVar` ile çalışmıyor
- Sayısal değerler için `DoubleVar` veya `IntVar` kullanılması gerekiyor

**Çözüm:**
```python
# YANLIŞ ❌
rpm_var = ctk.StringVar(value="450")

# DOĞRU ✅
rpm_var = ctk.DoubleVar(value=450)
```

**Yapılan Değişiklikler:**
1. ✅ RPM slider: `StringVar` → `DoubleVar`
2. ✅ Faz slider: `StringVar` → `DoubleVar`
3. ✅ Işık slider: `StringVar` → `DoubleVar`
4. ✅ Label güncellemeleri için callback fonksiyonları eklendi
5. ✅ Komut gönderirken tip dönüşümleri düzeltildi

## 🔍 Yaygın Hatalar ve Çözümleri

### 1. WebSocket Bağlantı Hataları

**Problem:** Cihaza bağlanılamıyor
```
❌ [device_name] Bağlantı hatası: ...
```

**Çözümler:**
- [ ] IP adresini kontrol edin
- [ ] Port numarasını kontrol edin (varsayılan: 8080)
- [ ] Cihazın çalıştığından emin olun
- [ ] Firewall ayarlarını kontrol edin
- [ ] Aynı ağda olduğunuzu doğrulayın

**Test Komutu:**
```bash
# Windows
ping 192.168.1.100

# Linux/Mac
ping -c 4 192.168.1.100
```

### 2. Komut Gönderilmiyor

**Problem:** Komutlar cihaza gitmiyor
```
⚠️ [device_name] Bağlı değil
```

**Çözümler:**
1. Cihaz durumunu kontrol edin (🟢 olmalı)
2. `gui.log` dosyasını inceleyin
3. Cihazı yeniden bağlayın:
   - "Bağlantıyı Kes" → Bekle → "Bağlan"
4. Device ID'nin doğru olduğunu kontrol edin

### 3. Ağ Taraması Çalışmıyor

**Problem:** Tarama hiçbir cihaz bulamıyor

**Çözümler:**
- [ ] IP aralığını kontrol edin (örn: 192.168.1)
- [ ] Timeout süresini artırın (Ayarlar > Tarama Timeout)
- [ ] Administrator/root yetkisi ile çalıştırın
- [ ] ICMP (ping) trafiğine izin verildiğinden emin olun

**Manuel Test:**
```python
# Python konsolunda test
import asyncio
import websockets

async def test():
    async with websockets.connect("ws://192.168.1.100:8080/ws") as ws:
        await ws.send("PING")
        response = await ws.recv()
        print(f"Cevap: {response}")

asyncio.run(test())
```

### 4. GUI Donuyor

**Problem:** Arayüz yanıt vermiyor

**Çözümler:**
1. Asyncio event loop'un çalıştığından emin olun
2. Uygulamayı yeniden başlatın
3. `gui.log` dosyasını kontrol edin
4. Python sürümünü kontrol edin (3.11+ önerilir)

### 5. Konfigürasyon Kayboldu

**Problem:** Cihazlar veya kısayollar kayboldu

**Çözümler:**
- [ ] `gui_config.json` dosyasını kontrol edin
- [ ] Dosya izinlerini kontrol edin
- [ ] Yedek dosya varsa geri yükleyin

**Yedekleme:**
```bash
# Windows
copy gui_config.json gui_config.backup.json

# Linux/Mac
cp gui_config.json gui_config.backup.json
```

## 🐛 Debug Modunu Etkinleştirme

### Log Seviyesini Değiştirme

`hologram_gui.py` dosyasının başında:

```python
# Detaylı loglar için
logging.basicConfig(
    level=logging.DEBUG,  # INFO → DEBUG
    ...
)
```

### Belirli Modüller İçin Debug

```python
# WebSocket bağlantıları için
logging.getLogger('websockets').setLevel(logging.DEBUG)

# Asyncio için
logging.getLogger('asyncio').setLevel(logging.DEBUG)
```

## 📝 Log Dosyası Analizi

### gui.log İnceleme

**Başarılı Bağlantı:**
```
✅ [holo1] Bağlandı: 192.168.1.100
[holo1] PING gönderildi
```

**Bağlantı Hatası:**
```
❌ [holo1] Bağlantı hatası: [Errno 10061] ...
🔄 [holo1] 3s sonra yeniden bağlanılacak...
```

**Komut Gönderimi:**
```
📤 [holo1] Komut gönderildi: model https://...
```

## 🔧 Manuel Testler

### 1. WebSocket Bağlantı Testi

```python
import asyncio
import websockets

async def test_connection(ip, port=8080):
    try:
        async with websockets.connect(f"ws://{ip}:{port}/ws") as ws:
            # PING gönder
            await ws.send("PING")
            response = await ws.recv()
            print(f"✅ PING cevabı: {response}")
            
            # ID iste
            await ws.send("GET_ID")
            device_id = await ws.recv()
            print(f"✅ Device ID: {device_id}")
            
            return True
    except Exception as e:
        print(f"❌ Hata: {e}")
        return False

# Test et
asyncio.run(test_connection("192.168.1.100"))
```

### 2. Komut Gönderme Testi

```python
async def test_command(ip, device_id, command, port=8080):
    try:
        async with websockets.connect(f"ws://{ip}:{port}/ws") as ws:
            message = f"{device_id} {command}"
            await ws.send(message)
            print(f"✅ Komut gönderildi: {message}")
            await asyncio.sleep(1)
            return True
    except Exception as e:
        print(f"❌ Hata: {e}")
        return False

# Test et
asyncio.run(test_command(
    "192.168.1.100",
    "DEVICE_192_168_1_100",
    "rpm 450"
))
```

### 3. Ağ Tarama Testi

```python
async def test_scan(ip_range="192.168.1"):
    import subprocess
    import platform
    
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    
    active_ips = []
    for i in range(1, 255):
        ip = f"{ip_range}.{i}"
        try:
            result = await asyncio.create_subprocess_exec(
                'ping', param, '1', '-w', '100', ip,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await asyncio.wait_for(result.wait(), timeout=1.0)
            if result.returncode == 0:
                active_ips.append(ip)
                print(f"✅ Aktif: {ip}")
        except:
            pass
    
    print(f"\n📡 Toplam {len(active_ips)} aktif IP bulundu")
    return active_ips

# Test et
asyncio.run(test_scan("192.168.1"))
```

## ⚠️ Bilinen Sınırlamalar

1. **Asyncio Event Loop**
   - Windows'ta bazı asyncio özellikleri farklı çalışabilir
   - Python 3.11+ kullanmanız önerilir

2. **WebSocket Bağlantıları**
   - SSL/TLS desteği yok (ws://, wss:// değil)
   - Kimlik doğrulama yok
   - Güvenli ağlarda kullanın

3. **Ağ Taraması**
   - Firewall ping'i engelleyebilir
   - Büyük ağlarda yavaş olabilir (254 IP)
   - Administrator/root yetkisi gerekebilir

4. **GUI Thread Safety**
   - Asyncio coroutine'leri Tkinter thread'inden çağrılır
   - Bazı durumlarda senkronizasyon sorunları olabilir

## 🆘 Acil Durum Çözümleri

### Uygulama Açılmıyor

```bash
# 1. Bağımlılıkları yeniden yükle
pip uninstall customtkinter websockets -y
pip install customtkinter websockets

# 2. Config dosyalarını sil
del gui_config.json
del gui_settings.json

# 3. Log dosyasını kontrol et
type gui.log  # Windows
cat gui.log   # Linux/Mac
```

### Cihazlar Görünmüyor

```python
# gui_config.json dosyasını düzenle
{
  "devices": {},
  "shortcuts": {}
}
```

### Tema Çalışmıyor

```python
# gui_settings.json dosyasını düzenle
{
  "theme": "dark",
  "color_theme": "blue"
}
```

## 📞 Destek Alma

### Log Toplama

Sorun bildirirken şunları paylaşın:

1. **gui.log** dosyası
2. **Hata mesajı** (tam metin)
3. **Python sürümü**: `python --version`
4. **İşletim sistemi**: Windows/Linux/Mac
5. **Paket sürümleri**: `pip freeze`

### Örnek Rapor

```
**Sorun:** Cihaza bağlanamıyorum

**Ortam:**
- Python: 3.11.2
- OS: Windows 11
- customtkinter: 5.2.1
- websockets: 12.0

**Hata:**
[gui.log'dan ilgili satırlar]

**Denenenler:**
- IP ve port kontrol edildi
- Firewall kapatıldı
- Cihaz çalışıyor ve aynı ağda
```

## 🔄 Sürüm Notları

### v1.1 (2025-02-08)
- ✅ Slider TypeError hatası düzeltildi
- ✅ StringVar → DoubleVar/IntVar dönüşümü
- ✅ Label güncelleme callback'leri eklendi
- ✅ Parametre gönderme düzeltildi

### v1.0 (2025-02-08)
- 🎉 İlk sürüm yayınlandı
- ✅ Tüm temel özellikler eklendi

---

**💡 İpucu:** Sorun çözemiyorsanız, uygulamayı kapatıp yeniden başlatın ve `gui.log` dosyasını inceleyin!