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

# Rafraîchissement forcé pour garantir des données fraîches
def refresh():
    st.cache_data.clear()
    st.rerun()

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
    cols_def = ["Titre", "Auteur", "Propriétaire", "Avis_delire", "Statut", "Emprunteur", "Note", "Date_Ajout", "Avis_Lecteurs"]
    df_livres = pd.DataFrame(data) if data else pd.DataFrame(columns=cols_def)
except Exception as e:
    st.error(f"Erreur de connexion : {e}")
    st.stop()

COL = {
    "Titre": "Titre", "Auteur": "Auteur", "Proprio": "Propriétaire",
    "Avis": "Avis_delire", "Statut": "Statut", "Emprunteur": "Emprunteur",
    "Note": "Note", "Date": "Date_Ajout", "Avis_Lecteurs": "Avis_Lecteurs"
}

def envoyer_whatsapp(message):
    return f"https://api.whatsapp.com/send?text={urllib.parse.quote(message)}"

# --- INTERFACE ---
st.title(" La boîte à livres à Méli-Mélo ")

col_user, col_refresh = st.columns([3, 1])
with col_user:
    liste_membres = get_liste_membres_fixes()
    utilisateur = st.selectbox("Utilisateur", liste_membres, key='user', label_visibility="collapsed")
with col_refresh:
    if st.button("🔄 Actualiser"):
        refresh()

# Message de bienvenue
st.success(f"😊 Bienvenue **{utilisateur}** !")

infos_user = get_membre_info(utilisateur)

# --- LOGIQUE NOTIFICATION FLASH ---
has_notif = False
nb_demandes = 0
if not df_livres.empty:
    mes_demandes = df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]] == "Demandé")]
    nb_demandes = len(mes_demandes)
    if nb_demandes > 0:
        has_notif = True
        st.warning(f"🔔 **Attention {utilisateur}** : Tu as {nb_demandes} demande(s) d'emprunt en attente !")

nom_onglet_emprunt = f"🤝 Emprunts ({nb_demandes})" if has_notif else "🤝 Emprunts"

st.write("---")
# RÉORGANISATION : Bibliothèque en premier, Mode d'emploi en dernier
onglets_noms = ["📖 Bibliothèque", nom_onglet_emprunt, "👤 Mon Profil", "➕ Ajouter"]
if utilisateur in ["Didier", "Amélie"]:
    onglets_noms.append("👤 Ajouter un membre")
onglets_noms.append("❓ Mode d'emploi")

onglets = st.tabs(onglets_noms)

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
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
                    if row.get(COL['Avis']): st.success(f"⭐ **L'avis du Proprio :** {row[COL['Avis']]}")
                    if row.get(COL['Avis_Lecteurs']):
                        with st.expander("💬 Voir les avis des lecteurs"):
                            st.markdown(row[COL['Avis_Lecteurs']])
                    
                    with st.expander("📝 J'ai déjà lu ce livre, je donne mon avis"):
                        n_l = st.select_slider("Ma Note", options=["📚","📚📚","📚📚📚","📚📚📚📚"], key=f"n_{idx}")
                        c_l = st.text_area("Mon commentaire", key=f"c_{idx}")
                        if st.button("Publier mon avis", key=f"p_{idx}"):
                            oidx = df_livres.index[df_livres[COL['Titre']] == row[COL['Titre']]][0] + 2
                            total = (str(row.get(COL["Avis_Lecteurs"], "")) + f"\n\n**{utilisateur}** ({n_l}) : {c_l}").strip()
                            sheet_livres.update_cell(oidx, 9, total)
                            refresh()

                    if statut == "Libre" and p_livre != utilisateur.strip():
                        if st.button(f"Demander l'emprunt", key=f"req_{idx}"):
                            oidx = df_livres.index[df_livres[COL['Titre']] == row[COL['Titre']]][0] + 2
                            sheet_livres.update_cell(oidx, 5, "Demandé")
                            sheet_livres.update_cell(oidx, 6, utilisateur); refresh()
                st.write("---")

# --- 2. EMPRUNTS ---
with onglets[1]:
    st.subheader("🤝 Suivi des emprunts")
    res = df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]].isin(['Demandé', 'Emprunté']))]
    if not res.empty:
        for idx, r in res.iterrows():
            emp = r[COL["Emprunteur"]]
            st.warning(f"🔔 **{emp}** attend une réponse pour : **{r[COL['Titre']]}**")
            if r[COL["Statut"]] == "Demandé":
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"✅ Valider", key=f"v_{idx}"):
                        oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                        sheet_livres.update_cell(oidx, 5, "Emprunté")
                        st.link_button("📱 Prévenir", envoyer_whatsapp(f"C'est OK pour '{r[COL['Titre']]}'. On s'organise ?"))
                with col2:
                    if st.button(f"❌ Décliner", key=f"d_{idx}"):
                        oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                        sheet_livres.update_cell(oidx, 5, "Libre"); sheet_livres.update_cell(oidx, 6, "")
                        st.link_button("📱 Prévenir (Refus)", envoyer_whatsapp(f"Désolé {emp}, je ne peux pas prêter '{r[COL['Titre']]}' pour le moment. 😉"))
            elif r[COL["Statut"]] == "Emprunté":
                if st.button(f"🔄 Marquer comme rendu", key=f"r_{idx}"):
                    oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                    sheet_livres.update_cell(oidx, 5, "Libre"); sheet_livres.update_cell(oidx, 6, ""); refresh()
    else: st.write("Aucune demande reçue pour vos livres.")

# --- 3. PROFIL ---
with onglets[2]:
    st.subheader(f"👤 {utilisateur}")
    with st.form("sugg"):
        s = st.text_input("Suggérer un nouveau membre (Nom & Prénom)")
        if st.form_submit_button("Préparer message WhatsApp"):
            st.link_button("📱 Envoyer à Didier/Amélie", envoyer_whatsapp(f"Hello, je suggère d'ajouter {s} au club ! 📚"))
    st.write("---")
    mes_l = df_livres[df_livres[COL["Proprio"]] == utilisateur]
    for idx, r in mes_l.iterrows():
        with st.expander(f"📙 {r[COL['Titre']]}"):
            if st.button("Supprimer de ma liste", key=f"del_{idx}"):
                oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                sheet_livres.delete_rows(oidx); refresh()

# --- 4. AJOUTER ---
with onglets[3]:
    mode = st.radio("", ["✅ Manuel", "📤 Import Excel"], horizontal=True)
    if mode == "✅ Manuel":
        with st.form("add"):
            t, a = st.text_input("Titre"), st.text_input("Auteur")
            n = st.select_slider("Ma note", options=["📚","📚📚","📚📚📚","📚📚📚📚"])
            c = st.text_area("Mon Avis (Proprio)")
            if st.form_submit_button("Ajouter à la boîte"):
                sheet_livres.append_row([t, a, utilisateur, c, "Libre", "", n, datetime.now().strftime("%Y-%m-%d"), ""]); refresh()
    else:
        st.markdown("### 📤 Importation groupée")
        st.link_button("📥 Télécharger le modèle Excel", "https://raw.githubusercontent.com/didierjaccoud144-bit/BiblioClub/main/BiblioMod.xlsx")
        up = st.file_uploader("Charge ton fichier rempli", type="xlsx")
        if up and st.button("Lancer l'import"):
            df_i = pd.read_excel(up).fillna("")
            for _, r in df_i.iterrows():
                sheet_livres.append_row([r['Titre'], r.get('Auteur',''), utilisateur, r.get('Avis',''), "Libre", "", r.get('Note',''), datetime.now().strftime("%Y-%m-%d"), ""]); refresh()

# --- 5. AJOUTER UN MEMBRE ---
idx_guide = 4
if utilisateur in ["Didier", "Amélie"]:
    idx_guide = 5
    with onglets[4]:
        st.subheader("👤 Inscrire un nouveau membre")
        with st.form("nm"):
            n, t, p, r = st.text_input("Prénom"), st.text_input("Téléphone"), st.text_input("Lieu (Position)"), st.text_input("Conditions Retrait")
            if st.form_submit_button("Enregistrer le membre"):
                sheet_membres.append_row([n, t, "", p, r]); st.success("Membre ajouté !"); refresh()

# --- DERNIER ONGLET : MODE D'EMPLOI DÉTAILLÉ ---
with onglets[idx_guide]:
    st.subheader("📖 Guide complet du membre")
    
    with st.expander("📱 1. Installer l'application sur mon écran", expanded=True):
        st.markdown("""
        Pour accéder à la boîte à livres en un clic, comme une vraie appli :
        * **Sur iPhone** : Ouvre le lien dans **Safari** -> Clique sur l'icône **Partage** (le carré avec une flèche vers le haut) -> Fais défiler et clique sur **« Sur l'écran d'accueil »**.
        * **Sur Android** : Ouvre le lien dans **Chrome** -> Clique sur les **3 petits points** en haut à droite -> Sélectionne **« Installer l'application »** ou « Ajouter à l'écran d'accueil ».
        """)

    with st.expander("🔍 2. Comment emprunter un livre ?"):
        st.markdown("""
        1. Navigue dans la **Bibliothèque**.
        2. Repère les livres avec le symbole **📗 (Vert)** : ils sont disponibles !
        3. Clique sur **"Demander l'emprunt"**. 
        4. Le livre passe en **📙 (Orange)**. Le propriétaire reçoit une alerte et doit valider ton emprunt.
        5. Une fois validé, contacte le propriétaire via WhatsApp pour convenir du retrait.
        """)

    with st.expander("🤝 3. Comment gérer mes propres livres ?"):
        st.markdown("""
        * Dès que tu te connectes, un **bandeau orange** t'avertit si quelqu'un veut t'emprunter un livre.
        * Va dans l'onglet **Emprunts** : tu peux **✅ Valider** (un message WhatsApp pré-rempli s'ouvrira) ou **❌ Décliner** si le livre n'est pas dispo.
        * Quand on te rend le livre, clique sur **🔄 Rendu** pour qu'il redevienne vert dans la liste.
        """)

    with st.expander("💬 4. Partager mon avis (Livre d'Or)"):
        st.markdown("""
        Tu as déjà lu un livre de la liste ? Enrichis l'expérience des autres !
        * Sous chaque livre dans la Bibliothèque, clique sur **"Donner mon avis"**.
        * Laisse ta note et ton commentaire. Tous les membres pourront le lire en cliquant sur **"Voir les avis des lecteurs"**.
        """)

    with st.expander("➕ 5. Ajouter ou Suggérer"):
        st.markdown("""
        * **Ajouter** : Dans l'onglet dédié, saisis tes livres manuellement ou utilise l'import Excel pour charger toute ta bibliothèque.
        * **Suggérer** : Dans ton **Profil**, utilise le formulaire pour proposer un nouvel ami. Didier ou Amélie s'occuperont de lui créer son accès.
        """)

st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
