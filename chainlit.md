# Velkommen til SQL Chatboten! 👋

Denne chatboten er designet for å hjelpe deg med å hente data fra databasen ved å oversette spørsmålene dine til SQL-spørringer.


>**Viktig:** Dett er **ikke** en generell samtale-AI, men spesialisert for å hente ut data basert på dine instruksjoner. Meldinger som ikke inneholder data-relaterte spørsmål vil ikke resultere i verdifulle svar. 

## Hvordan bruke chatboten

1.  **Still et spørsmål:** Skriv spørsmålet ditt i chat-feltet nederst.
2.  **Vær tydelig:** Formuler spørsmålet slik at det logisk kan oversettes til en databaseforespørsel.
3.  **Send:** Send inn spørsmålet ditt.

Chatboten vil:
*   Forsøke å forstå spørsmålet ditt.
*   Generere en SQL-spørring.
*   Kjøre spørringen mot databasen.
*   Presentere resultatet.

## Tips

For å få best mulig resultat:

*   **Vær Spesifikk:** Jo tydeligere spørsmålet er, jo bedre blir SQL-spørringen og resultatet.
*   **Fokuser på data:** Still spørsmål som kan besvares direkte fra dataene i tabellene.
*   **Bruke nøkkelord (valgfritt):** Hvis du kjenner tabell- eller kolonnenavn, inkluder det gjerne.

## Tilgjengelige data

Du kan stille spørsmål om data i følgende tabeller: WiP

## Feilsøking / Nysgjerrig? 🤔

Under hvert svar fra chatboten kan du se flere utvidbare seksjoner ("Agent Execution", "Step X: ..."). Disse viser:

*   Hvordan agenten tenkte.
*   Hvilke verktøy den brukte.
*   **Den eksakte SQL-spørringen som ble generert og kjørt.**

Dette er nyttig hvis du lurer på hvorfor resultatet ble som det ble, eller hvor noe gikk galt.

---

***Merk:*** *Dette er en Proof-of-Concept. SQL-genereringen er ikke alltid perfekt, og svært komplekse eller tvetydige spørsmål kan føre til feil eller uventede resultater. Det er brukt en simplere modell ved PoC for å holde kostnad nede. Mer komplekse modeller vil føre til bedre resultat*