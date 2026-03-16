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
except Exception as e:
    st.error(f"Erreur : {e}")
    st.stop()

# --- DÉTECTION COLONNES ---
col_p = "Prénom" if "Prénom" in df_membres.columns else df_membres.columns[0]
col_m = "Membre" if "Membre" in df_livres.columns else df_livres.columns[2]

def envoyer_whatsapp(telephone, message):
    return f"https://wa.me/{str(telephone).replace(' ', '')}?text={urllib.parse.quote(message)}"

# --- INTERFACE ---
st.title("📚 Le Biblio Club")
utilisateur = st.selectbox("👤 Qui êtes-vous ?", df_membres[col_p].tolist())
infos_user = df_membres[df_membres[col_p] == utilisateur].iloc[0]

st.write("---")
onglets = st.tabs(["📖 Bibliothèque", "🤝 Emprunts", "👤 Mon Profil", "➕ Ajouter", "📤 Import"])

# --- 1. BIBLIOTHÈQUE (AVEC BOUTON DEMANDER) ---
with onglets[0]:
    for idx, row in df_livres.iloc[::-1].iterrows():
        statut = str(row.get('Statut', 'Libre'))
        color = "green" if statut == "Libre" else "orange" if statut == "Demandé" else "red"
        
        with st.container():
            c1, c2 = st.columns([1, 4])
            with c1: st.title("📕")
            with c2:
                st.markdown(f"### {row['Titre']} :{color}[ ({statut})]")
                st.write(f"**Auteur :** {row.get('Auteur')} | **Proprio :** {row.get(col_m)}")
                
                if row.get('Avis_delire'):
                    st.success(f"💬 **Avis :** {row['Avis_delire']}")
                
                # BOUTON DEMANDER
                if statut == "Libre" and row.get(col_m) != utilisateur:
                    if st.button(f"Demander ce livre", key=f"req_{idx}"):
                        # Mise à jour dans Google Sheets (Ligne idx+2 car index 0 = ligne 2)
                        sheet_livres.update_cell(idx + 2, 5, "Demandé")
                        sheet_livres.update_cell(idx + 2, 6, utilisateur)
                        st.success("Demande envoyée ! Le propriétaire la verra sur son profil.")
                        st.rerun()
            st.write("---")

# --- 2. EMPRUNTS ---
with onglets[1]:
    st.subheader("🤝 Livres en mouvement")
    mask = df_livres['Statut'].isin(['Demandé', 'Emprunté'])
    if not df_livres[mask].empty:
        st.table(df_livres[mask][['Titre', col_m, 'Emprunteur', 'Statut']])
    else:
        st.info("Rien à signaler !")

# --- 3. MON PROFIL (GESTION DES DEMANDES) ---
with onglets[2]:
    st.subheader(f"Espace de {utilisateur}")
    mes_livres = df_livres[df_livres[col_m] == utilisateur]
    
    if not mes_livres.empty:
        for idx, row in mes_livres.iterrows():
            st.write(f"📙 **{row['Titre']}**")
            statut_actuel = row.get('Statut')
            
            if statut_actuel == "Demandé":
                demandeur = row.get('Emprunteur')
                st.warning(f"🔔 {demandeur} souhaite emprunter ce livre")
                
                if st.button(f"✅ Accepter la demande de {demandeur}", key=f"ok_{idx}"):
                    sheet_livres.update_cell(idx + 2, 5, "Emprunté")
                    tel_d = df_membres[df_membres[col_p] == demandeur].iloc[0].get('Téléphone', '')
                    msg = f"Hello {demandeur} ! C'est {utilisateur}. Ok pour '{row['Titre']}' ! Retrait : {infos_user.get('Infos_Retrait', 'Contacte-moi !')}"
                    st.link_button("📱 Envoyer confirmation WhatsApp", envoyer_whatsapp(tel_d, msg))
            
            elif statut_actuel == "Emprunté":
                if st.button(f"🔄 Marquer comme rendu", key=f"back_{idx}"):
                    sheet_livres.update_cell(idx + 2, 5, "Libre")
                    sheet_livres.update_cell(idx + 2, 6, "")
                    st.rerun()
            st.write("---")

# --- 4 & 5 (AJOUT / IMPORT) ---
with onglets[3]:
    with st.form("add_vfinal"):
        t, a = st.text_input("Titre"), st.text_input("Auteur")
        note = st.select_slider("Note", options=["📚", "📚📚", "📚📚📚", "📚📚📚📚"])
        com = st.text_area("Commentaire")
        if st.form_submit_button("Ajouter"):
            sheet_livres.append_row([t, a, utilisateur, f"{note} {com}", "Libre", ""])
            st.success("Ajouté !"); st.rerun()

with onglets[4]:
    up = st.file_uploader("Fichier Excel", type="xlsx")
    if up and st.button("Lancer l'import"):
        df_im = pd.read_excel(up)
        for _, r in df_im.iterrows():
            sheet_livres.append_row([r['Titre'], r.get('Auteur',''), utilisateur, r.get('Avis_delire',''), "Libre", ""])
        st.success("Import réussi !"); st.rerun()

st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
