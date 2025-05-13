# SQL Chatbot PoC

Dette prosjektet er en PoC Chainlit-applikasjon som demonstrerer en chatbot som kan interagere med en SQL-database. Brukere kan stille spørsmål som chatboten forsøker å oversette til SQL-spørringer. Resultatene fra spørringen vises deretter i en tabell, og brukerne kan laste ned resultatene som en CSV-fil.

## Funksjonalitet

*   **Naturlig Språk til SQL:** Oversetter brukerspørsmål til kjørbare SQL-spørringer.
*   **Databaseinteraksjon:** Kobler til en spesifisert SQL-database og utfører spørringer.
*   **Resultatvisning:** Viser spørringsresultater i et tabellformat ved hjelp av Pandas DataFrames.
*   **CSV-nedlasting:** Laste ned de viste resultatene som en CSV-fil.
*   **Debugging-visning:** Tilbyr en "expander" for å se mellomtrinnene som Langchain-agenten tar (inkludert den genererte SQL-koden).

## Oppsett og installasjon

1.  **Forutsetninger:**
    *   Python 3.9+
    *   Tilgang til en SQL-database. 
    *   En API-nøkkel og valgt modell.

2.  **Opprett og bruk venv:**
    ```bash
    python -m venv venv
    # På Windows
    venv\Scripts\activate
    # På macOS/Linux
    source venv/bin/activate
    ```

3.  **Installer requirement.txt:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Konfigurer .env:**
    ```dotenv
    AZURE_OPENAI_API_KEY="sk-or-v1-..."

    # Din Database Connection URI
    # Eksempel for PostgreSQL:
    # DATABASE_URI="postgresql+psycopg2://bruker:passord@host:port/database"
    ```

5.  **Databaseoppsett:**
    Sørg for at databasen spesifisert i `DATABASE_URI` eksisterer og er tilgjengelig. 
    Deretter må tilgjengelige tabeller settes i db_client.py

    Om ingen database er satt brukes lokal SQLite database. 

Deretter kan applikasjonen starte via 
    ```bash
    chainlit run app.py -w
    ```

## Struktur
    .
    ├── backend/
    │   ├── agent_builder.py    # Bygger SQL-agenten
    │   ├── config.py           # Laster miljøvariabler og konfigurasjon
    │   ├── db_client.py        # Init database-koblingen
    │   └── llm_client.py       # Starter LLM-klienten
    ├── .env                    # Lokale miljøvariabler
    ├── app.py                  # Chainlit for UI og chatlogikk 
    ├── requirements.txt        # Python-avhengigheter
    └── README.md               # Readme

