import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import time
import pytz

st.set_page_config(page_title="Urna Eletrônica", layout="wide")
st.title("🗳️ Eleição do Grêmio Estudantil")

# 1. GSheets
conn = st.connection("gsheets", type=GSheetsConnection)

students_df = conn.read(worksheet="alunos", ttl="1h")
candidates_df = conn.read(worksheet="candidatos", ttl=5)

students_df['ja_votou'] = pd.to_numeric(students_df['ja_votou'], errors='coerce').fillna(0).astype(int)

# --- Variáveis de Estado ---
if "current_class" not in st.session_state:
    st.session_state.current_class = students_df["turma"].dropna().unique()[0]
if 'selected_candidate' not in st.session_state:
    st.session_state.selected_candidate = None
# NOVA VARIÁVEL: Guarda a mensagem de sucesso temporariamente
if 'last_success' not in st.session_state:
    st.session_state.last_success = None


# --- Sidebar - Área do Mesário ---
st.sidebar.header("Área do Mesário")
available_classes = students_df["turma"].dropna().unique()

selected_class = st.sidebar.selectbox(
    "1. Selecione a Turma:", 
    available_classes,
    index=list(available_classes).index(st.session_state.current_class),
    key="class_selector"
)
st.session_state.current_class = selected_class

# Filtro (turma + não votou)
class_students = students_df[(students_df["turma"] == selected_class) & (students_df["ja_votou"] == 0)]

student_options = ["-- Selecione o Estudante --"] + class_students["nome"].tolist()
selected_student = st.sidebar.selectbox(
    "2. Selecione o Estudante:", 
    student_options,
    key=f"select_{selected_class}"
)

# Trava lógica pós voto
can_vote = False

if selected_student != "-- Selecione o Estudante --":
    st.info(f"Urna liberada para: {selected_student}")
    can_vote = True  # Destrava
else:
    st.info("Aguardando mesário selecionar um aluno...")
    can_vote = False # Trava

st.divider()

if st.session_state.last_success:
    st.success(st.session_state.last_success, icon="✅")
    st.session_state.last_success = None


st.subheader("Toque no seu candidato:")
candidates_list = candidates_df["candidato"].dropna().tolist()
num_cols = 2

def onclick(candidate_name):
    st.session_state.selected_candidate = candidate_name

for i in range(0, len(candidates_list), num_cols):
    batch = candidates_list[i : i + num_cols]
    cols = st.columns(num_cols)

    for j, name in enumerate(batch):
        actual_index = i + j
        with cols[j]:
            img = candidates_df.iloc[actual_index]['link_img']
            if pd.notna(img) and img != "x":
                st.image(img, use_container_width=True)

            # Trava
            lock = (not can_vote) or (st.session_state.selected_candidate is not None)

            st.button(
                f"VOTAR: {name}", 
                key=f"btn_{actual_index}", 
                use_container_width=True, 
                disabled=lock,
                on_click=onclick,
                args=(name,) # nome arg.
            )

# Gravação

if st.session_state.selected_candidate:
    with st.spinner("Gravando..."):

        # Atualiza Alunos
        students_df.loc[students_df['nome'] == selected_student, 'ja_votou'] = 1
        conn.update(worksheet="alunos", data=students_df)
                        
        # Atualiza Votos
        fuse_br = pytz.timezone("America/Sao_Paulo")
        now_br = datetime.now(fuse_br)
        votes_df = conn.read(worksheet="votos", ttl=5)
        
        new_vote = pd.DataFrame([{
            "data_hora": now_br.strftime("%d/%m/%Y %H:%M:%S"),
            "candidato_votado": st.session_state.selected_candidate
        }])
        
        updated_votes_df = pd.concat([votes_df, new_vote], ignore_index=True)
        conn.update(worksheet="votos", data=updated_votes_df)
                
    st.session_state.last_success = f"Voto de {selected_student} gravado com sucesso!"
    st.session_state.selected_candidate = None 
    st.rerun()