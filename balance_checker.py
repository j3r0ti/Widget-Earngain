import os
import json
import requests
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

# Note: This script now requires the sv-ttk library for the modern theme.
# Install it with: pip install sv-ttk
import sv_ttk

# --- Constants ---
DEFAULT_HONEYGAIN_INTERVAL_MIN = 5
CONFIG_FILE = "config.json"

# --- Configuration Management ---
def load_config():
    """Charge la configuration depuis config.json et assure la présence des clés par défaut."""
    if not os.path.exists(CONFIG_FILE):
        return {} # Retourne un dict vide pour forcer la configuration initiale
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        # S'assurer que les clés d'activation existent (pour la compatibilité ascendante)
        config.setdefault('earnapp_enabled', True)
        config.setdefault('honeygain_enabled', True)
        return config
    except (json.JSONDecodeError, IOError):
        return {}

def save_config(config):
    """Sauvegarde la configuration dans config.json."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except IOError:
        return False

# --- Fenêtre de Configuration ---
class ConfigWindow(tk.Toplevel):
    # ... (Classe ConfigWindow inchangée)
    def __init__(self, parent, current_config={}):
        super().__init__(parent)
        self.transient(parent)
        self.title("Configuration des identifiants")
        self.result = None
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.earnapp_var = tk.StringVar(value=current_config.get('earnapp_cookie', ''))
        self.hg_email_var = tk.StringVar(value=current_config.get('honeygain_email', ''))
        self.hg_pass_var = tk.StringVar(value=current_config.get('honeygain_password', ''))
        frame = ttk.Frame(self, padding="10")
        frame.pack(expand=True, fill="both")
        ttk.Label(frame, text="Cookie EarnApp:").pack(anchor="w")
        ttk.Entry(frame, textvariable=self.earnapp_var, width=50).pack(fill="x", pady=(0, 10))
        ttk.Label(frame, text="Email Honeygain:").pack(anchor="w")
        ttk.Entry(frame, textvariable=self.hg_email_var, width=50).pack(fill="x", pady=(0, 10))
        ttk.Label(frame, text="Mot de passe Honeygain:").pack(anchor="w")
        ttk.Entry(frame, textvariable=self.hg_pass_var, show="*", width=50).pack(fill="x", pady=(0, 20))
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="Enregistrer", command=self._on_save).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Annuler", command=self._on_cancel).pack(side="right")
        self.grab_set()
        self.wait_window(self)

    def _on_save(self):
        earnapp = self.earnapp_var.get().strip()
        hg_email = self.hg_email_var.get().strip()
        hg_pass = self.hg_pass_var.get()
        if not all([earnapp, hg_email, hg_pass]):
            messagebox.showwarning("Champs vides", "Veuillez remplir tous les champs.", parent=self)
            return
        self.result = {
            "earnapp_cookie": earnapp,
            "honeygain_email": hg_email,
            "honeygain_password": hg_pass
        }
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()

# --- Classe Principale de l'Application ---
class BalanceDashboard:
    def __init__(self, root, config):
        self.root = root
        self.config = config

        # ... (Variables d'état)
        self.earnapp_balance = "Désactivé"
        self.honeygain_balance = "Désactivé"
        self.honeygain_session = requests.Session()
        self.honeygain_token = None
        self.honeygain_interval_ms = int(self.config.get('honeygain_interval_min', DEFAULT_HONEYGAIN_INTERVAL_MIN) * 60 * 1000)
        self.honeygain_after_id = None
        self.earnapp_after_id = None
        self.settings_visible = False
        self.earnapp_next_run = None
        self.honeygain_next_run = None

        # Variables pour les widgets
        self.honeygain_interval_var = tk.StringVar(value=str(self.config.get('honeygain_interval_min', DEFAULT_HONEYGAIN_INTERVAL_MIN)))
        self.earnapp_enabled_var = tk.BooleanVar(value=self.config.get('earnapp_enabled', True))
        self.honeygain_enabled_var = tk.BooleanVar(value=self.config.get('honeygain_enabled', True))

        # Tailles de la fenêtre
        self.size_expanded = "350x320"
        self.size_collapsed = "350x150"

        self._setup_ui()
        self._update_services_from_config()

    def _setup_ui(self):
        self.root.title("Soldes")
        self.root.geometry(self.size_collapsed)
        self.root.attributes('-topmost', True)
        initial_alpha = 0.9
        self.root.attributes('-alpha', initial_alpha)

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(expand=True, fill="both")

        self.balances_label = ttk.Label(main_frame, text="Initialisation...", font=("Segoe UI", 11), justify=tk.LEFT)
        self.balances_label.pack(fill="x")

        self.earnapp_countdown_label = ttk.Label(main_frame, text="", font=("Segoe UI", 9))
        self.earnapp_countdown_label.pack(fill="x")
        self.honeygain_countdown_label = ttk.Label(main_frame, text="", font=("Segoe UI", 9))
        self.honeygain_countdown_label.pack(fill="x")

        self.settings_button = ttk.Button(main_frame, text="Afficher les paramètres", command=self._toggle_settings)
        self.settings_button.pack(fill="x", pady=5)

        self.controls_frame = ttk.LabelFrame(main_frame, text="Paramètres", padding="10")

        # ... (Contrôles existants + nouveaux toggles)
        toggles_frame = ttk.Frame(self.controls_frame)
        toggles_frame.pack(fill="x", pady=(0, 10))
        ttk.Checkbutton(toggles_frame, text="Activer EarnApp", variable=self.earnapp_enabled_var, command=self._on_service_toggle).pack(side="left", expand=True)
        ttk.Checkbutton(toggles_frame, text="Activer Honeygain", variable=self.honeygain_enabled_var, command=self._on_service_toggle).pack(side="left", expand=True)

        ttk.Button(self.controls_frame, text="Modifier les identifiants", command=self._open_config_editor).pack(fill="x", pady=(0,10))

        hg_frame = ttk.Frame(self.controls_frame)
        hg_frame.pack(fill="x", pady=5)
        ttk.Label(hg_frame, text="Intervalle Honeygain (min):").pack(side="left")
        ttk.Entry(hg_frame, width=5, textvariable=self.honeygain_interval_var).pack(side="left", padx=5)
        ttk.Button(hg_frame, text="Appliquer", command=self._apply_honeygain_interval).pack(side="left")

        alpha_frame = ttk.Frame(self.controls_frame)
        alpha_frame.pack(fill="x", pady=5)
        ttk.Label(alpha_frame, text="Transparence:").pack(side="left")
        ttk.Scale(alpha_frame, from_=0.3, to=1.0, value=initial_alpha, orient="horizontal", command=lambda v: self.root.attributes('-alpha', float(v))).pack(side="left", expand=True, fill="x", padx=5)

        self._update_countdown_labels()

    def _update_services_from_config(self):
        """Met à jour l'état des services en fonction de la config."""
        # EarnApp
        if self.earnapp_enabled_var.get() and not self.earnapp_after_id:
            self.earnapp_balance = "En attente..."
            threading.Thread(target=self.update_earnapp_balance, daemon=True).start()
        elif not self.earnapp_enabled_var.get() and self.earnapp_after_id:
            self.root.after_cancel(self.earnapp_after_id)
            self.earnapp_after_id = None
            self.earnapp_balance = "Désactivé"

        # Honeygain
        if self.honeygain_enabled_var.get() and not self.honeygain_after_id:
            self.honeygain_balance = "En attente..."
            self.honeygain_token = None
            threading.Thread(target=self.update_honeygain_balance, daemon=True).start()
        elif not self.honeygain_enabled_var.get() and self.honeygain_after_id:
            self.root.after_cancel(self.honeygain_after_id)
            self.honeygain_after_id = None
            self.honeygain_balance = "Désactivé"

        self._update_ui_visibility()
        self._update_display()

    def _on_service_toggle(self):
        """Gère le clic sur une case à cocher de service."""
        self.config['earnapp_enabled'] = self.earnapp_enabled_var.get()
        self.config['honeygain_enabled'] = self.honeygain_enabled_var.get()
        save_config(self.config)
        self._update_services_from_config()

    def _update_ui_visibility(self):
        """Met à jour la visibilité des labels."""
        if self.earnapp_enabled_var.get(): self.earnapp_countdown_label.pack(fill="x")
        else: self.earnapp_countdown_label.pack_forget()

        if self.honeygain_enabled_var.get(): self.honeygain_countdown_label.pack(fill="x")
        else: self.honeygain_countdown_label.pack_forget()

    def _toggle_settings(self):
        """Affiche/cache les paramètres et redimensionne la fenêtre."""
        if self.settings_visible:
            self.controls_frame.pack_forget()
            self.settings_button.config(text="Afficher les paramètres")
            self.root.geometry(self.size_collapsed)
        else:
            self.controls_frame.pack(expand=True, fill="x")
            self.settings_button.config(text="Cacher les paramètres")
            self.root.geometry(self.size_expanded)
        self.settings_visible = not self.settings_visible

    def _update_display(self):
        lines = []
        if self.earnapp_enabled_var.get(): lines.append(f"💰 EarnApp: {self.earnapp_balance}")
        if self.honeygain_enabled_var.get(): lines.append(f"🐝 Honeygain: {self.honeygain_balance}")

        final_text = "\n".join(lines) if lines else "Aucun service activé."
        self.balances_label.config(text=final_text)

    # ... (le reste des méthodes est soit inchangé, soit gère les nouvelles conditions d'activation)
    def _open_config_editor(self):
        config_window = ConfigWindow(self.root, self.config)
        new_config = config_window.result
        if new_config:
            self.config.update(new_config)
            if save_config(self.config):
                self._restart_updates()
            else:
                messagebox.showerror("Erreur", "Impossible de sauvegarder le fichier de configuration.", parent=self.root)

    def _restart_updates(self):
        if self.earnapp_after_id: self.root.after_cancel(self.earnapp_after_id); self.earnapp_after_id = None
        if self.honeygain_after_id: self.root.after_cancel(self.honeygain_after_id); self.honeygain_after_id = None
        self._update_services_from_config()

    def _update_countdown_labels(self):
        now = datetime.now()
        if self.earnapp_enabled_var.get() and self.earnapp_next_run:
            if self.earnapp_next_run > now: self.earnapp_countdown_label.config(text=f"EarnApp: prochaine màj dans {str(self.earnapp_next_run - now).split('.')[0]}")
            else: self.earnapp_countdown_label.config(text="EarnApp: actualisation en cours...")
        else: self.earnapp_countdown_label.config(text="")

        if self.honeygain_enabled_var.get() and self.honeygain_next_run:
            if self.honeygain_next_run > now: self.honeygain_countdown_label.config(text=f"Honeygain: prochaine màj dans {str(self.honeygain_next_run - now).split('.')[0]}")
            else: self.honeygain_countdown_label.config(text="Honeygain: actualisation en cours...")
        else: self.honeygain_countdown_label.config(text="")

        self.root.after(1000, self._update_countdown_labels)

    def _apply_honeygain_interval(self):
        try:
            new_interval_min = int(self.honeygain_interval_var.get())
            if new_interval_min > 0:
                self.config['honeygain_interval_min'] = new_interval_min
                self.honeygain_interval_ms = new_interval_min * 60 * 1000
                save_config(self.config)
                if self.honeygain_enabled_var.get():
                    if self.honeygain_after_id: self.root.after_cancel(self.honeygain_after_id)
                    threading.Thread(target=self.update_honeygain_balance, daemon=True).start()
        except ValueError: messagebox.showwarning("Invalide", "Veuillez entrer un nombre valide.", parent=self.root)

    def _schedule_honeygain_update(self):
        if not self.honeygain_enabled_var.get(): return
        self.honeygain_next_run = datetime.now() + timedelta(milliseconds=self.honeygain_interval_ms)
        self.honeygain_after_id = self.root.after(self.honeygain_interval_ms, lambda: threading.Thread(target=self.update_honeygain_balance, daemon=True).start())

    def _schedule_earnapp_update(self):
        if not self.earnapp_enabled_var.get(): return
        now = datetime.now()
        next_run = now.replace(minute=5, second=0, microsecond=0)
        if next_run <= now: next_run += timedelta(hours=1)
        self.earnapp_next_run = next_run
        delay_ms = int((self.earnapp_next_run - now).total_seconds() * 1000)
        self.earnapp_after_id = self.root.after(delay_ms, lambda: threading.Thread(target=self.update_earnapp_balance, daemon=True).start())

    def update_earnapp_balance(self):
        if not self.earnapp_enabled_var.get(): return
        try:
            headers = {'Cookie': self.config['earnapp_cookie']}
            response = requests.get('https://earnapp.com/dashboard/api/money?appid=earnapp_dashboard', headers=headers, timeout=15)
            response.raise_for_status()
            self.earnapp_balance = f"${response.json().get('balance', 0):.2f}"
        except Exception as e: self.earnapp_balance = "Erreur"
        self.root.after(0, self._update_display)
        self._schedule_earnapp_update()

    def update_honeygain_balance(self):
        if not self.honeygain_enabled_var.get(): return
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
            else: self.honeygain_balance = "Erreur (HTTP)"
        except Exception: self.honeygain_balance = "Erreur"
        self.root.after(0, self._update_display)
        self._schedule_honeygain_update()

    def _login_honeygain(self):
        try:
            login_data = {'email': self.config['honeygain_email'], 'password': self.config['honeygain_password']}
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
    root.withdraw()
    sv_ttk.set_theme("dark")

    config = load_config()
    if 'earnapp_cookie' not in config: # Si la clé principale manque, on force la config
        config_window = ConfigWindow(root, config)
        new_config = config_window.result
        if new_config:
            config.update(new_config)
            save_config(config)
        else:
            root.destroy()
            config = None

    if config is not None:
        root.deiconify()
        app = BalanceDashboard(root, config)
        root.mainloop()
