# Review del branch `tournament`

Data review: 5 settembre 2026  
Branch confrontato con: `main` (`e697310`)  
Commit del branch esaminati: `97896f4`, `2071fa4`

## Valutazione complessiva

Il branch e impostato bene a livello architetturale, ma non e ancora consigliato
il merge. Sono presenti almeno due problemi funzionali importanti e un problema
di autorizzazione.

La separazione principale delle responsabilita e sensata:

- la logica pura del bracket e in `calcio_balilla/core/tournament.py`;
- l'accesso SQL e concentrato nel repository;
- la registrazione del match e l'avanzamento del torneo avvengono nella stessa
  transazione;
- il generatore casuale e iniettabile, rendendo i test deterministici;
- non e stato introdotto un secondo aggiornamento ELO;
- la documentazione descrive chiaramente decisioni e limiti noti.

Prima del merge devono essere affrontati almeno i punti P1 relativi alla
cancellazione dei match e al cambio di season.

## Problemi rilevati

### P1 - Cancellare una partita del torneo rende incoerente il bracket

`MatchService.delete_match()` ripristina ELO e statistiche e rimuove il match,
ma non riconcilia lo stato del torneo. In particolare, non:

- riapre una serie che non ha piu le vittorie necessarie;
- rimuove il vincitore persistito dalla serie;
- ritira il vincitore dallo slot del turno successivo;
- riporta una serie successiva da `active` a `pending`;
- riapre un torneo la cui finale non risulta piu conclusa;
- rimuove il campione persistito.

Inoltre, `MatchRepository.get_match_by_id()` non recupera attualmente
`tournament_series_id`, quindi il flusso di cancellazione non sa se il match
appartiene a un torneo.

File coinvolti:

- `calcio_balilla/core/match_service.py`, metodo `delete_match()`;
- `calcio_balilla/data/match_repository.py`, metodo `get_match_by_id()`;
- `calcio_balilla/data/tournament_repository.py`;
- `calcio_balilla/ui/match_management.py`, funzione `show_delete_match()`.

Il problema e gia documentato in `docs/TOURNAMENT_IMPLEMENTATION.md`, ma la UI
continua a consentire la cancellazione.

Soluzione minima sicura:

- bloccare esplicitamente la cancellazione di qualsiasi Tournament match.

Soluzione completa preferibile:

- riconciliare transazionalmente il bracket partendo dai match rimasti;
- rifiutare la cancellazione quando esistono match in serie discendenti che
  dipendono dall'avanzamento da revocare;
- permettere all'amministratore di cancellare prima i match dei turni piu
  avanzati e poi quelli dei turni precedenti.

Criteri di accettazione:

- una vittoria decisiva cancellata riapre correttamente la serie;
- vincitore e campione vengono rimossi quando non sono piu validi;
- lo slot del turno successivo viene ripulito;
- una serie successiva senza entrambi gli sfidanti torna `pending`;
- non e possibile invalidare silenziosamente partite gia giocate nei turni
  successivi;
- ripristino ELO e riconciliazione del bracket sono atomici.

### P1 - Chiudere una season puo rendere un torneo incompletabile

`SeasonService.start_next_season()` chiude la season corrente senza controllare
se contiene tornei ancora attivi.

Dopo l'apertura della nuova season:

- la UI Tournament elenca solamente i tornei della season attiva;
- il form New Match elenca solamente i tornei della season attiva;
- `MatchService.record_match()` rifiuta correttamente una serie appartenente
  alla vecchia season.

Il torneo rimane quindi `active` nel database, ma non puo piu essere completato
attraverso l'applicazione.

File coinvolti:

- `calcio_balilla/core/season_service.py`;
- `calcio_balilla/core/match_service.py`;
- `calcio_balilla/ui/tournaments.py`;
- `calcio_balilla/ui/match_management.py`.

Soluzione consigliata:

- impedire la chiusura della season quando esiste almeno un torneo `active` per
  quella leaderboard e season;
- mostrare un errore chiaro con i tornei che devono essere completati o annullati.

In alternativa deve essere progettato esplicitamente uno stato `cancelled` e il
relativo flusso di archiviazione. Non e consigliabile spostare automaticamente
un torneo alla nuova season, perche i suoi match e l'ELO appartengono alla season
originaria.

Criteri di accettazione:

- una season con un torneo attivo non puo essere chiusa accidentalmente;
- una season senza tornei attivi continua a chiudersi come prima;
- il controllo e nello stesso flusso transazionale del cambio season;
- e presente un test per una possibile concorrenza fra creazione torneo e
  chiusura season.

### P1/P2 - La pagina di gestione non ricontrolla l'autorizzazione

Il pulsante `Manage tournament` viene mostrato solamente quando `can_manage()`
restituisce `True`, ma `_render_management_page()` apre la pagina in base al solo
valore conservato in session state.

Scenario riproducibile:

1. un manager apre `Manage tournament` sulla propria leaderboard;
2. cambia leaderboard usando il selettore globale;
3. la pagina corrente rimane `Manage Tournament`;
4. il manager puo creare un torneo nella leaderboard che non dovrebbe gestire.

Questo difetto esiste nel routing generale delle pagine amministrative, ma il
branch aggiunge una nuova operazione privilegiata esposta allo stesso problema.

File coinvolti:

- `calcio_balilla/ui/nav.py`;
- `calcio_balilla/ui/tournaments.py`;
- `calcio_balilla/ui/state.py`.

Soluzione consigliata:

- verificare `can_manage(selected_l_id)` anche durante il rendering di ogni
  pagina amministrativa;
- riportare l'utente alla home se non e autorizzato;
- considerare una validazione di autorizzazione anche nel livello applicativo
  se in futuro le operazioni saranno richiamabili fuori dalla UI Streamlit.

Criteri di accettazione:

- cambiare verso una leaderboard non autorizzata chiude la pagina di gestione;
- nessuna operazione di scrittura viene eseguita basandosi solamente sulla
  visibilita del pulsante;
- il comportamento e verificato almeno per manager, admin e guest.

### P2 - La validazione core accetta squadre duplicate o incomplete

`validate_series_match()` converte immediatamente le due squadre in `set`. In
questo modo perde l'informazione sulla cardinalita originale e puo accettare un
giocatore duplicato al posto del compagno.

Esempi osservati durante la review:

```python
validate_series_match(1, 2, (1, 1), (2, 3))
# Restituisce (None, 3) invece di sollevare ValueError.

validate_series_match(1, 2, (1, 3), (2, 2))
# Restituisce (3, None) invece di sollevare ValueError.
```

La UI impedisce attualmente di scegliere giocatori duplicati, ma il service non
deve dipendere esclusivamente da una validazione dell'interfaccia.

File coinvolti:

- `calcio_balilla/core/tournament.py`;
- `calcio_balilla/core/match_service.py`;
- `tests/test_tournament.py`.

Soluzione consigliata:

- verificare che ogni squadra contenga esattamente due ID distinti;
- verificare che i quattro giocatori siano distinti complessivamente;
- rifiutare esplicitamente compagni mancanti o `None`;
- mantenere le verifiche gia presenti su sfidanti, lati e compagni usati.

## Copertura dei test

La suite esistente passa completamente:

```text
Ran 37 tests in 2.915s
OK
```

Sono passati anche:

- `python3 -m compileall -q calcio_balilla app.py models.py db.py scoring.py`;
- `git diff --check main...HEAD`.

I nuovi test coprono soprattutto la logica pura. Prima del merge servono test di
service/repository o test di integrazione PostgreSQL per:

- creazione e ricostruzione persistita del bracket;
- avanzamento e completamento delle serie;
- completamento del torneo;
- rollback in caso di errore dopo l'aggiornamento ELO;
- cancellazione dei Tournament match;
- cambio season con torneo attivo;
- autorizzazione dopo il cambio di leaderboard;
- validazione di squadre duplicate;
- query e lock eseguiti contro PostgreSQL reale.

## Considerazioni strutturali non bloccanti

Repository, service e UI si scambiano spesso direttamente oggetti `Row` di
SQLAlchemy. Per il torneo sarebbe preferibile introdurre piccoli oggetti di
dominio tipizzati per torneo e serie, come gia fatto con `SeriesSpec`. Questo:

- renderebbe esplicito il contratto fra repository, service e UI;
- ridurrebbe la dipendenza dell'interfaccia dalla forma esatta delle query;
- semplificherebbe unit test e refactoring futuri.

Altri miglioramenti non bloccanti:

- mostrare un errore applicativo leggibile per nomi torneo duplicati, invece
  dell'eccezione SQL grezza;
- uniformare italiano e inglese nelle etichette UI;
- provare il bracket su mobile e con tornei grandi;
- valutare indici aggiuntivi sulle foreign key usate frequentemente.

## Igiene del worktree

Durante la review risultava non tracciato:

```text
.streamlit/secrets.toml.backup
```

`.gitignore` ignora `.streamlit/secrets.toml`, ma non il file `.backup`. Il file
non e stato aperto durante la review. Deve essere ignorato o rimosso prima di
usare comandi come `git add .`, per evitare di versionare accidentalmente
credenziali.

## Ordine di intervento suggerito

1. Bloccare temporaneamente la cancellazione dei Tournament match.
2. Bloccare la chiusura di una season con tornei attivi.
3. Correggere l'autorizzazione nel routing delle pagine amministrative.
4. Correggere la validazione delle squadre nel core.
5. Implementare la riconciliazione completa del bracket alla cancellazione.
6. Aggiungere test di servizio, repository e integrazione PostgreSQL.
7. Rifinire UX, messaggi di errore e layout mobile.

## Verdetto

La base e promettente e la separazione delle responsabilita e generalmente
buona. Il branch non dovrebbe pero essere considerato completo finche la
cancellazione dei match e il lifecycle della season non sono messi in sicurezza.
