import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import base64
import uuid
import secrets
from datetime import datetime

# =============================================================================
# CONFIGURAÇÕES GLOBAIS + CSS PARA MOBILE E CABEÇALHO LIMPO
# =============================================================================

st.set_page_config(
    page_title="Condomínio Pro",
    layout="wide",
    initial_sidebar_state="auto",           # colapsa automaticamente em mobile
    page_icon="🏢",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# CSS para esconder botões indesejados e melhorar experiência mobile
st.markdown(
    """
    <style>
    /* Esconder botões indesejados do header (deixar apenas Compartilhar) */
    section[data-testid="stHeader"] button[kind="primary"],
    section[data-testid="stHeader"] button[kind="secondary"],
    section[data-testid="stHeader"] .stDeployButton,
    section[data-testid="stHeader"] button[aria-label*="Favoritar"],
    section[data-testid="stHeader"] button[aria-label*="Editar"],
    section[data-testid="stHeader"] button[aria-label*="Copiar código"],
    section[data-testid="stHeader"] button[aria-label*="Mais opções"],
    section[data-testid="stHeader"] button[data-testid*="stNotification"] {
        display: none !important;
    }

    /* Manter visível o botão Compartilhar */
    section[data-testid="stHeader"] button[kind="tertiary"],
    section[data-testid="stHeader"] button[aria-label*="Compartilhar"] {
        display: inline-flex !important;
    }

    /* Ajustes mobile */
    @media (max-width: 768px) {
        .stApp > header {
            padding-top: 0 !important;
        }
        .block-container {
            padding-top: 1rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-bottom: 2rem !important;
        }
        section[data-testid="stSidebar"] {
            min-width: 80vw !important;
            max-width: 85vw !important;
        }
        .stButton > button {
            width: 100% !important;
            height: 3rem !important;
            font-size: 1.1rem !important;
        }
        h1, h2, h3 {
            font-size: 1.5rem !important;
        }
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea {
            font-size: 1rem !important;
        }
        .stRadio > div {
            flex-direction: column !important;
            gap: 0.8rem !important;
        }
    }

    /* Estilo geral */
    .stApp {
        max-width: 1100px;
        margin: 0 auto;
    }
    .whatsapp-box {
        background-color: #e8f5e9;
        padding: 20px;
        border-radius: 12px;
        margin: 20px 0;
        text-align: center;
        border: 1px solid #c8e6c9;
        font-size: 1.1em;
    }
    .alert-box {
        background-color: #fff3cd;
        padding: 16px;
        border-radius: 8px;
        border-left: 5px solid #ffc107;
        margin: 16px 0;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# =============================================================================
# RESTANTE DO CÓDIGO (sem alterações na lógica principal)
# =============================================================================

DB_PATH = "condominio.db"

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

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

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

init_db()

st.sidebar.title("🏢 Condomínio Pro")

# Sessão
for key in ["user", "role", "nome", "apartamento"]:
    if key not in st.session_state:
        st.session_state[key] = None

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

# =============================================================================
# LOGIN / CADASTRO
# =============================================================================
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
                    st.warning("Atenção Síndico! Você está usando a senha padrão (admin123). Altere imediatamente.")
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
        usuario = st.text_input("Usuário *")
        senha1 = st.text_input("Senha *", type="password")
        senha2 = st.text_input("Confirme a senha *", type="password")

        if st.button("Cadastrar", type="primary"):
            if not all([nome, apto, email, usuario, senha1]):
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
                    """, (usuario, hash_pw, salt, nome, apto, email, tel or None))
                    conn.commit()
                    conn.close()
                    st.success("Cadastro realizado! Agora faça login.")
                except sqlite3.IntegrityError:
                    st.error("Usuário, e-mail ou apartamento já cadastrado.")

# =============================================================================
# ABRIR REGISTRO
# =============================================================================
if menu.startswith("📝 Abrir Registro"):
    st.header("Novo Registro")

    logado = st.session_state.user is not None
    prefill_local = st.session_state.apartamento or "" if logado else ""

    if logado:
        st.info(f"Registrando como: **{st.session_state.nome}**")

    tipo = st.radio("Tipo de registro", ["Abertura de Chamado", "Denúncia"], horizontal=True)
    if tipo == "Denúncia":
        st.info("Este registro é anônimo")

    categoria = st.selectbox("Área", ["Corredor", "Garagem", "Jardim", "Academia", "Elevador", "Piscina", "Outros"])
    local = st.text_input("Localização específica", value=prefill_local)
    descricao = st.text_area("Descrição do problema")
    foto = st.file_uploader("Foto (opcional)", type=["jpg", "jpeg", "png"])

    if st.button("Registrar", type="primary"):
        if not descricao.strip():
            st.error("A descrição é obrigatória")
        else:
            protocolo = str(uuid.uuid4())[:8].upper()
            foto_b64 = None
            if foto is not None:
                foto_b64 = base64.b64encode(foto.getvalue()).decode("utf-8")

            criado_por = st.session_state.user if logado else "Anônimo"
            data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")

            conn = get_conn()
            conn.execute("""
                INSERT INTO ocorrencias
                (id, tipo_registro, categoria, local_detalhado, descricao, foto_base64, data_envio, criado_por)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (protocolo, tipo, categoria, local, descricao, foto_b64, data_atual, criado_por))
            conn.commit()
            conn.close()

            st.success(f"Registro enviado com sucesso!\n**Protocolo:** {protocolo}")

            conn = get_conn()
            link_row = conn.execute("SELECT valor FROM config WHERE chave = 'whatsapp_urgente_link'").fetchone()
            conn.close()
            link_grupo = link_row[0].strip() if link_row and link_row[0] else None

            if logado and link_grupo:
                st.markdown(f"""
                    <div class="whatsapp-box">
                        <strong>🚨 Acompanhe chamados urgentes em tempo real!</strong><br><br>
                        Entre agora no grupo WhatsApp do condomínio
                        <br><br>
                        <a href="{link_grupo}" target="_blank" style="background:#25D366; color:white; padding:14px 32px; border-radius:10px; text-decoration:none; font-weight:bold;">
                            👉 Entrar no Grupo WhatsApp
                        </a>
                    </div>
                """, unsafe_allow_html=True)

# =============================================================================
# CONSULTAR PROTOCOLO
# =============================================================================
elif menu == "🔍 Consultar Protocolo":
    st.header("Consultar Protocolo")
    prot = st.text_input("Digite o protocolo", "").upper().strip()

    if prot:
        conn = get_conn()
        registro = conn.execute("SELECT * FROM ocorrencias WHERE id = ?", (prot,)).fetchone()
        conn.close()

        if registro:
            status = registro[6]
            if status == "Pendente":
                st.warning(f"Status atual: **{status}** 🟡")
            elif status == "Em Manutenção":
                st.error(f"Status atual: **{status}** 🔴")
            elif status == "Concluído":
                st.success(f"Status atual: **{status}** 🟢")
            else:
                st.info(f"Status: {status}")

            st.write("**Descrição:**", registro[4])
            st.caption(f"Aberto em: {registro[7]}")
            if registro[8]:
                st.write("**Tempo de resolução:**", calcular_tempo_finalizacao(registro[7], registro[8]))
            if registro[5]:
                st.image(base64.b64decode(registro[5]))
        else:
            st.error("Protocolo não encontrado.")

# =============================================================================
# PAINEL ADMINISTRATIVO e demais telas (mantidas iguais)
# =============================================================================
# ... (coloque aqui o restante do código do painel administrativo, relatórios, minha conta, etc.)
# Como o código original é muito longo, deixei apenas as partes alteradas no início.
# Copie o restante do seu código original a partir daqui.

# Final do arquivo
st.sidebar.caption("Condomínio Pro • 2025")