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

# --- CONSTANTES ---
COL = {
    "Titre": "Titre", "Auteur": "Auteur", "Proprio": "Propriétaire",
    "Avis": "Avis_delire", "Statut": "Statut", "Emprunteur": "Emprunteur",
    "Note": "Note", "Date": "Date_Ajout"
}

# --- FONCTIONS WHATSAPP ---
def envoyer_whatsapp(message):
    # Ouvre WhatsApp et demande de choisir le contact
    return f"https://api.whatsapp.com/send?text={urllib.parse.quote(message)}"

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
        st.info("La boîte est vide. Ajoute un livre pour commencer !")
    else:
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
            u_actuel = str(utilisateur).strip()
            
            # Emojis demandés
            emoji, color = ("📗", "green") if statut == "Libre" else (("📙", "orange") if statut == "Demandé" else ("📕", "red"))
            
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
                    st.markdown(f"### {badge_new}{row[COL['Titre']]} {row.get(COL['Note'], '')} :{color}[ ({statut})]")
                    st.write(f"**{row[COL['Auteur']]}** | **Propriétaire :** {p_livre}")
                    if row.get(COL['Avis']): st.success(f"💬 {row[COL['Avis']]}")
                    
                    if statut == "Libre" and p_livre != u_actuel:
                        if st.button(f"Demander ce livre", key=f"req_{idx}"):
                            oidx = df_livres.index[df_livres[COL['Titre']] == row[COL['Titre']]][0] + 2
                            sheet_livres.update_cell(oidx, 5, "Demandé")
                            sheet_livres.update_cell(oidx, 6, u_actuel)
                            st.success("Demande envoyée !"); st.rerun()
                st.write("---")

# --- 2. EMPRUNTS (AVEC OPTION REFUS) ---
with onglets[1]:
    st.subheader("🤝 Suivi des emprunts")
    if not df_livres.empty:
        # A. Ce que J'AI demandé
        st.markdown("#### 📥 Mes demandes faites")
        mes_dem = df_livres[df_livres[COL["Emprunteur"]] == utilisateur]
        if not mes_dem.empty:
            for _, r in mes_dem.iterrows():
                st.info(f"📖 **{r[COL['Titre']]}** chez {r[COL['Proprio']]} ({r[COL['Statut']]})")
        else: st.write("Aucune demande en cours.")

        st.write("---")

        # B. Ce que les autres ME demandent
        st.markdown("#### 📤 Demandes reçues")
        mask_mouv = (df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]].isin(['Demandé', 'Emprunté']))
        mes_reçus = df_livres[mask_mouv]
        if not mes_reçus.empty:
            for idx, r in mes_reçus.iterrows():
                emp = r[COL["Emprunteur"]]
                st.warning(f"🔔 **{emp}** attend pour : **{r[COL['Titre']]}**")
                
                if r[COL["Statut"]] == "Demandé":
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        if st.button(f"✅ Valider", key=f"v_{idx}"):
                            oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                            sheet_livres.update_cell(oidx, 5, "Emprunté")
                            msg_ok = f"Hello {emp} ! C'est tout bon pour '{r[COL['Titre']]}'. Retrait : {infos_user.get('Infos_Retrait', 'On s arrange !')}"
                            st.link_button("📱 Prévenir (WhatsApp OK)", envoyer_whatsapp(msg_ok))
                    with col_b2:
                        if st.button(f"❌ Décliner", key=f"d_{idx}"):
                            oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                            sheet_livres.update_cell(oidx, 5, "Libre")
                            sheet_livres.update_cell(oidx, 6, "")
                            msg_refus = f"Coucou {emp} ! Désolé, je ne peux pas prêter '{r[COL['Titre']]}' pour le moment. On se redit dès qu'il est dispo ! 😉"
                            st.link_button("📱 Prévenir (WhatsApp Refus)", envoyer_whatsapp(msg_refus))
                
                elif r[COL["Statut"]] == "Emprunté":
                    if st.button(f"🔄 Livre rendu", key=f"ret_{idx}"):
                        oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                        sheet_livres.update_cell(oidx, 5, "Libre"); sheet_livres.update_cell(oidx, 6, ""); st.rerun()
        else: st.write("Rien à signaler pour vos livres.")
    else: st.write("La bibliothèque est vide.")

# --- 3. MON PROFIL & SUGGESTION ---
with onglets[2]:
    st.subheader(f"👤 Profil de {utilisateur}")
    st.markdown(f"📍 Domicile : **{infos_user.get('Position', 'Non renseigné')}**")
    st.write("---")
    
    st.markdown("#### 📢 Suggérer un nouveau membre")
    st.info("💡 Envoyez ensuite le message généré à Didier ou Amélie.")
    with st.form("sugg_form"):
        s_nom = st.text_input("Prénom & Nom du nouveau")
        if st.form_submit_button("Préparer le message WhatsApp"):
            msg_s = f"Hello, je suggère d'ajouter {s_nom} à La boîte à livres Méli-Mélo ! 📚"
            st.link_button("📱 Choisir le destinataire", envoyer_whatsapp(msg_s))
            
    st.write("---")
    st.subheader("📚 Ma collection")
    mes_l = df_livres[df_livres[COL["Proprio"]] == utilisateur]
    if not mes_l.empty:
        for idx, r in mes_l.iterrows():
            with st.expander(f"📙 {r[COL['Titre']]} ({r[COL['Statut']]})"):
                if st.button("Supprimer", key=f"del_{idx}"):
                    oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                    sheet_livres.delete_rows(oidx); st.rerun()
    else: st.info("Aucun livre ajouté.")

# --- 4. AJOUTER (MANUEL + IMPORT) ---
with onglets[3]:
    st.subheader("Partager des pépites")
    mode = st.radio("", ["✅ Manuel", "📤 Import Excel"], horizontal=True, label_visibility="collapsed")
    if mode == "✅ Manuel":
        with st.form("add"):
            t, a = st.text_input("Titre"), st.text_input("Auteur")
            n = st.select_slider("Note", options=["📚", "📚📚", "📚📚📚", "📚📚📚📚"])
            if st.form_submit_button("Ajouter"):
                d = datetime.now().strftime("%Y-%m-%d")
                sheet_livres.append_row([t, a, utilisateur, "", "Libre", "", n, d])
                st.success("Livre ajouté !"); st.rerun()
    else:
        st.markdown("### 📝 Mode d'emploi Import\n1. **Télécharge** le modèle.\n2. **Remplis** les colonnes.\n3. **Charge** le fichier.")
        st.link_button("📥 Télécharger BiblioMod.xlsx", "https://raw.githubusercontent.com/didierjaccoud144-bit/BiblioClub/main/BiblioMod.xlsx")
        up = st.file_uploader("Importer ton fichier Excel", type="xlsx")
        if up and st.button("Lancer l'importation"):
            try:
                df_im = pd.read_excel(up).fillna("")
                dt = datetime.now().strftime("%Y-%m-%d")
                for _, r in df_im.iterrows():
                    sheet_livres.append_row([str(r['Titre']), str(r.get('Auteur','')), utilisateur, str(r.get('Avis','')), "Libre", "", str(r.get('Note','')), dt])
                st.success("Import réussi !"); st.rerun()
            except Exception as e: st.error(f"Erreur : {e}")

# --- 5. GÉRANCE (ADMIN) ---
if utilisateur in ["Didier", "Amélie"]:
    with onglets[-1]:
        st.subheader("⚙️ Gérance administrative")
        with st.form("new_m"):
            n, t, p, r = st.text_input("Prénom"), st.text_input("Tél"), st.text_input("Lieu"), st.text_input("Retrait")
            if st.form_submit_button("Créer le compte"):
                sheet_membres.append_row([n, t, "", p, r]); st.success("Membre ajouté au registre !")

st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
