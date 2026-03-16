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

# --- FONCTION WHATSAPP ---
def envoyer_whatsapp(telephone, message):
    msg_code = urllib.parse.quote(message)
    link = f"https://wa.me/{telephone}?text={msg_code}"
    return link

# --- TITRE ---
st.title("📚 Le Biblio Club")
st.write("---")

# --- SÉLECTION UTILISATEUR ---
liste_membres = df_membres['Prénom'].tolist() if 'Prénom' in df_membres.columns else df_membres['Nom'].tolist()
utilisateur = st.selectbox("👤 Qui êtes-vous ?", liste_membres)
infos_user = df_membres[df_membres.iloc[:, 0] == utilisateur].iloc[0] # Choppe la ligne du membre

st.write("---")

# --- NAVIGATION ---
onglets = st.tabs(["📖 Bibliothèque", "🤝 Emprunts", "👤 Mon Profil", "➕ Ajouter", "📤 Import"])

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
    st.subheader("Les pépites disponibles")
    for idx, row in df_livres.iloc[::-1].iterrows():
        # Détermination du statut et de la couleur
        statut = str(row.get('Statut', 'Libre')).strip()
        color = "green" if statut == "Libre" else "orange" if statut == "Demandé" else "red"
        
        with st.container():
            c1, c2 = st.columns([1, 4])
            with c1: st.title("📕")
            with c2:
                st.markdown(f"### {row['Titre']} :{color}[ ({statut})]")
                st.write(f"**Auteur :** {row.get('Auteur')} | **Proprio :** {row.get('Membre')}")
                
                if statut == "Libre" and row['Membre'] != utilisateur:
                    if st.button(f"Demander à {row['Membre']}", key=f"btn_{idx}"):
                        # Message au proprio
                        tel_proprio = df_membres[df_membres.iloc[:, 0] == row['Membre']].iloc[0].get('Téléphone', '')
                        texte = f"Salut {row['Membre']}, c'est {utilisateur} ! Je serais super intéressé par ton livre '{row['Titre']}' sur le Biblio Club. Est-il disponible ? 😊"
                        st.link_button("📱 Envoyer la demande via WhatsApp", envoyer_whatsapp(tel_proprio, texte))
            st.write("---")

# --- 2. GESTION DES EMPRUNTS ---
with onglets[1]:
    st.subheader("🤝 Livres en mouvement")
    empruntes = df_livres[df_livres['Statut'].isin(['Demandé', 'Emprunté'])]
    if not empruntes.empty:
        st.table(empruntes[['Titre', 'Membre', 'Emprunteur', 'Statut']])
    else:
        st.info("Tous les livres sont au chaud chez leurs propriétaires !")

# --- 3. MON PROFIL & RÉPONSES ---
with onglets[2]:
    st.subheader(f"Mon espace ({utilisateur})")
    mes_livres = df_livres[df_livres['Membre'] == utilisateur]
    
    if not mes_livres.empty:
        for idx, row in mes_livres.iterrows():
            st.write(f"📙 **{row['Titre']}**")
            if row.get('Statut') == "Demandé":
                demandeur = row.get('Emprunteur', 'quelqu\'un')
                st.warning(f"⚠️ {demandeur} veut ce livre !")
                
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    if st.button("✅ Accepter", key=f"acc_{idx}"):
                        msg = f"Hello ! C'est {utilisateur}. Ton prêt pour '{row['Titre']}' est validé ! Tu peux passer le prendre {infos_user.get('Infos_Retrait', 'à mon adresse habituelle')}. À bientôt !"
                        # Note: Ici on cherche le tel du demandeur dans la table membres
                        tel_demandeur = df_membres[df_membres.iloc[:, 0] == demandeur].iloc[0].get('Téléphone', '')
                        st.link_button("Envoyer confirmation WhatsApp", envoyer_whatsapp(tel_demandeur, msg))
                with col_r2:
                    if st.button("❌ Refuser", key=f"ref_{idx}"):
                        st.write("Demande refusée (pensez à prévenir le membre par message !)")
            st.write("---")

# --- 4 & 5 (AJOUT/IMPORT) ---
with onglets[3]:
    with st.form("add"):
        t, a, av = st.text_input("Titre"), st.text_input("Auteur"), st.text_area("Avis")
        if st.form_submit_button("Ajouter"):
            sheet_livres.append_row([t, a, utilisateur, av, "Libre", ""])
            st.success("Livre ajouté !"); st.balloons()

with onglets[4]:
    up = st.file_uploader("Fichier Excel", type="xlsx")
    if up and st.button("Lancer l'import"):
        df_im = pd.read_excel(up)
        for _, r in df_im.iterrows():
            sheet_livres.append_row([r['Titre'], r.get('Auteur',''), utilisateur, r.get('Avis_delire',''), "Libre", ""])
        st.success("Import terminé !")

st.write("---")
st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
