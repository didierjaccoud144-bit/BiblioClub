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
    st.error(f"Erreur de connexion : {e}")
    st.stop()

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

# LOGIQUE NOTIFICATION ONGLET
has_notif = False
if not df_livres.empty:
    notif_mask = (df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]] == "Demandé")
    if not df_livres[notif_mask].empty:
        has_notif = True

nom_onglet_emprunt = "🤝 Emprunts (🔔)" if has_notif else "🤝 Emprunts"

st.write("---")
onglets_noms = ["📖 Bibliothèque", nom_onglet_emprunt, "👤 Mon Profil", "➕ Ajouter"]
if utilisateur in ["Didier", "Amélie"]:
    onglets_noms.append("⚙️ Gérance")
onglets = st.tabs(onglets_noms)

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
    if df_livres.empty:
        st.info("La boîte est vide. Ajoute un livre !")
    else:
        st.markdown("### 🔍 Trier par")
        tri = st.selectbox("", ["Derniers ajouts", "Note", "Titre (A-Z)", "Auteur", "Propriétaire"], label_visibility="collapsed")
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
                            sheet_livres.update_cell(oidx, 6, utilisateur)
                            st.rerun()
                st.write("---")

# --- 2. EMPRUNTS ---
with onglets[1]:
    st.subheader("🤝 Suivi des emprunts")
    mask_reçu = (df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]].isin(['Demandé', 'Emprunté']))
    res = df_livres[mask_reçu]
    if not res.empty:
        for idx, r in res.iterrows():
            emp = r[COL["Emprunteur"]]
            st.warning(f"🔔 **{emp}** attend une réponse pour : **{r[COL['Titre']]}**")
            if r[COL["Statut"]] == "Demandé":
                if st.button(f"✅ Valider le prêt", key=f"v_{idx}"):
                    oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                    sheet_livres.update_cell(oidx, 5, "Emprunté")
                    st.link_button("📱 Prévenir par WhatsApp", envoyer_whatsapp(get_membre_info(emp).get('Téléphone',''), f"Hello {emp} ! Ok pour '{r[COL['Titre']]}'. Retrait : {infos_user.get('Infos_Retrait')}"))
            elif r[COL["Statut"]] == "Emprunté":
                if st.button(f"🔄 Livre rendu", key=f"ret_{idx}"):
                    oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                    sheet_livres.update_cell(oidx, 5, "Libre"); sheet_livres.update_cell(oidx, 6, ""); st.rerun()
    else: st.write("Aucune action requise sur vos livres.")

# --- 3. MON PROFIL & SUGGESTION ---
with onglets[2]:
    st.subheader(f"👤 Profil de {utilisateur}")
    st.markdown(f"📍 Domicile : **{infos_user.get('Position', 'Non renseigné')}**")
    st.write("---")
    
    # FORMULAIRE DE SUGGESTION (Visible par tous)
    st.markdown("#### 📢 Suggérer un nouveau membre")
    st.info("💡 Le message WhatsApp généré devra être envoyé manuellement à Didier ou Amélie.")
    with st.form("sugg_form"):
        s_nom = st.text_input("Prénom & Nom du futur membre")
        s_tel = st.text_input("Numéro de téléphone")
        if st.form_submit_button("Préparer le message WhatsApp"):
            msg_sugg = f"Hello, je voudrais te suggérer de partager l'application 'La boîte à livres à Méli-Mélo' avec un nouveau membre.\n\nNom : {s_nom}\nTél : {s_tel}\n\nMerci !"
            st.link_button("📱 Ouvrir WhatsApp pour envoyer", envoyer_whatsapp("", msg_sugg))
    
    st.write("---")
    st.subheader("📚 Ma collection")
    mes_l = df_livres[df_livres[COL["Proprio"]] == utilisateur]
    for idx, r in mes_l.iterrows():
        with st.expander(f"📙 {r[COL['Titre']]} ({r[COL['Statut']]})"):
            if st.button("Supprimer", key=f"del_{idx}"):
                oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                sheet_livres.delete_rows(oidx); st.rerun()

# --- 4. AJOUTER ---
with onglets[3]:
    mode = st.radio("", ["✅ Manuel", "📤 Import Excel"], horizontal=True, label_visibility="collapsed")
    if mode == "✅ Manuel":
        with st.form("add"):
            t, a = st.text_input("Titre"), st.text_input("Auteur")
            n = st.select_slider("Note", options=["📚", "📚📚", "📚📚📚", "📚📚📚📚"])
            if st.form_submit_button("Ajouter"):
                sheet_livres.append_row([t, a, utilisateur, "", "Libre", "", n, datetime.now().strftime("%Y-%m-%d")])
                st.success("Livre ajouté !"); st.rerun()
    else:
        st.markdown("### 📝 Mode d'emploi Import\n1. Télécharge le modèle.\n2. Remplis les colonnes.\n3. Charge le fichier.")
        st.link_button("📥 Télécharger BiblioMod.xlsx", "https://raw.githubusercontent.com/didierjaccoud144-bit/BiblioClub/main/BiblioMod.xlsx")
        up = st.file_uploader("Importer ton fichier Excel", type="xlsx")
        if up and st.button("Lancer l'importation"):
            df_im = pd.read_excel(up).fillna("")
            for _, r in df_im.iterrows():
                sheet_livres.append_row([r['Titre'], r.get('Auteur',''), utilisateur, r.get('Avis',''), "Libre", "", r.get('Note',''), datetime.now().strftime("%Y-%m-%d")])
            st.rerun()

# --- 5. GÉRANCE (Uniquement création directe) ---
if utilisateur in ["Didier", "Amélie"]:
    with onglets[-1]:
        st.subheader("⚙️ Gérance administrative")
        with st.form("new_m"):
            n, t, p, r = st.text_input("Prénom"), st.text_input("Tél"), st.text_input("Lieu"), st.text_input("Retrait")
            if st.form_submit_button("Créer le compte immédiatement"):
                sheet_membres.append_row([n, t, "", p, r]); st.success("Membre ajouté au registre !")

st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
