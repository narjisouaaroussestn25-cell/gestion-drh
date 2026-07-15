import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime
from fpdf import FPDF # PDF

st.set_page_config(page_title="Suivi DRH", page_icon="📊", layout="wide")

# ====== التصميم الجديد: كحل + ذهبي ======
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    html, body, [class*="st-"] {
        font-family: 'Cairo', sans-serif;
        color: #E0E0E0; /* الكتابة كلها بيضاء */
    }
  .stApp {
        background-color:blue /* كحل غامق */
    }
    /* 1. الهيدر الذهبي */
    h1 {
        color: #FFFFFF!important;
        border-bottom: 3px solid #C8A25A; /* خط ذهبي لتحت */
        padding-bottom: 10px;
    }
    h2, h3, h4 {
        color: #FFFFFF!important;
    }
    /* 2. الـ Tabs */
    div[data-testid="stTabs"] button[aria-selected="true"] {
        color: #C8A25A!important; /* ذهبي */
        border-bottom: 3px solid #C8A25A!important;
        font-weight: 700;
    }
    div[data-testid="stTabs"] button {
        color: #A0A0A0;
        font-size: 16px;
    }
    /* 3. الـ Metrics بحال Cartes كحلة */
    div[data-testid="stMetricContainer"] {
        background-color: #1E222B; /* كحل فاتح شوية */
        border-left: 5px solid #C8A25A; /* خط ذهبي جانبي */
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        transition: all 0.3s;
    }
    div[data-testid="stMetricContainer"]:hover {
        background-color: #2A2F3A; /* كيضوي منين كدوز */
    }
    div[data-testid="stMetricLabel"] { color: #B0B0B0!important; font-weight: 600; }
    div[data-testid="stMetricValue"] { color: #FFFFFF!important; font-size: 28px!important; }

    /* 4. البوتنات */
  .stButton>button {
        background-color: #C8A25A; /* ذهبي */
        color: #0E1117; /* كحل */
        border-radius: 8px;
        border: none;
        font-weight: 700;
    }
  .stButton>button:hover {
        background-color: #E0B96A;
    }
    /* 5. Sidebar */
    [data-testid="stSidebar"] {
        background-color: #0A0D12;
    }
    [data-testid="stSidebar"] * { color: white!important; }

    /* الجداول */
    [data-testid="stDataFrame"] { background-color: #1E222B; }
    </style>
    """, unsafe_allow_html=True)

DB_PASSWORD = ""

def get_conn():
    return mysql.connector.connect(host="localhost", user="root", password=DB_PASSWORD, database="drh_supply_db")

@st.cache_data
def get_kpi_data():
    conn = get_conn()
    today = datetime.now().date().strftime('%Y-%m-%d')

    nb_articles = pd.read_sql("SELECT COUNT(*) as total FROM prestations", conn).iloc[0,0]
    nb_mouvements = pd.read_sql("SELECT COUNT(*) as total FROM details_demande", conn).iloc[0,0]
    top_sortie = pd.read_sql("""
        SELECT p.designation, SUM(dt.quantite) as Total_Sortie
        FROM details_demande dt JOIN prestations p ON dt.id_prestation = p.id_prestation
        WHERE dt.type_mouvement = 'Sortie' GROUP BY p.designation ORDER BY Total_Sortie DESC LIMIT 5
    """, conn)
    stock_df = pd.read_sql("""
        SELECT p.designation, COALESCE(SUM(CASE WHEN dt.type_mouvement = 'Entrée' THEN dt.quantite ELSE 0 END), 0) -
        COALESCE(SUM(CASE WHEN dt.type_mouvement = 'Sortie' THEN dt.quantite ELSE 0 END), 0) AS Stock
        FROM prestations p LEFT JOIN details_demande dt ON p.id_prestation = dt.id_prestation GROUP BY p.id_prestation
    """, conn)
    entree_total = pd.read_sql("""SELECT COALESCE(SUM(quantite), 0) as total FROM details_demande WHERE type_mouvement = 'Entrée'""", conn).iloc[0,0]
    sortie_total = pd.read_sql("""SELECT COALESCE(SUM(quantite), 0) as total FROM details_demande WHERE type_mouvement = 'Sortie'""", conn).iloc[0,0]
    entree_jour = pd.read_sql(f"""SELECT COALESCE(SUM(dt.quantite), 0) as total FROM details_demande dt JOIN demandes d ON dt.id_demande = d.id_demande WHERE dt.type_mouvement = 'Entrée' AND DATE(d.date_demande) = '{today}'""", conn).iloc[0,0]
    sortie_jour = pd.read_sql(f"""SELECT COALESCE(SUM(dt.quantite), 0) as total FROM details_demande dt JOIN demandes d ON dt.id_demande = d.id_demande WHERE dt.type_mouvement = 'Sortie' AND DATE(d.date_demande) = '{today}'""", conn).iloc[0,0]

    conn.close()
    return nb_articles, nb_mouvements, top_sortie, stock_df.fillna(0), entree_total, sortie_total, entree_jour, sortie_jour

@st.cache_data
def get_prestations_all():
    conn = get_conn()
    df = pd.read_sql("SELECT id_prestation, designation FROM prestations ORDER BY designation", conn)
    conn.close()
    return df

@st.cache_data
def get_prestations_utilisees():
    conn = get_conn()
    df = pd.read_sql("SELECT DISTINCT p.id_prestation, p.designation FROM prestations p INNER JOIN details_demande dt ON p.id_prestation = dt.id_prestation ORDER BY p.designation", conn)
    conn.close()
    return df

@st.cache_data
def get_historique_regroupe():
    conn = get_conn()
    query = """SELECT p.id_prestation, ROW_NUMBER() OVER (ORDER BY p.designation) AS 'N°', p.designation AS 'Désignation',
    DATE_FORMAT((SELECT MAX(d2.date_demande) FROM details_demande dt2 JOIN demandes d2 ON dt2.id_demande = d2.id_demande WHERE dt2.id_prestation = p.id_prestation AND dt2.type_mouvement = 'Entrée'), '%d/%m/%Y %H:%i') AS 'Date Entrée',
    (SELECT dt2.quantite FROM details_demande dt2 JOIN demandes d2 ON dt2.id_demande = d2.id_demande WHERE dt2.id_prestation = p.id_prestation AND dt2.type_mouvement = 'Entrée' ORDER BY d2.date_demande DESC LIMIT 1) AS 'Qté Entrée',
    (SELECT dt2.observation FROM details_demande dt2 JOIN demandes d2 ON dt2.id_demande = d2.id_demande WHERE dt2.id_prestation = p.id_prestation AND dt2.type_mouvement = 'Entrée' ORDER BY d2.date_demande DESC LIMIT 1) AS 'Obs Entrée',
    DATE_FORMAT((SELECT MAX(d2.date_demande) FROM details_demande dt2 JOIN demandes d2 ON dt2.id_demande = d2.id_demande WHERE dt2.id_prestation = p.id_prestation AND dt2.type_mouvement = 'Sortie'), '%d/%m/%Y %H:%i') AS 'Date Sortie',
    (SELECT dt2.quantite FROM details_demande dt2 JOIN demandes d2 ON dt2.id_demande = d2.id_demande WHERE dt2.id_prestation = p.id_prestation AND dt2.type_mouvement = 'Sortie' ORDER BY d2.date_demande DESC LIMIT 1) AS 'Qté Sortie',
    (SELECT dt2.observation FROM details_demande dt2 JOIN demandes d2 ON dt2.id_demande = d2.id_demande WHERE dt2.id_prestation = p.id_prestation AND dt2.type_mouvement = 'Sortie' ORDER BY d2.date_demande DESC LIMIT 1) AS 'Obs Sortie'
    FROM prestations p WHERE EXISTS (SELECT 1 FROM details_demande dt WHERE dt.id_prestation = p.id_prestation) ORDER BY p.designation"""
    df = pd.read_sql(query, conn)
    conn.close()
    return df.fillna('-')

@st.cache_data
def get_stock_detaille():
    conn = get_conn()
    query = """SELECT p.designation AS 'Désignation', DATE_FORMAT((SELECT MAX(d2.date_demande) FROM details_demande dt2 JOIN demandes d2 ON dt2.id_demande = d2.id_demande WHERE dt2.id_prestation = p.id_prestation AND dt2.type_mouvement = 'Entrée'), '%d/%m/%Y %H:%i') AS 'Entrée Date',
    (SELECT dt2.quantite FROM details_demande dt2 JOIN demandes d2 ON dt2.id_demande = d2.id_demande WHERE dt2.id_prestation = p.id_prestation AND dt2.type_mouvement = 'Entrée' ORDER BY d2.date_demande DESC LIMIT 1) AS 'Entrée Qté',
    (SELECT dt2.observation FROM details_demande dt2 JOIN demandes d2 ON dt2.id_demande = d2.id_demande WHERE dt2.id_prestation = p.id_prestation AND dt2.type_mouvement = 'Entrée' ORDER BY d2.date_demande DESC LIMIT 1) AS 'Entrée Obs',
    DATE_FORMAT((SELECT MAX(d2.date_demande) FROM details_demande dt2 JOIN demandes d2 ON dt2.id_demande = d2.id_demande WHERE dt2.id_prestation = p.id_prestation AND dt2.type_mouvement = 'Sortie'), '%d/%m/%Y %H:%i') AS 'Sortie Date',
    (SELECT dt2.quantite FROM details_demande dt2 JOIN demandes d2 ON dt2.id_demande = d2.id_demande WHERE dt2.id_prestation = p.id_prestation AND dt2.type_mouvement = 'Sortie' ORDER BY d2.date_demande DESC LIMIT 1) AS 'Sortie Qté',
    (SELECT dt2.observation FROM details_demande dt2 JOIN demandes d2 ON dt2.id_demande = d2.id_demande WHERE dt2.id_prestation = p.id_prestation AND dt2.type_mouvement = 'Sortie' ORDER BY d2.date_demande DESC LIMIT 1) AS 'Sortie Obs',
    COALESCE(SUM(CASE WHEN dt.type_mouvement = 'Entrée' THEN dt.quantite ELSE 0 END), 0) - COALESCE(SUM(CASE WHEN dt.type_mouvement = 'Sortie' THEN dt.quantite ELSE 0 END), 0) AS 'Stock'
    FROM prestations p LEFT JOIN details_demande dt ON p.id_prestation = dt.id_prestation LEFT JOIN demandes d ON dt.id_demande = d.id_demande GROUP BY p.id_prestation, p.designation ORDER BY p.designation"""
    df = pd.read_sql(query, conn)
    conn.close()
    return df.fillna('-')

@st.cache_data
def get_mouvements_by_article(id_prestation):
    conn = get_conn()
    query = """SELECT dt.type_mouvement AS 'Type', DATE_FORMAT(d.date_demande, '%d/%m/%Y %H:%i') AS 'Date', dt.quantite AS 'Qté', dt.observation AS 'Obs'
    FROM details_demande dt JOIN demandes d ON dt.id_demande = d.id_demande WHERE dt.id_prestation = %s ORDER BY d.date_demande DESC"""
    df = pd.read_sql(query, conn, params=(id_prestation,))
    conn.close()
    return df.fillna('-')

def ajouter_prestation(nouvelle_designation):
    conn = get_conn(); cursor = conn.cursor()
    try: cursor.execute("INSERT INTO prestations (designation, categorie) VALUES (%s, %s)", (nouvelle_designation, 'Divers')); conn.commit(); return cursor.lastrowid
    except Exception as e: conn.rollback(); st.error(f"Erreur ajout article: {e}"); return None
    finally: cursor.close(); conn.close()

def supprimer_prestation(id_prestation):
    conn = get_conn(); cursor = conn.cursor()
    try: cursor.execute("DELETE d FROM demandes d JOIN details_demande dt ON d.id_demande = dt.id_demande WHERE dt.id_prestation = %s", (id_prestation,)); cursor.execute("DELETE FROM prestations WHERE id_prestation = %s", (id_prestation,)); conn.commit(); return True
    except Exception as e: conn.rollback(); st.error(f"Erreur suppression: {e}"); return False
    finally: cursor.close(); conn.close()

def enregistrer_mouvement(id_prestation, type_mv, quantite, observation, datetime_mv):
    conn = get_conn(); cursor = conn.cursor()
    try: cursor.execute("INSERT INTO demandes (date_demande) VALUES (%s)", (datetime_mv,)); id_demande = cursor.lastrowid; cursor.execute("INSERT INTO details_demande (id_demande, id_prestation, type_mouvement, quantite, observation) VALUES (%s, %s, %s, %s, %s)", (id_demande, id_prestation, type_mv, quantite, observation)); conn.commit(); return True
    except Exception as e: conn.rollback(); st.error(f"Erreur: {e}"); return False
    finally: cursor.close(); conn.close()

def generer_pdf_article(df, designation, date_debut, date_fin):
    def clean(txt): return str(txt).encode('latin-1', 'replace').decode('latin-1')
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page(); pdf.set_font('Arial', 'B', 14); pdf.cell(0, 10, clean(f'Historique Article: {designation}'), 0, 1, 'C')
    pdf.set_font('Arial', '', 10); pdf.cell(0, 8, clean(f'Periode: du {date_debut} au {date_fin}'), 0, 1, 'C'); pdf.ln(5)
    pdf.set_font('Arial', 'B', 8); col_widths = [45, 20, 30, 15, 30, 15, 45]
    headers = ['Designation', 'Type', 'Date Entree', 'Qte E', 'Date Sortie', 'Qte S', 'Observation']
    for i, header in enumerate(headers): pdf.cell(col_widths[i], 8, clean(header), 1, 0, 'C')
    pdf.ln()
    pdf.set_font('Arial', '', 7)
    for index, row in df.iterrows():
        pdf.cell(col_widths[0], 7, clean(str(row['Désignation'])[:40]), 1); pdf.cell(col_widths[1], 7, clean(str(row['Type'])), 1, 0, 'C')
        pdf.cell(col_widths[2], 7, clean(str(row['Date Entree'])), 1); pdf.cell(col_widths[3], 7, clean(str(row['Qte Entree'])), 1, 0, 'C')
        pdf.cell(col_widths[4], 7, clean(str(row['Date Sortie'])), 1); pdf.cell(col_widths[5], 7, clean(str(row['Qte Sortie'])), 1, 0, 'C')
        pdf.cell(col_widths[6], 7, clean(str(row['Observation'])[:40]), 1); pdf.ln()
    return bytes(pdf.output())

st.title("📊 Application de Suivi des Demandes de Fournitures - DRH")

with st.sidebar:
    st.markdown("### ⚠️ Zone Dangereuse")
    if st.button("🚨 Réinitialiser TOUTE la base", type="primary", use_container_width=True): st.session_state.confirm_reset = True
    if st.session_state.get('confirm_reset', False):
        st.warning("Ceci va supprimer TOUT: Articles + Entrées + Sorties. Irréversible!")
        if st.checkbox("Je confirme la suppression totale"):
            if st.button("✅ Oui, Supprimer tout"):
                conn = get_conn(); cursor = conn.cursor()
                try: cursor.execute("SET FOREIGN_KEY_CHECKS = 0"); cursor.execute("TRUNCATE TABLE details_demande"); cursor.execute("TRUNCATE TABLE demandes"); cursor.execute("TRUNCATE TABLE prestations"); cursor.execute("SET FOREIGN_KEY_CHECKS = 1"); conn.commit(); st.success("✅ Base réinitialisée! Tout est vide."); st.session_state.confirm_reset = False; st.cache_data.clear(); st.rerun()
                except Exception as e: conn.rollback(); st.error(f"Erreur: {e}")
                finally: cursor.close(); conn.close()

st.markdown("---")
tab0, tab1, tab2, tab3, tab4 = st.tabs(["📊 Tableau de Bord", "📋 Historique Général", "➕ Nouvelle Mouvement", "📦 Stock Détail", "🔍 Par Article"])

with tab0:
    st.subheader("📊 Vue d'ensemble")
    nb_art, nb_mvt, top5, stock_df, entree_total, sortie_total, entree_jour, sortie_jour = get_kpi_data()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("📥 Total Entrées", f"{entree_total}")
    col2.metric("📤 Total Sorties", f"{sortie_total}")
    col3.metric("📉 Rupture", f"{len(stock_df[stock_df['Stock'] <= 0])}")
    col4.metric("📈 Entrées Auj", f"{entree_jour}")
    col5.metric("📉 Sorties Auj", f"{sortie_jour}")

    st.markdown("---")
    col_g, col_d = st.columns(2)
    with col_g:
        st.write("#### 🔥 Top 5 Articles les plus consommés")
        if not top5.empty: st.bar_chart(top5, x='designation', y='Total_Sortie', use_container_width=True)
        else: st.info("Aucune sortie enregistrée.")
    with col_d:
        st.write("#### ⚠️ Articles Stock Faible < 2")
        stock_faible = stock_df[stock_df['Stock'] < 2].sort_values('Stock')
        if not stock_faible.empty:
            st.dataframe(stock_faible, hide_index=True, use_container_width=True)
        else:
            st.success("✅ Tous les stocks sont OK > 2.")

with tab1:
    st.subheader("Historique Général"); st.warning("⚠️ Supprimer un article supprime aussi tout son historique Entrée/Sortie.")
    df_hist = get_historique_regroupe(); recherche = st.text_input("🔍 Rechercher une Désignation", placeholder="Tapez ici...")
    if recherche: df_hist = df_hist[df_hist['Désignation'].str.contains(recherche, case=False, na=False)]
    header_cols = st.columns([0.5, 3, 1.5, 1, 1.5, 1.5, 1, 1.5, 1])
    header_cols[0].markdown("**N°**"); header_cols[1].markdown("**Désignation**"); header_cols[2].markdown("**Date Entrée**"); header_cols[3].markdown("**Qté**"); header_cols[4].markdown("**Obs**"); header_cols[5].markdown("**Date Sortie**"); header_cols[6].markdown("**Qté**"); header_cols[7].markdown("**Obs**"); header_cols[8].markdown("**Action**"); st.markdown("---")
    for index, row in df_hist.iterrows():
        cols = st.columns([0.5, 3, 1.5, 1, 1.5, 1.5, 1, 1.5, 1])
        cols[0].write(row['N°']); cols[1].write(row['Désignation']); cols[2].write(row['Date Entrée']); cols[3].write(row['Qté Entrée']); cols[4].write(row['Obs Entrée']); cols[5].write(row['Date Sortie']); cols[6].write(row['Qté Sortie']); cols[7].write(row['Obs Sortie'])
        with cols[8]:
            if st.button("🗑️", key=f"del_{row['id_prestation']}", help=f"Supprimer {row['Désignation']}"):
                if supprimer_prestation(int(row['id_prestation'])): st.success(f"Article '{row['Désignation']}' et son historique supprimés."); st.cache_data.clear(); st.rerun()
        st.markdown("---")

with tab2:
    st.subheader("Ajouter une Entrée ou Sortie"); prestations = get_prestations_all()
    if 'ajouter_mode' not in st.session_state: st.session_state.ajouter_mode = False
    if st.button("➕ Ajouter nouvel article"): st.session_state.ajouter_mode = not st.session_state.ajouter_mode
    if st.session_state.ajouter_mode:
        nouvelle = st.text_input("Nom du nouvel article:", placeholder="Ex: Stylos rouge"); col_a, col_b = st.columns(2)
        if col_a.button("✅ Confirmer"):
            if nouvelle.strip(): new_id = ajouter_prestation(nouvelle.strip())
            if new_id: st.success(f"✅ '{nouvelle}' ajouté!"); st.session_state.ajouter_mode = False; st.cache_data.clear(); st.rerun()
        if col_b.button("❌ Annuler"): st.session_state.ajouter_mode = False; st.rerun(); st.markdown("---")
    with st.form(key="mouvement_form", clear_on_submit=True):
        prestations = get_prestations_all(); designation_choisie = st.selectbox("1. Sélectionner Désignation", options=prestations['designation'].tolist(), index=None, placeholder="Choisir un article...")
        type_mv = st.radio("2. Type de mouvement", ["Entrée", "Sortie"], horizontal=True); col_date, col_heure = st.columns(2)
        with col_date: date_mv = st.date_input("📅 Date", value=datetime.now().date(), format="DD/MM/YYYY")
        with col_heure: heure_mv = st.time_input("🕐 Heure", value=datetime.now().time())
        datetime_complet = datetime.combine(date_mv, heure_mv); quantite = st.number_input("3. Quantité", min_value=1, value=1); observation = st.text_input("4. Observation")
        if st.form_submit_button("💾 Enregistrer", type="primary", use_container_width=True):
            if designation_choisie:
                id_prest = int(prestations[prestations['designation'] == designation_choisie]['id_prestation'].values[0])
                if enregistrer_mouvement(id_prest, type_mv, int(quantite), observation, datetime_complet): st.success(f"✅ {type_mv} enregistrée le {datetime_complet.strftime('%d/%m/%Y à %H:%M')}!"); st.cache_data.clear()
            else: st.warning("⚠️ Sélectionnez un article d'abord")

with tab3:
    st.subheader("📦 Stock Détail"); df_stock = get_stock_detaille(); st.dataframe(df_stock, use_container_width=True, height=600, hide_index=True)

with tab4:
    st.subheader("🔍 Historique par Article")
    prestations = get_prestations_utilisees()
    if not prestations.empty:
        article_choisi = st.selectbox("1. Article", options=prestations['designation'].tolist(), index=None, placeholder="Choisir...")
        if article_choisi:
            id_prest = int(prestations[prestations['designation'] == article_choisi]['id_prestation'].values[0]); df_mouv_complet = get_mouvements_by_article(id_prest)
            type_choisi = st.selectbox("2. Type", options=["Tous les types", "Entrée", "Sortie"], index=0); col_date1, col_date2 = st.columns(2)
            with col_date1: date_debut = st.date_input("3. Date Début", value=datetime.now().date().replace(day=1), format="DD/MM/YYYY")
            with col_date2: date_fin = st.date_input("4. Date Fin", value=datetime.now().date(), format="DD/MM/YYYY")
            df_mouv_complet['Date_dt'] = pd.to_datetime(df_mouv_complet['Date'], format='%d/%m/%Y %H:%M'); df_filtre = df_mouv_complet
            if type_choisi!= "Tous les types": df_filtre = df_filtre[df_filtre['Type'] == type_choisi]
            df_filtre = df_filtre[(df_filtre['Date_dt'].dt.date >= date_debut) & (df_filtre['Date_dt'].dt.date <= date_fin)]
            df_pdf = pd.DataFrame()
            if not df_filtre.empty:
                entrees = df_filtre[df_filtre['Type'] == 'Entrée'].sort_values('Date_dt', ascending=False); sorties = df_filtre[df_filtre['Type'] == 'Sortie'].sort_values('Date_dt', ascending=False); max_len = max(len(entrees), len(sorties))

                # ====== CORRECTION ICI POUR EVITER ValueError ======
                obs_entrees = list(entrees['Obs'])
                obs_sorties = list(sorties['Obs'])
                obs_combined = obs_entrees + obs_sorties
                obs_combined += ['-'] * (max_len - len(obs_combined))
                obs_combined = obs_combined[:max_len]
                # ===================================================

                data = {'Désignation': [article_choisi]*max_len, 'Type': ['-']*max_len, 'Date Entree': list(entrees['Date']) + ['-']*(max_len-len(entrees)), 'Qte Entree': list(entrees['Qté']) + ['-']*(max_len-len(entrees)), 'Date Sortie': list(sorties['Date']) + ['-']*(max_len-len(sorties)), 'Qte Sortie': list(sorties['Qté']) + ['-']*(max_len-len(sorties)), 'Observation': obs_combined,}
                df_pdf = pd.DataFrame(data).fillna('-')
            st.write(f"### Historique de: **{article_choisi}** du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}")
            if not df_filtre.empty:
                st.dataframe(df_filtre.drop(columns=['Date_dt']), use_container_width=True, hide_index=True)
                pdf_bytes = generer_pdf_article(df_pdf, article_choisi, date_debut.strftime('%d/%m/%Y'), date_fin.strftime('%d/%m/%Y'))
                st.download_button(label="📄 Télécharger PDF", data=pdf_bytes, file_name=f"Historique_{article_choisi}.pdf", mime="application/pdf", use_container_width=True)
            else: st.info("Aucun mouvement trouvé pour ces filtres.")
    else: st.info("Aucun article enregistré pour le moment.")