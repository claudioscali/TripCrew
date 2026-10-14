# 🧳 TripCrew

**TripCrew** è un'applicazione web sviluppata in Flask per semplificare l'organizzazione di viaggi di gruppo e individuali. Permette di gestire itinerari, pianificare attività, organizzare l'attrezzatura e condividere inviti in modo rapido e sicuro.

---

## ✨ Funzionalità Principali

- **Gestione Viaggi & Itinerari:** Creazione e modifica di viaggi con pianificazione di attività dettagliate.
- **Equipaggiamento Condiviso vs. Personale:** Gestione dell'attrezzatura necessaria distinguendo tra oggetti personali e materiale di gruppo.
- **Inviti via Token & WhatsApp:** Generazione di link di invito sicuri da condividere per aggiungere partecipanti al viaggio.
- **Autenticazione Sicura:** Sistema di registrazione e login per la gestione delle sessioni utente.

---

## 🛠️ Tech Stack

- **Backend:** Python, Flask, Gunicorn
- **Database:** MySQL (Aiven Cloud)
- **Deployment:** Render.com
- **Connettore DB:** `mysql-connector-python`

---

## 📁 Struttura del Progetto

```text
tripcrew/
├── app.py              # Applicazione Flask principale e rotte
├── requirements.txt    # Dipendenze Python
├── tripcrew.sql        # Dump della struttura del database MySQL
├── static/             # File statici (CSS, immagini, JS)
└── templates/          # Template HTML (Jinja2)
```

---

## 🚀 Installazione Locale

### 1. Clonare il Repository
```bash
git clone https://github.com/claudioscali/TripCrew.git
cd TripCrew
```

### 2. Creare e Attivare l'Ambiente Virtuale
```bash
python -m venv venv
# Su Windows:
venv\Scripts\activate
# Su macOS/Linux:
source venv/bin/activate
```

### 3. Installare le Dipendenze
```bash
pip install -r requirements.txt
```

### 4. Configurare le Variabili d'Ambiente
Crea un file `.env` nella cartella principale del progetto:
```env
FLASK_SECRET_KEY=la_tua_chiave_segreta
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=la_tua_password
DB_NAME=tripcrew
```

### 5. Avviare l'Applicazione
```bash
python app.py
```

---

## 🌐 Architettura di Produzione

- **Hosting Web:** Render.com (Web Service guidato da `gunicorn app:app`).
- **Database Cloud:** MySQL gestito su Aiven.io con connessione cifrata SSL.
- **Environment Variables:** Configurate direttamente nel pannello di Render per isolare i segreti dal repository Git.