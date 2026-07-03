import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime, timezone, timedelta

BOT_TOKEN  = "8185628247:AAGh1gBPwzBaXLTZvU6RRUfXM3xN68eXmdg"
CHAT_ID    = "-1003562869508"
STATE_FILE = "tggf_state.json"
TR         = timezone(timedelta(hours=3))

KATEGORILER = {
    "Bas Boyu":   "VFZSUlBRPT0=",
    "BasAlti":    "VFZSTlBRPT0=",
    "Buyuk Orta": "VFZSSlBRPT0=",
}

EMOJI = {
    "Bas Boyu":   "🥇",
    "BasAlti":    "🥈",
    "Buyuk Orta": "🥉",
}

KATEGORI_ADI = {
    "Bas Boyu":   "BAS BOYU",
    "BasAlti":    "BASALTI",
    "Buyuk Orta": "BUYUK ORTA",
}

BASE = "https://tggf.com.tr/index.php?cat=website&subcat=sporcu-sonucesleme&edit=VFhwRk1RPT0="


def sayfa_cek(boy):
    r = requests.get(
        f"{BASE}&boy={boy}",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15
    )
    soup = BeautifulSoup(r.text, "html.parser")
    tablo = soup.find("table")
    if not tablo:
        return []
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
        })
    return satirlar


def galip_mi(sonuc_text):
    s = sonuc_text.upper().strip()
    return "GAL" in s or s == "G" or s == "1" or s == "W"


def eslesmeler_olustur(satirlar):
    sirali = []
    for s in satirlar:
        sira = s.get("sira", "").strip()
        if sira and sira != "--" and sira != "-" and sira.isdigit():
            sirali.append(s)
    sirali.sort(key=lambda x: int(x["sira"]))
    eslesmeler = []
    for i in range(0, len(sirali) - 1, 2):
        eslesmeler.append((sirali[i], sirali[i + 1]))
    return eslesmeler


def tg(mesaj):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={
            "chat_id":    CHAT_ID,
            "text":       mesaj,
            "parse_mode": "HTML"
        },
        timeout=10
    )


def state_yukle():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def state_kaydet(s):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)


def eslesme_mesaji(kategori, eslesmeler):
    saat = datetime.now(TR).strftime("%H:%M")
    em = EMOJI.get(kategori, "🤼")
    ad = KATEGORI_ADI.get(kategori, kategori)
    lines = [
        f"{em} <b>665.KIRKPINAR - {ad}</b>",
        f"🕐 {saat} | TUR ESLESMELER\n"
    ]
    for i, (a, b) in enumerate(eslesmeler, 1):
        lines.append(f"<b>{i}.</b> {a['sporcu']} ({a['il']})")
        lines.append(f"       ⚔️ VS ⚔️")
        lines.append(f"       {b['sporcu']} ({b['il']})\n")
    lines.append("📊 Kaynak: tggf.com.tr")
    return "\n".join(lines)


def sonuc_mesaji(kategori, mesajlar):
    saat = datetime.now(TR).strftime("%H:%M")
    em = EMOJI.get(kategori, "🤼")
    ad = KATEGORI_ADI.get(kategori, kategori)
    baslik = f"{em} <b>665.KIRKPINAR - {ad}</b>\n🕐 {saat} | SONUC\n\n"
    return baslik + "\n".join(mesajlar) + "\n\n📊 Kaynak: tggf.com.tr"


def main():
    state = state_yukle()
    saat = datetime.now(TR).strftime("%H:%M")
    print(f"[{saat}] Bot basladi...")

    for kategori, boy_param in KATEGORILER.items():
        try:
            yeni = sayfa_cek(boy_param)
            eski_map = {
                f"{s['sporcu']}|{s['il']}": s
                for s in state.get(kategori, [])
            }

            if not state.get(kategori) and yeni:
                eslesmeler = eslesmeler_olustur(yeni)
                if eslesmeler:
                    tg(eslesme_mesaji(kategori, eslesmeler))
                    print(f"[eslesme] {kategori}: {len(eslesmeler)} cift")
            else:
                mesajlar = []
                for s in yeni:
                    key = f"{s['sporcu']}|{s['il']}"
                    eski = eski_map.get(key)
                    if eski is None:
                        mesajlar.append(f"➕ <b>{s['sporcu']}</b> ({s['il']}) - Eklendi")
                    elif s["sonuc"] and s["sonuc"] != eski.get("sonuc", ""):
                        if galip_mi(s["sonuc"]):
                            em2 = "✅"
                            durum = "GALIP"
                        else:
                            em2 = "❌"
                            durum = "MAGUP"
                        tur = f" | Tur: {s['tur']}" if s["tur"] else ""
                        mesajlar.append(f"{em2} <b>{s['sporcu']}</b> ({s['il']}) - {durum}{tur}")
                    elif s["tur"] and s["tur"] != eski.get("tur", ""):
                        mesajlar.append(f"🔄 <b>{s['sporcu']}</b> ({s['il']}) - {s['tur']}. TUR")

                if mesajlar:
                    tg(sonuc_mesaji(kategori, mesajlar))
                    print(f"[guncelleme] {kategori}: {len(mesajlar)} degisim")
                else:
                    print(f"[-] {kategori}: degisim yok")

            state[kategori] = yeni

        except Exception as e:
            print(f"[HATA] {kategori}: {e}")

        time.sleep(1)

    state_kaydet(state)
    print(f"[{datetime.now(TR).strftime('%H:%M')}] Tamamlandi.")


if __name__ == "__main__":
    main()
