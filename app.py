import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import urllib.parse
from datetime import datetime, timedelta

# Importation du fichier de profil membres
from membres_profil import get_membre_info, get_liste_membres_fixes

# --- CONFIGURATION ---
st.set_page_config(page_title="Méli-Mélo", page_icon="📚", layout="centered")

def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"].to_dict()
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

# --- CHARGEMENT ---
try:
    client = get_gspread_client()
    spreadsheet = client.open("BiblioClub_Data") 
    sheet_livres = spreadsheet.worksheet("Livres")
    sheet_membres = spreadsheet.worksheet("Membres")
    data = sheet_livres.get_all_records()
    if not data:
        df_livres = pd.DataFrame(columns=["Titre", "Auteur", "Propriétaire", "Avis_delire", "Statut", "Emprunteur", "Note", "Date_Ajout"])
    else:
        df_livres = pd.DataFrame(data)
except Exception as e:
    st.error(f"Erreur : {e}")
    st.stop()

COL = {
    "Titre": "Titre", "Auteur": "Auteur", "Proprio": "Propriétaire",
    "Avis": "Avis_delire", "Statut": "Statut", "Emprunteur": "Emprunteur",
    "Note": "Note", "Date": "Date_Ajout"
}

# --- FONCTION PARTAGE UNIVERSEL ---
def envoyer_whatsapp(message):
    return f"https://api.whatsapp.com/send?text={urllib.parse.quote(message)}"

# --- INTERFACE ---
st.title(" La boîte à livres à Méli-Mélo ")

liste_membres = get_liste_membres_fixes()
st.markdown(f"👤 Membre : **{st.session_state.get('user', liste_membres[0])}**")
utilisateur = st.selectbox("Utilisateur", liste_membres, key='user', label_visibility="collapsed")
infos_user = get_membre_info(utilisateur)

# LOGIQUE NOTIFICATION
has_notif = False
if not df_livres.empty:
    notif_mask = (df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]] == "Demandé")
    if not df_livres[notif_mask].empty:
        has_notif = True

nom_onglet_emprunt = "🤝 Emprunts (🔔)" if has_notif else "🤝 Emprunts"

st.write("---")
onglets = st.tabs(["📖 Bibliothèque", nom_onglet_emprunt, "👤 Mon Profil", "➕ Ajouter", "⚙️ Gérance" if utilisateur in ["Didier", "Amélie"] else ""])

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
    if df_livres.empty:
        st.info("La boîte est vide !")
    else:
        st.markdown("### 🔍 Trier par")
        tri = st.selectbox("", ["Derniers ajouts", "Note", "Titre (A-Z)"], label_visibility="collapsed")
        df_tri = df_livres.copy()
        if tri == "Titre (A-Z)": df_tri = df_tri.sort_values(by=COL["Titre"])
        elif tri == "Note": df_tri = df_tri.sort_values(by=COL["Note"], ascending=False)
        else: df_tri = df_tri.iloc[::-1]

        for idx, row in df_tri.iterrows():
            statut = str(row.get(COL["Statut"], 'Libre')).strip() or "Libre"
            p_livre = str(row[COL["Proprio"]]).strip()
            emoji, color = ("📗", "green") if statut == "Libre" else (("📙", "orange") if statut == "Demandé" else ("📕", "red"))
            
            with st.container():
                c1, c2 = st.columns([1, 4])
                with c1: st.title(emoji)
                with c2:
                    st.markdown(f"### {row[COL['Titre']]} {row.get(COL['Note'], '')} :{color}[ ({statut})]")
                    st.write(f"**{row[COL['Auteur']]}** | **Propriétaire :** {p_livre}")
                    if statut == "Libre" and p_livre != utilisateur.strip():
                        if st.button(f"Demander", key=f"req_{idx}"):
                            oidx = df_livres.index[df_livres[COL['Titre']] == row[COL['Titre']]][0] + 2
                            sheet_livres.update_cell(oidx, 5, "Demandé")
                            sheet_livres.update_cell(oidx, 6, utilisateur)
                            st.rerun()
                st.write("---")

# --- 2. EMPRUNTS (AVEC REFUS ET PARTAGE MANUEL) ---
with onglets[1]:
    st.subheader("🤝 Suivi des emprunts")
    mask_reçu = (df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]].isin(['Demandé', 'Emprunté']))
    res = df_livres[mask_reçu]
    if not res.empty:
        for idx, r in res.iterrows():
            emp = r[COL["Emprunteur"]]
            st.warning(f"🔔 **{emp}** attend une réponse pour : **{r[COL['Titre']]}**")
            
            if r[COL["Statut"]] == "Demandé":
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button(f"✅ Valider", key=f"v_{idx}"):
                        oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                        sheet_livres.update_cell(oidx, 5, "Emprunté")
                        msg_ok = f"Hello {emp} ! C'est tout bon pour '{r[COL['Titre']]}'. Retrait : {infos_user.get('Infos_Retrait', 'On s arrange !')}"
                        st.link_button("📱 Choisir contact et envoyer OK", envoyer_whatsapp(msg_ok))
                with col_btn2:
                    if st.button(f"❌ Décliner", key=f"d_{idx}"):
                        oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                        sheet_livres.update_cell(oidx, 5, "Libre")
                        sheet_livres.update_cell(oidx, 6, "")
                        msg_refus = f"Coucou {emp} ! Désolé, je ne peux pas prêter '{r[COL['Titre']]}' pour le moment. On se redit dès qu'il est dispo ! 😉"
                        st.link_button("📱 Choisir contact et envoyer REFUS", envoyer_whatsapp(msg_refus))
            
            elif r[COL["Statut"]] == "Emprunté":
                if st.button(f"🔄 Livre rendu", key=f"ret_{idx}"):
                    oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                    sheet_livres.update_cell(oidx, 5, "Libre"); sheet_livres.update_cell(oidx, 6, ""); st.rerun()
    else: st.write("Aucune action requise.")

# --- 3. PROFIL & SUGGESTION ---
with onglets[2]:
    st.subheader(f"👤 Profil de {utilisateur}")
    st.write("---")
    st.markdown("#### 📢 Suggérer un nouveau membre")
    with st.form("sugg"):
        s_nom = st.text_input("Prénom & Nom du futur membre")
        if st.form_submit_button("Préparer le message"):
            msg_s = f"Hello, je suggère d'ajouter {s_nom} à La boîte à livres Méli-Mélo ! 📚"
            st.link_button("📱 Envoyer à Didier ou Amélie", envoyer_whatsapp(msg_s))
    st.write("---")
    # Liste des livres du membre pour suppression (inchangé)

# --- 4. AJOUTER ---
# [Garder le code précédent pour l'ajout manuel et l'import Excel]

st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
