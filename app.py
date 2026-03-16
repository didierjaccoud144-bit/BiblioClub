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
    
    # Nettoyage automatique des noms de colonnes et des données
    df_livres.columns = [c.strip() for c in df_livres.columns]
    df_membres.columns = [c.strip() for c in df_membres.columns]
except Exception as e:
    st.error(f"Erreur de connexion : {e}")
    st.stop()

# --- CONFIG COLONNES ---
col_p = "Prénom" if "Prénom" in df_membres.columns else df_membres.columns[0]
c_titre = "Titre"
c_proprio = "Maître" if "Maître" in df_livres.columns else "Maitre"
c_statut = "Statut"
c_squat = "Squatteur"

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
                st.write(f"**Auteur :** {row.get('Auteur')} | **Proprio :** {row.get(c_proprio)}")
                
                # BOUTON DEMANDER
                if statut == "Libre" and str(row.get(c_proprio)).strip() != utilisateur.strip():
                    if st.button(f"Demander ce livre", key=f"req_{idx}"):
                        sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_statut)+1, "Demandé")
                        sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_squat)+1, utilisateur)
                        st.success("Demande envoyée !"); st.rerun()
            st.write("---")

# --- 2. EMPRUNTS ---
with onglets[1]:
    mask = df_livres[c_statut].isin(['Demandé', 'Emprunté'])
    if not df_livres[mask].empty:
        st.table(df_livres[mask][[c_titre, c_proprio, c_squat, c_statut]])
    else: st.info("Rien en mouvement.")

# --- 3. MON PROFIL (LE CENTRE DE COMMANDE) ---
with onglets[2]:
    st.subheader(f"Espace de {utilisateur}")
    
    # On filtre les livres en étant TRÈS tolérant sur les espaces
    mes_livres = df_livres[df_livres[c_proprio].astype(str).str.strip() == utilisateur.strip()]
    
    if not mes_livres.empty:
        for idx, row in mes_livres.iterrows():
            st.markdown(f"📙 **{row[c_titre]}**")
            s = str(row.get(c_statut, '')).strip()
            
            if s == "Demandé":
                demandeur = row.get(c_squat)
                st.warning(f"🔔 {demandeur} attend ta réponse !")
                
                col_a, col_r = st.columns(2)
                with col_a:
                    if st.button(f"✅ Accepter {demandeur}", key=f"ok_{idx}"):
                        sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_statut)+1, "Emprunté")
                        tel_d = df_membres[df_membres[col_p] == demandeur].iloc[0].get('Téléphone', '')
                        msg = f"Hello {demandeur} ! C'est {utilisateur}. Prêt OK pour '{row[c_titre]}' ! Retrait : {infos_user.get('Coordonnees', 'Contacte-moi !')}"
                        st.link_button("📱 WhatsApp", envoyer_wa(tel_d, msg))
                with col_r:
                    if st.button(f"❌ Refuser", key=f"no_{idx}"):
                        sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_statut)+1, "Libre")
                        sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_squat)+1, "")
                        st.rerun()
            
            elif s == "Emprunté":
                if st.button(f"🔄 Marquer comme Rendu", key=f"end_{idx}"):
                    sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_statut)+1, "Libre")
                    sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_squat)+1, "")
                    st.rerun()
            else:
                st.write("✅ En rayon")
            st.write("---")
    else:
        st.info("Aucun livre trouvé à votre nom. Vérifiez que votre prénom est identique dans l'onglet Livres et Membres !")

# --- 4 & 5 (AJOUT/IMPORT) ---
with onglets[3]:
    with st.form("add"):
        t, a = st.text_input("Titre"), st.text_input("Auteur")
        n = st.select_slider("Note", options=["📚","📚📚","📚📚📚","📚📚📚📚"])
        if st.form_submit_button("Ajouter"):
            sheet_livres.append_row(["", t, a, utilisateur, "", "", n, "Libre"])
            st.rerun()

with onglets[4]:
    up = st.file_uploader("Excel", type="xlsx")
    if up and st.button("Importer"):
        df_im = pd.read_excel(up)
        for _, r in df_im.iterrows():
            sheet_livres.append_row(["", r['Titre'], r.get('Auteur',''), utilisateur, "", "", "", "Libre"])
        st.success("Fait !"); st.rerun()

st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
