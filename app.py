import os
from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect, 
    url_for, flash, session, jsonify
)
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import requests
from datetime import datetime, timedelta, date
from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client.errors import OAuthError
from werkzeug.middleware.proxy_fix import ProxyFix
from defusedxml import ElementTree as DefusedET
import math
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from flask_caching import Cache
from flask_talisman import Talisman

load_dotenv()

app = Flask(__name__)

csrf = CSRFProtect(app)
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache'})

app.secret_key = os.environ["FLASK_SECRET_KEY"]
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.permanent_session_lifetime = timedelta(days=30)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE") == "1"

# Render sta dietro a un proxy HTTPS: senza questo i link esterni escono con http://
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Legge se sei online in produzione (dove SESSION_COOKIE_SECURE vale "1")
IS_PRODUCTION = os.getenv("SESSION_COOKIE_SECURE") == "1"
Talisman(app, content_security_policy=None, force_https=IS_PRODUCTION)



limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)


def chiave_utente():
    """Limite per utente loggato (altrimenti per IP): amici sullo stesso Wi-Fi non si bloccano a vicenda."""
    return str(session.get("id_utente") or get_remote_address())


CENTESIMO = Decimal("0.01")

oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.environ["GOOGLE_CLIENT_ID"],
    client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@app.route("/")
def home():
    if "id_utente" in session:
        return redirect(url_for("menu"))
    return render_template("home.html")


def tentativo_accesso():
    try:
        connessione = mysql.connector.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            database=os.environ["DB_NAME"]
        )

        print("Connessione riuscita.")
        return connessione

    except Error as errore:
        print(f"Errore MySQL: {errore}")
        return None


@app.route("/login", methods=["POST", "GET"])
@limiter.limit("5 per minute")  # Protezione specifica contro brute-force
def login():
    if request.method=="POST":
        email=request.form.get("email", "").strip()
        password=request.form.get("password", "").strip()
        if not email or not password:
            flash("Inserisci email e password.", "error")
            return render_template("login.html")
        connessione=tentativo_accesso()
        if connessione is None: 
            flash("Errore di connessione al database.", "error")
            return render_template("login.html")
        cursor=None
        try:
            cursor=connessione.cursor()
            query="""
            SELECT id, username, password FROM utenti 
            WHERE email = %s 
            """
            cursor.execute(query,(email,))
            utente=cursor.fetchone()
            if utente and utente[2] and check_password_hash(utente[2], password):
                id_utente=utente[0]
                username=utente[1]
                session.permanent = True
                session["id_utente"]=id_utente
                session["username"]=username
                flash("Accesso effettuato correttamente.", "success")
                
                #Controlla se c'era un invito in sospeso
                if "pending_invitation" in session:
                    token_in_sospeso = session.pop("pending_invitation")
                    return redirect(url_for("unisciti_viaggio", token=token_in_sospeso))
                
                return redirect(url_for("menu"))
            else:
                flash("Email o password non corretti.", "error")
        except Error as errore_db:
            print(f"Errore MySQL: {errore_db}")
            flash("Si è verificato un errore durante il login.", "error")
        finally:
            if cursor is not None:
                cursor.close()
            connessione.close()
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear() # Cancella tutti i dati della sessione (id_utente e username)
    flash("Hai effettuato la disconnessione.", "success")
    return redirect(url_for("home"))

@app.route("/registrazione", methods=["POST","GET"])
@limiter.limit("5 per hour")
def registrazione():
    if request.method=="POST":
        username=request.form.get("username", "").strip()
        email=request.form.get("email", "").strip()
        password=request.form.get("password", "").strip()
        
        if not username or not password or not email:
            flash("Riempi tutti i campi.", "error")
            return render_template("registrazione.html")
        
        if len(password) < 8:
            flash("La password deve avere almeno 8 caratteri.", "error")
            return render_template("registrazione.html",
                                   username_inserito=username,
                                   email_inserita=email)
        
        hashed_password = generate_password_hash(password)
        
        connessione=tentativo_accesso()
        if connessione is None:
            flash("Errore di connessione al database", "error")
            return render_template("registrazione.html")
        cursor=None
        try:
            cursor=connessione.cursor()
            query="""
            INSERT INTO utenti (username, email, password)
            VALUES (%s, %s, %s)
            """
            cursor.execute(query, (username, email, hashed_password))
            
            # Eseguiamo il login automatico del nuovo utente
            id_nuovo_utente = cursor.lastrowid
            session.permanent = True
            session["id_utente"] = id_nuovo_utente
            session["username"] = username
            
            connessione.commit()
            flash("Benvenuto su TripCrew! Registrazione completata.", "success")
            
            # Controlliamo se è arrivato da un link di invito
            if "pending_invitation" in session:
                token_in_sospeso = session.pop("pending_invitation")
                return redirect(url_for("unisciti_viaggio", token=token_in_sospeso))
                
            # Se non ha inviti, va al normale menu
            return redirect(url_for("menu"))
        
        except mysql.connector.Error as errore_db:
            connessione.rollback()
            flash("Impossibile salvare i dati: username o email già in uso.", "error")
            return render_template('registrazione.html', 
                       username_inserito=request.form.get('username'),
                       email_inserita=request.form.get('email'))
        finally:
            if cursor is not None:
                cursor.close()
            connessione.close()
    return render_template("registrazione.html")

def genera_username_libero(cursor, base):
    # tiene solo lettere, numeri e . _ - (max 30 caratteri)
    base = "".join(c for c in base if c.isalnum() or c in "._-")[:30] or "utente"
    candidato = base
    numero = 1
    while True:
        cursor.execute("SELECT 1 FROM utenti WHERE username = %s", (candidato,))
        if cursor.fetchone() is None:
            return candidato
        numero += 1
        candidato = f"{base}{numero}"


@app.route("/login/google")
def login_google():
    redirect_uri = url_for("google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/auth/google/callback")
def google_callback():
    try:
        token = google.authorize_access_token()
    except OAuthError as errore:
        print(f"Errore OAuth Google: {errore}")
        flash("Accesso con Google non riuscito.", "error")
        return redirect(url_for("login"))

    info = token.get("userinfo")
    if not info or not info.get("email") or not info.get("email_verified"):
        flash("Google non ha confermato la tua email.", "error")
        return redirect(url_for("login"))

    google_id = info["sub"]
    email = info["email"]
    nome = info.get("name") or email.split("@")[0]

    connessione = tentativo_accesso()
    if connessione is None:
        flash("Errore di connessione al database.", "error")
        return redirect(url_for("login"))

    cursor = None
    try:
        cursor = connessione.cursor(dictionary=True)

        # 1. profilo Google già collegato a un account
        cursor.execute("SELECT id, username FROM utenti WHERE google_id = %s", (google_id,))
        utente = cursor.fetchone()

        if utente is None:
            # 2. esiste già un account con la stessa email?
            cursor.execute("SELECT id, username FROM utenti WHERE email = %s", (email,))
            utente = cursor.fetchone()

            if utente:
                # collega Google all'account e cancella la vecchia password
                cursor.execute(
                    "UPDATE utenti SET google_id = %s, password = NULL WHERE id = %s",
                    (google_id, utente["id"])
                )
            else:
                # 3. primo accesso: crea un nuovo account
                username = genera_username_libero(cursor, nome)
                cursor.execute(
                    "INSERT INTO utenti (username, email, password, google_id) VALUES (%s, %s, NULL, %s)",
                    (username, email, google_id)
                )
                utente = {"id": cursor.lastrowid, "username": username}

            connessione.commit()

        session.permanent = True
        session["id_utente"] = utente["id"]
        session["username"] = utente["username"]
        flash("Accesso effettuato con Google.", "success")

        # invito in sospeso, come nel login normale
        if "pending_invitation" in session:
            token_in_sospeso = session.pop("pending_invitation")
            return redirect(url_for("unisciti_viaggio", token=token_in_sospeso))

        return redirect(url_for("menu"))
    except mysql.connector.Error as errore_db:
        connessione.rollback()
        print(f"Errore MySQL: {errore_db}")
        flash("Si è verificato un errore durante l'accesso con Google.", "error")
        return redirect(url_for("login"))
    finally:
        if cursor is not None:
            cursor.close()
        connessione.close()

@app.route('/check_username', methods=['POST'])
@limiter.limit("30 per minute")
def check_username():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    if not username:
        return jsonify({"exists": False})
    
    connessione = tentativo_accesso()
    if connessione is None:
        # Se cade la connessione, restituiamo false per non bloccare l'interfaccia inutilmente
        return jsonify({"exists": False}) 
        
    cursor = None
    try:
        cursor = connessione.cursor(dictionary=True)
        # Corretto il nome della tabella in "utenti" come nel resto del tuo codice
        cursor.execute("SELECT username FROM utenti WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        if user:
            return jsonify({"exists": True})
        return jsonify({"exists": False})
        
    except mysql.connector.Error as errore_db:
        print(f"Errore controllo username: {errore_db}")
        return jsonify({"exists": False})
    finally:
        if cursor is not None:
            cursor.close()
        connessione.close()

@app.route("/menu", methods=["GET"])
def menu():
    if "id_utente" not in session:
        return redirect(url_for("login"))
    id_utente=session["id_utente"]
    username=session["username"]
    connessione=tentativo_accesso()
    if connessione is None:
        flash("Errore di connessione al database.", "error")
        return render_template("menu.html", username=username, viaggi=[])

    cursor = None
    try: 
        cursor=connessione.cursor(dictionary=True)
        query="""
        SELECT DISTINCT v.id, v.nome, v.destinazione, v.data_inizio, v.data_fine 
        FROM viaggi v 
        LEFT JOIN partecipanti p ON v.id=p.viaggio_id
        WHERE v.creatore_id=%s OR p.utente_id=%s
        ORDER BY v.data_inizio
        """
        cursor.execute(query, (id_utente, id_utente))
        viaggi = cursor.fetchall()
        return render_template(
            "menu.html",
            username=username,
            viaggi=viaggi
        )
    except Error as errore_db:
        print(f"Errore MySQL: {errore_db}")
        flash("Impossibile recuperare i viaggi.", "error")
        return render_template("menu.html", username=username, viaggi=[])
    finally:
        if cursor is not None:
            cursor.close()
        connessione.close()

@app.route("/create_trip", methods=["POST","GET"])
def create_trip():
    if "id_utente" not in session:
        return redirect(url_for("login"))
    
    if request.method=="POST":
        nome_viaggio=request.form.get("nome_viaggio", "").strip()
        destinazione=request.form.get("destinazione", "").strip()
        data_inizio=request.form.get("data_inizio", "").strip()
        data_fine=request.form.get("data_fine", "").strip()
        budget=request.form.get("budget", "").strip()
        tipo_viaggio=request.form.get("tipo_viaggio", "").strip()

        id_creatore=session["id_utente"]

        if not nome_viaggio or not destinazione or not data_inizio or not data_fine or not budget or not id_creatore or not tipo_viaggio:
            flash("Riempi tutti i campi.", "error")
            return render_template("create_trip.html", username=session["username"])

        if data_fine < data_inizio:
            flash("La data di fine deve essere successiva alla data di inizio.", "error")
            return render_template("create_trip.html", username=session["username"])

        try:
            budget=float(budget)
            if budget < 0:
                flash("Il budget non può essere negativo.", "error")
                return render_template("create_trip.html", username=session["username"])
        except ValueError:
            flash("Inserisci un budget valido.", "error")
            return render_template("create_trip.html", username=session["username"])

        connessione=tentativo_accesso()
        
        if connessione is None:
            flash("Errore di connessione al database", "error")
            return render_template("create_trip.html", username=session["username"])
        cursor=None
        try:
            cursor=connessione.cursor()

            cursor.execute("SELECT id FROM tipologie_viaggio WHERE nome =%s", (tipo_viaggio,))
            risultato=cursor.fetchone()
            if risultato is None: 
                flash ("La tipologia di viaggio non è valida.", "error")
                return render_template("create_trip.html", username=session["username"])
            tipo_viaggio_id = risultato[0]

            query="""
            INSERT INTO viaggi (nome, destinazione, data_inizio, data_fine, budget_persona, creatore_id, tipo_viaggio, tipo_viaggio_id)
            VALUES (%s, %s, %s,%s, %s, %s, %s, %s)
            """
            cursor.execute(query, (nome_viaggio, destinazione, data_inizio, data_fine, budget, id_creatore, tipo_viaggio, tipo_viaggio_id))

            id_viaggio=cursor.lastrowid

            query_partecipante="""
            INSERT INTO partecipanti (viaggio_id, utente_id)
            VALUES (%s, %s)
            """
            cursor.execute(query_partecipante, (id_viaggio, id_creatore))
            
            # 1. Inserisce l'attrezzatura DI GRUPPO (condiviso = 1)
            cursor.execute("""
                INSERT INTO attrezzatura(nome, categoria, viaggio_id, condiviso)
                SELECT nome, categoria, %s, 1
                FROM modelli_attrezzatura 
                WHERE tipo_viaggio_id = %s AND condiviso = 1
            """, (id_viaggio, tipo_viaggio_id))
            
            # 2. Inserisce l'attrezzatura PERSONALE (condiviso = 0) assegnandola subito al creatore
            cursor.execute("""
                INSERT INTO attrezzatura(nome, categoria, viaggio_id, condiviso, utente_id)
                SELECT nome, categoria, %s, 0, %s
                FROM modelli_attrezzatura 
                WHERE tipo_viaggio_id = %s AND condiviso = 0
            """, (id_viaggio, id_creatore, tipo_viaggio_id))
            
            connessione.commit()
            flash("Viaggio aggiunto correttamente.", "success")
            return redirect(url_for("menu"))
        except mysql.connector.Error as errore_db:
            connessione.rollback()
            print(f"Errore MySQL: {errore_db}")
            flash("Impossibile salvare i dati.", "error")
        finally:
            if cursor is not None:
                cursor.close()
            connessione.close()
    return render_template("create_trip.html", username=session["username"])



@app.route("/viaggio/<int:id_viaggio>")
def viaggio(id_viaggio):
    if "id_utente" not in session:
        return redirect(url_for("login"))
    
    id_utente=session["id_utente"]
    username=session["username"]

    connessione=tentativo_accesso()

    if connessione is None:
        flash("Errore di connessione al database.", "error")
        return redirect(url_for("menu"))

    cursor = None
    try: 
        cursor=connessione.cursor(dictionary=True)
        query="""
        SELECT DISTINCT v.id, v.nome, v.destinazione, v.data_inizio, v.data_fine, v.budget_persona, v.creatore_id, t.nome AS tipo_viaggio 
        FROM viaggi v 
        JOIN tipologie_viaggio t ON t.id=v.tipo_viaggio_id
        LEFT JOIN partecipanti p ON v.id=p.viaggio_id
        WHERE v.id= %s 
            AND (v.creatore_id=%s OR p.utente_id=%s)
        """
        cursor.execute(query, (id_viaggio, id_utente, id_utente))
        viaggio = cursor.fetchone()
        if viaggio is None:
            flash("Viaggio non trovato o non accessibile.", "error")
            return redirect(url_for("menu"))
        
        # riepiloghi mostrati nella pagina del viaggio
        cursor.execute("""
            SELECT
              (SELECT COUNT(*) FROM attrezzatura
                WHERE viaggio_id = %s AND (condiviso = 1 OR utente_id = %s)) AS tot_attrezzatura,
              (SELECT COUNT(*) FROM attrezzatura
                WHERE viaggio_id = %s AND preparato = 1 AND (condiviso = 1 OR utente_id = %s)) AS prep_attrezzatura,
              (SELECT COALESCE(SUM(importo), 0) FROM spese WHERE viaggio_id = %s) AS tot_spese,
              (SELECT COUNT(*) FROM (
                    SELECT creatore_id AS u_id FROM viaggi WHERE id = %s
                    UNION
                    SELECT utente_id FROM partecipanti WHERE viaggio_id = %s
              ) AS tutti) AS n_partecipanti
        """, (id_viaggio, id_utente, id_viaggio, id_utente, id_viaggio, id_viaggio, id_viaggio))
        riepilogo = cursor.fetchone()

        oggi = date.today()
        giorni = (viaggio["data_inizio"] - oggi).days
        if giorni > 1:
            stato_viaggio = f"Mancano {giorni} giorni alla partenza"
        elif giorni == 1:
            stato_viaggio = "Si parte domani!"
        elif giorni == 0:
            stato_viaggio = "Si parte oggi!"
        elif oggi <= viaggio["data_fine"]:
            stato_viaggio = "Viaggio in corso"
        else:
            stato_viaggio = "Viaggio concluso"

        cursor.execute("""
            SELECT nome, data, TIME_FORMAT(ora, '%H:%i') AS ora_formattata
            FROM attivita
            WHERE viaggio_id = %s AND data >= %s
            ORDER BY data ASC, ora ASC
            LIMIT 1
        """, (id_viaggio, oggi))
        prossima_tappa = cursor.fetchone()

        return render_template(
            "viaggio.html",
            username=username,
            viaggio=viaggio,
            riepilogo=riepilogo,
            stato_viaggio=stato_viaggio,
            prossima_tappa=prossima_tappa
        )
    except Error as errore_db:
        print(f"Errore MySQL: {errore_db}")
        flash("Impossibile recuperare i viaggi.", "error")
        return render_template("menu.html", username=username, viaggi=[])
    finally:
        if cursor is not None:
            cursor.close()
        connessione.close()


@app.route("/viaggio/<int:id_viaggio>/elimina", methods=["POST"])
def elimina_viaggio(id_viaggio):
    if "id_utente" not in session:
        return redirect(url_for("login"))
    id_utente = session["id_utente"]

    connessione = tentativo_accesso()
    if connessione is None:
        flash("Errore di connessione al database.", "error")
        return redirect(url_for("menu"))

    cursor = None
    try:
        cursor = connessione.cursor()

        # solo il creatore può eliminare il viaggio
        cursor.execute(
            "SELECT id FROM viaggi WHERE id = %s AND creatore_id = %s",
            (id_viaggio, id_utente)
        )
        if cursor.fetchone() is None:
            flash("Viaggio non trovato o non hai il permesso di eliminarlo.", "error")
            return redirect(url_for("menu"))

        # un solo DELETE: attrezzatura, partecipanti, spese e messaggi
        # vengono cancellati da MySQL grazie a ON DELETE CASCADE
        cursor.execute("DELETE FROM viaggi WHERE id = %s", (id_viaggio,))

        connessione.commit()
        flash("Viaggio eliminato.", "success")
        return redirect(url_for("menu"))
    except mysql.connector.Error as errore_db:
        connessione.rollback()
        print(f"Errore MySQL: {errore_db}")
        flash("Impossibile eliminare il viaggio.", "error")
        return redirect(url_for("viaggio", id_viaggio=id_viaggio))
    finally:
        if cursor is not None:
            cursor.close()
        connessione.close()

@app.route("/viaggio/<int:id_viaggio>/modifica", methods=["GET", "POST"])
def modifica_viaggio(id_viaggio):
    if "id_utente" not in session:
        return redirect(url_for("login"))
    
    id_utente = session["id_utente"]
    connessione = tentativo_accesso()
    
    if connessione is None:
        flash("Errore di connessione al database.", "error")
        return redirect(url_for("menu"))

    cursor = None
    try:
        cursor = connessione.cursor(dictionary=True)
        
        cursor.execute(
            """
            SELECT v.id, v.nome, v.destinazione, v.data_inizio, v.data_fine, v.budget_persona, v.creatore_id, v.tipo_viaggio_id, t.nome AS tipo_viaggio 
            FROM viaggi v 
            JOIN tipologie_viaggio t ON t.id = v.tipo_viaggio_id
            WHERE v.id = %s AND v.creatore_id = %s
            """,
            (id_viaggio, id_utente)
        )
        viaggio = cursor.fetchone()
        
        if viaggio is None:
            flash("Viaggio non trovato o non hai i permessi per modificarlo.", "error")
            return redirect(url_for("menu"))

        vecchio_tipo_id = viaggio["tipo_viaggio_id"]

        if request.method == "POST":
            nome_viaggio = request.form.get("nome_viaggio", "").strip()
            destinazione = request.form.get("destinazione", "").strip()
            data_inizio = request.form.get("data_inizio", "").strip()
            data_fine = request.form.get("data_fine", "").strip()
            budget = request.form.get("budget", "").strip()
            tipo_viaggio = request.form.get("tipo_viaggio", "").strip()

            if not nome_viaggio or not destinazione or not data_inizio or not data_fine or not budget or not tipo_viaggio:
                flash("Riempi tutti i campi.", "error")
                return render_template("edit_trip.html", username=session["username"], viaggio=viaggio)

            if data_fine < data_inizio:
                flash("La data di fine deve essere successiva alla data di inizio.", "error")
                return render_template("edit_trip.html", username=session["username"], viaggio=viaggio)

            try:
                budget = float(budget)
                if budget < 0:
                    flash("Il budget non può essere negativo.", "error")
                    return render_template("edit_trip.html", username=session["username"], viaggio=viaggio)
            except ValueError:
                flash("Inserisci un budget valido.", "error")
                return render_template("edit_trip.html", username=session["username"], viaggio=viaggio)

            # Ricava il nuovo tipo_viaggio_id dalla tabella tipologie_viaggio
            cursor.execute("SELECT id FROM tipologie_viaggio WHERE nome = %s", (tipo_viaggio,))
            risultato = cursor.fetchone()
            if risultato is None:
                flash("La tipologia di viaggio non è valida.", "error")
                return render_template("edit_trip.html", username=session["username"], viaggio=viaggio)
            
            tipo_viaggio_id = risultato["id"]

            query = """
            UPDATE viaggi 
            SET nome = %s, destinazione = %s, data_inizio = %s, data_fine = %s, 
                budget_persona = %s, tipo_viaggio = %s, tipo_viaggio_id = %s
            WHERE id = %s AND creatore_id = %s
            """
            cursor.execute(query, (nome_viaggio, destinazione, data_inizio, data_fine, budget, tipo_viaggio, tipo_viaggio_id, id_viaggio, id_utente))

            if vecchio_tipo_id != tipo_viaggio_id:
                # Sostituisce solo gli oggetti del vecchio modello: quelli aggiunti a mano
                # e quelli presenti anche nel nuovo modello restano (con assegnazioni e spunte)
                cursor.execute("""
                    DELETE a FROM attrezzatura a
                    JOIN modelli_attrezzatura mv
                      ON mv.tipo_viaggio_id = %s AND mv.nome = a.nome
                     AND mv.categoria = a.categoria AND mv.condiviso = a.condiviso
                    WHERE a.viaggio_id = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM modelli_attrezzatura mn
                          WHERE mn.tipo_viaggio_id = %s AND mn.nome = a.nome AND mn.condiviso = a.condiviso
                      )
                """, (vecchio_tipo_id, id_viaggio, tipo_viaggio_id))

                # Aggiunge gli oggetti DI GRUPPO del nuovo modello che mancano
                cursor.execute("""
                    INSERT INTO attrezzatura (nome, categoria, viaggio_id, condiviso)
                    SELECT m.nome, m.categoria, %s, 1
                    FROM modelli_attrezzatura m
                    WHERE m.tipo_viaggio_id = %s AND m.condiviso = 1
                      AND NOT EXISTS (
                          SELECT 1 FROM attrezzatura a
                          WHERE a.viaggio_id = %s AND a.condiviso = 1 AND a.nome = m.nome
                      )
                """, (id_viaggio, tipo_viaggio_id, id_viaggio))

                # Utenti attuali del viaggio (creatore + partecipanti)
                cursor.execute("""
                    SELECT creatore_id AS u_id FROM viaggi WHERE id = %s
                    UNION
                    SELECT utente_id AS u_id FROM partecipanti WHERE viaggio_id = %s
                """, (id_viaggio, id_viaggio))
                utenti_attuali = cursor.fetchall()

                # A ciascuno aggiunge gli oggetti PERSONALI del nuovo modello che gli mancano
                for u in utenti_attuali:
                    cursor.execute("""
                        INSERT INTO attrezzatura (nome, categoria, viaggio_id, condiviso, utente_id)
                        SELECT m.nome, m.categoria, %s, 0, %s
                        FROM modelli_attrezzatura m
                        WHERE m.tipo_viaggio_id = %s AND m.condiviso = 0
                          AND NOT EXISTS (
                              SELECT 1 FROM attrezzatura a
                              WHERE a.viaggio_id = %s AND a.condiviso = 0 AND a.utente_id = %s AND a.nome = m.nome
                          )
                    """, (id_viaggio, u['u_id'], tipo_viaggio_id, id_viaggio, u['u_id']))

            connessione.commit()
            
            flash("Viaggio modificato correttamente.", "success")
            return redirect(url_for("viaggio", id_viaggio=id_viaggio))

        return render_template("edit_trip.html", username=session["username"], viaggio=viaggio)

    except mysql.connector.Error as errore_db:
        connessione.rollback()
        print(f"Errore MySQL: {errore_db}")
        flash("Impossibile aggiornare i dati del viaggio.", "error")
        return redirect(url_for("viaggio", id_viaggio=id_viaggio))
    finally:
        if cursor is not None:
            cursor.close()
        connessione.close()


@app.route("/viaggio/<int:id_viaggio>/attrezzatura", methods=["GET","POST"])
def checklist_attrezzatura(id_viaggio):
    if "id_utente" not in session:
        return redirect (url_for("login"))
    id_utente = session["id_utente"]
    username = session["username"]

    connessione=tentativo_accesso()
    if connessione is None:
        flash("Errore di connessione al database.", "error")
        return redirect(url_for("menu"))
    cursor = None
    try:
        cursor = connessione.cursor(dictionary=True)
        # Verifica accesso al viaggio
        cursor.execute("""
        SELECT v.id, v.nome FROM viaggi v
        WHERE v.id = %s AND (v.creatore_id = %s OR EXISTS (
                SELECT 1 FROM partecipanti p WHERE p.viaggio_id = v.id AND p.utente_id = %s
            ))
        """, (id_viaggio, id_utente, id_utente))
        viaggio = cursor.fetchone()

        if viaggio is None:
            flash("Viaggio non trovato o non accessibile.", "error")
            return redirect(url_for("menu"))
        
        if request.method == "POST":
            azione = request.form.get("azione")
            item_id = request.form.get("item_id")
            
            # 1. Segna come preparato/da preparare
            if azione == "toggle":
                preparato = request.form.get("preparato")
                if item_id and preparato in ("0", "1"):
                    cursor.execute("""
                    UPDATE attrezzatura SET preparato = %s 
                    WHERE id = %s AND viaggio_id = %s AND utente_id = %s
                    """, 
                    (int(preparato), item_id, id_viaggio, id_utente))
                    connessione.commit()
            
            # 2. Assegna a se stessi ("Lo porto io"), solo se l'oggetto di gruppo è ancora libero
            elif azione == "assegna":
                if item_id:
                    cursor.execute(
                    """
                    UPDATE attrezzatura SET utente_id = %s
                    WHERE id = %s AND viaggio_id = %s
                        AND condiviso = 1 AND utente_id IS NULL
                    """,
                    (id_utente, item_id, id_viaggio)
                )
                preso = cursor.rowcount == 1
                connessione.commit()
                if preso:
                    flash("Hai preso in carico questo oggetto!", "success")
                else:
                    flash("Qualcun altro ha già preso in carico questo oggetto.", "error")

            # 3. Rimuovi assegnazione ("Non posso portarlo"), solo se l'oggetto di gruppo lo porti tu
            elif azione == "rimuovi_assegnazione":
                if item_id:
                    cursor.execute(
                        """
                        UPDATE attrezzatura SET utente_id = NULL, preparato = 0
                        WHERE id = %s AND viaggio_id = %s
                          AND condiviso = 1 AND utente_id = %s
                        """,
                        (item_id, id_viaggio, id_utente)
                    )
                    connessione.commit()

            # 4. Elimina oggetto (di gruppo, oppure personale solo se è tuo)
            elif azione == "elimina":
                if item_id:
                    cursor.execute(
                        """
                        DELETE FROM attrezzatura
                        WHERE id = %s AND viaggio_id = %s
                          AND (condiviso = 1 OR utente_id = %s)
                        """,
                        (item_id, id_viaggio, id_utente)
                    )
                    connessione.commit()
                    flash("Oggetto eliminato.", "success")
                    
            # 5. Aggiungi nuovo oggetto
            elif azione == "aggiungi":
                nome = request.form.get("nome", "").strip()
                categoria = request.form.get("categoria", "Altro").strip()
                descrizione = request.form.get("descrizione", "").strip()
                tipo_oggetto = request.form.get("tipo_oggetto", "condiviso")

                if nome:
                    if tipo_oggetto == "condiviso":
                        # Oggetto di gruppo: ne creiamo UNO solo
                        cursor.execute("""
                            INSERT INTO attrezzatura (nome, categoria, descrizione, viaggio_id, condiviso)
                            VALUES (%s, %s, %s, %s, 1)
                        """, (nome, categoria, descrizione or None, id_viaggio))
                    else:
                        # Oggetto personale: Ne creiamo UNO PER OGNI PARTECIPANTE + IL CREATORE
                        cursor.execute("""
                            SELECT creatore_id AS u_id FROM viaggi WHERE id = %s
                            UNION SELECT utente_id AS u_id FROM partecipanti WHERE viaggio_id = %s
                        """, (id_viaggio, id_viaggio))
                        utenti_viaggio = cursor.fetchall()
                        
                        for u in utenti_viaggio:
                            cursor.execute("""
                                INSERT INTO attrezzatura (nome, categoria, descrizione, viaggio_id, condiviso, utente_id)
                                VALUES (%s, %s, %s, %s, 0, %s)
                            """, (nome, categoria, descrizione or None, id_viaggio, u['u_id']))
                    
                    connessione.commit()
                    flash("Oggetto aggiunto alla checklist.", "success")
            return redirect(url_for("checklist_attrezzatura", id_viaggio=id_viaggio))
        
        # --- RECUPERO DATI PER IL TEMPLATE ---
        # A. Oggetti di GRUPPO
        cursor.execute("""
            SELECT a.id, a.nome, a.categoria, a.descrizione, a.preparato, a.utente_id, u.username AS assegnato_a
            FROM attrezzatura a
            LEFT JOIN utenti u ON a.utente_id = u.id
            WHERE a.viaggio_id = %s AND a.condiviso = 1
            ORDER BY a.categoria, a.nome
        """, (id_viaggio,))
        oggetti_gruppo = cursor.fetchall()

        # B. Oggetti PERSONALI (Solo quelli dell'utente loggato)
        cursor.execute("""
            SELECT id, nome, categoria, descrizione, preparato
            FROM attrezzatura
            WHERE viaggio_id = %s AND condiviso = 0 AND utente_id = %s
            ORDER BY categoria, nome
        """, (id_viaggio, id_utente))
        oggetti_personali = cursor.fetchall()

        totale = len(oggetti_gruppo) + len(oggetti_personali)
        preparati = sum(1 for item in oggetti_gruppo if item["preparato"]) + sum(1 for item in oggetti_personali if item["preparato"])

        return render_template(
            "attrezzatura.html",
            username=username,
            viaggio=viaggio,
            oggetti_gruppo=oggetti_gruppo,
            oggetti_personali=oggetti_personali,
            totale=totale,
            preparati=preparati,
            id_utente=id_utente
        )
    except mysql.connector.Error as errore_db:
        print(f"Errore MySQL: {errore_db}")
        flash("Si è verificato un errore nella checklist.", "error")
        return redirect(url_for("menu"))
    finally:
        if cursor is not None: cursor.close()
        connessione.close()



def crea_attrezzatura_personale(cursor, id_viaggio, utente_id):
    """Dà al nuovo partecipante gli oggetti personali già presenti nel viaggio (modello + aggiunti a mano)."""
    cursor.execute(
        """
        INSERT INTO attrezzatura (nome, categoria, descrizione, viaggio_id, condiviso, utente_id)
        SELECT DISTINCT nome, categoria, descrizione, viaggio_id, 0, %s
        FROM attrezzatura
        WHERE viaggio_id = %s AND condiviso = 0
        """,
        (utente_id, id_viaggio)
    )


@app.route("/viaggio/<int:id_viaggio>/lista_partecipanti", methods=["GET","POST"])
def lista_partecipanti(id_viaggio):
    if "id_utente" not in session:
        return redirect (url_for("login"))
    id_utente = session["id_utente"]
    username = session["username"]

    connessione=tentativo_accesso()
    if connessione is None:
        flash("Errore di connessione al database.", "error")
        return redirect(url_for("menu"))
    cursor = None
    try:
        cursor = connessione.cursor(dictionary=True)
        # Verifica che l'utente possa accedere al viaggio e recupera il token
        cursor.execute("""
        SELECT v.id, v.nome, v.token_invito, v.creatore_id
        FROM viaggi v
        WHERE v.id = %s AND (
                v.creatore_id = %s OR EXISTS (
                    SELECT 1 FROM partecipanti p WHERE p.viaggio_id = v.id AND p.utente_id = %s
                )
            )
        """, (id_viaggio, id_utente, id_utente))
        
        viaggio = cursor.fetchone()

        if viaggio is None:
            flash("Viaggio non trovato o non accessibile.", "error")
            return redirect(url_for("menu"))
        
        # GENERAZIONE PIGRA DEL LINK: Se il viaggio non ha ancora un token, creiamolo ora!
        if not viaggio.get("token_invito"):
            nuovo_token = secrets.token_urlsafe(16) # Genera una stringa casuale sicura
            cursor.execute("UPDATE viaggi SET token_invito = %s WHERE id = %s", (nuovo_token, id_viaggio))
            connessione.commit()
            viaggio["token_invito"] = nuovo_token
        
        if request.method == "POST":
            azione = request.form.get("azione")
            if azione=="aggiungi":
                username_nuovo = request.form.get("username", "").strip()

                if not username_nuovo:
                    flash("Inserisci l'username del nuovo partecipante.", "error")
                else:
                    cursor.execute(
                    """
                    SELECT id FROM utenti
                    WHERE username = %s
                    """,
                    (username_nuovo,)
                    )
                    utente=cursor.fetchone()
                    if utente is None:
                        flash("Nessun utente trovato con questo username", "error")
                        return redirect(url_for("lista_partecipanti", id_viaggio=id_viaggio))
                    else:
                        utente_id=utente["id"]
                    cursor.execute(
                        """
                        SELECT 1 FROM partecipanti
                        WHERE utente_id=%s AND viaggio_id=%s
                        """,
                        (utente_id, id_viaggio)
                    )
                    partecipante_esistente=cursor.fetchone()
                    if partecipante_esistente:
                        flash("Questo utente partecipa già al viaggio.", "error")
                    else:
                        cursor.execute(
                            """
                            INSERT INTO partecipanti (utente_id, viaggio_id)
                            VALUES (%s, %s)
                            """,
                            (utente_id, id_viaggio)
                        )

                        # Dopo aver aggiunto il partecipante, copiamogli gli oggetti personali!
                        crea_attrezzatura_personale(cursor, id_viaggio, utente_id)
                        
                        connessione.commit()
                        flash("Partecipante aggiunto al viaggio.", "success")
            #Elimina un partecipante dalla 
            elif azione == "elimina":
                utente_da_eliminare = request.form.get("utente_id", "")

                if not utente_da_eliminare.isdigit():
                    flash("Utente non valido.", "error")
                elif int(utente_da_eliminare) == viaggio["creatore_id"]:
                    flash("Il creatore non può essere rimosso dal viaggio.", "error")
                elif id_utente != viaggio["creatore_id"] and id_utente != int(utente_da_eliminare):
                    flash("Non hai i permessi per rimuovere questo partecipante.", "error")
                else:
                    utente_id_rimosso = int(utente_da_eliminare)
                    cursor.execute(
                        """
                        DELETE FROM partecipanti
                        WHERE utente_id = %s AND viaggio_id = %s
                        """,
                        (utente_id_rimosso, id_viaggio)
                    )
                    # pulizia: i suoi oggetti personali spariscono, quelli di gruppo che portava tornano liberi
                    cursor.execute(
                        "DELETE FROM attrezzatura WHERE viaggio_id = %s AND condiviso = 0 AND utente_id = %s",
                        (id_viaggio, utente_id_rimosso)
                    )
                    cursor.execute(
                        """
                        UPDATE attrezzatura SET utente_id = NULL, preparato = 0
                        WHERE viaggio_id = %s AND condiviso = 1 AND utente_id = %s
                        """,
                        (id_viaggio, utente_id_rimosso)
                    )
                    connessione.commit()
                    flash("Partecipante rimosso dal viaggio.", "success")
            return redirect(url_for("lista_partecipanti", id_viaggio=id_viaggio))
        
        #recupera i partecipanti di questo viaggio
        cursor.execute(
            """
            SELECT u.id AS utente_id, u.username
            FROM partecipanti p JOIN utenti u ON u.id=p.utente_id 
            WHERE viaggio_id = %s
            ORDER BY username
            """,
            (id_viaggio,)
        )

        partecipanti = cursor.fetchall()

        totale = len(partecipanti)

        return render_template(
            "lista_partecipanti.html",
            username=username,
            viaggio=viaggio,
            partecipanti=partecipanti,
            totale=totale
        )
    except mysql.connector.Error as errore_db:
        connessione.rollback()
        print(f"Errore MySQL: {errore_db}")
        flash("Si è verificato un errore nella lista.", "error")
        return redirect(url_for("menu"))
    finally:
        if cursor is not None:
            cursor.close()
        connessione.close()


@app.route("/viaggio/<int:id_viaggio>/spese", methods=["GET", "POST"])
def gestione_spese(id_viaggio):
    if "id_utente" not in session:
        return redirect(url_for("login"))
    id_utente = session["id_utente"]
    username = session["username"]
    connessione = tentativo_accesso()
    
    if connessione is None:
        flash("Errore di connessione al database.", "error")
        return redirect(url_for("menu"))

    cursor = None
    try:
        cursor = connessione.cursor(dictionary=True)
        cursor.execute("""
            SELECT v.id, v.nome FROM viaggi v
            WHERE v.id = %s AND (
                v.creatore_id = %s OR EXISTS (
                    SELECT 1 FROM partecipanti p WHERE p.viaggio_id = v.id AND p.utente_id = %s
                )
            )
        """, (id_viaggio, id_utente, id_utente))
        viaggio = cursor.fetchone()

        if not viaggio:
            flash("Viaggio non trovato o non accessibile.", "error")
            return redirect(url_for("menu"))

        if request.method =="POST":
            azione = request.form.get("azione")
            if azione == "aggiungi":
                descrizione = request.form.get("descrizione", "").strip()
                importo = request.form.get("importo", "").strip()
                categoria = request.form.get("categoria", "altro")
                data = request.form.get("data", "").strip()
                pagato_da = request.form.get("pagato_da")

                if descrizione and importo and data and pagato_da:
                    try:
                        importo_dec = Decimal(importo)
                        if not importo_dec.is_finite() or importo_dec <= 0 or importo_dec >= Decimal("100000000"):
                            raise InvalidOperation
                        importo_dec = importo_dec.quantize(CENTESIMO, rounding=ROUND_HALF_UP)
                    except InvalidOperation:
                        flash("Inserisci un importo valido.", "error")
                    else:
                        cursor.execute(
                            """
                            INSERT INTO spese (viaggio_id, utente_id, descrizione, importo, categoria, data)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (id_viaggio, pagato_da, descrizione, importo_dec, categoria, data))
                        connessione.commit()
                        flash("Spesa registrata con successo!", "success")
                else:
                    flash("Compila tutti i campi obbligatori.", "error")
            elif azione =="elimina":
                spesa_id = request.form.get("spesa_id")
                if spesa_id:
                    cursor.execute(
                        """
                        DELETE FROM spese 
                        WHERE id = %s AND viaggio_id = %s AND utente_id = %s
                        """, 
                        (spesa_id, id_viaggio, id_utente)
                        )
                    eliminato=cursor.rowcount 
                    connessione.commit()
                    if not eliminato:
                        flash("Non puoi eliminare una spesa che non hai fatto.", "error")
                    else:
                        flash("Spesa eliminata.", "success")
            
            return redirect(url_for("gestione_spese", id_viaggio=id_viaggio))

        cursor.execute(
            """
            SELECT u.id, u.username 
            FROM utenti u 
            WHERE u.id = (SELECT creatore_id FROM viaggi WHERE id = %s)
            UNION
            SELECT u.id, u.username 
            FROM utenti u 
            JOIN partecipanti p ON u.id = p.utente_id 
            WHERE p.viaggio_id = %s
            """,
            (id_viaggio, id_viaggio)
        )
        partecipanti = cursor. fetchall()
        totale_partecipanti = len(partecipanti)

        cursor.execute(
            """
            SELECT s.id, s.utente_id, s.descrizione, s.importo, s.categoria, s.data, u.username AS pagatore
            FROM spese s
            JOIN utenti u ON s.utente_id = u.id
            WHERE s.viaggio_id = %s
            ORDER BY s.data DESC
            """,
            (id_viaggio,)
        )
        spese=cursor.fetchall()
        totale_spese = sum((Decimal(str(s["importo"])) for s in spese), Decimal("0.00"))
        quota_capite = totale_spese / totale_partecipanti if totale_partecipanti > 0 else Decimal("0.00")

        # Inizializzo il dizionario dei bilanci per ogni partecipante
        bilanci = {p["username"]: {"pagato": Decimal("0.00"), "bilancio": -quota_capite} for p in partecipanti}

        for spesa in spese:
            pagatore = spesa["pagatore"]
            importo = Decimal(str(spesa["importo"]))
            # chi ha pagato ma non è più nel viaggio resta nei conti, così il totale torna a zero
            if pagatore not in bilanci:
                bilanci[pagatore] = {"pagato": Decimal("0.00"), "bilancio": Decimal("0.00")}
            bilanci[pagatore]["pagato"] += importo
            bilanci[pagatore]["bilancio"] += importo

        # arrotonda al centesimo solo alla fine, per la visualizzazione
        quota_capite = quota_capite.quantize(CENTESIMO, rounding=ROUND_HALF_UP)
        for dati in bilanci.values():
            dati["pagato"] = dati["pagato"].quantize(CENTESIMO, rounding=ROUND_HALF_UP)
            dati["bilancio"] = dati["bilancio"].quantize(CENTESIMO, rounding=ROUND_HALF_UP)

        return render_template(
            "spese.html", 
            viaggio=viaggio, 
            partecipanti=partecipanti, 
            spese=spese,
            totale_spese=totale_spese,
            quota_capite=quota_capite,
            bilanci=bilanci
        )

    except mysql.connector.Error as errore_db:
        print(f"Errore MySQL: {errore_db}")
        flash("Si è verificato un errore nel calcolo delle spese.", "error")
        return redirect(url_for("menu"))
    finally:
        if cursor: cursor.close()
        connessione.close()
                    
@app.route("/viaggio/<int:id_viaggio>/chat", methods=["GET", "POST"])
@limiter.limit("60 per minute", key_func=chiave_utente)  # la chat si aggiorna ogni 3 secondi: serve un limite suo
def chat_viaggio(id_viaggio):
    if "id_utente" not in session:
        return redirect(url_for("login"))
    
    id_utente = session["id_utente"]
    username = session["username"]
    connessione = tentativo_accesso()
    
    if connessione is None:
        flash("Errore di connessione al database.", "error")
        return redirect(url_for("menu"))

    cursor = None
    try:
        cursor = connessione.cursor(dictionary=True)
        
        # 1. Verifica accesso al viaggio
        cursor.execute("""
            SELECT v.id, v.nome FROM viaggi v
            WHERE v.id = %s AND (
                v.creatore_id = %s OR EXISTS (
                    SELECT 1 FROM partecipanti p WHERE p.viaggio_id = v.id AND p.utente_id = %s
                )
            )
        """, (id_viaggio, id_utente, id_utente))
        viaggio = cursor.fetchone()

        if not viaggio:
            flash("Viaggio non trovato o non accessibile.", "error")
            return redirect(url_for("menu"))

        # 2. Gestione POST (Aggiungi/Elimina messaggio)
        if request.method == "POST":
            azione = request.form.get("azione")
            
            if azione == "invia":
                testo = request.form.get("testo", "").strip()
                if testo:
                    cursor.execute("""
                        INSERT INTO messaggi_chat (viaggio_id, utente_id, testo)
                        VALUES (%s, %s, %s)
                    """, (id_viaggio, id_utente, testo))
                    connessione.commit()
                else:
                    flash("Il messaggio non può essere vuoto.", "error")
                    
            elif azione == "elimina":
                messaggio_id = request.form.get("messaggio_id")
                
                # Cerca il messaggio per verificare che esista
                cursor.execute("SELECT utente_id FROM messaggi_chat WHERE id = %s", (messaggio_id,))
                messaggio = cursor.fetchone()
                
                if messaggio:
                    # Controllo di sicurezza: l'utente loggato è l'autore del messaggio?
                    if messaggio["utente_id"] == id_utente:
                        cursor.execute("DELETE FROM messaggi_chat WHERE id = %s", (messaggio_id,))
                        connessione.commit()
                        flash("Messaggio eliminato.", "success")
                    else:
                        flash("Non puoi eliminare i messaggi degli altri utenti.", "error")

            return redirect(url_for("chat_viaggio", id_viaggio=id_viaggio))

        # 3. Recupera i messaggi
        cursor.execute("""
            SELECT m.id, m.testo, DATE_FORMAT(m.data_ora, '%d/%m/%Y %H:%i') as data_formattata, 
                   m.utente_id, u.username
            FROM messaggi_chat m
            JOIN utenti u ON m.utente_id = u.id
            WHERE m.viaggio_id = %s
            ORDER BY m.data_ora ASC
        """, (id_viaggio,))
        messaggi = cursor.fetchall()

        return render_template(
            "chat.html", 
            viaggio=viaggio, 
            messaggi=messaggi,
            utente_corrente_id=id_utente
        )

    except mysql.connector.Error as errore_db:
        print(f"Errore MySQL: {errore_db}")
        flash("Si è verificato un errore nel caricamento della chat.", "error")
        return redirect(url_for("menu"))
    finally:
        if cursor: cursor.close()
        connessione.close()

# ---------- Lettura e analisi dei file GPX ----------

def leggi_gpx(contenuto):
    """Legge un file GPX (bytes) e restituisce (punti, quote)."""
    try:
        radice = DefusedET.fromstring(contenuto)
    except Exception:
        raise ValueError("Il file non è un GPX valido.")

    punti = []
    quote = []
    # prima cerca i punti di una traccia (trkpt), poi quelli di un percorso (rtept)
    for tag_punto in ("trkpt", "rtept"):
        for el in radice.iter():
            if not isinstance(el.tag, str) or el.tag.split("}")[-1] != tag_punto:
                continue
            try:
                lat = float(el.get("lat"))
                lon = float(el.get("lon"))
            except (TypeError, ValueError):
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            punti.append([lat, lon])
            for figlio in el:
                if isinstance(figlio.tag, str) and figlio.tag.split("}")[-1] == "ele":
                    try:
                        quota = float(figlio.text)
                    except (TypeError, ValueError):
                        continue
                    if math.isfinite(quota):
                        quote.append(quota)
        if punti:
            break

    if len(punti) < 2:
        raise ValueError("Nel file non ci sono abbastanza punti per disegnare una traccia.")
    return punti, quote


def distanza_km(punti):
    """Distanza totale in km (formula di Haversine)."""
    totale = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(punti, punti[1:]):
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = p2 - p1
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        totale += 6371.0 * 2 * math.asin(math.sqrt(a))
    return totale


def dislivello_positivo(quote):
    """Salita totale in metri, ignorando le oscillazioni minori di 3 m."""
    if len(quote) < 2:
        return 0
    riferimento = quote[0]
    salita = 0.0
    for q in quote[1:]:
        if q - riferimento >= 3:
            salita += q - riferimento
            riferimento = q
        elif riferimento - q >= 3:
            riferimento = q
    return round(salita)


def semplifica(punti, massimo=3000):
    """Tiene al massimo ~3000 punti e arrotonda le coordinate a 5 decimali."""
    if len(punti) > massimo:
        passo = len(punti) / massimo
        punti = [punti[int(i * passo)] for i in range(massimo)] + [punti[-1]]
    return [[round(lat, 5), round(lon, 5)] for lat, lon in punti]



@app.route("/viaggio/<int:id_viaggio>/itinerario", methods=["GET", "POST"])
def itinerario_viaggio(id_viaggio):
    if "id_utente" not in session:
        return redirect(url_for("login"))
    
    id_utente = session["id_utente"]
    username = session["username"]
    connessione = tentativo_accesso()
    
    if connessione is None:
        flash("Errore di connessione al database.", "error")
        return redirect(url_for("menu"))

    cursor = None
    try:
        cursor = connessione.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT v.id, v.nome, v.destinazione, v.data_inizio, v.data_fine 
            FROM viaggi v
            WHERE v.id = %s AND (
                v.creatore_id = %s OR EXISTS (
                    SELECT 1 FROM partecipanti p WHERE p.viaggio_id = v.id AND p.utente_id = %s
                )
            )
        """, (id_viaggio, id_utente, id_utente))
        viaggio = cursor.fetchone()

        if not viaggio:
            flash("Viaggio non trovato o non accessibile.", "error")
            return redirect(url_for("menu"))

        if request.method == "POST":
            azione = request.form.get("azione")
            
            if azione == "aggiungi":
                nome = request.form.get("nome", "").strip()
                descrizione = request.form.get("descrizione", "").strip()
                data = request.form.get("data", "").strip()
                ora = request.form.get("ora", "").strip()
                luogo = request.form.get("luogo", "").strip()
                costo = request.form.get("costo", "0.00").strip()
                
                if not nome or not data:
                    flash("I campi Nome e Data sono obbligatori.", "error")
                else:
                    # Se i campi non sono riempiti impostiamo NULL (None in Python) o zero per il costo
                    ora = ora if ora else None
                    luogo = luogo if luogo else None
                    try:
                        costo = Decimal(costo) if costo else Decimal("0.00")
                        if not costo.is_finite() or costo < 0 or costo >= Decimal("100000000"):
                            raise InvalidOperation
                    except InvalidOperation:
                        flash("Inserisci un costo valido.", "error")
                    else:
                        cursor.execute("""
                            INSERT INTO attivita (viaggio_id, nome, descrizione, data, ora, luogo, COSTO)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (id_viaggio, nome, descrizione, data, ora, luogo, costo))
                        connessione.commit()
                        flash("Attività aggiunta all'itinerario.", "success")
                    
            elif azione == "elimina":
                attivita_id = request.form.get("attivita_id")
                if attivita_id:
                    cursor.execute("DELETE FROM attivita WHERE id = %s AND viaggio_id = %s", (attivita_id, id_viaggio))
                    connessione.commit()
                    flash("Attività eliminata.", "success")

            return redirect(url_for("itinerario_viaggio", id_viaggio=id_viaggio))

        # 3. Recupera e raggruppa le attività
        cursor.execute("""
            SELECT id, nome, descrizione, data, TIME_FORMAT(ora, '%H:%i') as ora_formattata, luogo, COSTO,
                   (gpx_punti IS NOT NULL) AS ha_gpx, gpx_km, gpx_dislivello
            FROM attivita
            WHERE viaggio_id = %s
            ORDER BY data ASC, ora ASC
        """, (id_viaggio,))
        attivita_db = cursor.fetchall()
        
        # Raggruppiamo le attività per data tramite un dizionario
        itinerario = {}
        for att in attivita_db:
            data_str = att['data'].strftime('%d/%m/%Y')
            if data_str not in itinerario:
                itinerario[data_str] = []
            itinerario[data_str].append(att)

        return render_template(
            "itinerario.html", 
            viaggio=viaggio, 
            itinerario=itinerario
        )

    except mysql.connector.Error as errore_db:
        print(f"Errore MySQL: {errore_db}")
        flash("Si è verificato un errore nel caricamento dell'itinerario.", "error")
        return redirect(url_for("menu"))
    finally:
        if cursor: cursor.close()
        connessione.close()

@app.errorhandler(413)
def file_troppo_grande(errore):
    flash("Il file è troppo grande (massimo 5 MB).", "error")
    id_viaggio = (request.view_args or {}).get("id_viaggio")
    if id_viaggio:
        return redirect(url_for("itinerario_viaggio", id_viaggio=id_viaggio))
    return redirect(url_for("menu"))


@app.route("/viaggio/<int:id_viaggio>/attivita/<int:id_attivita>/traccia", methods=["GET", "POST"])
def traccia_attivita(id_viaggio, id_attivita):
    if "id_utente" not in session:
        return redirect(url_for("login"))

    id_utente = session["id_utente"]
    connessione = tentativo_accesso()

    if connessione is None:
        flash("Errore di connessione al database.", "error")
        return redirect(url_for("menu"))

    cursor = None
    try:
        cursor = connessione.cursor(dictionary=True)

        # 1. Il viaggio deve esistere e l'utente deve farne parte
        cursor.execute("""
            SELECT v.id, v.nome
            FROM viaggi v
            WHERE v.id = %s AND (
                v.creatore_id = %s OR EXISTS (
                    SELECT 1 FROM partecipanti p WHERE p.viaggio_id = v.id AND p.utente_id = %s
                )
            )
        """, (id_viaggio, id_utente, id_utente))
        viaggio = cursor.fetchone()

        if not viaggio:
            flash("Viaggio non trovato o non accessibile.", "error")
            return redirect(url_for("menu"))

        # 2. L'attività deve appartenere a questo viaggio
        cursor.execute("""
            SELECT id, nome, data, gpx_nome, gpx_punti, gpx_km, gpx_dislivello
            FROM attivita
            WHERE id = %s AND viaggio_id = %s
        """, (id_attivita, id_viaggio))
        attivita = cursor.fetchone()

        if not attivita:
            flash("Attività non trovata.", "error")
            return redirect(url_for("itinerario_viaggio", id_viaggio=id_viaggio))

        if request.method == "POST":
            azione = request.form.get("azione")

            if azione == "carica":
                file = request.files.get("gpx")

                if not file or not file.filename:
                    flash("Seleziona un file GPX.", "error")
                elif not file.filename.lower().endswith(".gpx"):
                    flash("Il file deve avere estensione .gpx.", "error")
                else:
                    try:
                        punti, quote = leggi_gpx(file.read())
                    except ValueError as errore:
                        flash(str(errore), "error")
                    else:
                        km = round(distanza_km(punti), 2)
                        dislivello = dislivello_positivo(quote)
                        punti_json = json.dumps(semplifica(punti), separators=(",", ":"))
                        nome_file = os.path.basename(file.filename)[:150]

                        cursor.execute("""
                            UPDATE attivita
                            SET gpx_nome = %s, gpx_punti = %s, gpx_km = %s, gpx_dislivello = %s
                            WHERE id = %s AND viaggio_id = %s
                        """, (nome_file, punti_json, km, dislivello, id_attivita, id_viaggio))
                        connessione.commit()
                        flash("Traccia caricata.", "success")

            elif azione == "elimina":
                cursor.execute("""
                    UPDATE attivita
                    SET gpx_nome = NULL, gpx_punti = NULL, gpx_km = NULL, gpx_dislivello = NULL
                    WHERE id = %s AND viaggio_id = %s
                """, (id_attivita, id_viaggio))
                connessione.commit()
                flash("Traccia eliminata.", "success")

            return redirect(url_for("traccia_attivita", id_viaggio=id_viaggio, id_attivita=id_attivita))

        # GET: i punti sono salvati come testo JSON, li riconvertiamo in lista
        punti = json.loads(attivita["gpx_punti"]) if attivita["gpx_punti"] else None

        return render_template(
            "traccia.html",
            viaggio=viaggio,
            attivita=attivita,
            punti=punti
        )

    except mysql.connector.Error as errore_db:
        print(f"Errore MySQL: {errore_db}")
        flash("Si è verificato un errore con la traccia GPX.", "error")
        return redirect(url_for("itinerario_viaggio", id_viaggio=id_viaggio))
    finally:
        if cursor: cursor.close()
        connessione.close()

@app.route("/join/<token>")
def unisciti_viaggio(token):
    # Se l'utente non è loggato, salviamo il token in sessione e lo mandiamo al login
    if "id_utente" not in session:
        session["pending_invitation"] = token
        flash("Accedi o registrati per unirti al viaggio tramite l'invito.", "info")
        return redirect(url_for("home"))

    id_utente = session["id_utente"]
    connessione = tentativo_accesso()
    if connessione is None:
        return redirect(url_for("menu"))

    cursor = None
    try:
        cursor = connessione.cursor(dictionary=True)
        
        # 1. Trova il viaggio associato a questo token
        cursor.execute("SELECT id, nome, creatore_id, tipo_viaggio_id FROM viaggi WHERE token_invito = %s", (token,))
        viaggio = cursor.fetchone()

        if not viaggio:
            flash("Il link di invito non è valido o è scaduto.", "error")
            return redirect(url_for("menu"))

        id_viaggio = viaggio["id"]

        # 2. Controlla se è già il creatore
        if viaggio["creatore_id"] == id_utente:
            return redirect(url_for("viaggio", id_viaggio=id_viaggio))

        # 3. Controlla se è già un partecipante
        cursor.execute("SELECT 1 FROM partecipanti WHERE viaggio_id = %s AND utente_id = %s", (id_viaggio, id_utente))
        if cursor.fetchone():
            flash("Fai già parte di questo viaggio!", "info")
            return redirect(url_for("viaggio", id_viaggio=id_viaggio))

        # 4. Aggiungi l'utente ai partecipanti
        cursor.execute("INSERT INTO partecipanti (viaggio_id, utente_id) VALUES (%s, %s)", (id_viaggio, id_utente))

        # 5. Genera la sua attrezzatura PERSONALE (modello + oggetti aggiunti dal gruppo)
        crea_attrezzatura_personale(cursor, id_viaggio, id_utente)

        connessione.commit()
        flash(f"Fantastico! Ti sei unito al viaggio '{viaggio['nome']}'.", "success")
        return redirect(url_for("viaggio", id_viaggio=id_viaggio))

    except mysql.connector.Error as errore_db:
        connessione.rollback()
        print(f"Errore MySQL: {errore_db}")
        flash("Si è verificato un errore durante l'iscrizione al viaggio.", "error")
        return redirect(url_for("menu"))
    finally:
        if cursor: cursor.close()
        connessione.close()


# Cache manuale: risultati validi 30 minuti, "località non trovata" 10 minuti,
# gli errori temporanei non vengono memorizzati.
def fetch_meteo_api(destinazione):
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return {"error": "API Key non configurata", "cod": 500}

    destinazione = destinazione.strip()[:100]
    chiave_cache = f"meteo:{destinazione.lower()}"
    in_cache = cache.get(chiave_cache)
    if in_cache is not None:
        return in_cache

    # con params, requests codifica la destinazione e non si possono iniettare altri parametri
    params = {"q": destinazione, "units": "metric", "lang": "it", "appid": api_key}
    try:
        res_now = requests.get("https://api.openweathermap.org/data/2.5/weather", params=params, timeout=5)
        if res_now.status_code == 404:
            risultato = {
                "error": f"Meteo non disponibile per «{destinazione}». Prova con il nome di una città vicina.",
                "cod": 404,
            }
            cache.set(chiave_cache, risultato, timeout=600)
            return risultato
        res_forecast = requests.get("https://api.openweathermap.org/data/2.5/forecast", params=params, timeout=5)
        if res_now.status_code != 200 or res_forecast.status_code != 200:
            return {"error": "Impossibile recuperare i dati meteo", "cod": 500}
        risultato = {"cod": 200, "corrente": res_now.json(), "previsioni": res_forecast.json()}
    except (requests.RequestException, ValueError):
        return {"error": "Impossibile recuperare i dati meteo", "cod": 500}

    cache.set(chiave_cache, risultato, timeout=1800)
    return risultato

@app.route("/api/meteo/<destinazione>")
@limiter.limit("15 per minute")
def get_meteo(destinazione):
    # Il controllo dei permessi avviene SEMPRE
    if "id_utente" not in session:
        return jsonify({"error": "Non autorizzato"}), 401

    # La chiamata API avviene solo se la cache è scaduta
    dati = fetch_meteo_api(destinazione)

    if dati.get("cod") != 200:
        return jsonify(dati), dati.get("cod", 500)

    return jsonify(dati), 200

@app.route('/healthz')
@limiter.exempt
def health_check():
    connessione = tentativo_accesso()
    if connessione:
        cursor = connessione.cursor()
        cursor.execute("SELECT 1;")
        cursor.close()
        connessione.close()
        return "OK", 200
    return "DB Error", 500

if __name__=="__main__":
    app.run(debug=True)

