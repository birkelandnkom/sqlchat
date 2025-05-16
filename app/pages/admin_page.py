import streamlit as st
import pandas as pd
import json
import os
import sys
import altair as alt
from datetime import datetime, time

PROJECT_ROOT_FOR_IMPORT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT_FOR_IMPORT not in sys.path:
    sys.path.append(PROJECT_ROOT_FOR_IMPORT)

PROJECT_ROOT_FOR_LOGS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FEEDBACK_LOG_FILE = os.path.join(PROJECT_ROOT_FOR_LOGS, "logs", "feedback_log.jsonl")

def load_feedback_data():
    logs = []
    if os.path.exists(FEEDBACK_LOG_FILE):
        try:
            with open(FEEDBACK_LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        logs.append(json.loads(line))
                    except json.JSONDecodeError:
                        print(f"Warning: Could not decode a line in the log file: {line.strip()}")
                        continue
        except Exception as e:
            st.error(f"En feil oppstod under lesing av loggfilen: {e}")
            return []
    return logs

def display_admin_page_content():
    if not os.path.exists(FEEDBACK_LOG_FILE):
        st.warning(f"Loggfilen ({FEEDBACK_LOG_FILE}) ble ikke funnet. Ingen data å vise.")
        st.caption("Loggfilen blir opprettet når den første tilbakemeldingen blir gitt.")
        return

    logs = load_feedback_data()

    if not logs:
        st.info("Ingen tilbakemeldinger er logget ennå.")
        return

    df_logs_original = pd.DataFrame(logs)

    if 'timestamp' not in df_logs_original.columns:
        st.error("Loggfilen mangler 'timestamp'-kolonnen, som er nødvendig for dashboardet.")
        return
    
    try:
        df_logs_original['timestamp'] = pd.to_datetime(df_logs_original['timestamp'])
    except Exception as e:
        st.error(f"Kunne ikke konvertere 'timestamp'-kolonnen til datoformat: {e}. Sjekk loggformatet.")
        return
    
    df_logs = df_logs_original.copy()


    if 'feedback_type' in df_logs.columns:
        feedback_counts = df_logs['feedback_type'].value_counts().reset_index()
        feedback_counts.columns = ['feedback_type', 'count']
        color_scale = alt.Scale(
            domain=['thumbs_up', 'thumbs_down'],
            range=['#3CB371', '#FF4500'] 
        )

        pie_chart = alt.Chart(feedback_counts).mark_arc(innerRadius=20).encode(
            theta=alt.Theta(field="count", type="quantitative"),
            color=alt.Color(
                field="feedback_type", 
                type="nominal", 
                scale=color_scale,
                legend=None 
            ),
            tooltip=['feedback_type', 'count']
        ).properties(
            title="",
            height=100,
        )

        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns([1,1,1,1])

        with metric_col1:
            st.markdown("Antall tilbakemeldinger")
            st.markdown("<h3 style='color: dodgerblue; margin-top: -20px;'>"+str(df_logs.shape[0]), unsafe_allow_html=True)

        with metric_col2:
            st.markdown("Positive 👍")
            st.markdown("<h3 style='color: mediumseagreen; margin-top: -20px;'>"+str(feedback_counts[feedback_counts['feedback_type'] == 'thumbs_up']['count'].iloc[0] if 'thumbs_up' in feedback_counts['feedback_type'].values else 0)+"</h1>", unsafe_allow_html=True)

        with metric_col3:
            st.markdown("Negative 👎")
            st.markdown("<h3 style='color: orangered; margin-top: -20px;'>"+str(feedback_counts[feedback_counts['feedback_type'] == 'thumbs_down']['count'].iloc[0] if 'thumbs_down' in feedback_counts['feedback_type'].values else 0)+"</h1>", unsafe_allow_html=True)
            
        with metric_col4:
            st.altair_chart(pie_chart, use_container_width=True)
    else:
        st.info("Ingen 'feedback_type' kolonne funnet i loggene for å lage diagram.")

    st.markdown("---")

    if 'feedback_type' in df_logs.columns and not df_logs.empty:
        df_time_series = df_logs.set_index('timestamp')
        feedback_over_time = df_time_series.groupby([pd.Grouper(freq='D'), 'feedback_type']).size().unstack(fill_value=0)
        
        if 'thumbs_up' not in feedback_over_time.columns:
            feedback_over_time['thumbs_up'] = 0
        if 'thumbs_down' not in feedback_over_time.columns:
            feedback_over_time['thumbs_down'] = 0
            
        feedback_over_time = feedback_over_time.reset_index()
        
        feedback_over_time_long = feedback_over_time.melt(
            id_vars=['timestamp'], 
            value_vars=['thumbs_up', 'thumbs_down'],
            var_name='feedback_type', 
            value_name='count'
        )

        if not feedback_over_time_long.empty:
            feedback_over_time_long['timestamp'] = pd.to_datetime(feedback_over_time_long['timestamp'])

            time_chart = alt.Chart(feedback_over_time_long).mark_area(
                point=alt.OverlayMarkDef(),
                opacity=0.2, 
                line=True    
            ).encode(
                x=alt.X('timestamp:T', title='Dato', axis=alt.Axis(format='%d.%m.%y')), 
                y=alt.Y('count:Q', title='Antall Tilbakemeldinger', stack=None),
                color=alt.Color('feedback_type:N', 
                                scale=color_scale, 
                                legend=alt.Legend(title='Tilbakemeldingstype')),
                tooltip=[
                    alt.Tooltip('timestamp:T', title='Dato', format='%e %b %Y %H:%M'),
                    alt.Tooltip('feedback_type:N', title='Type'),
                    alt.Tooltip('count:Q', title='Antall')
                ]
            ).properties(
                title='Daglig trend av tilbakemeldinger'
            ).interactive()

            st.altair_chart(time_chart, use_container_width=True)
        else:
            st.write("Ingen data for tilbakemeldinger over tid å vise.")
    st.markdown("---")

    st.header("📜 Detaljert loggdata")


    df_logs_filtered = df_logs.copy()

    if 'timestamp' in df_logs_filtered.columns:
        df_logs_filtered['timestamp_dt'] = pd.to_datetime(df_logs_filtered['timestamp'], errors='coerce', utc=True)
        df_logs_filtered.dropna(subset=['timestamp_dt'], inplace=True)
    
    col1, col2 = st.columns(2)

    with col1:
        if 'timestamp_dt' in df_logs_filtered.columns and not df_logs_filtered['timestamp_dt'].empty:
            min_date_val = df_logs_filtered['timestamp_dt'].min().date()
            max_date_val = df_logs_filtered['timestamp_dt'].max().date()
            
            date_range = st.date_input(
                "Velg datoperiode",
                value=(min_date_val, max_date_val),
                min_value=min_date_val,
                max_value=max_date_val,
                key="date_filter_admin"
            )
            if len(date_range) == 2:
                start_date, end_date = date_range
                start_datetime = pd.Timestamp(datetime.combine(start_date, time.min), tz='UTC')
                end_datetime = pd.Timestamp(datetime.combine(end_date, time.max), tz='UTC')
                df_logs_filtered = df_logs_filtered[
                    (df_logs_filtered['timestamp_dt'] >= start_datetime) &
                    (df_logs_filtered['timestamp_dt'] <= end_datetime)
                ]
        else:
            st.caption("Datofiltrering ikke tilgjengelig.")

    with col2:
        if 'feedback_type' in df_logs_filtered.columns:
            unique_feedback_types = df_logs_filtered['feedback_type'].dropna().unique().tolist()
            selected_feedback_types = st.multiselect(
                "Filtrer på tilbakemeldingstype",
                options=unique_feedback_types,
                default=unique_feedback_types,
                key="feedback_type_filter_admin"
            )
            if selected_feedback_types:
                df_logs_filtered = df_logs_filtered[df_logs_filtered['feedback_type'].isin(selected_feedback_types)]
        else:
            st.caption("Filtrering på tilbakemeldingstype ikke tilgjengelig.")

    search_term = st.text_input(
        "Søk i 'user_query' eller 'assistant_response'",
        key="search_term_filter_admin",
        placeholder="Skriv søkeord her..."
    )

    if search_term:
        search_term_lower = search_term.lower()
        query_match = pd.Series([False] * len(df_logs_filtered), dtype=bool)
        response_match = pd.Series([False] * len(df_logs_filtered), dtype=bool)

        if 'user_query' in df_logs_filtered.columns and not df_logs_filtered.empty:
            query_match = df_logs_filtered['user_query'].astype(str).str.lower().str.contains(search_term_lower, na=False)
        if 'assistant_response' in df_logs_filtered.columns and not df_logs_filtered.empty:
            response_match = df_logs_filtered['assistant_response'].astype(str).str.lower().str.contains(search_term_lower, na=False)
        
        if not df_logs_filtered.empty:
            df_logs_filtered = df_logs_filtered[query_match | response_match]
        else: # Handle case where df_logs_filtered might be empty before search
            df_logs_filtered = pd.DataFrame(columns=df_logs.columns) # Keep structure but empty


    if df_logs_filtered.empty:
        st.info("Ingen logger samsvarer med de valgte filtrene.")
    else:
        st.write(f"Fant {df_logs_filtered.shape[0]} loggoppføringer etter filtrering.")
        try:
            df_display = df_logs_filtered.copy()
            
            if 'timestamp' in df_display.columns:
                try:
                    df_display['timestamp'] = pd.to_datetime(df_display['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S UTC')
                except Exception as e:
                    st.warning(f"Kunne ikke formatere 'timestamp'-kolonnen for visning: {e}.")
            
            if 'timestamp_dt' in df_display.columns:
                 df_display = df_display.drop(columns=['timestamp_dt'])

            columns_to_show_preference = [
                'timestamp', 'feedback_type', 'feedback_score_value', 'user_query', 
                'assistant_response', 'message_id', 'preceding_user_message_id'
            ]
            
            existing_columns_in_df = df_display.columns.tolist()
            final_columns_to_display = [col for col in columns_to_show_preference if col in existing_columns_in_df]
            for col in existing_columns_in_df:
                if col not in final_columns_to_display:
                    final_columns_to_display.append(col)
            
            st.dataframe(df_display[final_columns_to_display], use_container_width=True)

            st.markdown("---")
            st.subheader("🔍 Rådata (JSON)")
            st.caption("Klikk på en rad for å se detaljer.")
            
            for index, row in df_logs_filtered.iterrows():
                expander_label = f"Logg #{index + 1} - Tid: {row.get('timestamp').strftime('%Y-%m-%d %H:%M:%S UTC') if pd.notnull(row.get('timestamp')) else 'N/A'} | Type: {row.get('feedback_type', 'N/A')}"
                row_dict = row.to_dict()
                if 'timestamp' in row_dict and pd.notnull(row_dict['timestamp']) and isinstance(row_dict['timestamp'], datetime):
                     row_dict['timestamp'] = row_dict['timestamp'].isoformat()
                if 'timestamp_dt' in row_dict and pd.notnull(row_dict['timestamp_dt']) and isinstance(row_dict['timestamp_dt'], datetime): 
                     row_dict['timestamp_dt'] = row_dict['timestamp_dt'].isoformat()

                with st.expander(expander_label):
                    st.json(row_dict)

        except Exception as e:
            st.error(f"En feil oppstod under behandling av loggdata for DataFrame: {e}")
            st.dataframe(df_logs_filtered.head())


if not st.session_state.get("password_correct"):
    st.warning("Vennligst logg inn via hovedsiden for å få tilgang.")
    if st.button("Gå til innloggingssiden"):
        st.info("Bruk navigasjonen i sidepanelet for å gå til innloggingssiden (hovedsiden).")
else:
    if st.session_state.get("user_identifier") == "admin":
        display_admin_page_content()
    else:
        st.error("Utilgjengelig.")
        st.warning("Du har ikke de nødvendige rettighetene for å se denne siden.")
        st.info(f"Du er logget inn som: {st.session_state.get('user_identifier')}")

