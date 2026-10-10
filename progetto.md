# TripCrew — organizzatore di viaggi outdoor di gruppo

Progetto finale del corso di Python (Flask, MySQL, HTML, CSS, Jinja). Documento di analisi e raccolta idee.

## Il problema

Quando 3-5 persone organizzano un campeggio, un trekking o un viaggio economico, le informazioni finiscono solitamente in:

- WhatsApp
- Google Maps
- note
- Splitwise
- fogli Excel
- checklist

Il vero problema non è tanto «fare una lista delle cose da portare». È capire:

**chi porta cosa, cosa manca e quanto spenderà ogni partecipante.**

## Posizionamento e nicchia

Esistono già app di camping planning e checklist condivise (per esempio CampCritter, CampMate e altri), che coprono buona parte del terreno delle liste di attrezzatura. Per questo l'app non va impostata come semplice packing list.

La nicchia è invece: **logistica condivisa + budget di un piccolo viaggio outdoor.**

## Utenti

**Organizzatore**

È un partecipante che crea il viaggio e inserisce i partecipanti.

**Partecipante**

Può:

- vedere il viaggio
- prendere in carico dell'attrezzatura
- registrare spese
- vedere cosa manca

## Dati: esempio di viaggio

**Dolomiti — Agosto**

- 4 partecipanti
- 5 giorni
- Budget massimo: €250 a persona

**Attrezzatura**

| Oggetto | Responsabile |
| --- | --- |
| Tenda | Claudio |
| Fornello | Luca |
| Pentola | Marco |
| Powerbank | Chiara |
| Torcia | ❌ MANCA |

**Spese**

| Voce | Importo |
| --- | --- |
| Campeggio | €80 |
| Benzina | €60 |
| Parcheggio | €20 |
| Spesa | €48 |

## Database

**UTENTI**

- id
- nome
- email
- password

**VIAGGI**

- id
- nome
- destinazione
- data\_inizio
- data\_fine
- budget\_persona
- creatore\_id

**PARTECIPANTI**

- id
- viaggio\_id
- utente\_id

**ATTREZZATURA**

- id
- nome
- categoria

**ATTREZZATURA\_VIAGGIO**

- id
- viaggio\_id
- attrezzatura\_id
- utente\_id
- quantita
- stato

**SPESE**

- id
- viaggio\_id
- utente\_id
- descrizione
- importo
- categoria
- data

**ATTIVITA**

- id
- viaggio\_id
- nome
- costo
- data

## Relazioni

```
               UTENTE
               /   \
              /     \
             v       v
       PARTECIPANTE  SPESA
             |
             v
           VIAGGIO
          /   |    \
         /    |     \
        v     v      v
 ATTREZZATURA SPESA ATTIVITA
      VIAGGIO
         |
         v
   ATTREZZATURA
```

Relazione molti-a-molti tra UTENTI e VIAGGI:

```
UTENTI
   N
   |
   |
PARTECIPANTI
   |
   |
   N
VIAGGI
```

La tabella `partecipanti` fa da junction table.

## Funzioni principali

- registrazione e login
- crea viaggio
- invita o aggiungi partecipante
- aggiungi elemento alla checklist
- assegna un oggetto a una persona
- segna oggetto come pronto
- visualizza cosa manca
- registra una spesa
- suddividi automaticamente le spese
- calcola costo totale
- calcola costo per persona
- confronta costo previsto e budget
- aggiungi attività
- dashboard del viaggio

## Esempio di dashboard

```
DOLOMITI 2027

Budget
€192 / €250 per persona
██████████████░░░░ 77%

ATTREZZATURA

18/21 elementi pronti

Manca:
❌ torcia
❌ kit pronto soccorso
❌ powerbank

SPESE

Campeggio       €80
Benzina         €60
Spesa           €48

Totale          €188
```

## Funzione interessante

Flask potrebbe evidenziare automaticamente:

- **«⚠ Budget quasi superato»** quando `spesa_per_persona > budget * 0.9`
- **«✅ Tutta l'attrezzatura essenziale è stata assegnata»** quando non rimangono elementi senza responsabile

## Funzioni aggiunte

- **Attrezzatura essenziale o opzionale.** Ogni elemento della checklist è marcato come essenziale o opzionale; il conteggio di "cosa manca" e gli avvisi si basano sugli elementi essenziali.
- **Avvisi automatici.** Budget quasi superato e attrezzatura essenziale tutta assegnata (vedi sezione precedente): l'app dice cosa fare, non si limita ad archiviare i dati.
- **"Chi deve quanto a chi".** A fine viaggio l'app calcola il saldo di ogni partecipante (quanto ha speso meno la sua quota) e propone il numero minimo di pagamenti per pareggiare i conti.

## Funzioni extra scelte per il progetto

Quattro funzioni scelte tra le idee proposte. Nascono dal confronto con le app esistenti (CampingBuddy, TrailMuster, PackParty, Packup e altre), non da recensioni di utenti: le recensioni trovate erano troppo poche per indicare funzioni mancanti.

1. **Menu, lista della spesa e spese.** Si pianificano i pasti per giorno e per tipo (colazione, pranzo, cena). Ogni pasto ha ingredienti con quantità per persona: l'app moltiplica per il numero di partecipanti e somma gli ingredienti uguali di tutti i pasti, ottenendo la lista della spesa. Ogni ingrediente ha un incaricato; quando viene segnato come acquistato con il prezzo reale, il costo entra automaticamente nelle spese.
2. **Quantità necessaria e doppioni.** Per ogni elemento della checklist si indica quanti ne servono (per esempio 2 tende per 4 persone). Più persone possono prendersene in carico una parte: l'app mostra quanti ne mancano e segnala i doppioni, cioè quantità assegnata maggiore di quella necessaria.
3. **Viaggio da modello.** Un viaggio si può duplicare: si copiano checklist con quantità e categorie, pasti, ingredienti e budget previsto, ma non le assegnazioni né le spese. Il nuovo viaggio ricorda da quale è stato copiato e ogni utente ha uno storico dei propri viaggi.
4. **Spese previste e spese effettive.** L'organizzatore fissa un budget previsto per categoria (campeggio, trasporto, cibo, attività, altro). La dashboard confronta per ogni categoria quanto è stato speso a persona con quanto previsto e avvisa quando si supera il 90%.

## Idee rimandate (sviluppi futuri)

Non fanno parte del progetto del corso per ora, ma possono essere aggiunte in seguito:

- **Quote in base ai giorni di presenza.** Chi arriva più tardi o parte prima paga meno le spese a notte (servono `giorno_arrivo` e `giorno_partenza` in `partecipanti`).
- **Auto e passaggi.** Ogni auto ha conducente e posti; benzina, pedaggi e parcheggio si dividono tra i passeggeri (tabelle `auto` e `passeggeri_auto`).
- **Carico di peso equilibrato.** Ogni oggetto ha un peso in kg e l'app avvisa se uno zaino supera di molto la media del gruppo (campo `peso_kg`).
- **Quota d'uso per chi presta attrezzatura.** Piccola quota, definita dal gruppo, per chi porta oggetti costosi come la tenda; entra nel calcolo dei saldi.

## Schema database aggiornato

Questo schema sostituisce quello della sezione Database, che resta come prima versione. Le novità: `attrezzatura_viaggio` descrive cosa serve e in che quantità, la nuova tabella `assegnazioni` dice chi se ne prende in carico, `spese_partecipanti` permette il calcolo dei saldi, mentre `budget_categoria`, `pasti` e `ingredienti_pasto` servono per budget e menu.

| Tabella | Campi | Note |
| --- | --- | --- |
| utenti | `id`, `nome`, `email`, `password_hash` | email univoca |
| viaggi | `id`, `nome`, `destinazione`, `data_inizio`, `data_fine`, `budget_persona`, `creatore_id`, `viaggio_origine_id` | `viaggio_origine_id` vuoto se il viaggio non è una copia |
| partecipanti | `id`, `viaggio_id`, `utente_id` | tabella ponte; coppia viaggio-utente univoca |
| attrezzatura | `id`, `nome`, `categoria` | catalogo degli oggetti |
| attrezzatura\_viaggio | `id`, `viaggio_id`, `attrezzatura_id`, `quantita_necessaria`, `essenziale` | cosa serve al viaggio e in che quantità |
| assegnazioni | `id`, `attrezzatura_viaggio_id`, `utente_id`, `quantita`, `stato` | chi porta quanto; stato: assegnato, pronto |
| spese | `id`, `viaggio_id`, `utente_id`, `descrizione`, `importo`, `categoria`, `data` | `utente_id` è chi ha pagato |
| spese\_partecipanti | `spesa_id`, `utente_id`, `quota` | chi contribuisce a una spesa e per quanto |
| attivita | `id`, `viaggio_id`, `nome`, `costo`, `data` | `costo` previsto |
| budget\_categoria | `id`, `viaggio_id`, `categoria`, `importo_previsto` | una riga per categoria e viaggio |
| pasti | `id`, `viaggio_id`, `giorno`, `tipo`, `descrizione` | tipo: colazione, pranzo, cena, altro |
| ingredienti\_pasto | `id`, `pasto_id`, `nome`, `unita`, `quantita_per_persona`, `costo_stimato`, `incaricato_id`, `acquistato`, `spesa_id` | `spesa_id` si compila quando l'ingrediente viene acquistato |

Note sulle tabelle: `attivita.costo` è un costo previsto, mentre una spesa realmente pagata va registrata in `spese` con categoria attività. `categoria` in `spese` e in `budget_categoria` usa lo stesso elenco fisso (campeggio, trasporto, cibo, attività, altro).

## Calcoli principali

- **Cosa manca per un elemento:** `quantita_necessaria` meno la somma delle `quantita` in `assegnazioni`. Se il risultato è positivo manca qualcosa, se è negativo c'è un doppione. Il messaggio "tutta l'attrezzatura essenziale è assegnata" compare quando nessun elemento essenziale ha mancanti.
- **Saldo di un partecipante:** somma di ciò che ha pagato (`spese`) meno la somma delle sue quote (`spese_partecipanti`). Chi ha saldo positivo deve ricevere, chi ha saldo negativo deve pagare; l'app abbina i saldi più grandi per ridurre il numero di pagamenti.
- **Costo per persona:** somma delle quote del partecipante; con ripartizione equa coincide con il totale diviso il numero di partecipanti.
- **Budget:** avviso "Budget quasi superato" quando il costo per persona supera il 90% del budget, sia sul totale sia per singola categoria (confronto con `budget_categoria`).
- **Lista della spesa:** `quantita_per_persona` per il numero di partecipanti, sommata per gli ingredienti con stesso nome e stessa unità (`GROUP BY nome, unita`).
- **Viaggio da modello:** si duplicano `attrezzatura_viaggio`, `pasti`, `ingredienti_pasto` (senza acquisto) e `budget_categoria`, valorizzando `viaggio_origine_id`.

## Struttura del progetto Flask

```
tripcrew/
  app.py                 # crea l'app Flask e registra i blueprint
  config.py              # chiave segreta e dati di connessione MySQL
  db.py                  # connessione al database e funzioni di query
  schema.sql             # creazione delle tabelle
  blueprints/
    auth.py              # registrazione, login, logout
    viaggi.py            # crea viaggio, partecipanti, dashboard, duplica viaggio
    attrezzatura.py      # checklist, assegnazioni, cosa manca
    spese.py             # spese, quote, saldi
    pasti.py             # menu, ingredienti, lista della spesa
    budget.py            # budget per categoria e avvisi
  services/
    saldi.py             # calcolo dei saldi e dei pagamenti minimi
    avvisi.py            # regole degli avvisi (90% del budget, essenziale assegnato)
  templates/
    base.html
    auth/ viaggi/ attrezzatura/ spese/ pasti/
  static/css/style.css
```

La logica dei calcoli sta in `services/`, separata dalle route di Flask: così si può verificare con test semplici nella fase di verifica.

## Idee future da implementare

*(spazio per aggiungere nuove idee man mano che mi vengono in mente)*

-
