import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import urllib.parse
from datetime import datetime, timedelta

# Importation du fichier de profil membres
from membres_profil import get_membre_info, get_liste_membres_fixes

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
    sheet_livres = spreadsheet.worksheet("Livres")
    df_livres = pd.DataFrame(sheet_livres.get_all_records())
except Exception as e:
    st.error(f"Erreur de connexion : {e}")
    st.stop()

# --- CONSTANTES COLONNES (Mises à jour) ---
COL = {
    "Titre": "Titre", 
    "Auteur": "Auteur", 
    "Proprio": "Propriétaire",  # Changement ici
    "Avis": "Avis_delire", 
    "Statut": "Statut", 
    "Emprunteur": "Emprunteur",
    "Note": "Note", 
    "Date": "Date_Ajout"
}

def envoyer_whatsapp(telephone, message):
    return f"https://wa.me/{str(telephone).replace(' ', '')}?text={urllib.parse.quote(message)}"

def show_avatar(url, size=40):
    if url:
        st.markdown(f'<img src="{url}" style="width:{size}px; height:{size}px; border-radius:50%; margin-right:10px; object-fit: cover;">', unsafe_allow_html=True)

# --- INTERFACE ---
st.title("📚 Le Biblio Club")

liste_membres = get_liste_membres_fixes()
col_u1, col_u2 = st.columns([1, 4])
with col_u1:
    prenom_user = st.session_state.get('user', liste_membres[0])
    infos_user = get_membre_info(prenom_user)
    show_avatar(infos_user.get('Avatar',''), size=55)
with col_u2:
    utilisateur = st.selectbox("", liste_membres, key='user', label_visibility="collapsed")
    infos_user = get_membre_info(utilisateur)

st.write("---")
onglets = st.tabs(["📖 Bibliothèque", "🤝 Emprunts", "👤 Mon Profil", "➕ Ajouter"])

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
    st.markdown("### 🔍 Trier par")
    tri = st.selectbox("", ["Derniers ajouts", "Note (la meilleure)", "Titre (A-Z)", "Auteur", "Propriétaire"], label_visibility="collapsed")
    
    df_tri = df_livres.copy()
    if tri == "Titre (A-Z)": df_tri = df_tri.sort_values(by=COL["Titre"])
    elif tri == "Auteur": df_tri = df_tri.sort_values(by=COL["Auteur"])
    elif tri == "Propriétaire": df_tri = df_tri.sort_values(by=COL["Proprio"])
    elif tri == "Note (la meilleure)": df_tri = df_tri.sort_values(by=COL["Note"], ascending=False)
    else: df_tri = df_tri.iloc[::-1]

    for idx, row in df_tri.iterrows():
        statut = str(row.get(COL["Statut"], 'Libre')).strip() or "Libre"
        color = "green" if statut == "Libre" else "orange" if statut == "Demandé" else "red"
        
        # Badge Nouveauté
        badge_new = ""
        try:
            date_livre = datetime.strptime(str(row[COL["Date"]]), "%Y-%m-%d")
            if datetime.now() - date_livre < timedelta(days=7):
                badge_new = "🆕 "
        except: pass

        with st.container():
            c1, c2 = st.columns([1, 4])
            with c1: st.title("📕")
            with c2:
                # Affichage Titre + Note
                st.markdown(f"### {badge_new}{row[COL['Titre']]} {row.get(COL['Note'], '')}")
                # Affichage Propriétaire dans le visuel
                st.write(f"**{row[COL['Auteur']]}** | :{color}[({statut})] | **Propriétaire :** {row[COL['Proprio']]}")
                
                if row.get(COL['Avis']):
                    st.success(f"💬 {row[COL['Avis']]}")
                
                if statut == "Libre" and str(row[COL['Proprio']]) != utilisateur:
                    if st.button(f"Demander ce livre", key=f"req_{idx}"):
                        original_idx = df_livres[df_livres[COL['Titre']] == row[COL['Titre']]].index[0]
                        sheet_livres.update_cell(original_idx + 2, 5, "Demandé")
                        sheet_livres.update_cell(original_idx + 2, 6, utilisateur)
                        st.success("Demande envoyée !")
                        st.rerun()
            st.write("---")

# --- 2. EMPRUNTS ---
with onglets[1]:
    st.subheader("🤝 Suivi des emprunts")
    st.markdown("#### 📥 Mes demandes faites")
    mes_emprunts = df_livres[df_livres[COL["Emprunteur"]] == utilisateur]
    if not mes_emprunts.empty:
        for _, r in mes_emprunts.iterrows():
            st.info(f"📖 **{r[COL['Titre']]}** chez {r[COL['Proprio']]} ({r[COL['Statut']]})")
    else:
        st.write("Aucune demande en cours.")

    st.write("---")
    st.markdown("#### 📤 Demandes reçues")
    mes_livres_mouv = df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]].isin(['Demandé', 'Emprunté']))]
    if not mes_livres_mouv.empty:
        for idx, r in mes_livres_mouv.iterrows():
            emp = r[COL["Emprunteur"]]
            st.warning(f"🔔 **{emp}** -> **{r[COL['Titre']]}**")
            if r[COL["Statut"]] == "Demandé":
                if st.button(f"✅ Valider prêt", key=f"ok_{idx}"):
                    oidx = df_livres[df_livres[COL['Titre']] == r[COL['Titre']]].index[0]
                    sheet_livres.update_cell(oidx + 2, 5, "Emprunté")
                    info_d = get_membre_info(emp)
                    msg = f"Hello {emp} ! Ok pour '{r[COL['Titre']]}'. Retrait : {infos_user.get('Infos_Retrait')}"
                    st.link_button("📱 WhatsApp", envoyer_whatsapp(info_d.get('Téléphone',''), msg))
            elif r[COL["Statut"]] == "Emprunté":
                if st.button(f"🔄 Marquer comme rendu", key=f"ret_{idx}"):
                    oidx = df_livres[df_livres[COL['Titre']] == r[COL['Titre']]].index[0]
                    sheet_livres.update_cell(oidx + 2, 5, "Libre")
                    sheet_livres.update_cell(oidx + 2, 6, "")
                    st.rerun()
    else:
        st.write("Rien à signaler pour vos livres.")

# --- 3. MON PROFIL ---
with onglets[2]:
    st.subheader(f"👤 {utilisateur}")
    st.markdown(f"📍 Position : **{infos_user.get('Position')}**")
    st.write("---")
    mes_propres_livres = df_livres[df_livres[COL["Proprio"]] == utilisateur]
    for idx, r in mes_propres_livres.iterrows():
        with st.expander(f"📙 {r[COL['Titre']]} ({r[COL['Statut']]})"):
            if st.button("Supprimer", key=f"del_{idx}"):
                oidx = df_livres[df_livres[COL['Titre']] == r[COL['Titre']]].index[0]
                sheet_livres.delete_rows(oidx + 2)
                st.rerun()

# --- 4. AJOUTER ---
with onglets[3]:
    with st.form("ajout_vfinal"):
        t = st.text_input("Titre")
        a = st.text_input("Auteur")
        note = st.select_slider("Note", options=["📚", "📚📚", "📚📚📚", "📚📚📚📚"])
        com = st.text_area("Avis-Délire")
        if st.form_submit_button("Ajouter"):
            d = datetime.now().strftime("%Y-%m-%d")
            sheet_livres.append_row([t, a, utilisateur, com, "Libre", "", note, d])
            st.success("Ajouté !"); st.rerun()

st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
