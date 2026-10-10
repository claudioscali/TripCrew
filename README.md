# TripCrew — Organizzatore di viaggi outdoor di gruppo

Progetto finale del corso di Python (Flask, MySQL, HTML, CSS, Jinja).

TripCrew è una web application pensata per organizzare piccoli viaggi outdoor di gruppo, come campeggi, trekking e viaggi economici, concentrando in un unico posto **partecipanti, attrezzatura, spese, budget, attività e pasti**.

Il progetto nasce come applicazione per il corso di Python, ma è progettato con una struttura che permetta di continuare lo sviluppo anche dopo la conclusione del corso.

---

## 1. Il problema

Quando 3-5 persone organizzano un campeggio, un trekking o un viaggio economico, le informazioni finiscono solitamente distribuite tra:

* WhatsApp
* Google Maps
* note personali
* applicazioni per dividere le spese
* fogli Excel
* checklist

Il problema non è semplicemente creare una lista delle cose da portare.

È necessario coordinare contemporaneamente:

* chi partecipa;
* cosa serve;
* chi porta cosa;
* quanti oggetti servono;
* cosa manca;
* quanto è già stato speso;
* chi ha pagato;
* quanto deve contribuire ogni partecipante;
* quali attività sono previste;
* quanto rimane del budget;
* cosa bisogna acquistare.

TripCrew vuole quindi fornire un unico strumento per gestire la **logistica e l'organizzazione economica di un piccolo viaggio outdoor di gruppo**.

---

## 2. Posizionamento e nicchia

Esistono già applicazioni dedicate al camping planning, alle checklist condivise e alla divisione delle spese.

Per questo TripCrew non viene concepito come una semplice packing list o come un semplice sistema per dividere le spese.

La nicchia del progetto è:

> **logistica condivisa + gestione dell'attrezzatura + budget + spese + organizzazione delle attività per piccoli viaggi outdoor di gruppo.**

L'obiettivo è fare in modo che i dati inseriti dall'utente producano informazioni utili e non vengano semplicemente archiviati.

Esempi:

* l'app segnala se manca attrezzatura essenziale;
* segnala eventuali doppioni;
* avvisa quando il budget si sta avvicinando al limite;
* calcola quanto deve ricevere o pagare ogni partecipante;
* genera automaticamente la lista della spesa;
* permette di utilizzare un viaggio precedente come modello.

---

# 3. Utenti

## Organizzatore

È un partecipante che crea il viaggio.

Può:

* creare e modificare il viaggio;
* aggiungere o rimuovere partecipanti;
* aggiungere elementi alla checklist;
* assegnare l'attrezzatura ai partecipanti;
* gestire il budget;
* inserire attività;
* organizzare i pasti;
* visualizzare dashboard e riepiloghi.

## Partecipante

Può:

* vedere i viaggi a cui partecipa;
* vedere le attività;
* prendere in carico parte dell'attrezzatura;
* segnare l'attrezzatura come pronta;
* registrare le proprie spese;
* visualizzare il proprio saldo;
* consultare menu e lista della spesa.

Un utente può essere organizzatore di alcuni viaggi e semplice partecipante di altri.

---

# 4. Esempio di viaggio

## Dolomiti — Agosto 2027

* 4 partecipanti
* 5 giorni
* Budget massimo: €250 a persona

### Attrezzatura

| Oggetto       | Quantità necessaria | Responsabile | Stato                  |
| ------------- | ------------------: | ------------ | ---------------------- |
| Tenda 3 posti |                   1 | Claudio      | Pronta                 |
| Fornello      |                   1 | Luca         | Assegnato              |
| Pentola       |                   1 | Marco        | Pronta                 |
| Powerbank     |                   2 | Chiara       | Parzialmente assegnato |
| Torcia        |                   2 | —            | ❌ Mancante             |

### Spese

| Voce       | Importo |
| ---------- | ------: |
| Campeggio  |     €80 |
| Benzina    |     €60 |
| Parcheggio |     €20 |
| Spesa      |     €48 |

Totale: **€208**

---

# 5. Database

Il database è composto inizialmente dalle seguenti tabelle:

```text
UTENTI
VIAGGI
PARTECIPANTI
ATTREZZATURA
ATTREZZATURA_VIAGGIO
ASSEGNAZIONI
SPESE
SPESE_PARTECIPANTI
ATTIVITA
BUDGET_CATEGORIA
PASTI
INGREDIENTI_PASTO
```

## UTENTI

Contiene gli utenti registrati a TripCrew.

```text
id
nome
cognome
email
password_hash
data_registrazione
```

`email` è univoca.

La password viene memorizzata come hash e non in chiaro.

---

## VIAGGI

Rappresenta il viaggio.

```text
id
nome
destinazione
data_inizio
data_fine
budget_persona
creatore_id
viaggio_origine_id
```

`creatore_id` identifica l'utente che ha creato il viaggio.

`viaggio_origine_id` viene valorizzato quando il viaggio è stato creato duplicando un viaggio precedente.

---

## PARTECIPANTI

È la tabella ponte tra utenti e viaggi.

```text
id
viaggio_id
utente_id
data_iscrizione
ruolo
```

La coppia `viaggio_id + utente_id` deve essere univoca.

Un utente può partecipare a più viaggi e un viaggio può avere più partecipanti.

---

## ATTREZZATURA

È il **catalogo degli elementi disponibili in TripCrew**.

Non rappresenta ciò che viene portato in un singolo viaggio.

```text
id
nome
categoria
descrizione
```

Esempio:

```text
1 | Tenda 2 posti        | campeggio
2 | Tenda 3 posti        | campeggio
3 | Fornello             | cucina
4 | Pentola              | cucina
5 | Powerbank            | elettronica
6 | Kit pronto soccorso  | sicurezza
```

Lo stesso elemento del catalogo può essere utilizzato in più viaggi senza duplicarlo.

---

## ATTREZZATURA_VIAGGIO

Collega il catalogo dell'attrezzatura a uno specifico viaggio.

```text
id
viaggio_id
attrezzatura_id
quantita_necessaria
essenziale
```

Esempio:

```text
viaggio_id | attrezzatura_id | quantita_necessaria | essenziale
----------------------------------------------------------------
1          | 1               | 1                  | 1
1          | 3               | 1                  | 1
1          | 5               | 2                  | 0
```

Questa tabella risponde alla domanda:

> "Cosa serve per questo viaggio e in quale quantità?"

---

## ASSEGNAZIONI

Indica chi si prende in carico una determinata quantità dell'attrezzatura necessaria.

```text
id
attrezzatura_viaggio_id
utente_id
quantita
stato
```

`stato` può assumere inizialmente valori come:

```text
assegnato
pronto
```

Esempio:

```text
attrezzatura_viaggio_id | utente_id | quantita | stato
------------------------------------------------------
1                       | 2         | 1        | pronto
3                       | 5         | 1        | assegnato
```

Questa separazione permette a più persone di portare quantità diverse dello stesso elemento.

Esempio:

> Servono 4 bottiglie d'acqua → Claudio ne porta 2, Marco ne porta 2.

Non viene quindi duplicato l'elemento nel catalogo.

---

## SPESE

Registra le spese realmente sostenute.

```text
id
viaggio_id
utente_id
descrizione
importo
categoria
data
```

`utente_id` rappresenta la persona che ha effettuato il pagamento.

Le categorie utilizzate inizialmente sono:

```text
campeggio
trasporto
cibo
attività
altro
```

---

## SPESE_PARTECIPANTI

Indica come una singola spesa deve essere suddivisa tra i partecipanti.

```text
spesa_id
utente_id
quota
```

Esempio:

Una spesa di €80 per il campeggio viene divisa tra quattro partecipanti:

```text
spesa_id | utente_id | quota
---------------------------
15       | 2         | 20
15       | 5         | 20
15       | 8         | 20
15       | 11        | 20
```

Questo permette di gestire anche divisioni non perfettamente uguali.

---

## ATTIVITA

Rappresenta le attività previste durante il viaggio.

```text
id
viaggio_id
nome
descrizione
data
ora
luogo
costo
```

`costo` rappresenta il costo previsto dell'attività.

Se l'attività viene effettivamente pagata, la spesa reale viene registrata nella tabella `spese`.

---

## BUDGET_CATEGORIA

Permette di stabilire un budget previsto per ciascuna categoria di spesa.

```text
id
viaggio_id
categoria
importo_previsto
```

Esempio:

```text
categoria    | importo previsto
--------------------------------
campeggio    | €100
trasporto    | €80
cibo         | €70
attività     | €50
altro        | €30
```

---

## PASTI

Rappresenta i pasti pianificati durante il viaggio.

```text
id
viaggio_id
giorno
tipo
descrizione
```

`tipo` può essere:

```text
colazione
pranzo
cena
altro
```

---

## INGREDIENTI_PASTO

Contiene gli ingredienti necessari per ogni pasto.

```text
id
pasto_id
nome
unita
quantita_per_persona
costo_stimato
incaricato_id
acquistato
spesa_id
```

`quantita_per_persona` permette di calcolare automaticamente la quantità complessiva necessaria in base al numero di partecipanti.

`incaricato_id` indica chi deve acquistare l'ingrediente.

`acquistato` indica se l'ingrediente è già stato acquistato.

`spesa_id` collega l'acquisto alla relativa spesa quando questa viene registrata.

---

# 6. Relazioni

Schema concettuale semplificato:

```text
                         UTENTI
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
           VIAGGI    PARTECIPANTI     SPESE
              │            │            │
              │            │            ▼
              │            │    SPESE_PARTECIPANTI
              │            │
              │            │
      ┌───────┼────────────┐
      │       │            │
      ▼       ▼            ▼
 ATTREZZ.  ATTIVITA   BUDGET_CATEGORIA
      │
      ▼
ATTREZZATURA_VIAGGIO
      │
      ▼
 ASSEGNAZIONI
      │
      ▼
    UTENTI


VIAGGI
   │
   ▼
  PASTI
   │
   ▼
INGREDIENTI_PASTO
   │
   ├──────────────► UTENTI
   │
   └──────────────► SPESE
```

## Relazione molti-a-molti tra UTENTI e VIAGGI

```text
UTENTI
   N
   │
   │
PARTECIPANTI
   │
   │
   N
VIAGGI
```

La tabella `partecipanti` funziona da **junction table**.

Anche `attrezzatura_viaggio` rappresenta una relazione tra viaggi e attrezzatura:

```text
ATTREZZATURA
     N
     │
     │
ATTREZZATURA_VIAGGIO
     │
     │
     N
VIAGGI
```

Le `assegnazioni` permettono poi di collegare l'attrezzatura necessaria alle persone che se ne prendono carico.

---

# 7. Funzioni principali

## Account

* registrazione
* login
* logout
* gestione del profilo

## Viaggi

* creare un viaggio
* modificare un viaggio
* eliminare un viaggio
* visualizzare i propri viaggi
* visualizzare il dettaglio di un viaggio
* aggiungere partecipanti
* rimuovere partecipanti
* distinguere organizzatore e partecipanti
* duplicare un viaggio precedente

## Attrezzatura

* visualizzare il catalogo
* aggiungere elementi al catalogo
* modificare elementi del catalogo
* aggiungere attrezzatura a un viaggio
* indicare la quantità necessaria
* indicare se un elemento è essenziale
* assegnare quantità ai partecipanti
* segnare l'attrezzatura come pronta
* visualizzare cosa manca
* individuare eventuali doppioni

## Spese

* registrare una spesa
* modificare una spesa
* eliminare una spesa
* scegliere la categoria
* indicare chi ha effettuato il pagamento
* definire come dividere la spesa
* visualizzare il totale
* visualizzare quanto ha pagato ogni partecipante
* calcolare il saldo di ogni partecipante
* calcolare i pagamenti necessari per pareggiare i conti

## Budget

* impostare un budget complessivo per persona
* impostare budget per categoria
* confrontare previsto ed effettivo
* visualizzare percentuale di budget utilizzata
* generare avvisi automatici

## Attività

* aggiungere attività
* modificare attività
* eliminare attività
* indicare data, ora e luogo
* indicare il costo previsto

## Pasti

* creare pasti per giorno
* scegliere il tipo di pasto
* aggiungere ingredienti
* indicare quantità per persona
* assegnare l'acquisto a un partecipante
* segnare ingredienti come acquistati
* generare automaticamente la lista della spesa

---

# 8. Dashboard del viaggio

La dashboard rappresenta il punto centrale dell'applicazione.

Esempio:

```text
╔══════════════════════════════════════════╗
║             DOLOMITI 2027                ║
║        10 agosto → 15 agosto              ║
╚══════════════════════════════════════════╝

PARTECIPANTI
4 persone

────────────────────────────────────────────

BUDGET

€192 / €250 per persona

██████████████░░░░ 77%

⚠ Budget quasi raggiunto

────────────────────────────────────────────

ATTREZZATURA

18 / 21 elementi pronti

Manca:

❌ 2 × Torcia
❌ 1 × Kit pronto soccorso

────────────────────────────────────────────

SPESE

Campeggio       €80
Trasporto       €60
Cibo            €48

Totale          €188

────────────────────────────────────────────

PROSSIME ATTIVITÀ

10 agosto — Trekking
11 agosto — Lago di Braies

────────────────────────────────────────────

PASTI

Prossimo pasto:
Cena — 10 agosto

Lista della spesa:
✓ Pasta
✓ Pomodori
❌ Pane
❌ Formaggio
```

La dashboard non deve essere soltanto una pagina informativa: deve utilizzare i dati presenti nel database per produrre **indicatori e avvisi**.

---

# 9. Calcoli principali

## 9.1 Attrezzatura mancante

Per ogni elemento:

```text
quantità mancante =
quantità necessaria -
somma delle quantità assegnate
```

Se:

```text
quantità mancante > 0
```

l'app segnala che manca dell'attrezzatura.

Se:

```text
quantità mancante < 0
```

l'app segnala un doppione.

Esempio:

```text
Necessarie: 4
Assegnate:  3

→ manca 1
```

oppure:

```text
Necessarie: 4
Assegnate:  5

→ 1 elemento in più del necessario
```

L'avviso:

> ✅ Tutta l'attrezzatura essenziale è assegnata

compare quando nessun elemento essenziale presenta quantità mancante.

---

# 10. Saldo dei partecipanti

Per ogni partecipante:

```text
saldo =
totale pagato -
totale delle proprie quote
```

Se il saldo è positivo:

> il partecipante deve ricevere denaro.

Se il saldo è negativo:

> il partecipante deve pagare denaro.

Esempio:

```text
Claudio   +€35
Marco     +€15
Luca      -€30
Chiara    -€20
```

L'app può quindi proporre i trasferimenti necessari per pareggiare i conti:

```text
Luca → Claudio   €30
Chiara → Claudio €5
Chiara → Marco   €15
```

L'obiettivo è ridurre il numero di pagamenti necessari.

---

# 11. Costo per persona

Il costo effettivamente sostenuto da un partecipante viene calcolato dalla somma delle sue quote nelle spese.

Con una divisione equa:

```text
costo per persona =
totale spese / numero partecipanti
```

Con divisioni personalizzate:

```text
costo per persona =
somma delle quote individuali
```

---

# 12. Gestione del budget

L'app confronta:

```text
spesa effettiva
```

con:

```text
budget previsto
```

sia complessivamente sia per categoria.

Viene generato un avviso quando il budget utilizzato raggiunge il 90%.

Esempio:

```text
Budget trasporto: €80

Spesa attuale: €74

92,5%

⚠ Budget trasporto quasi superato
```

---

# 13. Lista della spesa

Gli ingredienti dei pasti vengono trasformati automaticamente in una lista della spesa.

Per ogni ingrediente:

```text
quantità totale =
quantità per persona × numero partecipanti
```

Gli ingredienti uguali vengono aggregati.

Esempio:

```text
Pasta
100 g/persona × 4 persone
= 400 g

Pomodori
150 g/persona × 4 persone
= 600 g
```

Gli ingredienti vengono raggruppati per:

```text
nome + unità
```

utilizzando una logica equivalente a:

```sql
GROUP BY nome, unita
```

Ogni ingrediente può avere un incaricato.

Quando viene segnato come acquistato:

1. viene registrato il prezzo reale;
2. viene creata o collegata una spesa;
3. la spesa entra automaticamente nel budget del viaggio.

---

# 14. Viaggio da modello

Un viaggio può essere duplicato per creare rapidamente un nuovo viaggio.

Vengono copiati:

* checklist dell'attrezzatura;
* quantità necessarie;
* categorie;
* elementi essenziali;
* pasti;
* ingredienti;
* budget per categoria.

Non vengono copiati:

* assegnazioni;
* spese;
* acquisti effettuati.

Il nuovo viaggio conserva il riferimento:

```text
viaggio_origine_id
```

in modo da sapere da quale viaggio è stato creato.

Esempio:

```text
Dolomiti 2026
      │
      │ duplica
      ▼
Dolomiti 2027
```

Questo permette di utilizzare TripCrew anche per viaggi ricorrenti.

---

# 15. Funzioni extra scelte per il progetto

Le seguenti funzionalità sono state selezionate perché aggiungono valore concreto all'applicazione senza renderne impossibile la realizzazione durante il corso.

### 1. Menu, lista della spesa e spese

Si pianificano i pasti per giorno e per tipo:

* colazione;
* pranzo;
* cena;
* altro.

Ogni pasto contiene ingredienti con quantità per persona.

TripCrew:

1. moltiplica le quantità per il numero di partecipanti;
2. raggruppa gli ingredienti uguali;
3. genera la lista della spesa;
4. assegna ogni acquisto a un partecipante;
5. registra il prezzo reale;
6. collega automaticamente l'acquisto alle spese.

### 2. Quantità necessaria e doppioni

Per ogni elemento della checklist si indica la quantità necessaria.

Più persone possono prendersene in carico una parte.

L'app mostra:

* quantità necessaria;
* quantità assegnata;
* quantità mancante;
* eventuale quantità in eccesso.

### 3. Viaggio da modello

Un viaggio può essere duplicato.

Vengono copiati:

* checklist;
* quantità;
* categorie;
* elementi essenziali;
* pasti;
* ingredienti;
* budget previsto.

Non vengono copiate:

* assegnazioni;
* spese;
* acquisti.

### 4. Spese previste e spese effettive

L'organizzatore può impostare un budget previsto per categoria:

* campeggio;
* trasporto;
* cibo;
* attività;
* altro.

La dashboard confronta:

```text
previsto vs effettivo
```

per ogni categoria e genera un avviso quando viene superato il 90%.

---

# 16. Idee rimandate — sviluppi futuri

Queste funzionalità non fanno parte della prima versione del progetto del corso, ma potranno essere aggiunte successivamente.

## Quote in base ai giorni di presenza

Un partecipante potrebbe arrivare più tardi o partire prima.

In futuro `partecipanti` potrebbe quindi contenere:

```text
giorno_arrivo
giorno_partenza
```

per calcolare quote proporzionate ai giorni effettivi di presenza.

---

## Auto e passaggi

In futuro TripCrew potrebbe gestire:

* automobili;
* conducenti;
* posti disponibili;
* passeggeri;
* benzina;
* pedaggi;
* parcheggi.

Potrebbero essere introdotte tabelle come:

```text
AUTO
PASSEGGERI_AUTO
```

---

## Distribuzione del peso

Ogni elemento dell'attrezzatura potrebbe avere:

```text
peso_kg
```

TripCrew potrebbe calcolare il peso trasportato da ogni partecipante e segnalare squilibri eccessivi.

---

## Quota d'uso per chi presta attrezzatura

Il gruppo potrebbe decidere una piccola quota per chi mette a disposizione attrezzatura personale costosa, come una tenda o un fornello.

La quota potrebbe entrare nel calcolo dei saldi.

---

# 17. Struttura del progetto Flask

La struttura prevista è:

```text
tripcrew/

├── app.py
├── config.py
├── db.py
├── schema.sql
├── requirements.txt
│
├── blueprints/
│   ├── auth.py
│   ├── viaggi.py
│   ├── attrezzatura.py
│   ├── spese.py
│   ├── pasti.py
│   └── budget.py
│
├── services/
│   ├── saldi.py
│   └── avvisi.py
│
├── templates/
│   ├── base.html
│   │
│   ├── auth/
│   ├── viaggi/
│   ├── attrezzatura/
│   ├── spese/
│   ├── pasti/
│   └── budget/
│
└── static/
    └── css/
        └── style.css
```

### `app.py`

Crea e configura l'app Flask e registra i blueprint.

### `config.py`

Contiene:

* configurazione Flask;
* secret key;
* dati di connessione al database.

Le informazioni sensibili non devono essere inserite direttamente nel codice e potranno essere gestite tramite variabili d'ambiente.

### `db.py`

Gestisce:

* connessione MySQL;
* esecuzione delle query;
* operazioni comuni sul database.

### `schema.sql`

Contiene la struttura del database e la creazione delle tabelle.

### `blueprints/`

Contiene le route suddivise per funzionalità:

* `auth.py` → registrazione, login e logout;
* `viaggi.py` → viaggi, partecipanti, dashboard e duplicazione;
* `attrezzatura.py` → catalogo, checklist e assegnazioni;
* `spese.py` → spese, quote e saldi;
* `pasti.py` → pasti, ingredienti e lista della spesa;
* `budget.py` → budget per categoria e avvisi.

### `services/`

Contiene la logica di business più complessa.

In particolare:

* `saldi.py` → calcolo dei saldi e dei pagamenti necessari;
* `avvisi.py` → regole per gli avvisi automatici.

Separare questi calcoli dalle route permette di testarli indipendentemente.

---

# 18. Approccio allo sviluppo

Lo sviluppo sarà organizzato in tre fasi:

## Analisi

* definizione del problema;
* identificazione degli utenti;
* progettazione del database;
* definizione delle relazioni;
* definizione delle funzionalità.

## Sviluppo

1. configurazione dell'ambiente virtuale;
2. configurazione MySQL;
3. creazione e verifica dello schema del database;
4. configurazione Flask;
5. connessione Flask → MySQL;
6. autenticazione;
7. CRUD dei viaggi;
8. gestione dei partecipanti;
9. gestione dell'attrezzatura;
10. gestione delle spese;
11. gestione delle attività;
12. gestione di pasti e lista della spesa;
13. dashboard;
14. calcoli e avvisi automatici;
15. miglioramento dell'interfaccia HTML/CSS.

## Verifica

* test delle singole funzioni;
* verifica delle query SQL;
* test dei CRUD;
* test dei calcoli;
* controllo dei casi limite;
* verifica dei permessi tra organizzatore e partecipante;
* verifica dell'integrità dei dati;
* test completo del flusso di creazione e gestione di un viaggio.

---

# 19. Obiettivo del progetto

L'obiettivo della prima versione di TripCrew è realizzare una web application funzionante nella quale un gruppo possa:

> **creare un viaggio, gestire i partecipanti, organizzare l'attrezzatura, pianificare attività e pasti, controllare il budget, registrare le spese e sapere esattamente cosa manca e come dividere i costi.**

Il progetto verrà inizialmente sviluppato utilizzando:

```text
Python
Flask
MySQL
HTML
CSS
Jinja
```

L'architettura sarà progettata in modo da poter aggiungere successivamente nuove funzionalità senza dover riprogettare completamente il database.

---

# 20. Idee future

Spazio per nuove funzionalità da valutare durante lo sviluppo:

*
*
*
*
*
