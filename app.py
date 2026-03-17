import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import urllib.parse
from datetime import datetime

# Importation du fichier de profil membres
from membres_profil import get_membre_info, get_liste_membres_fixes

# --- CONFIGURATION ---
st.set_page_config(page_title="Méli-Mélo", page_icon="📚", layout="centered")

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
st.cache_data.clear()
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

st.success(f"😊 Bienvenue **{utilisateur}** !")

# NOTIFICATIONS
has_notif = False
nb_demandes = 0
if not df_livres.empty:
    mes_demandes = df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]] == "Demandé")]
    nb_demandes = len(mes_demandes)
    if nb_demandes > 0:
        has_notif = True
        st.warning(f"🔔 **Alerte** : Tu as {nb_demandes} demande(s) de prêt en attente !")

nom_onglet_emprunt = f"🤝 Emprunts ({nb_demandes})" if has_notif else "🤝 Emprunts"

st.write("---")
onglets_noms = ["📖 Bibliothèque", nom_onglet_emprunt, "👤 Mon Profil", "➕ Ajouter"]
if utilisateur in ["Didier", "Amélie"]:
    onglets_noms.append("👤 Gérance")
onglets_noms.append("❓ Mode d'emploi")

onglets = st.tabs(onglets_noms)

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
    recherche = st.text_input("🔍 Rechercher un titre ou un auteur...", "").lower()
    tri = st.selectbox("Trier par", ["Derniers ajouts", "Note", "Titre (A-Z)"])
    df_tri = df_livres.copy()
    if recherche:
        df_tri = df_tri[df_tri[COL["Titre"]].str.lower().str.contains(recherche) | df_tri[COL["Auteur"]].str.lower().str.contains(recherche)]
    if tri == "Titre (A-Z)": df_tri = df_tri.sort_values(by=COL["Titre"])
    elif tri == "Note": df_tri = df_tri.sort_values(by=COL["Note"], ascending=False)
    else: df_tri = df_tri.iloc[::-1]

    for idx, row in df_tri.iterrows():
        statut = str(row.get(COL["Statut"], 'Libre')).strip() or "Libre"
        p_livre = str(row[COL["Proprio"]]).strip()
        emoji, color = ("📗", "green") if statut == "Libre" else (("⏳", "orange") if statut == "Demandé" else ("📕", "red"))
        with st.container():
            c1, c2 = st.columns([1, 4])
            with c1: st.title(emoji)
            with c2:
                st.markdown(f"### {row[COL['Titre']]} {row.get(COL['Note'], '')} :{color}[ ({statut})]")
                st.write(f"**{row[COL['Auteur']]}** | **Propriétaire :** {p_livre}")
                if row.get(COL['Avis']): st.success(f"⭐ **L'avis du proprio :** {row[COL['Avis']]}")
                if row.get(COL['Avis_Lecteurs']):
                    with st.expander("💬 Avis des autres lecteurs"): st.markdown(row[COL['Avis_Lecteurs']])
                with st.expander("📝 Mon avis sur ce livre"):
                    n_l = st.select_slider("Note", options=["📚","📚📚","📚📚📚","📚📚📚📚"], key=f"n_{idx}")
                    c_l = st.text_area("Commentaire", key=f"c_{idx}")
                    if st.button("Publier mon avis", key=f"p_{idx}"):
                        oidx = int(df_livres.index[df_livres[COL['Titre']] == row[COL['Titre']]][0] + 2)
                        total = (str(row.get(COL["Avis_Lecteurs"], "")) + f"\n\n**{utilisateur}** ({n_l}) : {c_l}").strip()
                        sheet_livres.update_cell(oidx, 9, total); refresh()
                if statut == "Libre" and p_livre != utilisateur.strip():
                    if st.button(f"Demander l'emprunt", key=f"req_{idx}"):
                        oidx = int(df_livres.index[df_livres[COL['Titre']] == row[COL['Titre']]][0] + 2)
                        sheet_livres.update_cell(oidx, 5, "Demandé"); sheet_livres.update_cell(oidx, 6, utilisateur); refresh()
            st.write("---")

# --- 2. EMPRUNTS ---
with onglets[1]:
    st.subheader("🤝 Suivi des demandes")
    res = df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]].isin(['Demandé', 'Emprunté']))]
    if not res.empty:
        for idx, r in res.iterrows():
            emp = r[COL["Emprunteur"]]
            st.warning(f"🔔 **{emp}** souhaite emprunter : **{r[COL['Titre']]}**")
            if r[COL["Statut"]] == "Demandé":
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"✅ Valider le prêt", key=f"v_{idx}"):
                        oidx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2)
                        sheet_livres.update_cell(oidx, 5, "Emprunté")
                        st.link_button("📱 Envoyer un WhatsApp", envoyer_whatsapp(f"Hello {emp}, c'est tout bon pour '{r[COL['Titre']]}'. On se voit quand pour que je te le passe ?"))
                with col2:
                    if st.button(f"❌ Refuser", key=f"d_{idx}"):
                        oidx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2)
                        sheet_livres.update_cell(oidx, 5, "Libre"); sheet_livres.update_cell(oidx, 6, ""); refresh()
            elif r[COL["Statut"]] == "Emprunté":
                if st.button(f"🔄 Marquer comme rendu", key=f"r_{idx}"):
                    oidx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2)
                    sheet_livres.update_cell(oidx, 5, "Libre"); sheet_livres.update_cell(oidx, 6, ""); refresh()
    else: st.write("Aucune demande ou prêt en cours pour vos livres.")

# --- 3. PROFIL ---
with onglets[2]:
    st.subheader(f"👤 Profil de {utilisateur}")
    st.markdown("### 📦 Mes livres prêtés ou demandés")
    mes_prets = df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]].isin(['Demandé', 'Emprunté']))]
    if not mes_prets.empty:
        recap = mes_prets[[COL["Titre"], COL["Emprunteur"], COL["Statut"]]].copy()
        recap[COL["Statut"]] = recap[COL["Statut"]].replace({"Demandé": "⏳ Demande reçue", "Emprunté": "📕 Chez l'emprunteur"})
        st.table(recap)
    else: st.info("Tous vos livres sont actuellement à la maison. 🏠")
    
    st.write("---")
    st.markdown("#### 📢 Suggérer un nouveau membre")
    st.write("Une personne veut rejoindre Méli-Mélo ? Proposez-la ici !")
    with st.form("sugg"):
        s = st.text_input("Nom, Prénom et si possible n° de tél")
        if st.form_submit_button("Envoyer la suggestion"):
            st.link_button("📱 WhatsApp à Didier/Amélie", envoyer_whatsapp(f"Salut ! Je suggère d'ajouter ce nouveau membre au club : {s}"))
    
    st.write("---")
    st.markdown("#### 📚 Gérer ma collection")
    mes_l = df_livres[df_livres[COL["Proprio"]] == utilisateur]
    for idx, r in mes_l.iterrows():
        st_lbl = "⏳ Demandé" if r[COL['Statut']] == "Demandé" else r[COL['Statut']]
        with st.expander(f"📙 {r[COL['Titre']]} ({st_lbl})"):
            if st.button("Supprimer définitivement", key=f"del_{idx}"):
                oidx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2)
                sheet_livres.delete_rows(oidx); refresh()

# --- 4. AJOUTER ---
with onglets[3]:
    st.subheader("➕ Ajouter des livres à la bibliothèque")
    mode = st.radio("Méthode d'ajout :", ["✅ Un par un (Manuel)", "📤 Plusieurs livres (Import Excel)"], horizontal=True)
    if mode == "✅ Un par un (Manuel)":
        with st.form("add"):
            t = st.text_input("Titre du livre")
            a = st.text_input("Auteur")
            n = st.select_slider("Ma note personnelle", ["📚","📚📚","📚📚📚","📚📚📚📚"])
            c = st.text_area("Mon avis (pour donner envie !)")
            if st.form_submit_button("Ajouter à la bibliothèque"):
                sheet_livres.append_row([t, a, utilisateur, c, "Libre", "", n, datetime.now().strftime("%Y-%m-%d"), ""]); refresh()
    else:
        st.info("Utilisez cette méthode pour importer votre bibliothèque d'un coup.")
        st.link_button("📥 Télécharger le modèle Excel", "https://raw.githubusercontent.com/didierjaccoud144-bit/BiblioClub/main/BiblioMod.xlsx")
        up = st.file_uploader("Déposez votre fichier Excel ici", type="xlsx")
        if up and st.button("Lancer l'importation massive"):
            try:
                df_i = pd.read_excel(up).fillna("")
                lignes = [[str(ri['Titre']), str(ri.get('Auteur','')), utilisateur, str(ri.get('Avis','')), "Libre", "", str(ri.get('Note','📚📚')), datetime.now().strftime("%Y-%m-%d"), ""] for _, ri in df_i.iterrows()]
                sheet_livres.append_rows(lignes); refresh()
            except Exception as e: st.error(f"Erreur de format : {e}")

# --- 5. GÉRANCE & MODE D'EMPLOI ---
idx_guide = 4
if utilisateur in ["Didier", "Amélie"]:
    idx_guide = 5
    with onglets[4]:
        st.subheader("👤 Administration")
        with st.form("nm"):
            n, t, p, r = st.text_input("Prénom"), st.text_input("Tél"), st.text_input("Lieu"), st.text_input("Retrait")
            if st.form_submit_button("Enregistrer le membre"):
                sheet_membres.append_row([n, t, "", p, r]); st.success("Membre ajouté !"); refresh()

with onglets[idx_guide]:
    st.title("📖 Mode d'emploi Méli-Mélo")
    
    with st.expander("📱 1. Installer l'application sur son téléphone", expanded=True):
        st.markdown("""
        L'application Méli-Mélo s'installe comme une "App" classique pour être accessible en un clic :
        * **Sur iPhone (Safari)** : Appuyez sur l'icône **Partage** (le carré avec une flèche vers le haut) tout en bas, puis faites défiler et choisissez **« Sur l'écran d'accueil »**.
        * **Sur Android (Chrome)** : Appuyez sur les **3 petits points** en haut à droite, puis choisissez **« Installer l'application »** ou **« Ajouter à l'écran d'accueil »**.
        """)

    with st.expander("🔍 2. Trouver un livre"):
        st.markdown("""
        * Utilisez la **Barre de recherche** en haut de la bibliothèque pour taper un titre ou un auteur.
        * Utilisez le menu de **Tri** pour voir les derniers livres ajoutés ou les mieux notés.
        * **Code couleur :**
            * 📗 **Vert** : Disponible.
            * ⏳ **Sablier** : Quelqu'un a demandé le livre, on attend la réponse du proprio.
            * 📕 **Rouge** : Le livre est actuellement chez un emprunteur.
        """)

    with st.expander("➕ 3. Partager ses propres livres"):
        st.markdown("""
        Deux solutions dans l'onglet **Ajouter** :
        * **Le mode Manuel** : Idéal pour ajouter un livre de temps en temps.
        * **L'import Excel** : Si vous avez 50 livres à partager, téléchargez notre modèle Excel, remplissez-le et renvoyez-le via l'appli. C'est magique !
        """)

    with st.expander("🤝 4. Emprunter et Prêter (Le cycle WhatsApp)"):
        st.markdown("""
        1.  **La Demande** : Vous voulez un livre ? Cliquez sur **Demander**.
        2.  **La Validation** : Le propriétaire reçoit une alerte sur son appli. S'il accepte, il clique sur **Valider**.
        3.  **Le Contact** : Un bouton **WhatsApp** apparaît. Il permet d'envoyer un message pré-rempli pour fixer le rendez-vous (ex: "Je te le pose demain au retrait ?").
        4.  **Le Retour** : Quand le livre revient chez son propriétaire, ce dernier clique sur **🔄 Rendu** pour le remettre en vert.
        """)

    with st.expander("📢 5. Suggérer un nouveau membre"):
        st.markdown("""
        Le club grandit grâce à vous ! Dans l'onglet **Mon Profil**, vous pouvez proposer un ami. 
        En cliquant sur le bouton, un message **WhatsApp** est automatiquement généré pour prévenir Didier ou Amélie, qui s'occuperont de créer l'accès.
        """)

st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
