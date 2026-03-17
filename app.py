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
    # Sécurité si la bibliothèque est vide
    df_livres = pd.DataFrame(data) if data else pd.DataFrame(columns=["Titre", "Auteur", "Propriétaire", "Avis_delire", "Statut", "Emprunteur", "Note", "Date_Ajout"])
except Exception as e:
    st.error(f"Erreur de connexion : {e}")
    st.stop()

COL = {
    "Titre": "Titre", "Auteur": "Auteur", "Proprio": "Propriétaire",
    "Avis": "Avis_delire", "Statut": "Statut", "Emprunteur": "Emprunteur",
    "Note": "Note", "Date": "Date_Ajout"
}

# --- FONCTION WHATSAPP UNIVERSELLE ---
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
onglets_noms = ["❓ Mode d'emploi", "📖 Bibliothèque", nom_onglet_emprunt, "👤 Mon Profil", "➕ Ajouter"]

# RENOMMAGE : Gérance devient "Ajouter un membre" pour les admins
if utilisateur in ["Didier", "Amélie"]:
    onglets_noms.append("👤 Ajouter un membre")

onglets = st.tabs(onglets_noms)

# --- 0. MODE D'EMPLOI ---
with onglets[0]:
    st.subheader("🚀 Bienvenue au Club !")
    st.markdown("""
    ### 📱 1. L'installer sur votre téléphone
    * **Sur iPhone** : Icône **Partage** -> **« Sur l'écran d'accueil »**.
    * **Sur Android** : Les **3 petits points** -> **« Installer l'application »**.
    
    ### 🎨 2. Les couleurs
    * 📗 **Livre Vert** : Disponible !
    * 📙 **Livre Orange** : Demande en cours.
    * 📕 **Livre Rouge** : Déjà en prêt.
    """)
    st.success("Bonnes lectures ! 📖")

# --- 1. BIBLIOTHÈQUE ---
with onglets[1]:
    if df_livres.empty:
        st.info("La boîte est vide.")
    else:
        tri = st.selectbox("Trier par", ["Derniers ajouts", "Note", "Titre (A-Z)"])
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
                    if row.get(COL['Avis']): st.success(f"💬 {row[COL['Avis']]}")
                    if statut == "Libre" and p_livre != utilisateur.strip():
                        if st.button(f"Demander", key=f"req_{idx}"):
                            oidx = df_livres.index[df_livres[COL['Titre']] == row[COL['Titre']]][0] + 2
                            sheet_livres.update_cell(oidx, 5, "Demandé")
                            sheet_livres.update_cell(oidx, 6, utilisateur); st.rerun()
                st.write("---")

# --- 2. EMPRUNTS ---
with onglets[2]:
    st.subheader("🤝 Suivi des emprunts")
    mask_reçu = (df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]].isin(['Demandé', 'Emprunté']))
    res = df_livres[mask_reçu]
    if not res.empty:
        for idx, r in res.iterrows():
            emp = r[COL["Emprunteur"]]
            st.warning(f"🔔 **{emp}** attend : **{r[COL['Titre']]}**")
            if r[COL["Statut"]] == "Demandé":
                cb1, cb2 = st.columns(2)
                with cb1:
                    if st.button(f"✅ Valider", key=f"v_{idx}"):
                        oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                        sheet_livres.update_cell(oidx, 5, "Emprunté")
                        st.link_button("📱 Prévenir", envoyer_whatsapp(f"C'est OK pour '{r[COL['Titre']]}'. Retrait : {infos_user.get('Infos_Retrait')}"))
                with cb2:
                    if st.button(f"❌ Décliner", key=f"d_{idx}"):
                        oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                        sheet_livres.update_cell(oidx, 5, "Libre"); sheet_livres.update_cell(oidx, 6, "")
                        st.link_button("📱 Prévenir", envoyer_whatsapp(f"Désolé, je ne peux pas prêter '{r[COL['Titre']]}' pour le moment. 😉"))
            elif r[COL["Statut"]] == "Emprunté":
                if st.button(f"🔄 Rendu", key=f"ret_{idx}"):
                    oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                    sheet_livres.update_cell(oidx, 5, "Libre"); sheet_livres.update_cell(oidx, 6, ""); st.rerun()
    else: st.write("Rien à signaler.")

# --- 3. PROFIL ---
with onglets[3]:
    st.subheader(f"👤 Profil de {utilisateur}")
    st.markdown("#### 📢 Suggérer un membre")
    with st.form("sugg"):
        s_nom = st.text_input("Prénom & Nom")
        if st.form_submit_button("Préparer message"):
            st.link_button("📱 Envoyer à Didier/Amélie", envoyer_whatsapp(f"Hello, je suggère d'ajouter {s_nom} ! 📚"))
    st.write("---")
    mes_l = df_livres[df_livres[COL["Proprio"]] == utilisateur]
    for idx, r in mes_l.iterrows():
        with st.expander(f"📙 {r[COL['Titre']]} ({r[COL['Statut']]})"):
            if st.button("Supprimer", key=f"del_{idx}"):
                oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                sheet_livres.delete_rows(oidx); st.rerun()

# --- 4. AJOUTER ---
with onglets[4]:
    mode = st.radio("", ["✅ Manuel", "📤 Import Excel"], horizontal=True)
    if mode == "✅ Manuel":
        with st.form("a"):
            t, a = st.text_input("Titre"), st.text_input("Auteur")
            n = st.select_slider("Note", options=["📚", "📚📚", "📚📚📚", "📚📚📚📚"])
            if st.form_submit_button("Ajouter"):
                sheet_livres.append_row([t, a, utilisateur, "", "Libre", "", n, datetime.now().strftime("%Y-%m-%d")]); st.rerun()
    else:
        st.link_button("📥 Modèle Excel", "https://raw.githubusercontent.com/didierjaccoud144-bit/BiblioClub/main/BiblioMod.xlsx")
        up = st.file_uploader("Fichier .xlsx", type="xlsx")
        if up and st.button("Importer"):
            df_im = pd.read_excel(up).fillna("")
            for _, r in df_im.iterrows():
                sheet_livres.append_row([r['Titre'], r.get('Auteur',''), utilisateur, r.get('Avis',''), "Libre", "", r.get('Note',''), datetime.now().strftime("%Y-%m-%d")]); st.rerun()

# --- 5. AJOUTER UN MEMBRE (Anciennement Gérance) ---
if utilisateur in ["Didier", "Amélie"]:
    with onglets[-1]:
        st.subheader("👤 Ajouter un nouveau membre")
        with st.form("nm"):
            n, t, p, r = st.text_input("Prénom"), st.text_input("Tél"), st.text_input("Lieu"), st.text_input("Retrait")
            if st.form_submit_button("Enregistrer"):
                sheet_membres.append_row([n, t, "", p, r]); st.success("Fait !")

st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
