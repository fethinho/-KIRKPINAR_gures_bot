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
def tur_no_bul(metin):
    """Metinden tur numarasini cikar. '( 2 TUR)', '( 3 TUR)' gibi formatlari yakalar."""
    m = re.search(r'(\d+)\s*TUR', metin, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None

def sayfa_cek(boy):
    """Sadece EN UST tabloyu oku ve tur_no ile satirlari dondur."""
    r = requests.get(
        f"{BASE}&boy={boy}",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15
    )
    soup = BeautifulSoup(r.text, "html.parser")

    tablo = soup.find("table")
    if not tablo:
        return None

    tur_no = 1
    for th in tablo.find_all("th"):
        n = tur_no_bul(th.get_text())
        if n:
            tur_no = n
            break

    satirlar = []
    for tr in tablo.find_all("tr")[1:]:
        td = tr.find_all("td")
        if len(td) < 3:
            continue
        sporcu = td[2].get_text(strip=True) if len(td) > 2 else ""
        il     = td[3].get_text(strip=True) if len(td) > 3 else ""
        sonuc  = td[4].get_text(strip=True) if len(td) > 4 else ""
        if not sporcu or sporcu in ("-", "--"):
            continue
        satirlar.append({
            "sporcu": sporcu,
            "il":     il,
            "sonuc":  sonuc,
            "tur_no": tur_no,
        })
    return {"tur_no": tur_no, "satirlar": satirlar}

# -------------------------------------------------------------------
def durum_belirle(sonuc):
    s = sonuc.upper().strip()
    if not s or s in ("-", "--", ""):
        return "bekliyor"
    if "GAL" in s or s in ("G", "G#", "1", "W"):
        return "galip"
    return "maglup"

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

def eslesme_mesaji(kategori, tur_no, satirlar):
    """Yeni tur basladinda eslesme listesi gonder."""
    saat = datetime.now(TR).strftime("%H:%M")
    em   = EMOJI.get(kategori, "\U0001f93c")
    ad   = KATEGORI_ADI.get(kategori, kategori)
    lines = [
        f"{em} <b>665.KIRKPINAR - {ad}</b>",
        f"\U0001f550 {saat} | {tur_no}. TUR ESLESMELER\n",
    ]
    # Ciftleri kura sirasi ile olustur (1-2, 3-4, ...)
    ciftler = [satirlar[i:i+2] for i in range(0, len(satirlar)-1, 2)]
    for i, cift in enumerate(ciftler, 1):
        a = cift[0]
        b = cift[1] if len(cift) > 1 else None
        if b:
            lines.append(f"<b>{i}.</b> {a['sporcu']} ({a['il']})")
            lines.append(f"   \u2694\ufe0f VS \u2694\ufe0f")
            lines.append(f"   {b['sporcu']} ({b['il']})\n")
    lines.append("\U0001f4ca Kaynak: tggf.com.tr")
    return "\n".join(lines)

def yeni_tur_listesi_mesaji(kategori, tur_no, satirlar):
    """Yeni tura gecildiginde o turdaki sporcu listesi."""
    saat = datetime.now(TR).strftime("%H:%M")
    em   = EMOJI.get(kategori, "\U0001f93c")
    ad   = KATEGORI_ADI.get(kategori, kategori)
    lines = [
        f"{em} <b>665.KIRKPINAR - {ad}</b>",
        f"\U0001f550 {saat} | {tur_no}. TURA KALANLAR ({len(satirlar)} sporcu)\n",
    ]
    for i, s in enumerate(satirlar, 1):
        lines.append(f"{i}. {s['sporcu']} ({s['il']})")
    lines.append(f"\n\U0001f4ca Kaynak: tggf.com.tr")
    return "\n".join(lines)

def sonuc_guncelleme_mesaji(kategori, tur_no, galip_satirlar):
    """Tur icinde gelen galip guncellemeleri."""
    saat = datetime.now(TR).strftime("%H:%M")
    em   = EMOJI.get(kategori, "\U0001f93c")
    ad   = KATEGORI_ADI.get(kategori, kategori)
    lines = [
        f"{em} <b>665.KIRKPINAR - {ad}</b>",
        f"\U0001f550 {saat} | {tur_no}. TUR - YENİ GALİPLER\n",
    ]
    for s in galip_satirlar:
        lines.append(f"\u2705 <b>{s['sporcu']}</b> ({s['il']}) - GALİP")
    lines.append(f"\n\U0001f4ca Kaynak: tggf.com.tr")
    return "\n".join(lines)

# -------------------------------------------------------------------
def main():
    state = state_yukle()
    saat  = datetime.now(TR).strftime("%H:%M")
    print(f"[{saat}] Bot basladi...")

    for kategori, boy_param in KATEGORILER.items():
        try:
            veri = sayfa_cek(boy_param)
            if not veri or not veri["satirlar"]:
                print(f"[-] {kategori}: veri yok")
                continue

            tur_no  = veri["tur_no"]
            satirlar = veri["satirlar"]
            tur_key  = f"{kategori}__tur"
            eski_tur = state.get(tur_key + "_no", 0)
            eski_sporcu_map = {s["sporcu"]: s for s in state.get(tur_key + "_list", [])}

            print(f"[kontrol] {kategori}: sayfa_tur={tur_no}, state_tur={eski_tur}, sporcu={len(satirlar)}")

            if tur_no != eski_tur:
                # --- YENİ TUR BAŞLADI ---
                print(f"[YENİ TUR] {kategori}: {eski_tur} -> {tur_no}")

                # 1) Eslesme mesaji (sadece tur 2 ve sonrasi icin, tur 1 eslesme zaten ilk gonderildi)
                tg(eslesme_mesaji(kategori, tur_no, satirlar))
                print(f"[eslesme] {kategori} Tur{tur_no}: {len(satirlar)//2} cift")

                # 2) Sporcu listesi (X. TURA KALANLAR)
                tg(yeni_tur_listesi_mesaji(kategori, tur_no, satirlar))
                print(f"[liste] {kategori} Tur{tur_no}: {len(satirlar)} sporcu")

                # State guncelle
                state[tur_key + "_no"]   = tur_no
                state[tur_key + "_list"] = satirlar

            else:
                # --- AYNI TUR, YENİ GALİP KONTROLÜ ---
                yeni_galipler = []
                for s in satirlar:
                    sporcu = s["sporcu"]
                    yeni_d = durum_belirle(s["sonuc"])
                    eski_s = eski_sporcu_map.get(sporcu)
                    eski_d = durum_belirle(eski_s["sonuc"]) if eski_s else "bekliyor"

                    if yeni_d == "galip" and eski_d != "galip":
                        yeni_galipler.append(s)
                        print(f"  yeni galip: {sporcu}")

                if yeni_galipler:
                    tg(sonuc_guncelleme_mesaji(kategori, tur_no, yeni_galipler))
                    print(f"[guncelleme] {kategori} Tur{tur_no}: {len(yeni_galipler)} yeni galip")
                else:
                    print(f"[-] {kategori} Tur{tur_no}: degisim yok")

                # State guncelle (sadece liste)
                state[tur_key + "_list"] = satirlar

        except Exception as e:
            import traceback
            print(f"[HATA] {kategori}: {e}")
            traceback.print_exc()
        time.sleep(1)

    state_kaydet(state)
    print(f"[{datetime.now(TR).strftime('%H:%M')}] Tamamlandi.")

if __name__ == "__main__":
    main()
