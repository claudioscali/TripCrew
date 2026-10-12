import os
from dotenv import load_dotenv

load_dotenv()
from flask import (
    Flask, render_template, request, redirect, 
    url_for, flash, session
)
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash

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
            flash("Errrore di connessione al database.", "error")
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
                return redirect(url_for("menu"))
            else:
                flash("Email o password non corretti.", "error")
        except Error as errore_db:
            print(f"Errore MySQL: {errore_db}")
            flash("Si è verificato un errore durante il login.", "errore")
        finally:
            if cursor is not None:
                cursor.close()
            connessione.close()
    return render_template("login.html")

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
            connessione.commit()
            flash("Utente salvato correttamente.", "success")
            return redirect(url_for("home"))
        except mysql.connector.Error as errore_db:
            connessione.rollback()
            flash("Impossibile salvare i dati.", "error")
        finally:
            if cursor is not None:
                cursor.close()
            connessione.close()
    return render_template("registrazione.html")

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

            cursor.execute(
                """
                INSERT INTO attrezzatura(nome, categoria, viaggio_id)
                SELECT nome, categoria, %s
                FROM modelli_attrezzatura 
                WHERE tipo_viaggio_id =%s
                """, (id_viaggio, tipo_viaggio_id)
            )
            
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
        SELECT DISTINCT v.id, v.nome, v.destinazione, v.data_inizio, v.data_fine, v.budget_persona, t.nome AS tipo_viaggio 
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
        #verifica che l'utente possa accedere al viaggio
        cursor.execute("""
        SELECT v.id, v.nome FROM viaggi v
        WHERE v.id = %s
            AND (
            v.creatore_id = %s 
            OR EXISTS (
                SELECT 1 FROM partecipanti p
                WHERE p.viaggio_id = v.id
                    AND p.utente_id = %s    
            )
        )
        """, (id_viaggio, id_utente, id_utente))
        
        viaggio = cursor.fetchone()

        if viaggio is None:
            flash("Viaggio non trovato o non accessibile.", "error")
            return redirect(url_for("menu"))
        
        if request.method == "POST":
            azione = request.form.get("azione")
            #segna un oggetto come preparato o da preparare
            if azione == "toggle":
                item_id = request.form.get("item_id")
                preparato = request.form.get("preparato")

                if item_id and preparato in ("0", "1"):
                    cursor.execute(
                        """
                        UPDATE attrezzatura
                        SET preparato = %s
                        WHERE id = %s AND viaggio_id = %s
                        """,
                        (int(preparato), item_id, id_viaggio)
                    )
                    connessione.commit()
                else:
                    flash("Dati dell'oggetti non validi.", "error")
            elif azione=="aggiungi":
                nome = request.form.get("nome", "").strip()
                categoria = request.form.get("categoria", "").strip()
                descrizione = request.form.get("descrizione", "").strip()

                if not nome:
                    flash("Inserisci il nome dell'oggetto.", "error")
                else:
                    if not categoria:
                        categoria="Altro"
                    cursor.execute(
                        """
                        INSERT INTO attrezzatura (nome, categoria, descrizione, viaggio_id)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (nome, categoria, descrizione or None, id_viaggio)
                    )
                    connessione.commit()
                    flash("Oggetto aggiunto alla checklist.", "success")
            #Elimina un oggetto dalla checklist
            elif azione== "elimina":
                item_id=request.form.get("item_id")

                if item_id and item_id.isdigit():
                    cursor.execute(
                        """
                        DELETE FROM attrezzatura
                        WHERE id = %s AND viaggio_id=%s
                        """,
                        (int(item_id), id_viaggio)
                    )
                    connessione.commit()
                    flash("Oggetto eliminato dalla checklist.", "success")
                else:
                    flash("Oggetto non valido.", "error")
            return redirect(url_for("checklist_attrezzatura", id_viaggio=id_viaggio))
        
        #recupera gli oggetti di questo viaggio
        cursor.execute(
            """
            SELECT id, nome, categoria, descrizione, preparato
            FROM attrezzatura
            WHERE viaggio_id = %s
            ORDER BY categoria, nome
            """,
            (id_viaggio,)
        )

        oggetti = cursor.fetchall()

        totale = len(oggetti)
        preparati = sum(bool(item["preparato"]) for item in oggetti)

        return render_template(
            "attrezzatura.html",
            username=username,
            viaggio=viaggio,
            oggetti=oggetti,
            totale=totale,
            preparati=preparati
        )
    except mysql.connector.Error as errore_db:
        connessione.rollback()
        print(f"Errore MySQL: {errore_db}")
        print(f"Codice errore: {errore_db.errno}")
        print(f"SQLSTATE: {errore_db.sqlstate}")

        flash("Si è verificato un errore nella checklist.", "error")
        return redirect(url_for("menu"))
    finally:
        if cursor is not None:
            cursor.close()
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
        #verifica che l'utente possa accedere al viaggio
        cursor.execute("""
        SELECT v.id, v.nome
        FROM viaggi v
        WHERE v.id = %s
            AND (
                v.creatore_id = %s
                OR EXISTS (
                    SELECT 1
                    FROM partecipanti p
                    WHERE p.viaggio_id = v.id
                        AND p.utente_id = %s
                )
            )
        """, (id_viaggio, id_utente, id_utente))
        
        viaggio = cursor.fetchone()

        if viaggio is None:
            flash("Viaggio non trovato o non accessibile.", "error")
            return redirect(url_for("menu"))
        
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











if __name__=="__main__":
    app.run(debug=True)

