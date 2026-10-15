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

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]

@app.route("/")
def home():
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
            if utente and check_password_hash(utente[2], password):
                id_utente=utente[0]
                username=utente[1]
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
def registrazione():
    if request.method=="POST":
        username=request.form.get("username", "").strip()
        email=request.form.get("email", "").strip()
        password=request.form.get("password", "").strip()
        
        if not username or not password or not email:
            flash("Riempi tutti i campi.", "error")
            return render_template("registrazione.html")
        
        hashed_password = generate_password_hash(password)
        
        connessione=tentativo_accesso()
        if connessione is None:
            flash("Errore di connessione al database")
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


@app.route('/check_username', methods=['POST'])
def check_username():
    data = request.get_json()
    username = data.get('username')
    
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
            flash("Errore di connessione al database")
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
        
        return render_template(
            "viaggio.html",
            username=username,
            viaggio=viaggio
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
                # Rimuove la vecchia attrezzatura associata al viaggio
                cursor.execute("DELETE FROM attrezzatura WHERE viaggio_id = %s", (id_viaggio,))
                
                # 3A. Inserisce la nuova attrezzatura DI GRUPPO
                cursor.execute("""
                    INSERT INTO attrezzatura (nome, categoria, viaggio_id, condiviso)
                    SELECT nome, categoria, %s, 1
                    FROM modelli_attrezzatura 
                    WHERE tipo_viaggio_id = %s AND condiviso = 1
                """, (id_viaggio, tipo_viaggio_id))

                # 3B. Recupera tutti gli utenti attualmente iscritti al viaggio (creatore + partecipanti)
                cursor.execute("""
                    SELECT creatore_id AS u_id FROM viaggi WHERE id = %s
                    UNION 
                    SELECT utente_id AS u_id FROM partecipanti WHERE viaggio_id = %s
                """, (id_viaggio, id_viaggio))
                utenti_attuali = cursor.fetchall()

                # 3C. Crea l'attrezzatura PERSONALE per OGNUNO di loro
                for u in utenti_attuali:
                    cursor.execute("""
                        INSERT INTO attrezzatura (nome, categoria, viaggio_id, condiviso, utente_id)
                        SELECT nome, categoria, %s, 0, %s
                        FROM modelli_attrezzatura 
                        WHERE tipo_viaggio_id = %s AND condiviso = 0
                    """, (id_viaggio, u['u_id'], tipo_viaggio_id))

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
                    cursor.execute("UPDATE attrezzatura SET preparato = %s WHERE id = %s AND viaggio_id = %s", (int(preparato), item_id, id_viaggio))
                    connessione.commit()
            
            # 2. Assegna a se stessi ("Lo porto io")
            elif azione == "assegna":
                if item_id:
                    cursor.execute("UPDATE attrezzatura SET utente_id = %s WHERE id = %s AND viaggio_id = %s", (id_utente, item_id, id_viaggio))
                    connessione.commit()
                    flash("Hai preso in carico questo oggetto!", "success")
            
            # 3. Rimuovi assegnazione ("Non posso portarlo")
            elif azione == "rimuovi_assegnazione":
                if item_id:
                    cursor.execute("UPDATE attrezzatura SET utente_id = NULL, preparato = 0 WHERE id = %s AND viaggio_id = %s", (item_id, id_viaggio))
                    connessione.commit()
            
            # 4. Elimina oggetto
            elif azione == "elimina":
                if item_id:
                    cursor.execute("DELETE FROM attrezzatura WHERE id = %s AND viaggio_id = %s", (item_id, id_viaggio))
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
        SELECT v.id, v.nome, v.token_invito
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
                        cursor.execute("SELECT DISTINCT nome, categoria, descrizione FROM attrezzatura WHERE viaggio_id = %s AND condiviso = 0", (id_viaggio,))
                        oggetti_personali_esistenti = cursor.fetchall()
                        for o in oggetti_personali_esistenti:
                            cursor.execute("""
                                INSERT INTO attrezzatura (nome, categoria, descrizione, viaggio_id, condiviso, utente_id)
                                VALUES (%s, %s, %s, %s, 0, %s)
                            """, (o['nome'], o['categoria'], o['descrizione'], id_viaggio, utente_id))
                        
                        connessione.commit()
                        flash("Partecipante aggiunto al viaggio.", "success")
            #Elimina un partecipante dalla 
            elif azione== "elimina":
                utente_da_eliminare=request.form.get("utente_id", "")

                if utente_da_eliminare.isdigit():
                    cursor.execute(
                        """
                        DELETE FROM partecipanti
                        WHERE utente_id = %s AND viaggio_id=%s
                        """,
                        (int(utente_da_eliminare), id_viaggio)
                    )
                    connessione.commit()

                    flash("Partecipante eliminato dalla lista.", "success")
                else:
                    flash("Utente non valido.", "error")
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
                    cursor.execute(
                        """
                        INSERT INTO spese (viaggio_id, utente_id, descrizione, importo, categoria, data)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (id_viaggio, pagato_da, descrizione, importo, categoria, data))
                    connessione.commit()
                    flash("Spesa registrata con successo!", "success")
                else:
                    flash("Compila tutti i campi obbligatori.", "error")
            elif azione =="elimina":
                spesa_id = request.form.get("spesa_id")
                if spesa_id:
                    cursor.execute(
                        """
                        DELETE FROM spese WHERE id = %s AND viaggio_id = %s
                        """, 
                        (spesa_id, id_viaggio)
                        )
                    connessione.commit()
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
            SELECT s.id, s.descrizione, s.importo, s.categoria, s.data, u.username AS pagatore
            FROM spese s
            JOIN utenti u ON s.utente_id = u.id
            WHERE s.viaggio_id = %s
            ORDER BY s.data DESC
            """,
            (id_viaggio,)
        )
        spese=cursor.fetchall()
        totale_spese = sum(float(s["importo"]) for s in spese)
        quota_capite = totale_spese / totale_partecipanti if totale_partecipanti > 0 else 0
        
        # Inizializzo il dizionario dei bilanci per ogni partecipante
        bilanci = {p["username"]: {"pagato": 0.0, "bilancio": -quota_capite} for p in partecipanti}

        for spesa in spese:
            pagatore = spesa["pagatore"]
            importo = float(spesa["importo"])
            if pagatore in bilanci:
                bilanci[pagatore]["pagato"] += importo
                bilanci[pagatore]["bilancio"] += importo

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
            SELECT v.id, v.nome, v.data_inizio, v.data_fine 
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
                    costo = float(costo) if costo else 0.00
                    
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
            SELECT id, nome, descrizione, data, TIME_FORMAT(ora, '%H:%i') as ora_formattata, luogo, COSTO
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

        # 5. Genera la sua attrezzatura PERSONALE basata sulla tipologia del viaggio
        cursor.execute("""
            INSERT INTO attrezzatura (nome, categoria, viaggio_id, condiviso, utente_id)
            SELECT nome, categoria, %s, 0, %s
            FROM modelli_attrezzatura 
            WHERE tipo_viaggio_id = %s AND condiviso = 0
        """, (id_viaggio, id_utente, viaggio["tipo_viaggio_id"]))

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

@app.route('/healthz')
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

