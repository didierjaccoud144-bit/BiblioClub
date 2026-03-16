import subprocess
import sys

# --- INSTALLATION AUTOMATIQUE ---
for library in ["xlsxwriter", "openpyxl", "gspread", "google-auth"]:
    try:
        __import__(library)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", library])

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import os
import io
import time

# ==========================================
# 1. CONFIGURATION & STYLE
# ==========================================
st.set_page_config(page_title="Biblio Club", layout="wide", page_icon="📚")

LISTE_AVATARS = ["🪄", "🎅", "🧑‍🎄", "🧙‍♀️", "🧶", "🧚‍♀️", "🐱", "🇨🇭", "☕️", "🫖", "🐈‍⬛", "⛄️"]

st.markdown("""
    <style>
    h1 { font-weight: 800; color: #ff4b4b; margin-bottom: 0px; }
    .stExpander { border: 1px solid #e0e0e0; border-radius: 12px; background-color: rgba(128, 128, 128, 0.05); }
    .notif-box { background-color: #fff3cd; border-left: 5px solid #ffc107; padding: 15px; border-radius: 8px; margin-bottom: 10px; color: #856404; font-weight: bold; }
    .msg-recu { background-color: #d4edda; border-left: 5px solid #28a745; padding: 15px; border-radius: 8px; margin-bottom: 10px; color: #155724; }
    .instruction-box { background-color: #e8f5e9; border: 1px dashed #28a745; padding: 10px; border-radius: 5px; margin-top: 5px; }
    .review-box { background-color: #f1f3f4; padding: 10px; border-radius: 10px; margin-bottom: 5px; border-left: 3px solid #ff4b4b; }
    .score-books { color: #ff4b4b; font-weight: bold; }
    .footer { text-align: center; color: #888; font-size: 0.8em; margin-top: 50px; border-top: 1px solid #eee; padding-top: 20px; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. CONNEXIONS & UTILS
# ==========================================
SHEET_ID = "1_F6C1u79GVp4zwAdzWq_kxBwTX8t2B0VwA-VFG2p2l8"

def get_gspread_client():
    repertoire = os.path.dirname(os.path.abspath(__file__))
    path_cle = os.path.join(repertoire, "cle_google.json")
    if not os.path.exists(path_cle): path_cle = os.path.join(repertoire, "cle_google.json.txt")
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(path_cle, scopes=scope)
    return gspread.authorize(creds)

def generer_modele_excel():
    output = io.BytesIO()
    df_modele = pd.DataFrame(columns=['Titre', 'Auteur', 'Id_livre', 'Avis_delire'])
    df_modele.loc[0] = ["Le Petit Prince", "St-Exupéry", "9782070612758", "Indémodable !"]
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_modele.to_excel(writer, index=False)
    return output.getvalue()

@st.cache_data(ttl=2)
def load_data(sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    df = pd.read_csv(url)
    df.columns = [str(c).strip().capitalize().replace('é','e').replace('î','i') for c in df.columns]
    df = df.fillna("").replace("nan", "").replace("None", "")
    if sheet_name == "Livres":
        nouveaux_noms = ['ID_livre', 'Titre', 'Auteur', 'Maitre', 'Squatteur', 'Date-Pret', 'Avis_Delire', 'Statut', 'Coordonnees', 'Date_Ajout']
        if len(df.columns) >= len(nouveaux_noms):
            df.columns = nouveaux_noms + list(df.columns[len(nouveaux_noms):])
        df['Maitre'] = df['Maitre'].str.strip()
    elif sheet_name == "Membres":
        df.columns = ['Prenom', 'Code_secret', 'Avatar', 'Position'] + list(df.columns[4:])
        df['Prenom'] = df['Prenom'].str.strip()
    return df

# ==========================================
# 3. ACTIONS
# ==========================================
def executer_action(onglet, action, index_row=None, data=None):
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(SHEET_ID).worksheet(onglet)
        row_idx = int(index_row) + 2 if index_row is not None else None
        
        if action == "ajouter_avis":
            ancien = sheet.cell(row_idx, 7).value or ""
            nouveau = f"[{user_name}|{data['note']}|{data['commentaire']}]"
            sheet.update_cell(row_idx, 7, f"{ancien} | {nouveau}" if ancien else nouveau)
        elif action == "valider":
            demandeur = str(data['statut']).split("Attente:")[1].strip()
            sheet.update_cell(row_idx, 5, demandeur) 
            sheet.update_cell(row_idx, 6, datetime.now().strftime("%d/%m/%Y")) 
            sheet.update_cell(row_idx, 8, f"Valide: {data['msg']}") 
        elif action == "demander":
            sheet.update_cell(row_idx, 8, f"Attente: {user_name}") 
        elif action == "rendre":
            sheet.update_cell(row_idx, 5, "") 
            sheet.update_cell(row_idx, 6, "") 
            sheet.update_cell(row_idx, 8, "Dispo")
        elif action == "maj_profil":
            sheet.update_cell(row_idx, 3, data['avatar']) 
            sheet.update_cell(row_idx, 4, data['coord'])
        elif action == "ajouter_ligne": sheet.append_row(data)
        elif action == "ajouter_batch": sheet.append_rows(data.values.tolist())
        elif action == "supprimer": sheet.delete_rows(row_idx)
            
        st.cache_data.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Erreur : {e}")

df_livres = load_data("Livres")
df_membres = load_data("Membres")

# ==========================================
# 4. BARRE LATÉRALE
# ==========================================
with st.sidebar:
    st.title("👤 Mon Espace")
    liste_p = [p for p in df_membres['Prenom'].tolist() if str(p).strip() != ""]
    user_name = st.selectbox("Qui es-tu ?", ["Choisir..."] + liste_p)
    
    avatar_val, coord_val, user_idx = "📖", "", None
    if user_name != "Choisir...":
        user_name = user_name.strip()
        user_info = df_membres[df_membres['Prenom'] == user_name]
        if not user_info.empty:
            user_idx = user_info.index[0]
            avatar_val = user_info['Avatar'].values[0] or "📖"
            coord_val = str(user_info['Position'].values[0])
            st.success(f"Salut {user_name} {avatar_val}")

# ==========================================
# 5. MESSAGES, NOTIFS & GESTION
# ==========================================
st.title("🧙‍♂️ Biblio Club : Le Cercle des Dix")

if user_name != "Choisir...":
    demandes_recues = df_livres[(df_livres['Maitre'] == user_name) & (df_livres['Statut'].astype(str).str.contains("Attente:", na=False))]
    mes_messages = df_livres[(df_livres['Squatteur'] == user_name) & (df_livres['Statut'].astype(str).str.contains("Valide:", na=False))]
    
    badge = " 🔴" if (not demandes_recues.empty or not mes_messages.empty) else ""

    if not mes_messages.empty:
        st.subheader("📬 Messages pour moi")
        for idx, row in mes_messages.iterrows():
            msg_p = str(row['Statut']).split("Valide:")[1]
            st.markdown(f"""<div class="msg-recu">✅ <b>{row['Maitre']}</b> a accepté pour <i>"{row['Titre']}"</i> !<br>📍 {msg_p}</div>""", unsafe_allow_html=True)

    if not demandes_recues.empty:
        st.subheader("🔔 Demandes à valider")
        for idx, row in demandes_recues.iterrows():
            demandeur = str(row['Statut']).split("Attente:")[1].strip()
            with st.container():
                st.markdown(f"""<div class="notif-box">🤝 {demandeur} demande : "{row['Titre']}"</div>""", unsafe_allow_html=True)
                with st.form(key=f"val_{idx}"):
                    instr = st.text_input("Consigne de retrait", placeholder="Ex: Sur mon paillasson...")
                    if st.form_submit_button("Confirmer le prêt"):
                        executer_action("Livres", "valider", index_row=idx, data={'statut': row['Statut'], 'msg': instr})

    with st.expander(f"✨ MON ESPACE PERSONNEL & GESTION{badge}"):
        t1, t2, t3 = st.tabs(["👤 Profil", "➕ Ajout Manuel", "📤 Import Excel"])
        with t1:
            st.metric("Livres en prêt", len(df_livres[df_livres['Maitre'] == user_name]))
            with st.form("f_prof"):
                new_a = st.selectbox("Avatar", LISTE_AVATARS, index=LISTE_AVATARS.index(avatar_val) if avatar_val in LISTE_AVATARS else 0)
                new_c = st.text_input("Localité", value=coord_val)
                if st.form_submit_button("Mettre à jour"):
                    executer_action("Membres", "maj_profil", index_row=user_idx, data={'avatar': new_a, 'coord': new_c})
        with t2:
            with st.form("f_add_man", clear_on_submit=True):
                at, aa, avis = st.text_input("Titre *"), st.text_input("Auteur"), st.text_area("Mon Avis")
                if st.form_submit_button("Ajouter"):
                    if at: executer_action("Livres", "ajouter_ligne", data=["", at, aa, user_name, "", "", avis, "Dispo", coord_val, datetime.now().strftime("%d/%m/%Y")])
        with t3:
            st.download_button("📝 Modèle Excel", data=generer_modele_excel(), file_name="modele.xlsx")
            f_imp = st.file_uploader("Fichier Excel", type=['xlsx'])
            if f_imp:
                df_i = pd.read_excel(f_imp)
                if st.button("🚀 Confirmer l'import"):
                    df_i.columns = [str(c).strip().capitalize() for c in df_i.columns]
                    df_f = pd.DataFrame()
                    df_f['ID']=df_i['Id_livre'] if 'Id_livre' in df_i.columns else ""; df_f['Titre']=df_i['Titre']
                    df_f['Auteur']=df_i['Auteur'] if 'Auteur' in df_i.columns else "Inconnu"
                    df_f['Maitre']=user_name; df_f['Squatteur']=""; df_f['Date']=""
                    df_f['Avis']=df_i['Avis_delire'] if 'Avis_delire' in df_i.columns else ""
                    df_f['Statut']="Dispo"; df_f['Coord']=coord_val
                    df_f['Date_Ajout']=datetime.now().strftime("%d/%m/%Y")
                    executer_action("Livres", "ajouter_batch", data=df_f.fillna(""))

# ==========================================
# 6. BIBLIOTHÈQUE (L'AFFICHAGE REVENU !)
# ==========================================
st.write("---")
st.subheader("📚 La Bibliothèque")
st.markdown('<div style="font-size:0.8em; color:gray; margin-bottom:10px;">📗 Dispo | 📙 En demande | 📕 Emprunté | 🆕 Nouveau</div>', unsafe_allow_html=True)

df_visible = df_livres[df_livres['Titre'] != ""]
for index, row in df_visible.iterrows():
    titre, proprio, statut = str(row['Titre']), str(row['Maitre']), str(row['Statut'])
    squatteur = str(row['Squatteur']).strip()
    
    is_dispo = (statut == "" or statut == "Dispo" or statut == "nan")
    is_attente = "Attente:" in statut
    ico = "📗" if is_dispo else ("📙" if is_attente else "📕")
    
    badge_new = ""
    try:
        d_l = datetime.strptime(str(row['Date_Ajout']), "%d/%m/%Y")
        if datetime.now() - d_l < timedelta(days=7): badge_new = " 🆕"
    except: pass

    with st.expander(f"{ico} {titre} — {row['Auteur']}{badge_new}"):
        col_t, col_a = st.columns([2, 1])
        with col_t:
            loc = f" ({row['Coordonnees']})" if str(row['Coordonnees']).strip() != "" else ""
            st.write(f"**Proprio :** {proprio}{loc}")
            
            # Avis cumulés
            st.markdown("**💬 Avis :**")
            avis_l = str(row['Avis_Delire']).split(" | ")
            if avis_l and avis_l[0] != "":
                for av in avis_l:
                    if "[" in av:
                        try:
                            p = av.replace("[","").replace("]","").split("|")
                            st.markdown(f"""<div class="review-box"><b>{p[0]}</b> {"📚"*int(p[1])}<br>{p[2]}</div>""", unsafe_allow_html=True)
                        except: pass
                    elif av.strip(): st.write(f"• {av}")
            else: st.info("Aucun avis.")

        with col_a:
            if user_name != "Choisir...":
                with st.popover("✍️ Avis"):
                    n = st.slider("Note", 1, 5, 3, key=f"s_{index}")
                    c = st.text_area("Texte", key=f"c_{index}")
                    if st.button("Publier", key=f"b_{index}"): executer_action("Livres", "ajouter_avis", index_row=index, data={'note': n, 'commentaire': c})
            st.divider()
            if user_name == proprio:
                if st.button("🗑️ Supprimer", key=f"d_{index}"): executer_action("Livres", "supprimer", index_row=index)
                if not is_dispo and not is_attente:
                    if st.button("📥 Rendu", key=f"r_{index}"): executer_action("Livres", "rendre", index_row=index)
            elif is_dispo and user_name != "Choisir...":
                if st.button("✨ Emprunter", key=f"q_{index}"): executer_action("Livres", "demander", index_row=index)

# ==========================================
# 7. CRÉDITS
# ==========================================
st.markdown(f"""<div class="footer">Une création <b>DJA’WEB</b> avec l’aide de Gemini IA</div>""", unsafe_allow_html=True)