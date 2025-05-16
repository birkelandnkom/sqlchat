# SQL Chatbot (Streamlit PoC)

Dette prosjektet er en Proof-of-Concept (PoC) Streamlit-applikasjon som demonstrerer en chatbot som kan interagere med en SQL-database. Brukere kan stille spørsmål på naturlig språk, som chatboten forsøker å oversette til SQL-spørringer. Resultatene fra spørringen vises, og brukerne kan også få hjelp av AI til å visualisere dataene og laste ned resultatene som en CSV-fil. Applikasjonen inkluderer også sporing av token-forbruk og estimert gCO₂e-utslipp.

<img src="images/system_context_diagram.jpg" alt="System Diagram" title="System context overview" width="900">

## Funksjonalitet

* **Naturlig Språk til SQL:** Oversetter brukerspørsmål til kjørbare SQL-spørringer ved hjelp av en LangChain-agent.
* **Databaseinteraksjon:** Kobler til en spesifisert SQL-database (standard er Chinook SQLite) og utfører genererte spørringer.
* **Resultatvisning:** Viser spørringsresultater i et tabellformat (Streamlit DataFrame).
* **CSV-nedlasting:** Lar brukere laste ned de viste resultatene som en CSV-fil via en nedlastingsknapp.
* **AI-drevet Datavisualisering:** Tilbyr en funksjon der en AI (LLM) analyserer returnerte data og foreslår/genererer en passende visualisering (f.eks. søyle-, linje-, eller punktdiagram) ved hjelp av Streamlits innebygde graf-funksjoner.
* **Debugging-visning:** Tilbyr en utvidbar seksjon ("expander") under hvert svar for å se mellomtrinnene som Langchain-agenten tar, inkludert den genererte SQL-koden.
* **Sporing av Ressursbruk:**
    * Viser totalt antall tokens brukt i løpet av brukerøkten.
    * Viser estimert gCO₂e-utslipp for økten, med en ekvivalens til dagligdags bruk (f.eks. bruk av en LED-pære).
* **Brukertilpasset Grensesnitt:**
    * Enkel passordautentisering for PoC.
    * Tilpasset tema og logo (Nkom-inspirert).

## Oppsett og installasjon

1.  **Forutsetninger:**
    * Python 3.9+
    * Tilgang til en SQL-database (en `chinook.db` SQLite-database brukes som standard hvis ingen annen `DATABASE_URI` er satt).
    * Azure OpenAI API-nøkkel og endepunkt (`AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`).

2.  **Opprett og aktiver et virtuelt miljø:**
    ```bash
    python -m venv venv
    # På Windows
    venv\Scripts\activate
    # På macOS/Linux
    source venv/bin/activate
    ```

3.  **Installer avhengigheter:**
    Sørg for at `requirements.txt` inkluderer `streamlit` og andre nødvendige pakker.
    ```bash
    pip install -r requirements.txt
    ```

4.  **Konfigurer miljøvariabler:**
    Opprett en `.env`-fil i prosjektets rotmappe med følgende innhold (juster etter behov):
    ```dotenv
    AZURE_OPENAI_API_KEY="DIN_AZURE_OPENAI_NØKKEL"
    AZURE_OPENAI_ENDPOINT="DITT_AZURE_OPENAI_ENDEPUNKT"

    # Valgfritt: Din Database Connection URI
    # Hvis ikke satt, brukes en lokal filbasert SQLite-database (chinook.db)
    # Eksempel for PostgreSQL:
    # DATABASE_URI="postgresql+psycopg2://bruker:passord@host:port/database"
    ```

5.  **Databaseoppsett:**
    * Hvis du ikke bruker standard `chinook.db`, sørg for at databasen spesifisert i `DATABASE_URI` eksisterer og er tilgjengelig.
    * Tabellene som agenten skal ha tilgang til, er definert i `backend/db_client.py`. Standardoppsettet bruker tabeller fra Chinook-databasen.

6.  **Kjør applikasjonen:**
    Naviger til prosjektets rotmappe i terminalen og kjør:
    ```bash
    streamlit run app/app.py
    ```
    Applikasjonen vil da være tilgjengelig i nettleseren din, vanligvis på `http://localhost:8501`.
    Standard brukernavn/passord for PoC-innloggingen er `admin`/`admin`.

## Prosjektstruktur

    project_root/
    ├── app/                      # Frontend (Streamlit) kode
    │   ├── app.py                # Hovedinngangspunkt for Streamlit-appen
    │   ├── components/           # UI-komponenter for Streamlit
    │   │   ├── sidebar.py
    │   │   └── chat_interface.py
    │   └── services/             # Tjenester brukt av frontend (autentisering, prosessering)
    │       ├── auth.py
    │       └── processing.py
    ├── backend/                  # Backend-logikk (LangChain agent, LLM-klient, DB-klient)
    │   ├── agent_builder.py
    │   ├── config.py
    │   ├── db_client.py
    │   ├── llm_client.py
    │   └── token_tracer.py
    ├── public/                   # Statiske ressurser (logoer, favicon)
    │   ├── favicon.png
    │   ├── logo_dark.png
    │   ├── logo_light.png
    │   └── logo_wide_text.png
    ├── .streamlit/               # Streamlit konfigurasjonsmappe
    │   └── config.toml           # Streamlit temakonfigurasjon
    ├── .env                      # Lokale miljøvariabler (IKKE COMMIT DENNE!)
    ├── requirements.txt          # Python-avhengigheter
    └── README.md                 # Denne filen

## Backend

Backend-logikken, som håndterer opprettelsen av LangChain SQL-agenten, LLM-klientinteraksjon, og databaseforbindelsen, er i hovedsak uendret fra den opprinnelige Chainlit-versjonen og ligger i `backend/`-mappen.


