import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from datetime import datetime, timezone, timedelta

BOT_TOKEN  = "8185628247:AAGh1gBPwzBaXLTZvU6RRUfXM3xN68eXmdg"
CHAT_ID    = "-1003562869508"
STATE_FILE = "tggf_state.json"
TR = timezone(timedelta(hours=3))

KATEGORILER = {
    "Bas Boyu":   "VFZSUlBRPT0=",
    "BasAlti":    "VFZSTlBRPT0=",
    "Buyuk Orta": "VFZSSlBRPT0=",
}
EMOJI = {
    "Bas Boyu":   "\U0001f947",
    "BasAlti":    "\U0001f948",
    "Buyuk Orta": "\U0001f949",
}
KATEGORI_ADI = {
    "Bas Boyu":   "BAS BOYU",
    "BasAlti":    "BASALTI",
    "Buyuk Orta": "BUYUK ORTA",
}
BASE = "https://tggf.com.tr/index.php?cat=website&subcat=sporcu-sonucesleme&edit=VFhwRk1RPT0="

# -------------------------------------------------------------------
def sayfa_cek(boy):
    """Sayfadaki TUM turlarin tablolarini cek.
    Her tur icin { 'tur_no': int, 'satirlar': [...] } donduruyor.
    """
    r = requests.get(
        f"{BASE}&boy={boy}",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15
    )
    soup = BeautifulSoup(r.text, "html.parser")

    sonuc = []
    # Her tablo oncekilerin tur basligini <th> veya tablonun ustundeki
    # div/p/h icinde tasir; basit yaklasim: tablolari sirayla bul,
    # her tablonun onceki kardes elementinde tur numarasini ara
    tablolar = soup.find_all("table")
    for tablo in tablolar:
        # Tur numarasini tablonun yakin cevresinden bul
        tur_no = 1
        # Tablo basligindaki <th> satirina bak
        tur_th = tablo.find("th")
        if tur_th:
            m = re.search(r"(\d+)\s*TUR", tur_th.get_text(), re.IGNORECASE)
            if m:
                tur_no = int(m.group(1))
        # Tablonun onceki elementlerine de bak
        prev = tablo.find_previous(string=re.compile(r"\d+\s*TUR", re.IGNORECASE))
        if prev:
            m = re.search(r"(\d+)\s*TUR", prev, re.IGNORECASE)
            if m:
                tur_no = int(m.group(1))

        satirlar = []
        for tr in tablo.find_all("tr")[1:]:
            td = tr.find_all("td")
            if len(td) < 4:
                continue
            satirlar.append({
                "sira":   td[0].get_text(strip=True),
                "kura":   td[1].get_text(strip=True),
                "sporcu": td[2].get_text(strip=True),
                "il":     td[3].get_text(strip=True),
                "sonuc":  td[4].get_text(strip=True) if len(td) > 4 else "",
                "tur":    td[5].get_text(strip=True) if len(td) > 5 else "",
                "tur_no": tur_no,
            })
        if satirlar:
            sonuc.append({"tur_no": tur_no, "satirlar": satirlar})
    return sonuc

# -------------------------------------------------------------------
def durum_belirle(sonuc, tur_sutun):
    s = sonuc.upper().strip()
    t = tur_sutun.strip()
    if not s and not t:
        return "bekliyor"
    if t and (not s or s in ("TUR", "-", "--")):
        return "tur_atladi"
    if not s or s in ("-", "--"):
        return "bekliyor"
    if "GAL" in s or s in ("G", "1", "W"):
        return "galip"
    return "maglup"

def sporcu_satir_formatla(s):
    durum = durum_belirle(s.get("sonuc", ""), s.get("tur", ""))
    tur_no = s.get("tur", "").strip()
    tur_yaz = f" | Tur: {tur_no}" if tur_no else ""
    if durum == "galip":
        return f"\u2705 <b>{s['sporcu']}</b> ({s['il']}) - GALIP{tur_yaz}"
    elif durum == "maglup":
        return f"\u274c <b>{s['sporcu']}</b> ({s['il']}) - MAGLUP{tur_yaz}"
    elif durum == "tur_atladi":
        return f"\U0001f503 <b>{s['sporcu']}</b> ({s['il']}) - TUR ATLADI (Bye){tur_yaz}"
    return None

def eslesmeler_olustur(satirlar):
    # Kura siralamasi ile cift olustur
    gecerli = [s for s in satirlar
               if s.get("sira", "").strip().isdigit() or
                  s.get("kura", "").strip().replace("T","").isdigit()]
    try:
        gecerli.sort(key=lambda x: int(x["kura"].replace("T","")) if x["kura"].replace("T","").isdigit() else 9999)
    except Exception:
        pass
    eslesmeler = []
    for i in range(0, len(gecerli) - 1, 2):
        eslesmeler.append((gecerli[i], gecerli[i+1]))
    return eslesmeler

def tg(mesaj):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "HTML"},
            timeout=10
        )
        print(f"[TG] {r.status_code}")
    except Exception as e:
        print(f"[TG HATA] {e}")

def state_yukle():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def state_kaydet(s):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

def eslesme_mesaji(kategori, tur_no, eslesmeler):
    saat = datetime.now(TR).strftime("%H:%M")
    em = EMOJI.get(kategori, "\U0001f93c")
    ad = KATEGORI_ADI.get(kategori, kategori)
    lines = [
        f"{em} <b>665.KIRKPINAR - {ad}</b>",
        f"\U0001f550 {saat} | {tur_no}. TUR ESLESMELER\n"
    ]
    for i, (a, b) in enumerate(eslesmeler, 1):
        lines.append(f"<b>{i}.</b> {a['sporcu']} ({a['il']})")
        lines.append(f"   \u2694\ufe0f VS \u2694\ufe0f")
        lines.append(f"   {b['sporcu']} ({b['il']})\n")
    lines.append("\U0001f4ca Kaynak: tggf.com.tr")
    return "\n".join(lines)

def sonuc_mesaji(kategori, tur_no, mesajlar):
    saat = datetime.now(TR).strftime("%H:%M")
    em = EMOJI.get(kategori, "\U0001f93c")
    ad = KATEGORI_ADI.get(kategori, kategori)
    baslik = f"{em} <b>665.KIRKPINAR - {ad}</b>\n\U0001f550 {saat} | {tur_no}. TUR SONUCLARI\n\n"
    return baslik + "\n".join(mesajlar) + "\n\n\U0001f4ca Kaynak: tggf.com.tr"

# -------------------------------------------------------------------
def main():
    state = state_yukle()
    saat = datetime.now(TR).strftime("%H:%M")
    print(f"[{saat}] Bot basladi...")

    for kategori, boy_param in KATEGORILER.items():
        try:
            tur_tablolar = sayfa_cek(boy_param)
            if not tur_tablolar:
                print(f"[-] {kategori}: veri yok")
                continue

            # Her tur tablosunu ayri isle
            for tur_data in tur_tablolar:
                tur_no   = tur_data["tur_no"]
                satirlar = tur_data["satirlar"]
                tur_key  = f"{kategori}__tur{tur_no}"

                eski_list = state.get(tur_key, [])
                eski_map  = {f"{s['sporcu']}|{s['il']}": s for s in eski_list}
                ilk       = (len(eski_list) == 0)

                if ilk:
                    # Yeni tur - eslesme mesaji gonder
                    eslesmeler = eslesmeler_olustur(satirlar)
                    if eslesmeler:
                        tg(eslesme_mesaji(kategori, tur_no, eslesmeler))
                        print(f"[eslesme] {kategori} Tur{tur_no}: {len(eslesmeler)} cift")
                    # Mevcut sonuclari da gonder
                    mesajlar = []
                    for s in satirlar:
                        d = durum_belirle(s.get("sonuc",""), s.get("tur",""))
                        if d != "bekliyor":
                            satir = sporcu_satir_formatla(s)
                            if satir:
                                mesajlar.append(satir)
                    if mesajlar:
                        tg(sonuc_mesaji(kategori, tur_no, mesajlar))
                        print(f"[ilk-sonuc] {kategori} Tur{tur_no}: {len(mesajlar)} sporcu")
                else:
                    # Degisen sonuclari gonder
                    mesajlar = []
                    for s in satirlar:
                        key = f"{s['sporcu']}|{s['il']}"
                        eski = eski_map.get(key)
                        yeni_sonuc = s.get("sonuc","").strip()
                        yeni_tur   = s.get("tur","").strip()
                        eski_sonuc = eski.get("sonuc","").strip() if eski else ""
                        eski_tur   = eski.get("tur","").strip()   if eski else ""

                        if yeni_sonuc != eski_sonuc or yeni_tur != eski_tur:
                            d = durum_belirle(yeni_sonuc, yeni_tur)
                            if d != "bekliyor":
                                satir = sporcu_satir_formatla(s)
                                if satir:
                                    mesajlar.append(satir)
                                    print(f"  degisim: {s['sporcu']} | {eski_sonuc}->{yeni_sonuc}")

                    if mesajlar:
                        tg(sonuc_mesaji(kategori, tur_no, mesajlar))
                        print(f"[guncelleme] {kategori} Tur{tur_no}: {len(mesajlar)} degisim")
                    else:
                        print(f"[-] {kategori} Tur{tur_no}: degisim yok")

                state[tur_key] = satirlar

        except Exception as e:
            print(f"[HATA] {kategori}: {e}")
        time.sleep(1)

    state_kaydet(state)
    print(f"[{datetime.now(TR).strftime('%H:%M')}] Tamamlandi.")

if __name__ == "__main__":
    main()
