"""Date de reference d'une edition, partagee par toute la chaine (collect, summarize, generate_html, publish).

Par defaut : maintenant (cron du samedi). Pour rattraper une edition manquee :
RADAR_DATE=2026-11-07 python3 scripts/collect.py
La fenetre collectee est [RADAR_DATE - 7 jours, RADAR_DATE] a 05:00 et la semaine ISO est celle de RADAR_DATE.
"""
import os
from datetime import datetime


def reference_date() -> datetime:
    """Renvoie la date de reference : RADAR_DATE (YYYY-MM-DD) si definie et non vide, sinon maintenant.

    Une valeur invalide fait planter : un rattrapage qui retomberait en silence sur maintenant
    publierait la mauvaise semaine sans prevenir.
    """
    raw = os.environ.get("RADAR_DATE", "").strip()
    if not raw:
        return datetime.now()
    try:
        ref = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        raise SystemExit(f"RADAR_DATE invalide : {raw!r}, format attendu YYYY-MM-DD")
    if ref > datetime.now():
        raise SystemExit(f"RADAR_DATE dans le futur : {raw}")
    # meme heure que le cron (05:00 UTC, l'heure du runner) : la fenetre rattrapee est exactement
    # celle qu'aurait eue le run manque, sans chevauchement avec l'edition suivante
    return ref.replace(hour=5)
