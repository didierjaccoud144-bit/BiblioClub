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
    df_livres = pd.DataFrame(sheet_livres.get_all_records())
except Exception as e:
    st.error(f"Erreur de connexion : {e}")
    st.stop()

# --- CONSTANTES ---
COL = {
    "Titre": "Titre", "Auteur": "Auteur", "Proprio": "Propriétaire",
    "Avis": "Avis_delire", "Statut": "Statut", "Emprunteur": "Emprunteur",
    "Note": "Note", "Date": "Date_Ajout"
}

def envoyer_whatsapp(telephone, message):
    if not telephone: return "#"
    return f"https://wa.me/{str(telephone).replace(' ', '')}?text={urllib.parse.quote(message)}"

# --- INTERFACE ---
st.title(" La boîte à livres à Méli-Mélo ")

liste_membres = get_liste_membres_fixes()
st.markdown(f"👤 Membre : **{st.session_state.get('user', liste_membres[0])}**")
utilisateur = st.selectbox("Utilisateur", liste_membres, key='user', label_visibility="collapsed")
infos_user = get_membre_info(utilisateur)

st.write("---")

onglets_noms = ["📖 Bibliothèque", "🤝 Emprunts", "👤 Mon Profil", "➕ Ajouter"]
if utilisateur in ["Didier", "Amélie"]:
    onglets_noms.append("⚙️ Gérance")
onglets = st.tabs(onglets_noms)

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
    st.markdown("### 🔍 Trier par")
    tri = st.selectbox("", ["Derniers ajouts", "Note", "Titre (A-Z)", "Auteur", "Propriétaire"], label_visibility="collapsed")
    
    df_tri = df_livres.copy()
    if tri == "Titre (A-Z)": df_tri = df_tri.sort_values(by=COL["Titre"])
    elif tri == "Auteur": df_tri = df_tri.sort_values(by=COL["Auteur"])
    elif tri == "Propriétaire": df_tri = df_tri.sort_values(by=COL["Proprio"])
    elif tri == "Note": df_tri = df_tri.sort_values(by=COL["Note"], ascending=False)
    else: df_tri = df_tri.iloc[::-1]

    for idx, row in df_tri.iterrows():
        statut = str(row.get(COL["Statut"], 'Libre')).strip() or "Libre"
        p_livre = str(row[COL["Proprio"]]).strip()
        user_nom = str(utilisateur).strip()
        
        # LOGIQUE VISUELLE DEMANDÉE
        if statut == "Libre":
            emoji, color = "📗", "green"
        elif statut == "Demandé":
            emoji, color = "📙", "orange"
        else: # Emprunté
            emoji, color = "📕", "red"
        
        badge_new = ""
        try:
            date_l = datetime.strptime(str(row[COL["Date"]]), "%Y-%m-%d")
            if datetime.now() - date_l < timedelta(days=7):
                badge_new = "🆕 "
        except: pass

        with st.container():
            c1, c2 = st.columns([1, 4])
            with c1: st.title(emoji)
            with c2:
                # Statut à côté du titre
                st.markdown(f"### {badge_new}{row[COL['Titre']]} {row.get(COL['Note'], '')} :{color}[ ({statut})]")
                st.write(f"**{row[COL['Auteur']]}** | **Propriétaire :** {p_livre}")
                if row.get(COL['Avis']): st.success(f"💬 {row[COL['Avis']]}")
                
                # Sécurité : Pas de bouton sur mes propres livres
                if statut == "Libre" and p_livre != user_nom:
                    if st.button(f"Demander ce livre", key=f"req_{idx}"):
                        oidx = df_livres.index[df_livres[COL['Titre']] == row[COL['Titre']]][0] + 2
                        sheet_livres.update_cell(oidx, 5, "Demandé")
                        sheet_livres.update_cell(oidx, 6, user_nom)
                        st.success("Demande envoyée !"); st.rerun()
            st.write("---")

# --- 2. EMPRUNTS ---
with onglets[1]:
    st.subheader("🤝 Suivi des emprunts")
    mes_dem = df_livres[df_livres[COL["Emprunteur"]] == utilisateur]
    if not mes_dem.empty:
        for _, r in mes_dem.iterrows():
            st.info(f"📖 **{r[COL['Titre']]}** chez {r[COL['Proprio']]} ({r[COL['Statut']]})")
    else: st.write("Aucune demande en cours.")
    st.write("---")
    mask_reçu = (df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]].isin(['Demandé', 'Emprunté']))
    mes_reçus = df_livres[mask_reçu]
    if not mes_reçus.empty:
        for idx, r in mes_reçus.iterrows():
            emp = r[COL["Emprunteur"]]
            st.warning(f"🔔 **{emp}** -> **{r[COL['Titre']]}**")
            if r[COL["Statut"]] == "Demandé":
                if st.button(f"✅ Valider prêt", key=f"ok_{idx}"):
                    oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                    sheet_livres.update_cell(oidx, 5, "Emprunté")
                    info_d = get_membre_info(emp)
                    st.link_button("📱 WhatsApp", envoyer_whatsapp(info_d.get('Téléphone',''), f"Hello {emp} ! Ok pour '{r[COL['Titre']]}'. Retrait : {infos_user.get('Infos_Retrait')}"))
            elif r[COL["Statut"]] == "Emprunté":
                if st.button(f"🔄 Rendu", key=f"ret_{idx}"):
                    oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                    sheet_livres.update_cell(oidx, 5, "Libre"); sheet_livres.update_cell(oidx, 6, ""); st.rerun()

# --- 3. MON PROFIL ---
with onglets[2]:
    st.subheader(f"👤 {utilisateur}")
    st.markdown(f"📍 Domicile : **{infos_user.get('Position', 'Non renseigné')}**")
    st.write("---")
    mes_p = df_livres[df_livres[COL["Proprio"]] == utilisateur]
    for idx, r in mes_p.iterrows():
        with st.expander(f"📙 {r[COL['Titre']]} ({r[COL['Statut']]})"):
            if st.button("Supprimer", key=f"del_{idx}"):
                oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                sheet_livres.delete_rows(oidx); st.rerun()

# --- 4. AJOUTER ---
with onglets[3]:
    mode = st.radio("", ["✅ Manuel", "📤 Import Excel"], horizontal=True, label_visibility="collapsed")
    if mode == "✅ Manuel":
        with st.form("manual"):
            t, a = st.text_input("Titre"), st.text_input("Auteur")
            note = st.select_slider("Note", options=["📚", "📚📚", "📚📚📚", "📚📚📚📚"])
            c = st.text_area("Avis-Délire")
            if st.form_submit_button("Ajouter à la boîte"):
                d = datetime.now().strftime("%Y-%m-%d")
                sheet_livres.append_row([t, a, utilisateur, c, "Libre", "", note, d])
                st.success("Livre ajouté !"); st.rerun()
    else:
        st.markdown("### 📝 Mode d'emploi Import")
        st.markdown("1. **Télécharge** le modèle.\n2. **Remplis** (Titre, Auteur, Avis, Note).\n3. **Charge** le fichier ci-dessous.")
        st.link_button("📥 Télécharger BiblioMod.xlsx", "https://raw.githubusercontent.com/didierjaccoud144-bit/BiblioClub/main/BiblioMod.xlsx")
        
        up = st.file_uploader("Glisse et dépose ton fichier ici", type="xlsx")
        
        if up and st.button("Lancer l'importation"):
            try:
                # CORRECTION "NAN" : On remplace les cases vides par du texte vide
                df_im = pd.read_excel(up).fillna("")
                dt = datetime.now().strftime("%Y-%m-%d")
                for _, r in df_im.iterrows():
                    sheet_livres.append_row([str(r['Titre']), str(r.get('Auteur','')), utilisateur, str(r.get('Avis','')), "Libre", "", str(r.get('Note','')), dt])
                st.success("Importation terminée !"); st.rerun()
            except Exception as e:
                st.error(f"Erreur : {e}")

# --- 5. GÉRANCE ---
if utilisateur in ["Didier", "Amélie"]:
    with onglets[-1]:
        st.subheader("⚙️ Gérance administrative")
        with st.form("new_m"):
            n, t, p, r = st.text_input("Prénom"), st.text_input("Tél"), st.text_input("Lieu"), st.text_input("Retrait")
            if st.form_submit_button("Ajouter le membre"):
                sheet_membres.append_row([n, t, "", p, r]); st.success("Membre ajouté !")

st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
