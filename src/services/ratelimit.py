"""Limitation des tentatives (connexion, inscription), comptées dans la table auth_attempt.

Les compteurs sont stockés EN BASE et non en mémoire : un hébergeur lance souvent plusieurs processus, et une
limite gardée en mémoire serait contournable (chaque processus aurait son propre compteur).
"""
import os
import time

from flask import request


def client_ip():
    """Adresse IP du visiteur.

    Derrière le serveur d'un hébergeur, l'adresse vue par Flask est celle du serveur frontal : avec TRUST_PROXY=1
    dans le .env, on lit celle qu'il transmet (X-Real-IP, sinon la dernière adresse de X-Forwarded-For, qui est
    celle ajoutée par le proxy de confiance). Sans ce réglage, ces en-têtes (falsifiables) sont ignorés.
    """
    if os.environ.get('TRUST_PROXY') == '1':
        ip = request.headers.get('X-Real-IP', '').strip()
        if not ip:
            forwarded = request.headers.get('X-Forwarded-For', '')
            ip = forwarded.split(',')[-1].strip() if forwarded else ''
        if ip:
            return ip[:64]
    return request.remote_addr or 'inconnue'


def rl_count(conn, bucket, window_seconds):
    """Nombre d'événements du seau `bucket` dans les `window_seconds` dernières secondes."""
    since = int(time.time()) - window_seconds
    return conn.execute("SELECT COUNT(*) AS n FROM auth_attempt WHERE bucket=? AND ts>=?", (bucket, since)).fetchone()['n']


def rl_hit(conn, bucket):
    """Compte un événement dans le seau (et oublie ceux de plus de 24 h)."""
    now = int(time.time())
    conn.execute("INSERT INTO auth_attempt(bucket, ts) VALUES(?, ?)", (bucket, now))
    conn.execute("DELETE FROM auth_attempt WHERE ts < ?", (now - 24 * 3600,))


def rl_reset(conn, bucket):
    """Vide le seau (connexion réussie)."""
    conn.execute("DELETE FROM auth_attempt WHERE bucket=?", (bucket,))
