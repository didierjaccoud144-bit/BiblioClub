import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import urllib.parse

# --- CONFIGURATION ---
st.set_page_config(page_title="Biblio Club", page_icon="📚", layout="centered")

def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"].to_dict()
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

# --- CHARGEMENT ---
try:
    client = get_gspread_client()
    spreadsheet = client.open("BiblioClub_Data") 
    sheet_membres = spreadsheet.worksheet("Membres")
    sheet_livres = spreadsheet.worksheet("Livres")
    df_membres = pd.DataFrame(sheet_membres.get_all_records())
    df_livres = pd.DataFrame(sheet_livres.get_all_records())
    df_livres.columns = [c.strip() for c in df_livres.columns]
    df_membres.columns = [c.strip() for c in df_membres.columns]
except Exception as e:
    st.error(f"Erreur : {e}")
    st.stop()

# --- DÉTECTION COLONNES ---
def find_col(df, names):
    for n in names:
        if n in df.columns: return n
    return df.columns[0]

c_titre = find_col(df_livres, ["Titre"])
c_auteur = find_col(df_livres, ["Auteur"])
c_proprio = find_col(df_livres, ["Maître", "Maitre", "Membre"])
c_statut = find_col(df_livres, ["Statut"])
c_emprunteur = find_col(df_livres, ["Squatteur", "Emprunteur"])
c_avis = find_col(df_livres, ["Avis_Delire", "Avis"])
col_p = find_col(df_membres, ["Prénom", "Nom"])

def envoyer_wa(tel, msg):
    return f"https://wa.me/{str(tel).replace(' ', '')}?text={urllib.parse.quote(msg)}"

# --- INTERFACE ---
st.title("📚 Le Biblio Club")
utilisateur = st.selectbox("👤 Qui êtes-vous ?", df_membres[col_p].tolist())
infos_user = df_membres[df_membres[col_p] == utilisateur].iloc[0]

st.write("---")
onglets = st.tabs(["📖 Bibliothèque", "🤝 Emprunts", "👤 Mon Profil", "➕ Ajouter", "📤 Import"])

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
    for idx, row in df_livres.iloc[::-1].iterrows():
        s = str(row.get(c_statut, 'Libre')).strip()
        statut = s if s != "" else "Libre"
        color = "green" if statut == "Libre" else "orange" if statut == "Demandé" else "red"
        
        with st.container():
            c1, c2 = st.columns([1, 4])
            with c1: st.title("📕")
            with c2:
                st.markdown(f"### {row[c_titre]} :{color}[ ({statut})]")
                st.write(f"**Auteur :** {row[c_auteur]} | **Proprio :** {row[c_proprio]}")
                if row.get(c_avis): st.success(f"💬 {row[c_avis]}")
                
                if statut == "Libre" and str(row[c_proprio]) != utilisateur:
                    if st.button(f"Demander ce livre", key=f"req_{idx}"):
                        sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_statut)+1, "Demandé")
                        sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_emprunteur)+1, utilisateur)
                        st.success("Demande envoyée !"); st.rerun()
            st.write("---")

# --- 2. EMPRUNTS ---
with onglets[1]:
    st.subheader("🤝 Livres en mouvement")
    mask = df_livres[c_statut].isin(['Demandé', 'Emprunté'])
    if not df_livres[mask].empty:
        st.dataframe(df_livres[mask][[c_titre, c_proprio, c_emprunteur, c_statut]], hide_index=True)
    else: st.info("Tout est en rayon !")

# --- 3. MON PROFIL (LOGIQUE DE DÉCISION) ---
with onglets[2]:
    st.subheader(f"Espace de {utilisateur}")
    mes_livres = df_livres[df_livres[c_proprio] == utilisateur]
    
    if not mes_livres.empty:
        for idx, row in mes_livres.iterrows():
            st.write(f"📙 **{row[c_titre]}**")
            statut_actuel = str(row.get(c_statut, ''))
            
            if statut_actuel == "Demandé":
                demandeur = row.get(c_emprunteur)
                st.warning(f"🔔 {demandeur} attend votre réponse pour ce livre.")
                
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.button(f"✅ Valider le prêt", key=f"ok_{idx}"):
                        sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_statut)+1, "Emprunté")
                        tel_d = df_membres[df_membres[col_p] == demandeur].iloc[0].get('Téléphone', '')
                        msg = f"Hello {demandeur} ! C'est {utilisateur}. Prêt OK pour '{row[c_titre]}' ! Retrait : {infos_user.get('Coordonnees', 'Contacte-moi !')}"
                        st.link_button("📱 WhatsApp de confirmation", envoyer_wa(tel_d, msg))
                with col_b2:
                    if st.button(f"❌ Refuser", key=f"no_{idx}"):
                        sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_statut)+1, "Libre")
                        sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_emprunteur)+1, "")
                        st.rerun()
            
            elif statut_actuel == "Emprunté":
                if st.button(f"🔄 Livre rendu / Clôturer", key=f"end_{idx}"):
                    sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_statut)+1, "Libre")
                    sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_emprunteur)+1, "")
                    st.rerun()
            st.write("---")

# --- 4 & 5 (AJOUT / IMPORT) ---
with onglets[3]:
    with st.form("add"):
        t, a = st.text_input("Titre"), st.text_input("Auteur")
        note = st.select_slider("Note", options=["📚", "📚📚", "📚📚📚", "📚📚📚📚"])
        com = st.text_area("Avis")
        if st.form_submit_button("Ajouter"):
            sheet_livres.append_row(["", t, a, utilisateur, "", "", f"{note} {com}", "Libre"])
            st.success("Ajouté !"); st.rerun()

with onglets[4]:
    up = st.file_uploader("Excel", type="xlsx")
    if up and st.button("Importer"):
        df_im = pd.read_excel(up)
        for _, r in df_im.iterrows():
            sheet_livres.append_row(["", r['Titre'], r.get('Auteur',''), utilisateur, "", "", r.get('Avis_delire',''), "Libre"])
        st.success("Fait !"); st.rerun()

st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
