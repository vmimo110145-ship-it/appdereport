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

# ====================== FUNÇÕES ======================
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

# ====================== BANCO ======================
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

    # Admin padrão
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

# ====================== INTERFACE ======================
st.set_page_config(page_title="Condomínio Pro", layout="wide", page_icon="🏢")

st.markdown("""
    <style>
    .stButton>button {width: 100%; border-radius: 8px; font-weight: bold; margin-top: 8px;}
    .whatsapp-box {background-color: #e8f5e9; padding: 20px; border-radius: 12px; margin: 20px 0; text-align: center; border: 1px solid #c8e6c9; font-size: 1.1em;}
    .alert-box {background-color: #fff3cd; padding: 16px; border-radius: 8px; border-left: 5px solid #ffc107; margin: 16px 0;}
    </style>
""", unsafe_allow_html=True)

# Sessão
for key in ["user", "role", "nome", "apartamento"]:
    if key not in st.session_state:
        st.session_state[key] = None

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

# ====================== LOGIN / CADASTRO ======================
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
                    st.warning("""
                        **Atenção Síndico!**  
                        Você está usando a senha padrão (admin123).  
                        Por segurança, altere sua senha imediatamente em:  
                        Painel Administrativo → Minha Conta
                    """)
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

# ====================== ABRIR REGISTRO ======================
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
                        Entre agora no grupo WhatsApp do condomínio para receber notificações instantâneas sobre urgências (vazamentos, falta de luz, segurança, etc.)
                        <br><br>
                        <a href="{link_grupo}" target="_blank" style="background:#25D366; color:white; padding:14px 32px; border-radius:10px; text-decoration:none; font-weight:bold; font-size:1.1em; display:inline-block;">
                            👉 Entrar no Grupo WhatsApp
                        </a>
                    </div>
                """, unsafe_allow_html=True)
            elif logado:
                st.caption("O grupo de urgências ainda não foi configurado pelo síndico.")

# ====================== CONSULTAR PROTOCOLO ======================
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

# ====================== PAINEL ADMINISTRATIVO ======================
elif menu == "📊 Painel Administrativo":
    st.header("Painel Administrativo")

    tabs = st.tabs(["Atendimentos", "Relatórios", "Novo Administrador", "Minha Conta", "Usuários Cadastrados", "Configurações"])

    with tabs[0]:  # Atendimentos
        conn = get_conn()
        df_pendentes = pd.read_sql_query("""
            SELECT * FROM ocorrencias
            WHERE status != 'Concluído'
            ORDER BY data_envio DESC
        """, conn)
        conn.close()

        if df_pendentes.empty:
            st.info("Não há atendimentos pendentes no momento.")
        else:
            for idx, row in df_pendentes.iterrows():
                cor_emoji = "🟡" if row["status"] == "Pendente" else "🔴"
                with st.expander(f"{cor_emoji} {row['id']} - {row['tipo_registro']}"):
                    st.write(f"**Criado por:** {row['criado_por']}")
                    st.write(f"**Local:** {row['categoria']} ({row['local_detalhado']})")
                    st.write(f"**Descrição:** {row['descricao']}")
                    if row["foto_base64"]:
                        st.image(base64.b64decode(row["foto_base64"]))

                    col1, col2 = st.columns([3, 1])

                    with col1:
                        opcoes_status = ["Pendente", "Em Manutenção", "Concluído"]
                        indice_atual = opcoes_status.index(row["status"]) if row["status"] in opcoes_status else 0

                        novo_status = st.selectbox(
                            "Alterar status",
                            options=opcoes_status,
                            index=indice_atual,
                            key=f"status_select_{row['id']}"
                        )

                    with col2:
                        if st.button("Salvar", key=f"salvar_{row['id']}", type="primary"):
                            data_conclusao = None
                            if novo_status == "Concluído":
                                data_conclusao = datetime.now().strftime("%d/%m/%Y %H:%M")

                            conn = get_conn()
                            conn.execute("""
                                UPDATE ocorrencias
                                SET status = ?, data_conclusao = ?
                                WHERE id = ?
                            """, (novo_status, data_conclusao, row["id"]))
                            conn.commit()
                            conn.close()

                            st.success(f"Status alterado para **{novo_status}**")
                            st.rerun()

                        if st.button("Excluir", key=f"delete_{row['id']}", help="Excluir este chamado"):
                            if st.session_state.get(f"confirm_delete_{row['id']}", False):
                                conn = get_conn()
                                conn.execute("DELETE FROM ocorrencias WHERE id = ?", (row['id'],))
                                conn.commit()
                                conn.close()
                                st.success(f"Chamado {row['id']} excluído.")
                                st.rerun()
                            else:
                                st.session_state[f"confirm_delete_{row['id']}"] = True
                                st.warning("Clique novamente em Excluir para confirmar a exclusão permanente.")

    with tabs[1]:
        st.subheader("Relatório de Concluídos")
        conn = get_conn()
        df_concluidos = pd.read_sql_query("SELECT * FROM ocorrencias WHERE status = 'Concluído'", conn)
        conn.close()

        if df_concluidos.empty:
            st.info("Ainda não há registros concluídos.")
        else:
            df_concluidos["Tempo de resolução"] = df_concluidos.apply(
                lambda r: calcular_tempo_finalizacao(r["data_envio"], r["data_conclusao"]), axis=1
            )
            st.dataframe(
                df_concluidos[["id", "tipo_registro", "categoria", "data_envio", "data_conclusao", "Tempo de resolução", "criado_por"]],
                use_container_width=True,
                hide_index=True
            )

    with tabs[2]:
        st.subheader("Cadastrar novo administrador")
        novo_user = st.text_input("Nome de usuário")
        nova_senha = st.text_input("Senha", type="password")

        if st.button("Criar"):
            if not novo_user or not nova_senha:
                st.error("Preencha usuário e senha")
            else:
                salt = generate_salt()
                hash_senha = hash_password(nova_senha, salt)
                try:
                    conn = get_conn()
                    conn.execute("""
                        INSERT INTO usuarios (username, password_hash, salt, role, nome_completo)
                        VALUES (?, ?, ?, 'admin', 'Administrador')
                    """, (novo_user, hash_senha, salt))
                    conn.commit()
                    conn.close()
                    st.success("Administrador criado!")
                except:
                    st.error("Usuário já existe.")

    with tabs[3]:  # Minha Conta
        st.subheader("Alterar minha senha")
        senha_atual = st.text_input("Senha atual", type="password")
        nova_senha = st.text_input("Nova senha", type="password")
        nova_senha_conf = st.text_input("Confirmar nova senha", type="password")

        if st.button("Alterar Senha", type="primary"):
            if not all([senha_atual, nova_senha, nova_senha_conf]):
                st.error("Preencha todos os campos")
            elif nova_senha != nova_senha_conf:
                st.error("As novas senhas não coincidem")
            elif nova_senha == senha_atual:
                st.error("A nova senha deve ser diferente da atual")
            else:
                conn = get_conn()
                row = conn.execute("""
                    SELECT password_hash, salt FROM usuarios
                    WHERE username = ? AND role = 'admin'
                """, (st.session_state.user,)).fetchone()

                if row and verify_password(senha_atual, row[0], row[1]):
                    novo_salt = generate_salt()
                    novo_hash = hash_password(nova_senha, novo_salt)
                    conn.execute("""
                        UPDATE usuarios
                        SET password_hash = ?, salt = ?
                        WHERE username = ?
                    """, (novo_hash, novo_salt, st.session_state.user))
                    conn.commit()
                    conn.close()
                    st.success("Senha alterada com sucesso!")
                else:
                    st.error("Senha atual incorreta")
                    conn.close()

    with tabs[4]:  # Usuários Cadastrados
        st.subheader("Usuários Cadastrados (Moradores)")

        conn = get_conn()
        df_usuarios = pd.read_sql_query("""
            SELECT username, nome_completo, apartamento, email, telefone, data_cadastro, ativo
            FROM usuarios
            WHERE role = 'morador'
            ORDER BY data_cadastro DESC
        """, conn)
        conn.close()

        if df_usuarios.empty:
            st.info("Ainda não há moradores cadastrados.")
        else:
            filtro = st.text_input("Filtrar por nome ou apartamento", "")
            if filtro:
                df_filtrado = df_usuarios[
                    df_usuarios['nome_completo'].str.contains(filtro, case=False, na=False) |
                    df_usuarios['apartamento'].str.contains(filtro, case=False, na=False)
                ]
            else:
                df_filtrado = df_usuarios

            st.dataframe(
                df_filtrado.rename(columns={
                    'username': 'Usuário',
                    'nome_completo': 'Nome',
                    'apartamento': 'Apartamento',
                    'email': 'E-mail',
                    'telefone': 'Telefone',
                    'data_cadastro': 'Data Cadastro',
                    'ativo': 'Ativo (1=Sim, 0=Não)'
                }),
                use_container_width=True,
                hide_index=True
            )

            # Gerenciar usuário (Bloquear / Desbloquear / Excluir)
            st.subheader("Gerenciar Usuário")
            usuario_sel = st.selectbox("Selecione o usuário", df_usuarios['username'].tolist())

            col1, col2, col3 = st.columns(3)

            with col1:
                acao_bloqueio = st.radio("Bloqueio", ["Bloquear", "Desbloquear"])

                if st.button("Aplicar Bloqueio"):
                    novo_ativo = 0 if acao_bloqueio == "Bloquear" else 1
                    conn = get_conn()
                    conn.execute("UPDATE usuarios SET ativo = ? WHERE username = ?", (novo_ativo, usuario_sel))
                    conn.commit()
                    conn.close()
                    st.success(f"Usuário {usuario_sel} {'bloqueado' if novo_ativo == 0 else 'desbloqueado'} com sucesso!")
                    st.rerun()

            with col2:
                if st.button("Excluir Usuário", type="primary"):
                    if st.session_state.get(f"confirm_delete_user_{usuario_sel}", False):
                        conn = get_conn()
                        conn.execute("DELETE FROM usuarios WHERE username = ?", (usuario_sel,))
                        conn.commit()
                        conn.close()
                        st.success(f"Usuário {usuario_sel} excluído permanentemente.")
                        if f"confirm_delete_user_{usuario_sel}" in st.session_state:
                            del st.session_state[f"confirm_delete_user_{usuario_sel}"]
                        st.rerun()
                    else:
                        st.session_state[f"confirm_delete_user_{usuario_sel}"] = True
                        st.warning(f"**Confirma exclusão permanente do usuário {usuario_sel}?** Clique novamente em Excluir Usuário para confirmar.")

            with col3:
                st.caption("Atenção: exclusão é irreversível")

    with tabs[5]:
        st.subheader("Configurações")
        conn = get_conn()
        row = conn.execute("SELECT valor FROM config WHERE chave = 'whatsapp_urgente_link'").fetchone()
        link_atual = row[0] if row else ""

        novo_link = st.text_input("Link do grupo WhatsApp", value=link_atual, placeholder="https://chat.whatsapp.com/...")
        if st.button("Salvar"):
            conn.execute("INSERT OR REPLACE INTO config (chave, valor) VALUES ('whatsapp_urgente_link', ?)", (novo_link.strip(),))
            conn.commit()
            conn.close()
            st.success("Link salvo!")
            st.rerun()

# ====================== MEUS CHAMADOS ======================
elif menu == "👋 Meus Chamados":
    st.header(f"Registros de {st.session_state.nome}")

    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM ocorrencias WHERE criado_por = ? ORDER BY data_envio DESC", conn, params=(st.session_state.user,))
    conn.close()

    if df.empty:
        st.info("Nenhum registro encontrado.")
    else:
        for _, reg in df.iterrows():
            with st.expander(f"{reg['id']} - {reg['categoria']}"):
                st.write("**Status:**", reg["status"])
                st.write("**Local:**", reg["local_detalhado"])
                st.write("**Descrição:**", reg["descricao"])
                if reg["foto_base64"]:
                    st.image(base64.b64decode(reg["foto_base64"]))
                if reg["data_conclusao"]:
                    st.write("**Resolvido em:**", calcular_tempo_finalizacao(reg["data_envio"], reg["data_conclusao"]))

st.sidebar.caption("Condomínio Pro • 2025")