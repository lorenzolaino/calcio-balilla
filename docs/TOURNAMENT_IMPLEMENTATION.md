# Tournament mode — implementation handoff

## Stato dello sviluppo

La modalità Tournament a eliminazione diretta è stata implementata localmente.
Le modifiche sono attualmente nel working tree e non sono state automaticamente
spostate su un branch né committate.

Ultima verifica eseguita:

```text
python3 -m unittest discover -s tests
Ran 37 tests
OK
```

È stata verificata la compilazione dei file Python e `git diff --check` non ha
segnalato errori. Non è ancora stata eseguita una prova end-to-end con una vera
istanza PostgreSQL e con l'interfaccia Streamlit aperta nel browser.

Le due chat condivise come contesto aggiuntivo non erano accessibili
dall'ambiente di sviluppo. Il prompt dettagliato dell'utente è stato usato come
fonte autoritativa.

## Obiettivo funzionale

Il torneo è individuale e a eliminazione diretta. Gli sfidanti di una serie sono
due giocatori iscritti al torneo, ma ogni partita è una normale partita 2 contro
2 della leaderboard:

```text
Serie: A contro B
Partita: A + X contro B + Y
```

X e Y non devono essere iscritti al torneo. La partita continua a usare il
normale sistema ELO e compare nella normale history. Il torneo non assegna
direttamente punti, bonus o modificatori ELO.

## File creati

- `calcio_balilla/core/tournament.py`
  - logica pura e testabile;
  - calcolo preliminari e bye;
  - generazione bracket;
  - best of 3 e best of 5;
  - risultato delle serie;
  - generazione e validazione dei compagni.
- `calcio_balilla/core/tournament_service.py`
  - creazione transazionale del torneo;
  - recupero del ranking precedente;
  - sorteggio contestuale dei compagni.
- `calcio_balilla/data/tournament_repository.py`
  - query e persistenza di tornei, partecipanti e serie;
  - ricostruzione di vittorie e compagni dai match;
  - completamento e avanzamento delle serie.
- `calcio_balilla/ui/tournaments.py`
  - pagina `Manage tournament`;
  - pagina `Tournament` con bracket e sorteggio.
- `tests/test_tournament.py`
  - test della logica pura del torneo.

## File modificati

- `db.py`
- `models.py`
- `calcio_balilla/app_facade.py`
- `calcio_balilla/core/match_service.py`
- `calcio_balilla/data/match_repository.py`
- `calcio_balilla/ui/match_management.py`
- `calcio_balilla/ui/nav.py`
- `calcio_balilla/ui/state.py`
- `tests/test_db_schema.py`

## Architettura adottata

È stata estesa l'architettura esistente senza creare un secondo percorso per le
partite:

```text
Streamlit UI
    -> ApplicationFacade
        -> TournamentService / MatchService
            -> TournamentRepository / repository esistenti
                -> PostgreSQL
```

La business logic indipendente dal database è in `core/tournament.py`. La UI
non contiene regole di avanzamento, calcolo dei bye o validazione dei compagni.

Il punto più importante è che `MatchService.record_match()` resta l'unico flusso
di registrazione. Il parametro opzionale `tournament_series_id` aggiunge il
comportamento Tournament senza cambiare quello delle normali partite.

## Modello dati

Lo schema viene aggiornato in modo idempotente da `init_db()`, seguendo il
sistema già usato dal progetto. Non esiste una directory di migration separata.

### `tournaments`

Contiene:

- leaderboard associata;
- season associata;
- nome;
- stato `active` o `completed`;
- eventuale vincitore;
- data di creazione.

Il nome è univoco nella combinazione leaderboard/season. Sono supportati più
tornei per la stessa leaderboard e season, purché abbiano nomi diversi.

### `tournament_participants`

Tabella molti-a-molti tra torneo e giocatori iscritti. I compagni delle singole
partite non devono comparire qui.

### `tournament_series`

Ogni record rappresenta una serie e contiene:

- torneo;
- indice e nome del turno;
- posizione nel turno;
- due sfidanti, eventualmente ancora non definiti;
- indicazione della finale;
- stato `pending`, `active` o `completed`;
- vincitore;
- `next_series_id` e `next_slot` per rappresentare l'avanzamento.

Il bracket è quindi un grafo persistito. Quando una serie termina, il vincitore
viene inserito nello slot corretto della serie successiva.

### Collegamento dei match

È stata aggiunta la colonna opzionale:

```text
matches.tournament_series_id
```

Una partita senza valore in questa colonna è una normale partita e mantiene il
comportamento precedente. È stato aggiunto anche l'indice
`idx_matches_tournament_series`.

Vittorie della serie e compagni già usati non sono duplicati in colonne: vengono
ricostruiti interrogando i normali match associati alla serie.

## Generazione del bracket

La generazione avviene una sola volta durante la creazione e il risultato viene
salvato nel database.

Per `N` partecipanti viene calcolata la maggiore potenza di due `P <= N`.

Se `N` è una potenza di due:

- non ci sono preliminari;
- non ci sono bye.

Altrimenti:

```text
serie preliminari = N - P
giocatori nei preliminari = 2 * (N - P)
bye = 2 * P - N
```

Gli accoppiamenti vengono sorteggiati senza utilizzare rating, ELO o ranking. Il
random generator può essere iniettato nei test; nell'app viene usato
`random.SystemRandom`.

## Assegnazione dei bye

I bye sono assegnati, tra i soli iscritti, usando la classifica dell'ultima
season chiusa della stessa leaderboard. L'ordinamento è:

1. rating decrescente;
2. vittorie decrescenti;
3. differenza reti decrescente;
4. ID giocatore crescente.

Se la precedente classifica non contiene abbastanza iscritti, gli slot rimasti
sono assegnati per ID giocatore crescente. Il fallback è quindi deterministico.
Il ranking viene usato esclusivamente per i bye e non per gli accoppiamenti.

## Serie e avanzamento

- Tutte le serie non finali sono best of 3: servono 2 vittorie.
- La finale è best of 5: servono 3 vittorie.
- Le vittorie vengono ricostruite dai match della serie.
- Una serie conclusa viene marcata `completed`.
- Il vincitore viene inserito automaticamente nella serie successiva.
- Una serie successiva diventa `active` quando entrambi gli sfidanti sono noti.
- La vittoria della finale completa il torneo e salva il campione.
- `MatchService` rifiuta un nuovo match associato a una serie non attiva.

## Sorteggio dei compagni

Il sorteggio è nella pagina `Tournament` e non registra una partita.

Per una serie A-B:

- A e B devono essere presenti e non possono essere compagni;
- vengono usati solo giocatori selezionati come presenti;
- i compagni possono non essere iscritti al torneo;
- i due compagni devono essere differenti;
- un giocatore già compagno di A nella serie non può tornare con A;
- lo stesso giocatore può successivamente giocare con B;
- il vincolo si resetta in una nuova serie;
- tutte le coppie valide vengono determinate prima del sorteggio;
- se non esiste una coppia completa valida, non viene restituito un risultato
  parziale.

La pagina mostra anche i compagni già usati da ciascuno sfidante, ricostruiti dai
match persistiti.

## Validazione durante il salvataggio

Il sorteggio UI è solo un helper. Il normale form può essere compilato
manualmente, quindi `MatchService.record_match()` rivalida sempre:

- serie esistente e attiva;
- stessa leaderboard e stessa season;
- entrambi gli sfidanti presenti;
- sfidanti su squadre opposte;
- sfidanti non usati come compagni;
- compagni differenti;
- compagno non già usato con lo stesso sfidante nella serie.

La validazione e il lock della serie avvengono nella stessa transazione usata per
registrare la partita.

## ELO e consistenza transazionale

Non è stato creato alcun ELO Tournament.

Per una Tournament match il flusso è:

1. apertura della transazione esistente;
2. caricamento e lock della serie;
3. validazione Tournament;
4. controllo duplicati esistente;
5. singolo calcolo ELO tramite `scoring.calculate_match_updates_for_states()`;
6. aggiornamento delle statistiche;
7. inserimento del normale match con `tournament_series_id`;
8. inserimento della normale rating history;
9. ricostruzione del risultato della serie;
10. eventuale completamento e avanzamento.

Se una fase fallisce, la transazione effettua il rollback. Non esiste un secondo
aggiornamento ELO e non vengono assegnati punti per serie, turno o torneo.

## Interfaccia utente

Sono state aggiunte due destinazioni alla navigazione.

### `Manage tournament`

Visibile nella sezione di management. Usa la leaderboard selezionata nel
selettore globale in alto e permette di:

- inserire il nome;
- scegliere gli iscritti dalla season corrente;
- creare e persistere il bracket;
- vedere i tornei già creati.

### `Tournament`

Visibile vicino alla sezione Seasons e permette di:

- selezionare un torneo della season corrente;
- vedere i round in colonne;
- vedere sfidanti, vittorie, stato e vincitore;
- vedere il campione;
- selezionare una serie attiva;
- vedere i compagni già utilizzati;
- selezionare i presenti;
- sorteggiare la prossima coppia di compagni.

### Form `New Match`

Il form esistente ora include:

- selezione `No tournament` oppure torneo attivo;
- selezione di una serie attiva del torneo;
- normale selezione delle quattro persone e del risultato.

Il salvataggio continua a chiamare il normale `record_match()`.

## Test aggiunti

I test Tournament coprono:

- bracket con 4, 5, 6, 7, 8 e 9 partecipanti;
- conteggio preliminari e bye;
- assenza di preliminari per potenze di due;
- assegnazione bye dal ranking e fallback deterministico;
- random generator con seed;
- assenza di bilanciamento per ranking;
- best of 3, risultati 2-0 e 2-1;
- finale best of 5, risultati 3-0 e 3-2;
- serie non ancora conclusa;
- vincoli dei compagni;
- possibilità di cambiare lato nella stessa serie;
- esclusione degli sfidanti dai compagni;
- compagni distinti;
- impossibilità di creare una combinazione valida;
- validazione di match inseriti manualmente;
- reset del vincolo in una serie successiva;
- presenza delle nuove tabelle, colonna e indice nello schema.

La suite preesistente continua a verificare l'ELO e il normale comportamento
delle partite.

## Come salvare il lavoro su un branch

Le modifiche possono essere salvate con:

```bash
git switch -c feature/tournaments
git add .
git commit -m "Add tournament mode"
git push -u origin feature/tournaments
```

Prima di usare `git add .`, controllare sempre `git status --short` per evitare
di includere modifiche locali non pertinenti.

## Come provare su un altro PC

```bash
git fetch origin
git switch feature/tournaments
python3 -m pip install -r requirements.txt
export DATABASE_URL="postgresql://utente:password@localhost:5432/calcio_balilla"
python3 -m streamlit run app.py
```

Aprire poi `http://localhost:8501`.

Il database PostgreSQL indicato deve esistere. `init_db()` crea o aggiorna le
tabelle al primo avvio.

Per rieseguire i test:

```bash
python3 -m unittest discover -s tests
```

## Checklist per la prova manuale

1. Aprire `Manage tournament` con una season attiva.
2. Creare tornei da 4, 5, 6 e 8 giocatori.
3. Riavviare Streamlit e verificare che i bracket siano invariati.
4. Verificare che i bye vadano ai migliori della precedente season.
5. Aprire `Tournament`, selezionare una serie e sorteggiare i compagni.
6. Registrare il match dal normale `New Match` associandolo alla serie.
7. Controllare history ed ELO dei quattro partecipanti.
8. Registrare una vittoria 2-0 e controllare l'avanzamento.
9. Provare una serie 2-1 distribuita su più giorni.
10. Completare una finale 3-0 o 3-2 e verificare il campione.
11. Provare a riutilizzare lo stesso compagno con lo stesso sfidante.
12. Provare sfidanti sulla stessa squadra e controllare il rifiuto.
13. Provare un giocatore non iscritto come compagno.
14. Controllare layout desktop e mobile.

## Punti ancora da verificare o migliorare

### Test con PostgreSQL reale

La suite usa prevalentemente unit test e mock. Occorre verificare le query e le
transazioni contro PostgreSQL reale, oltre all'applicazione idempotente dello
schema su un database già popolato.

### Cancellazione di Tournament match

Il normale sistema consente la cancellazione dei match e ripristina l'ELO. Non è
ancora stata implementata la ricostruzione retroattiva del bracket quando viene
cancellato un match appartenente a una serie già conclusa.

**Priorità: P1 — fondamentale prima di considerare completa la gestione
amministrativa dei tornei.**

Il problema rilevato in review è il seguente: quando viene cancellata la partita
decisiva che aveva completato una serie, `MatchService.delete_match()` ripristina
le statistiche ELO e rimuove il match, ma attualmente non:

- riapre la serie;
- cancella il vincitore persistito della serie;
- ritira il giocatore dallo slot del turno successivo;
- aggiorna lo stato della serie successiva;
- riapre un torneo la cui finale non risulta più conclusa;
- cancella l'eventuale campione persistito.

Il bracket può quindi rimanere completato anche se, in base ai match rimasti, lo
sfidante non ha più raggiunto le vittorie necessarie. Se nel frattempo sono state
giocate serie successive, possono inoltre esistere risultati dipendenti da un
avanzamento che non è più valido.

Fino a quando non viene aggiunta questa funzione, evitare di cancellare dalla
history una Tournament match che ha contribuito alla chiusura e all'avanzamento
di una serie.

#### Strategia di implementazione proposta

La soluzione preferibile è una riconciliazione transazionale del bracket, non un
semplice aggiornamento puntuale della serie cancellata. Lo stato derivabile deve
essere ricalcolato dai match rimasti, trattandoli come fonte autoritativa.

Il flusso previsto per `delete_match()` è:

1. caricare il match con il relativo `tournament_series_id`;
2. se non appartiene a un torneo, mantenere esattamente il comportamento attuale;
3. bloccare con `FOR UPDATE` il torneo e le sue serie per evitare aggiornamenti
   concorrenti;
4. validare se esistono match giocati nei turni successivi che dipendono dal
   vincitore della serie interessata;
5. rimuovere il match e ripristinare l'ELO con la logica esistente;
6. ricostruire vittorie, vincitore e stato della serie dai match rimasti;
7. propagare l'eventuale cambiamento verso tutte le serie successive;
8. aggiornare stato e vincitore del torneo;
9. completare tutte le operazioni nella stessa transazione, effettuando rollback
   completo in caso di errore.

#### Gestione delle dipendenze già giocate

La cancellazione non deve invalidare silenziosamente match già disputati nei
turni successivi. La prima implementazione sicura dovrebbe adottare questa
regola:

- consentire la cancellazione se non esistono match nelle serie discendenti
  dipendenti dall'avanzamento da revocare;
- rifiutare chiaramente la cancellazione se una serie successiva contiene già
  almeno un match;
- spiegare all'amministratore quali serie o match dipendenti devono essere
  cancellati prima, procedendo dal turno più avanzato verso quello precedente.

Questo approccio evita cancellazioni ricorsive implicite e mantiene il normale
ripristino ELO sotto il controllo dell'amministratore. Una futura funzione
esplicita di rollback ricorsivo potrebbe cancellare i match discendenti, ma
dovrebbe richiedere conferma e mostrare in anticipo tutti i match e gli
aggiornamenti ELO coinvolti.

#### API e repository previsti

L'implementazione può essere mantenuta nell'architettura esistente aggiungendo al
`TournamentRepository` operazioni simili a:

- recupero del `tournament_series_id` insieme ai dettagli del match;
- lock del torneo e di tutte le serie ordinate per round;
- ricerca delle serie discendenti e dei relativi match;
- reset di `status` e `winner_id` per serie e torneo;
- rimozione del vincitore da `challenger1_id` o `challenger2_id` nella serie
  successiva;
- riconciliazione completa del bracket dai match persistiti.

La regola best of 3/best of 5 deve continuare a usare
`core.tournament.series_result()`, evitando di duplicare il calcolo in
`MatchService` o nel repository.

#### Casi di test necessari

Prima di considerare risolto il punto P1 servono almeno questi test:

- cancellazione di un match Tournament non decisivo;
- cancellazione della vittoria decisiva di una serie 2-0;
- cancellazione della vittoria decisiva di una serie 2-1;
- riapertura di una finale 3-0 e 3-2;
- rimozione del campione e riapertura del torneo;
- rimozione del vincitore dallo slot della serie successiva;
- passaggio della serie successiva da `active` a `pending`;
- rifiuto della cancellazione quando la serie discendente ha già dei match;
- possibilità di cancellare prima i match discendenti e poi il match originario;
- rollback atomico se la riconciliazione fallisce;
- ripristino ELO eseguito una sola volta;
- nessun cambiamento nella cancellazione delle partite normali.

In sintesi, una soluzione futura deve:

- bloccare la cancellazione se esistono serie successive già giocate; oppure
- annullare in sicurezza tutti gli avanzamenti dipendenti;
- ricostruire stato, vincitori e campione a partire dai match rimasti.

### UI bracket

Il bracket usa colonne Streamlit e dati persistiti. È funzionale, ma potrebbe
richiedere rifiniture grafiche dopo una prova su schermi piccoli o con tornei
molto grandi.

### Test d'integrazione aggiuntivi

Sono consigliati test con un database temporaneo per verificare in modo completo:

- creazione e ricostruzione persistita;
- lock concorrenti sulla stessa serie;
- avanzamento SQL del vincitore;
- rollback con errore dopo il calcolo ELO;
- rifiuto di una serie appartenente a season o leaderboard differenti;
- garanzia end-to-end della singola applicazione ELO.

## Decisioni da non cambiare accidentalmente

- Non introdurre un ELO separato per il torneo.
- Non applicare bonus per serie, turni o vittoria del torneo.
- Non rigenerare il bracket ai rerun di Streamlit.
- Non usare ELO o ranking per bilanciare gli accoppiamenti.
- Usare il ranking precedente solamente per i bye.
- Non obbligare i compagni a essere iscritti.
- Non creare un secondo form o service indipendente per salvare i match.
- Continuare a ricostruire vittorie e compagni dai normali match associati.
- Mantenere validazioni Tournament nel core/service, non solamente nella UI.
