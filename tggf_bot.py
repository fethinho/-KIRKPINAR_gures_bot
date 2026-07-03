import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime, timezone, timedelta

BOT_TOKEN  = "8185628247:AAGh1gBPwzBaXLTZvU6RRUfXM3xN68eXmdg"
CHAT_ID    = "-1003562869508"
STATE_FILE = "tggf_state.json"

TR = timezone(timedelta(hours=3))

KATEGORILER = {
    "Baş Boyu":   "VFZSUlBRPT0=",
    "BaşAltı":    "VFZSTlBRPT0=",
    "Büyük Orta": "VFZSSlBRPT0=",
}

EMOJI = {
    "Baş Boyu":   "🥇",
    "BaşAltı":    "🥈",
    "Büyük Orta": "🥉",
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
            "sporcu": td[2].get_text(strip=True),
            "il":     td[3].get_text(strip=True),
            "sonuc":  td[4].get_text(strip=True) if len(td) > 4 else "",
            "tur":    td[5].get_text(strip=True) if len(td) > 5 else "",
        })
    return satirlar


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
    tg("🔧 Bot çalışıyor - test mesajı")

def state_yukle():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def state_kaydet(s):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)


def main():
    state = state_yukle()
    saat  = datetime.now(TR).strftime("%H:%M")

    for kategori, boy_param in KATEGORILER.items():
        try:
            yeni     = sayfa_cek(boy_param)
            eski_map = {
                f"{s['sporcu']}|{s['il']}": s
                for s in state.get(kategori, [])
            }
            mesajlar = []

            for s in yeni:
                key  = f"{s['sporcu']}|{s['il']}"
                eski = eski_map.get(key)

                # Yeni sporcu — sadece state doluysa bildir
                if eski is None and state.get(kategori):
                    mesajlar.append(
                        f"➕ <b>{s['sporcu']}</b> ({s['il']}) — Eklendi"
                    )
                # Sonuç değişimi
                elif eski is not None and s["sonuc"] and s["sonuc"] != eski["sonuc"]:
                    em  = "✅" if s["sonuc"] in ["G", "GALİP", "1", "W"] else "❌"
                    tur = f" | Tur:{s['tur']}" if s["tur"] else ""
                    mesajlar.append(
                        f"{em} <b>{s['sporcu']}</b> ({s['il']}) → {s['sonuc']}{tur}"
                    )

            if mesajlar:
                baslik = (
                    f"{EMOJI[kategori]} <b>665.KIRKPINAR — "
                    f"{kategori.upper()}</b>\n🕐 {saat}\n\n"
                )
                tg(baslik + "\n".join(mesajlar))
                print(f"[✓] {kategori}: {len(mesajlar)} güncelleme")
            else:
                print(f"[-] {kategori}: değişim yok")

            state[kategori] = yeni

        except Exception as e:
            print(f"[HATA] {kategori}: {e}")

        time.sleep(1)

    state_kaydet(state)
    print(f"[{saat}] Tamamlandı.")


if __name__ == "__main__":
    main()
