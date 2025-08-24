import os
import requests
import threading
import tkinter as tk
from tkinter import ttk
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Note: This script now requires the sv-ttk library for the modern theme.
# Install it with: pip install sv-ttk
import sv_ttk

# --- Configuration ---
load_dotenv()

EARNAPP_COOKIE = os.getenv("EARNAPP_COOKIE")
HONEYGAIN_EMAIL = os.getenv("HONEYGAIN_EMAIL")
HONEYGAIN_PASSWORD = os.getenv("HONEYGAIN_PASSWORD")

DEFAULT_HONEYGAIN_INTERVAL_MIN = 5


# --- Classe Principale de l'Application ---
class BalanceDashboard:
    def __init__(self, root):
        self.root = root
        self.earnapp_balance = "Chargement..."
        self.honeygain_balance = "Chargement..."
        
        self.honeygain_session = requests.Session()
        self.honeygain_token = None

        # Variables pour les nouvelles fonctionnalités
        self.honeygain_interval_ms = int(DEFAULT_HONEYGAIN_INTERVAL_MIN * 60 * 1000)
        self.honeygain_after_id = None
        self.honeygain_interval_var = tk.StringVar(value=str(DEFAULT_HONEYGAIN_INTERVAL_MIN))
        
        self.settings_visible = False
        self.earnapp_next_run = None
        self.honeygain_next_run = None

        self._setup_ui()
        self._start_updates()

    def _setup_ui(self):
        """Configure l'interface graphique."""
        self.root.title("Soldes")
        self.root.geometry("350x250")
        self.root.attributes('-topmost', True)
        
        initial_alpha = 0.9
        self.root.attributes('-alpha', initial_alpha)

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(expand=True, fill="both")

        # --- Section des soldes ---
        balances_frame = ttk.Frame(main_frame)
        balances_frame.pack(fill="x")
        self.balances_label = ttk.Label(balances_frame, text="Initialisation...", font=("Segoe UI", 11), justify=tk.LEFT)
        self.balances_label.pack(fill="x")

        # --- Section des comptes à rebours ---
        countdown_frame = ttk.Frame(main_frame, padding=(0, 10, 0, 5))
        countdown_frame.pack(fill="x")
        self.earnapp_countdown_label = ttk.Label(countdown_frame, text="EarnApp: en attente...", font=("Segoe UI", 9))
        self.earnapp_countdown_label.pack(fill="x")
        self.honeygain_countdown_label = ttk.Label(countdown_frame, text="Honeygain: en attente...", font=("Segoe UI", 9))
        self.honeygain_countdown_label.pack(fill="x")

        # --- Bouton pour les paramètres ---
        self.settings_button = ttk.Button(main_frame, text="Afficher les paramètres", command=self._toggle_settings)
        self.settings_button.pack(fill="x", pady=5)

        # --- Frame cachée pour les contrôles ---
        self.controls_frame = ttk.LabelFrame(main_frame, text="Paramètres", padding="10")
        # Ne pas .pack() ici pour la cacher par défaut

        # Contrôle de l'intervalle Honeygain
        hg_frame = ttk.Frame(self.controls_frame)
        hg_frame.pack(fill="x", pady=5)
        ttk.Label(hg_frame, text="Intervalle Honeygain (min):").pack(side="left")
        ttk.Entry(hg_frame, width=5, textvariable=self.honeygain_interval_var).pack(side="left", padx=5)
        ttk.Button(hg_frame, text="Appliquer", command=self._apply_honeygain_interval).pack(side="left")

        # Contrôle de la transparence
        alpha_frame = ttk.Frame(self.controls_frame)
        alpha_frame.pack(fill="x", pady=5)
        ttk.Label(alpha_frame, text="Transparence:").pack(side="left")
        ttk.Scale(alpha_frame, from_=0.3, to=1.0, value=initial_alpha, orient="horizontal", command=self._update_transparency).pack(side="left", expand=True, fill="x", padx=5)

    def _start_updates(self):
        """Lance les tâches de mise à jour et le minuteur."""
        threading.Thread(target=self.update_earnapp_balance, daemon=True).start()
        threading.Thread(target=self.update_honeygain_balance, daemon=True).start()
        self._update_countdown_labels() # Lancement du minuteur

    # --- Méthodes de l'interface ---

    def _toggle_settings(self):
        """Affiche ou cache le panneau des paramètres."""
        if self.settings_visible:
            self.controls_frame.pack_forget()
            self.settings_button.config(text="Afficher les paramètres")
        else:
            self.controls_frame.pack(expand=True, fill="x")
            self.settings_button.config(text="Cacher les paramètres")
        self.settings_visible = not self.settings_visible
    
    def _update_countdown_labels(self):
        """Met à jour les comptes à rebours toutes les secondes."""
        now = datetime.now()
        # Pour EarnApp
        if self.earnapp_next_run:
            if self.earnapp_next_run > now:
                delta = self.earnapp_next_run - now
                self.earnapp_countdown_label.config(text=f"EarnApp: prochaine màj dans {str(delta).split('.')[0]}")
            else:
                self.earnapp_countdown_label.config(text="EarnApp: actualisation en cours...")
        
        # Pour Honeygain
        if self.honeygain_next_run:
            if self.honeygain_next_run > now:
                delta = self.honeygain_next_run - now
                self.honeygain_countdown_label.config(text=f"Honeygain: prochaine màj dans {str(delta).split('.')[0]}")
            else:
                self.honeygain_countdown_label.config(text="Honeygain: actualisation en cours...")

        self.root.after(1000, self._update_countdown_labels)

    def _update_display(self):
        """Met à jour le texte du label des soldes."""
        text = f"💰 EarnApp: {self.earnapp_balance}\n🐝 Honeygain: {self.honeygain_balance}"
        self.balances_label.config(text=text)

    def _update_transparency(self, value):
        self.root.attributes('-alpha', float(value))

    def _apply_honeygain_interval(self):
        try:
            new_interval_min = int(self.honeygain_interval_var.get())
            if new_interval_min <= 0:
                print("L'intervalle doit être un nombre positif.")
                return
            
            self.honeygain_interval_ms = new_interval_min * 60 * 1000
            print(f"Nouvel intervalle Honeygain: {new_interval_min} minutes.")

            if self.honeygain_after_id:
                self.root.after_cancel(self.honeygain_after_id)
            
            threading.Thread(target=self.update_honeygain_balance, daemon=True).start()
        except ValueError:
            print("Veuillez entrer un nombre valide pour l'intervalle.")

    # --- Logique de planification ---

    def _schedule_honeygain_update(self):
        self.honeygain_next_run = datetime.now() + timedelta(milliseconds=self.honeygain_interval_ms)
        self.honeygain_after_id = self.root.after(
            self.honeygain_interval_ms,
            lambda: threading.Thread(target=self.update_honeygain_balance, daemon=True).start()
        )

    def _schedule_earnapp_update(self):
        now = datetime.now()
        next_run = now.replace(minute=5, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(hours=1)
            
        self.earnapp_next_run = next_run
        delay_ms = int((self.earnapp_next_run - now).total_seconds() * 1000)
        
        print(f"Prochaine mise à jour EarnApp planifiée à {self.earnapp_next_run.strftime('%H:%M:%S')}")
        self.root.after(delay_ms, lambda: threading.Thread(target=self.update_earnapp_balance, daemon=True).start())

    # --- Logique des APIs (inchangée) ---
    def update_earnapp_balance(self):
        try:
            headers = {'Cookie': EARNAPP_COOKIE}
            url = 'https://earnapp.com/dashboard/api/money?appid=earnapp&version=1.562.221'
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            self.earnapp_balance = f"${data.get('balance', 0):.2f}"
        except Exception:
            self.earnapp_balance = "Erreur"
        
        self.root.after(0, self._update_display)
        self._schedule_earnapp_update()

    def update_honeygain_balance(self):
        if not self.honeygain_token:
            if not self._login_honeygain():
                self.honeygain_balance = "Erreur (Login)"
                self.root.after(0, self._update_display)
                self._schedule_honeygain_update()
                return
        try:
            headers = {'Authorization': f'Bearer {self.honeygain_token}'}
            response = self.honeygain_session.get('https://dashboard.honeygain.com/api/v1/users/balances', headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()['data']
            self.honeygain_balance = f"{data['payout']['credits']} crédits (${data['payout']['usd_cents'] / 100:.2f})"
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                self.honeygain_token = None
                threading.Thread(target=self.update_honeygain_balance, daemon=True).start()
                return
            else:
                self.honeygain_balance = "Erreur (HTTP)"
        except Exception:
            self.honeygain_balance = "Erreur"
        
        self.root.after(0, self._update_display)
        self._schedule_honeygain_update()

    def _login_honeygain(self):
        try:
            login_data = {'email': HONEYGAIN_EMAIL, 'password': HONEYGAIN_PASSWORD}
            response = self.honeygain_session.post('https://dashboard.honeygain.com/api/v1/users/tokens', json=login_data, timeout=15)
            response.raise_for_status()
            self.honeygain_token = response.json()['data']['access_token']
            return True
        except Exception:
            self.honeygain_token = None
            return False

# --- Point d'entrée de l'application ---
if __name__ == "__main__":
    root = tk.Tk()
    
    # Appliquer le thème moderne
    sv_ttk.set_theme("dark")

    app = BalanceDashboard(root)
    root.mainloop()
