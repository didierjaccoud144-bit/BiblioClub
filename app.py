import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import urllib.parse
from datetime import datetime, timedelta

# Importation du fichier de profil membres (contenant MEMBRES_FIXES)
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
    st.error(f"Erreur de lecture : {e}")
    st.stop()

# --- CONSTANTES ---
# Noms des colonnes du Sheet
COL = {
    "Titre": "Titre", "Auteur": "Auteur", "Proprio": "Propriétaire",
    "Avis": "Avis_delire", "Statut": "Statut", "Emprunteur": "Emprunteur",
    "Note": "Note", "Date": "Date_Ajout"
}

# Nombre de jours pour le badge nouveauté
JOURS_NOUVEAUTE = 7

def envoyer_whatsapp(telephone, message):
    if not telephone: return "#"
    return f"https://wa.me/{str(telephone).replace(' ', '')}?text={urllib.parse.quote(message)}"

def show_avatar(url, size=40):
    if url:
        st.markdown(f'<img src="{url}" style="width:{size}px; height:{size}px; border-radius:50%; margin-right:10px; object-fit: cover;">', unsafe_allow_html=True)

# --- INTERFACE ---
st.title("📚 Le Biblio Club")

# Sélection Utilisateur (visible sur mobile)
liste_membres = get_liste_membres_fixes()
col_u1, col_u2 = st.columns([1, 4])
with col_u1:
    # Affiche l'avatar Notion du membre sélectionné
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
    # SYSTÈME DE TRI
    st.markdown("### 🔍 Trier par")
    tri = st.selectbox("", ["Derniers ajouts", "Note (la meilleure)", "Titre (A-Z)", "Auteur", "Propriétaire"], label_visibility="collapsed")
    
    df_tri = df_livres.copy()
    if tri == "Titre (A-Z)": df_tri = df_tri.sort_values(by=COL["Titre"])
    elif tri == "Auteur": df_tri = df_tri.sort_values(by=COL["Auteur"])
    elif tri == "Propriétaire": df_tri = df_tri.sort_values(by=COL["Proprio"])
    elif tri == "Note (la meilleure)": df_tri = df_tri.sort_values(by=COL["Note"], ascending=False)
    else: df_tri = df_tri.iloc[::-1] # Derniers ajouts

    for idx, row in df_tri.iterrows():
        statut = str(row.get(COL["Statut"], 'Libre')).strip() or "Libre"
        color = "green" if statut == "Libre" else "orange" if statut == "Demandé" else "red"
        
        # Emoji livre dynamique : Vert si libre, Gris sinon
        # emoji_livre = "🟢" if statut == "Libre" else "📕"

        # Logique badge Nouveauté
        badge_new = ""
        try:
            date_livre = datetime.strptime(str(row[COL["Date"]]), "%Y-%m-%d")
            if datetime.now() - date_livre < timedelta(days=JOURS_NOUVEAUTE):
                badge_new = "🆕 "
        except: pass # Si la date est mal formatée, on n'affiche rien

        # Affichage Note
        score_visual = f"{row.get(COL['Note'], '')}"

        with st.container():
            c1, c2 = st.columns([1, 4])
            with c1: 
                # st.title(emoji_livre)
                st.title("🟢") # On remet le livre vert par défaut
            with c2:
                # Affichage Titre + Badge + Note
                st.markdown(f"### {badge_new}{row[COL['Titre']]} {score_visual}")
                st.write(f"**{row[COL['Auteur']]}** | :{color}[({statut})] | **Propriétaire :** {row[COL['Proprio']]}")
                
                if row.get(COL['Avis']):
                    st.success(f"💬 **Avis-Délire :** {row[COL['Avis']]}")
                
                # BOUTON DEMANDER (uniquement si Libre et pas mon livre)
                if statut == "Libre" and str(row[COL['Proprio']]) != utilisateur:
                    if st.button(f"Demander ce livre", key=f"req_{idx}"):
                        original_idx = df_livres[df_livres[COL['Titre']] == row[COL['Titre']]].index[0]
                        sheet_livres.update_cell(original_idx + 2, 5, "Demandé")
                        sheet_livres.update_cell(idx + 2, 6, utilisateur)
                        st.success("Demande envoyée !")
                        st.rerun()
            st.write("---")

# --- 2. GESTION DES EMPRUNTS (CENTRALISÉE) ---
with onglets[1]:
    st.subheader("🤝 Suivi des emprunts")
    
    st.markdown("#### 📥 Livres que j'ai demandés (ou chez moi)")
    mask_e = df_livres[COL["Emprunteur"]] == utilisateur
    mes_emprunts = df_livres[mask_e]
    if not mes_emprunts.empty:
        for _, r in mes_emprunts.iterrows():
            st.info(f"📖 **{r[COL['Titre']]}** chez {r[COL['Proprio']]} ({r[COL['Statut']]})")
    else:
        st.write("Aucune demande en cours.")

    st.write("---")
    
    st.markdown("#### 📤 Demandes reçues pour mes livres")
    mask_p = (df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]].isin(['Demandé', 'Emprunté']))
    mes_livres_mouv = df_livres[mask_p]
    if not mes_livres_mouv.empty:
        for idx, r in mes_livres_mouv.iterrows():
            emp = r[COL["Emprunteur"]]
            st.warning(f"🔔 **{emp}** -> **{r[COL['Titre']]}**")
            
            if r[COL["Statut"]] == "Demandé":
                if st.button(f"✅ Valider prêt pour {emp}", key=f"ok_{idx}"):
                    oidx = df_livres[df_livres[COL['Titre']] == r[COL['Titre']]].index[0]
                    sheet_livres.update_cell(oidx + 2, 5, "Emprunté")
                    info_d = get_membre_info(emp)
                    tel_d = info_d.get('Téléphone', '')
                    msg = f"Hello {emp} ! Ok pour '{r[COL['Titre']]}'. Retrait : {infos_user.get('Infos_Retrait', 'Passe me voir !')}"
                    st.link_button("📱 Confirmation WhatsApp", envoyer_whatsapp(tel_d, msg))
            
            elif r[COL["Statut"]] == "Emprunté":
                if st.button(f"🔄 Marquer comme rendu", key=f"ret_{idx}"):
                    oidx = df_livres[df_livres[COL['Titre']] == r[COL['Titre']]].index[0]
                    sheet_livres.update_cell(oidx + 2, 5, "Libre")
                    sheet_livres.update_cell(oidx + 2, 6, "")
                    st.rerun()
    else:
        st.write("Rien à signaler pour vos livres.")

# --- 3. MON PROFIL (Avatar, Position, Mes Livres) ---
with onglets[2]:
    st.subheader(f"👤 Espace de {utilisateur}")
    
    # Affichage de l'avatar et position (fixe)
    col_p1, col_p2 = st.columns([1, 3])
    with col_p1:
        show_avatar(infos_user.get('Avatar',''), size=80)
    with col_p2:
        st.markdown(f"**📍 Position :** {infos_user.get('Position', 'Non indiquée')}")
        st.markdown(f"**📱 Tél :** {infos_user.get('Téléphone', '---')}")
        st.markdown(f"**🏠 Infos Retrait :** *{infos_user.get('Infos_Retrait', '---')}*")
    
    st.write("---")
    
    # Liste de mes livres avec suppression
    st.subheader(f"🔖 Mes livres ({utilisateur})")
    mask_m = df_livres[COL["Proprio"]] == utilisateur
    mes_propres_livres = df_livres[mask_m]
    if not mes_propres_livres.empty:
        for idx, row in mes_propres_livres.iterrows():
            with st.expander(f"📙 {row[COL['Titre']]} ({row[COL['Statut']]})"):
                st.write(f"Date d'ajout : {row.get(COL['Date'])}")
                st.write(f"Note : {row.get(COL['Note'])}")
                
                # Suppression
                st.write("---")
                if st.button(f"🗑️ Supprimer définitivement", key=f"del_{idx}"):
                    oidx = df_livres[df_livres[COL['Titre']] == row[COL['Titre']]].index[0]
                    sheet_livres.delete_rows(oidx + 2)
                    st.rerun()
            st.write("")
    else:
        st.info("Tu n'as pas encore de livres.")

# --- 4. AJOUTER (FUSIONNÉ : MANUEL + IMPORT) ---
with onglets[3]:
    st.subheader("Partager des livres")
    
    # Choix du module : Manuel ou Import
    mode_ajout = st.radio("", ["✅ Ajout Manuel", "📤 Import Excel"], label_visibility="collapsed")
    st.write("---")
    
    # --- A. AJOUT MANUEL ---
    if mode_ajout == "✅ Ajout Manuel":
        with st.form("ajout_manuel"):
            st.markdown("#### Ajouter un seul livre")
            t = st.text_input("Titre du livre")
            a = st.text_input("Auteur")
            note = st.select_slider("Ma note (Biblio-Score)", options=["📚", "📚📚", "📚📚📚", "📚📚📚📚"])
            com = st.text_area("Mon Avis-Délire")
            if st.form_submit_button("Partager avec le Club"):
                # Date du jour automatique
                d = datetime.now().strftime("%Y-%m-%d")
                # Ajout de la ligne avec les 8 colonnes
                sheet_livres.append_row([t, a, utilisateur, com, "Libre", "", note, d])
                st.success("C'est en ligne !"); st.rerun()

    # --- B. IMPORT EXCEL ---
    else:
        st.markdown("#### Importer plusieurs livres d'un coup")
        
        c_i1, c_i2 = st.columns([3, 2])
        with c_i1:
            st.markdown("""
            **La marche à suivre en 3 points :**
            1. **Télécharge** le fichier modèle ci-contre.
            2. **Remplis**-le avec tes livres (Titre, Auteur, Avis, Note).
            3. **Charge** le fichier complété ci-dessous.
            """)
        with c_i2:
            st.markdown("##### 1. Télécharger le modèle")
            # --- À FAIRE PAR DIDIER ---
            # Crée un fichier Excel vide sur GitHub avec les colonnes Titre, Auteur, Avis, Note
            # Puis mets son lien de téléchargement ici
            lien_modele = "https://github.com/votre_repo/Raw/Biblio_Club/modele_import.xlsx"
            st.link_button("📥 Télécharger modèle.xlsx", lien_modele)
        
        st.write("---")
        st.markdown("##### 2. Charger ton fichier complété")
        up_import = st.file_uploader("", type="xlsx", key="up_imp", label_visibility="collapsed")
        
        if up_import and st.button("Lancer l'import (3. Valider)"):
            try:
                df_im = pd.read_excel(up_import)
                date_today = datetime.now().strftime("%Y-%m-%d")
                for _, r in df_im.iterrows():
                    # Colonnes : Titre, Auteur, Membre, Avis, Statut, Emprunteur, Note, Date
                    # (On récupère Avis et Note du fichier, les autres sont fixes)
                     sheet_livres.append_row([
                        r['Titre'], r.get('Auteur',''), utilisateur, 
                        r.get('Avis',''), "Libre", "", r.get('Note',''), date_today
                     ])
                st.success("L'import est réussi ! Ils sont en ligne.")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur d'import : {e}")
