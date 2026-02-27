import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import base64
import uuid
import secrets
from datetime import datetime

# ====================== CONFIGURAÇÕES ======================
DB_PATH = "condominio.db"

# ====================== FUNÇÕES DE SEGURANÇA ======================
def generate_salt() -> str:
    return base64.b64encode(secrets.token_bytes(16)).decode()

def hash_password(plain: str, salt: str) -> str:
    salt_bytes = base64.b64decode(salt)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt_bytes, 100_000)
    return base64.b64encode(dk).decode()

def verify_password(plain: str, stored_hash: str, stored_salt: str) -> bool:
    return hash_password(plain, stored_salt) == stored_hash

def calcular_tempo_finalizacao(inicio_str, fim_str):
    try:
        fmt = "%d/%m/%Y %H:%M"
        inicio = datetime.strptime(inicio_str, fmt)
        fim = datetime.strptime(fim_str, fmt)
        delta = fim - inicio
        dias = delta.days
        horas = delta.seconds // 3600
        minutos = (delta.seconds // 60) % 60
        partes = []
        if dias: partes.append(f"{dias}d")
        if horas: partes.append(f"{horas}h")
        if minutos or not partes: partes.append(f"{minutos}min")
        return " ".join(partes)
    except:
        return "N/A"

# ====================== BANCO DE DADOS ======================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# AJUSTE DE PERFORMANCE: Garante que o banco inicie apenas uma vez por sessão do servidor
@st.cache_resource
def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT NOT NULL,
        nome_completo TEXT,
        apartamento TEXT,
        email TEXT UNIQUE,
        telefone TEXT,
        data_cadastro TEXT DEFAULT (datetime('now','localtime')),
        ativo INTEGER DEFAULT 1
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS ocorrencias (
        id TEXT PRIMARY KEY,
        tipo_registro TEXT,
        categoria TEXT NOT NULL,
        local_detalhado TEXT,
        descricao TEXT NOT NULL,
        foto_base64 TEXT,
        status TEXT DEFAULT 'Pendente',
        data_envio TEXT,
        data_conclusao TEXT,
        criado_por TEXT DEFAULT 'Anônimo'
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS config (
        chave TEXT PRIMARY KEY,
        valor TEXT
    )""")

    # Criar Admin padrão se não existir
    if not cur.execute("SELECT 1 FROM usuarios WHERE username = 'admin'").fetchone():
        salt = generate_salt()
        hash_pw = hash_password("admin123", salt)
        cur.execute("""
            INSERT INTO usuarios (username, password_hash, salt, role, nome_completo, apartamento)
            VALUES (?, ?, ?, 'admin', 'Síndico Principal', 'Admin')
        """, ("admin", hash_pw, salt))

    cur.execute("INSERT OR IGNORE INTO config (chave, valor) VALUES ('whatsapp_urgente_link', '')")

    conn.commit()
    conn.close()
    return True

# Inicializa o banco
init_db()

# ====================== INTERFACE E ESTILO ======================
st.set_page_config(page_title="Condomínio Pro", layout="wide", page_icon="🏢")

st.markdown("""
    <style>
    .stButton>button {width: 100%; border-radius: 8px; font-weight: bold; margin-top: 8px;}
    .whatsapp-box {background-color: #e8f5e9; padding: 20px; border-radius: 12px; margin: 20px 0; text-align: center; border: 1px solid #c8e6c9; font-size: 1.1em;}
    .alert-box {background-color: #fff3cd; padding: 16px; border-radius: 8px; border-left: 5px solid #ffc107; margin: 16px 0;}
    </style>
""", unsafe_allow_html=True)

# Estado da Sessão
for key in ["user", "role", "nome", "apartamento"]:
    if key not in st.session_state:
        st.session_state[key] = None

# Sidebar
st.sidebar.title("🏢 Condomínio Pro")

if st.session_state.user is None:
    menu_options = ["📝 Abrir Registro (Anônimo)", "🔍 Consultar Protocolo", "👤 Login / Cadastro"]
else:
    menu_options = ["📝 Abrir Registro", "🔍 Consultar Protocolo"]
    if st.session_state.role == "admin":
        menu_options.append("📊 Painel Administrativo")
    menu_options += ["👋 Meus Chamados", "🚪 Sair"]

menu = st.sidebar.radio("Navegação", menu_options)

if menu == "🚪 Sair":
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()

# ====================== LÓGICA DAS PÁGINAS ======================

if menu == "👤 Login / Cadastro":
    st.header("Área do Morador")
    tab_login, tab_cad = st.tabs(["Entrar", "Cadastrar"])

    with tab_login:
        usr = st.text_input("Usuário / E-mail / Apartamento")
        pwd = st.text_input("Senha", type="password")
        if st.button("Entrar", type="primary"):
            conn = get_conn()
            row = conn.execute("""
                SELECT username, password_hash, salt, role, nome_completo, apartamento, ativo
                FROM usuarios
                WHERE (username = ? OR email = ? OR apartamento = ?) AND ativo = 1
            """, (usr, usr, usr)).fetchone()
            conn.close()

            if row and verify_password(pwd, row[1], row[2]):
                st.session_state.user = row[0]
                st.session_state.role = row[3]
                st.session_state.nome = row[4]
                st.session_state.apartamento = row[5]
                st.success(f"Bem-vindo, {row[4]}!")
                
                if row[0] == "admin" and pwd == "admin123":
                    st.warning("**Atenção Síndico!** Altere sua senha padrão no Painel Administrativo.")
                st.rerun()
            else:
                st.error("Credenciais inválidas ou usuário inativo.")

    with tab_cad:
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Nome completo *")
            apto = st.text_input("Apartamento *")
        with col2:
            email = st.text_input("E-mail *")
            tel = st.text_input("Telefone (opcional)")
        usuario_cad = st.text_input("Nome de Usuário (Login) *")
        senha1 = st.text_input("Senha *", type="password")
        senha2 = st.text_input("Confirme a senha *", type="password")

        if st.button("Cadastrar", type="primary"):
            if not all([nome, apto, email, usuario_cad, senha1]):
                st.error("Preencha os campos obrigatórios")
            elif senha1 != senha2:
                st.error("As senhas não coincidem")
            else:
                salt = generate_salt()
                hash_pw = hash_password(senha1, salt)
                try:
                    conn = get_conn()
                    conn.execute("""
                        INSERT INTO usuarios
                        (username, password_hash, salt, role, nome_completo, apartamento, email, telefone)
                        VALUES (?, ?, ?, 'morador', ?, ?, ?, ?)
                    """, (usuario_cad, hash_pw, salt, nome, apto, email, tel or None))
                    conn.commit()
                    conn.close()
                    st.success("Cadastro realizado! Agora faça login.")
                except sqlite3.IntegrityError:
                    st.error("Usuário, e-mail ou apartamento já cadastrado.")

elif menu.startswith("📝 Abrir Registro"):
    st.header("Novo Registro")
    logado = st.session_state.user is not None
    prefill_local = st.session_state.apartamento if logado else ""

    if logado:
        st.info(f"Registrando como: **{st.session_state.nome}**")

    tipo = st.radio("Tipo de registro", ["Abertura de Chamado", "Denúncia"], horizontal=True)
    categoria = st.selectbox("Área", ["Corredor", "Garagem", "Jardim", "Academia", "Elevador", "Piscina", "Outros"])
    local = st.text_input("Localização específica", value=prefill_local)
    descricao = st.text_area("Descrição do problema")
    foto = st.file_uploader("Foto (opcional)", type=["jpg", "jpeg", "png"])

    if st.button("Registrar", type="primary"):
        if not descricao.strip():
            st.error("A descrição é obrigatória")
        else:
            protocolo = str(uuid.uuid4())[:8].upper()
            foto_b64 = base64.b64encode(foto.getvalue()).decode("utf-8") if foto else None
            criado_por = st.session_state.user if (logado and tipo != "Denúncia") else "Anônimo"
            data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")

            conn = get_conn()
            conn.execute("""
                INSERT INTO ocorrencias (id, tipo_registro, categoria, local_detalhado, descricao, foto_base64, data_envio, criado_por)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (protocolo, tipo, categoria, local, descricao, foto_b64, data_atual, criado_por))
            conn.commit()
            
            link_row = conn.execute("SELECT valor FROM config WHERE chave = 'whatsapp_urgente_link'").fetchone()
            conn.close()

            st.success(f"Registro enviado! Protocolo: **{protocolo}**")
            
            if logado and link_row and link_row[0]:
                st.markdown(f"""<div class="whatsapp-box"><strong>🚨 Urgências?</strong><br><a href="{link_row[0]}" target="_blank">Entrar no Grupo WhatsApp</a></div>""", unsafe_allow_html=True)

elif menu == "🔍 Consultar Protocolo":
    st.header("Consultar Protocolo")
    prot = st.text_input("Digite o protocolo").upper().strip()
    if prot:
        conn = get_conn()
        registro = conn.execute("SELECT * FROM ocorrencias WHERE id = ?", (prot,)).fetchone()
        conn.close()
        if registro:
            st.info(f"Status: **{registro[6]}**")
            st.write(f"**Categoria:** {registro[2]} | **Data:** {registro[7]}")
            st.write(f"**Descrição:** {registro[4]}")
            if registro[5]: st.image(base64.b64decode(registro[5]))
        else:
            st.error("Protocolo não encontrado.")

elif menu == "📊 Painel Administrativo":
    st.header("Painel Administrativo")
    t1, t2, t3, t4 = st.tabs(["Atendimentos", "Usuários", "Configurações", "Minha Conta"])
    
    with t1:
        conn = get_conn()
        df = pd.read_sql_query("SELECT * FROM ocorrencias WHERE status != 'Concluído' ORDER BY data_envio DESC", conn)
        conn.close()
        for _, row in df.iterrows():
            with st.expander(f"📌 {row['id']} - {row['categoria']}"):
                st.write(row['descricao'])
                novo_st = st.selectbox("Status", ["Pendente", "Em Manutenção", "Concluído"], key=f"st_{row['id']}")
                if st.button("Atualizar", key=f"btn_{row['id']}"):
                    conn = get_conn()
                    dt_conc = datetime.now().strftime("%d/%m/%Y %H:%M") if novo_st == "Concluído" else None
                    conn.execute("UPDATE ocorrencias SET status = ?, data_conclusao = ? WHERE id = ?", (novo_st, dt_conc, row['id']))
                    conn.commit()
                    conn.close()
                    st.rerun()

    with t3:
        conn = get_conn()
        link_at = conn.execute("SELECT valor FROM config WHERE chave = 'whatsapp_urgente_link'").fetchone()
        novo_link = st.text_input("Link WhatsApp", value=link_at[0] if link_at else "")
        if st.button("Salvar Config"):
            conn.execute("INSERT OR REPLACE INTO config (chave, valor) VALUES ('whatsapp_urgente_link', ?)", (novo_link,))
            conn.commit()
            conn.close()
            st.success("Configuração salva!")

elif menu == "👋 Meus Chamados":
    st.header("Meus Chamados")
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM ocorrencias WHERE criado_por = ?", conn, params=(st.session_state.user,))
    conn.close()
    if df.empty: st.info("Você não possui chamados abertos.")
    else: st.dataframe(df[['id', 'categoria', 'status', 'data_envio']], use_container_width=True)

st.sidebar.caption("Condomínio Pro • 2026")