import os
import time
import requests
import threading
import tkinter as tk
from tkinter import ttk
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()

# 1. Utilisation de constantes pour une meilleure lisibilité
EARNAPP_COOKIE = os.getenv("EARNAPP_COOKIE")
HONEYGAIN_EMAIL = os.getenv("HONEYGAIN_EMAIL")
HONEYGAIN_PASSWORD = os.getenv("HONEYGAIN_PASSWORD")

# Intervalles de mise à jour en millisecondes
EARNAPP_UPDATE_INTERVAL_MS = 60 * 60 * 1000  # 1 heure
HONEYGAIN_UPDATE_INTERVAL_MS = 5 * 60 * 1000   # 5 minutes


# --- Classe Principale de l'Application ---
class BalanceDashboard:
    """
    Une classe pour encapsuler la logique et l'état de l'application.
    Cela évite l'utilisation de variables globales.
    """
    def __init__(self, root):
        self.root = root
        self.earnapp_balance = "Chargement..."
        self.honeygain_balance = "Chargement..."
        # Pour stocker le token Honeygain et ne pas se reconnecter à chaque fois
        self.honeygain_session = requests.Session()
        self.honeygain_token = None

        self._setup_ui()
        self._start_updates()

    def _setup_ui(self):
        """Configure l'interface graphique."""
        self.root.title("Soldes")
        self.root.geometry("320x100")
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.9)
        self.root.resizable(True, True)

        self.label = ttk.Label(self.root, text="Initialisation...", font=("Segoe UI", 11), justify=tk.LEFT)
        self.label.pack(expand=True, fill="both", padx=10, pady=5)

    def _start_updates(self):
        """Lance les tâches de mise à jour en arrière-plan."""
        # Utilisation de "threading" pour ne pas bloquer l'interface au démarrage
        threading.Thread(target=self.update_earnapp_balance, daemon=True).start()
        threading.Thread(target=self.update_honeygain_balance, daemon=True).start()

    def update_display(self):
        """Met à jour le texte du label dans le thread principal de Tkinter."""
        text = f"EarnApp: {self.earnapp_balance}\nHoneygain: {self.honeygain_balance}"
        self.label.config(text=text)

    def schedule_update(self, interval_ms, update_function):
        """Planifie une fonction de mise à jour pour qu'elle s'exécute après un certain délai."""
        self.root.after(interval_ms, lambda: threading.Thread(target=update_function, daemon=True).start())

    # --- Logique pour EarnApp ---
    def update_earnapp_balance(self):
        """Récupère et met à jour le solde EarnApp."""
        try:
            headers = {'Cookie': EARNAPP_COOKIE}
            url = 'https://earnapp.com/dashboard/api/money?appid=earnapp_dashboard'
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status() # Lève une exception pour les codes d'erreur HTTP
            data = response.json()
            self.earnapp_balance = f"${data.get('balance', 0):.2f}"
        except requests.exceptions.RequestException as e:
            print(f"Erreur réseau EarnApp: {e}")
            self.earnapp_balance = "Erreur (Réseau)"
        except Exception as e:
            print(f"Erreur inattendue EarnApp: {e}")
            self.earnapp_balance = "Erreur"

        # Les mises à jour de l'UI doivent se faire dans le thread principal
        self.root.after(0, self.update_display)
        # Planifie la prochaine mise à jour
        if EARNAPP_UPDATE_INTERVAL_MS > 0:
            self.schedule_update(EARNAPP_UPDATE_INTERVAL_MS, self.update_earnapp_balance)

    # --- Logique pour Honeygain ---
    def _login_honeygain(self):
        """Gère la connexion à Honeygain et stocke le token."""
        try:
            login_data = {'email': HONEYGAIN_EMAIL, 'password': HONEYGAIN_PASSWORD}
            response = self.honeygain_session.post(
                'https://dashboard.honeygain.com/api/v1/users/tokens',
                json=login_data,
                timeout=15
            )
            response.raise_for_status()
            self.honeygain_token = response.json()['data']['access_token']
            print("Connexion à Honeygain réussie.")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Erreur de connexion à Honeygain: {e}")
            self.honeygain_token = None
            return False

    def update_honeygain_balance(self):
        """Récupère et met à jour le solde Honeygain."""
        if not self.honeygain_token:
            if not self._login_honeygain():
                self.honeygain_balance = "Erreur (Login)"
                self.root.after(0, self.update_display)
                if HONEYGAIN_UPDATE_INTERVAL_MS > 0:
                    self.schedule_update(HONEYGAIN_UPDATE_INTERVAL_MS, self.update_honeygain_balance)
                return

        try:
            headers = {'Authorization': f'Bearer {self.honeygain_token}'}
            response = self.honeygain_session.get(
                'https://dashboard.honeygain.com/api/v1/users/balances',
                headers=headers,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()['data']
            payout_cents = data['payout']['usd_cents']
            payout_credits = data['payout']['credits']
            self.honeygain_balance = f"{payout_credits} crédits (${payout_cents / 100:.2f})"

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401: # Token expiré ou invalide
                print("Token Honeygain expiré. Tentative de reconnexion...")
                self.honeygain_token = None # Réinitialise le token pour forcer une nouvelle connexion
                # Relance immédiatement la mise à jour sans attendre le prochain intervalle
                threading.Thread(target=self.update_honeygain_balance, daemon=True).start()
                return # Arrête l'exécution actuelle pour éviter une double planification
            else:
                print(f"Erreur HTTP Honeygain: {e}")
                self.honeygain_balance = "Erreur (HTTP)"
        except requests.exceptions.RequestException as e:
            print(f"Erreur réseau Honeygain: {e}")
            self.honeygain_balance = "Erreur (Réseau)"
        except Exception as e:
            print(f"Erreur inattendue Honeygain: {e}")
            self.honeygain_balance = "Erreur"

        self.root.after(0, self.update_display)
        if HONEYGAIN_UPDATE_INTERVAL_MS > 0:
            self.schedule_update(HONEYGAIN_UPDATE_INTERVAL_MS, self.update_honeygain_balance)


# --- Point d'entrée de l'application ---
if __name__ == "__main__":
    root = tk.Tk()
    app = BalanceDashboard(root)
    root.mainloop()
