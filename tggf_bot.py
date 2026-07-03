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
            "sira":   td[0].get_text(strip=True),
            "kura":   td[1].get_text(strip=True),
            "sporcu": td[2].get_text(strip=True),
            "il":     td[3].get_text(strip=True),
            "sonuc":  td[4].get_text(strip=True) if len(td) > 4 else "",
            "tur":    td[5].get_text(strip=True) if len(td) > 5 else "",
        })
    return satirlar


def eslesmeler_olustur(satirlar):
    """Kura numarasını integer'a çevirip sıralı eşleştirir."""
    sirali = []
    for s in satirlar:
        try:
            kura_no = int(s.get("kura", "0"))
            if kura_no > 0:
                sirali.append((kura_no, s))
        except:
            continue
    
    # Kura numarasına göre sırala
    sirali.sort(key=lambda x: x[0])
    
    # Ardışık çiftleri eşleştir (1-2, 3-4, 5-6...)
    eslesmeler = []
    for i in range(0, len(sirali) - 1, 2):
        eslesmeler.append((sirali[i][1], sirali[i+1][1]))
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
    em   = EMOJI.get(kategori, "🤼")
    satirlar = [
        f"{em} <b>665.KIRKPINAR — {kategori.upper()}</b>",
        f"🕐 {saat} | TUR EŞLEŞMELERİ\n"
    ]
    for i, (a, b) in enumerate(eslesmeler, 1):
        satirlar.append(
            f"<b>{i}.</b> {a['sporcu']} ({a['il']})\n"
            f"       ⚔️  VS  ⚔️\n"
            f"       {b['sporcu']} ({b['il']})\n"
        )
    satirlar.append("📊 Kaynak: tggf.com.tr")
    return "\n".join(satirlar)


def sonuc_mesaji(kategori, mesajlar):
    saat = datetime.now(TR).strftime("%H:%M")
    em   = EMOJI.get(kategori, "🤼")
    baslik = (
        f"{em} <b>665.KIRKPINAR — {kategori.upper()}</b>\n"
        f"🕐 {saat} | SONUÇ GÜNCELLEMESİ\n\n"
    )
    return baslik + "\n".join(mesajlar) + "\n\n📊 Kaynak: tggf.com.tr"


def main():
    state = state_yukle()
    saat  = datetime.now(TR).strftime("%H:%M")
    print(f"[{saat}] Bot başladı...")

    for kategori, boy_param in KATEGORILER.items():
        try:
            yeni     = sayfa_cek(boy_param)
            eski_map = {
                f"{s['sporcu']}|{s['il']}": s
                for s in state.get(kategori, [])
            }

            # ── İLK ÇALIŞMA: Eşleşmeleri gönder ──────────────────
            if not state.get(kategori) and yeni:
                eslesmeler = eslesmeler_olustur(yeni)
                if eslesmeler:
                    tg(eslesme_mesaji(kategori, eslesmeler))
                    print(f"[⚔️] {kategori}: eşleşmeler gönderildi")

            # ── SONRAKI ÇALIŞMALAR: Değişimleri gönder ───────────
            else:
                mesajlar = []
                for s in yeni:
                    key  = f"{s['sporcu']}|{s['il']}"
                    eski = eski_map.get(key)

                    # Yeni sporcu eklendiyse
                    if eski is None:
                        mesajlar.append(
                            f"➕ <b>{s['sporcu']}</b> ({s['il']}) — Eklendi"
                        )
                    # Sonuç değiştiyse
                    elif s["sonuc"] and s["sonuc"] != eski.get("sonuc", ""):
                        em  = "✅" if s["sonuc"] in ["G", "GALİP", "1", "W"] else "❌"
                        tur = f" | Tur: {s['tur']}" if s["tur"] else ""
                        mesajlar.append(
                            f"{em} <b>{s['sporcu']}</b> ({s['il']}) "
                            f"→ {s['sonuc']}{tur}"
                        )
                    # Tur değiştiyse (yeni tura geçti)
                    elif s["tur"] and s["tur"] != eski.get("tur", ""):
                        mesajlar.append(
                            f"🔄 <b>{s['sporcu']}</b> ({s['il']}) "
                            f"→ {s['tur']}. TUR"
                        )

                if mesajlar:
                    tg(sonuc_mesaji(kategori, mesajlar))
                    print(f"[✓] {kategori}: {len(mesajlar)} güncelleme gönderildi")
                else:
                    print(f"[-] {kategori}: değişim yok")

            state[kategori] = yeni

        except Exception as e:
            print(f"[HATA] {kategori}: {e}")

        time.sleep(1)

    state_kaydet(state)
    print(f"[{datetime.now(TR).strftime('%H:%M')}] Tamamlandı.")


if __name__ == "__main__":
    main()
