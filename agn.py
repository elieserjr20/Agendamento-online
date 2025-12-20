import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.field_path import FieldPath
from datetime import datetime, timedelta
import time
import os
import json
from PIL import Image
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
import re
import unicodedata
import streamlit.components.v1 as components
import base64

# --- DEFINIÇÃO DE CAMINHOS SEGUROS (PARA O FAVICON) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# --- CARREGAR O ÍCONE DA PÁGINA ---
try:
    # Lembre-se que o ícone precisa estar na pasta 'static' do seu projeto no Render
    favicon_path = os.path.join(STATIC_DIR, "icon_any_192.png")
    favicon = Image.open(favicon_path)
except FileNotFoundError:
    st.warning("Arquivo 'icon_any_192.png' não encontrado na pasta 'static'. Usando emoji padrão.")
    favicon = "📅" # Um emoji de calendário como alternativa

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(
    page_title="Agendamento Interno",
    page_icon=favicon,
    layout="wide" # ou "wide", como preferir
)
def aplicar_tema_natal():
    # --- 1. CARREGAR IMAGEM DO GORRO (LOCAL) ---
    gorro_path = os.path.join(STATIC_DIR, "gorro.png")
    gorro_src = ""
    
    # Verifica se o arquivo existe e converte para Base64
    if os.path.exists(gorro_path):
        with open(gorro_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        gorro_src = f"data:image/png;base64,{encoded_string}"
    else:
        # Se não encontrar, usa o Emoji como backup para não quebrar
        gorro_src = "" 

    # --- 2. DEFINIR O CONTEÚDO HTML DO GORRO ---
    # Se achou a imagem, usa a tag <img>, se não, usa emoji ou nada
    html_gorro = ""
    if gorro_src:
        html_gorro = f'<img src="{gorro_src}" class="santa-hat">'
    else:
        # Backup caso esqueças de colocar a imagem
        html_gorro = '<div class="santa-hat-emoji">🎅</div>'

    # --- 3. CSS E ESTILOS ---
    st.markdown(f"""
    <style>
        /* --- AJUSTE DE MARGENS (MOBILE) --- */
        div.block-container {{
            padding-top: 1rem;
            padding-bottom: 5rem;
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }}

        /* --- REMOVE ESPAÇOS ENTRE COLUNAS --- */
        [data-testid="column"] {{
            padding: 0px !important;
            margin: 0px !important;
        }}
        [data-testid="stHorizontalBlock"] {{
            gap: 0px !important; /* Cola as colunas */
        }}

        /* --- TRANSFORMA BOTÕES EM CÉLULAS DE TABELA --- */
        div.stButton > button {{
            width: 100%;
            border-radius: 0px;         /* Quadrado (Excel) */
            height: 45px;               /* Altura Fixa */
            margin: 0px !important;
            border: 1px solid #333;     /* Borda da grade */
            font-weight: bold;
            font-size: 13px;
            text-shadow: 0px 1px 1px rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        /* --- CORES DOS BOTÕES (STATUS) --- */
        
        /* LIVRE (Verde) -> Usaremos type="secondary" */
        div.stButton > button[kind="secondary"] {{
            background-color: #28a745 !important;
            color: white !important;
            border-color: #1e7e34 !important;
        }}
        div.stButton > button[kind="secondary"]:hover {{
            background-color: #218838 !important;
        }}

        /* OCUPADO (Vermelho) -> Usaremos type="primary" */
        div.stButton > button[kind="primary"] {{
            background-color: #dc3545 !important;
            color: white !important;
            border-color: #bd2130 !important;
        }}

        /* FECHADO/ALMOÇO (Cinza) -> Usaremos disabled=True */
        div.stButton > button:disabled {{
            background-color: #6c757d !important;
            color: rgba(255,255,255,0.8) !important;
            border-color: #545b62 !important;
            opacity: 1 !important; /* Tira a transparência padrão */
            cursor: not-allowed;
        }}

        /* --- ESTILOS DE COLUNAS DE TEXTO --- */
        .time-cell {{
            height: 45px;
            background-color: #1E1E1E;
            color: #FFC107; /* Dourado */
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-family: monospace;
            border: 1px solid #333;
            border-right: none; /* Evita borda dupla */
        }}
        
        .header-cell {{
            background-color: #000;
            color: white;
            text-align: center;
            padding: 10px 0;
            border: 1px solid #333;
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 0px;
        }}

        /* --- DECORAÇÃO DE NATAL --- */
        .christmas-watermark {{
            position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
            z-index: 0; text-align: center; pointer-events: none; width: 100%; opacity: 0.15;
        }}
        .christmas-tree {{ font-size: 20rem; position: relative; display: inline-block; }}
        .santa-hat {{ 
            position: absolute; top: -60px; left: 50%; transform: translateX(-50%) rotate(10deg); 
            width: 150px; z-index: 10; 
        }}
        .santa-hat-emoji {{ position: absolute; top: -20px; right: 20px; font-size: 6rem; }}
        
        @keyframes snow {{
            0% {{ transform: translateY(-100px); opacity: 0; }}
            100% {{ transform: translateY(100vh); opacity: 0.3; }}
        }}
        .snowflake {{
            position: fixed; top: -10px; color: #FFF; font-size: 1em;
            animation: snow linear infinite; pointer-events: none; z-index: 99;
        }}
    </style>

    <div class="christmas-watermark">
        <div class="christmas-tree">
            {html_gorro} 🎄
        </div>
        <div style="font-family:cursive; font-size: 4rem; color: #CD5C5C; margin-top: -40px;">Feliz Natal</div>
    </div>
    <div class="snowflake" style="left: 10%; animation-duration: 10s;">❄</div>
    <div class="snowflake" style="left: 30%; animation-duration: 12s;">❅</div>
    <div class="snowflake" style="left: 70%; animation-duration: 14s;">❄</div>
    """, unsafe_allow_html=True)
    
# APLICAR O TEMA AQUI:
aplicar_tema_natal()


st.markdown("<a id='top_anchor'></a>", unsafe_allow_html=True)


# --- INICIALIZAÇÃO DO FIREBASE E E-MAIL (Mesmo do código original) ---

FIREBASE_CREDENTIALS = None
EMAIL = os.environ.get("EMAIL_CREDENCIADO")
SENHA = os.environ.get("EMAIL_SENHA")

# 2. Carrega o caminho para o ficheiro de credenciais do Firebase
#    (O Render coloca o caminho nesta variável de ambiente)
FIREBASE_SECRET_PATH = os.environ.get("FIREBASE_SECRET_PATH")

if FIREBASE_SECRET_PATH:
    try:
        # Abre e lê o ficheiro JSON a partir do caminho fornecido
        with open(FIREBASE_SECRET_PATH, 'r') as f:
            FIREBASE_CREDENTIALS = json.load(f)
    except FileNotFoundError:
        st.error(f"ERRO: O arquivo de credenciais não foi encontrado no caminho: {FIREBASE_SECRET_PATH}")
    except json.JSONDecodeError:
        st.error("ERRO: O conteúdo do arquivo de credenciais não é um JSON válido.")
    except Exception as e:
        st.error(f"ERRO ao ler o Secret File do Firebase: {e}")
else:
    st.error("ERRO CRÍTICO: A variável de ambiente 'FIREBASE_SECRET_PATH' não está definida. Verifique as suas configurações no Render.")

# --- Inicialização do Firebase ---
if FIREBASE_CREDENTIALS and not firebase_admin._apps:
    try:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Erro ao inicializar a aplicação Firebase: {e}")

db = firestore.client() if firebase_admin._apps else None


# --- DADOS BÁSICOS ---
servicos = ["Tradicional", "Social", "Degradê", "Pezim", "Navalhado", "Barba", "Abordagem de visagismo", "Consultoria de visagismo"]
barbeiros = ["Aluizio", "Lucas Borges"]


# --- FUNÇÕES DE BACKEND (Adaptadas e Novas) ---
# VERSÃO CORRETA DA FUNÇÃO
# COLOQUE ESTA VERSÃO NO LUGAR DA SUA FUNÇÃO enviar_email

def enviar_email(assunto, mensagem):
    """
    Função atualizada para enviar e-mails usando a API da Brevo.
    Lê a chave da API e o e-mail do remetente das variáveis de ambiente do Render.
    MOSTRA AVISOS NA TELA se as chaves falharem.
    """
    # Passo 1: O código busca a chave secreta no "cofre" do Render.
    api_key = os.environ.get("BREVO_API_KEY")
    
    # Passo 2: O código busca o teu e-mail (que também está no "cofre").
    sender_email = os.environ.get("EMAIL_CREDENCIADO")

    # Se não encontrar as chaves no Render, avisa no log E NA TELA.
    if not api_key or not sender_email:
        print("AVISO: Credenciais da Brevo (BREVO_API_KEY ou EMAIL_CREDENCIADO) não configuradas. E-mail não enviado.")
        # --- MELHORIA ADICIONADA ---
        st.warning("AVISO: Credenciais de E-mail não configuradas no servidor. A notificação não foi enviada.")
        # ---------------------------
        return

    # Passo 3: Configura a comunicação com a Brevo.
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = api_key
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

    # Passo 4: Monta o e-mail.
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": sender_email}],
        sender={"name": "Painel Interno Barbearia", "email": sender_email},
        subject=assunto,
        text_content=mensagem
    )

    try:
        # Passo 5: Envia o e-mail.
        api_instance.send_transac_email(send_smtp_email)
        print(f"E-mail de notificação ('{assunto}') enviado com sucesso pela Brevo.")
    except ApiException as e:
        print(f"ERRO ao enviar e-mail com a Brevo: {e}")
        # --- MELHORIA ADICIONADA ---
        st.error(f"Ocorreu um erro ao tentar enviar o e-mail de notificação: {e}")
        # ---------------------------

def buscar_agendamentos_do_dia(data_obj):
    """
    Busca todos os agendamentos do dia em UMA ÚNICA CONSULTA e retorna um dicionário.
    A chave é o ID do documento, e o valor são os dados do agendamento.
    """
    if not db:
        st.error("Firestore não inicializado.")
        return {}
    
    ocupados_map = {}
    prefixo_id = data_obj.strftime('%Y-%m-%d')
    try:
        docs = db.collection('agendamentos') \
                 .order_by(FieldPath.document_id()) \
                 .start_at([prefixo_id]) \
                 .end_at([prefixo_id + '\uf8ff']) \
                 .stream()
        for doc in docs:
            ocupados_map[doc.id] = doc.to_dict()
    except Exception as e:
        st.error(f"Erro ao buscar agendamentos do dia: {e}")
    return ocupados_map

# FUNÇÕES DE ESCRITA (JÁ CORRIGIDAS NA NOSSA CONVERSA)
def salvar_agendamento(data_obj, horario, nome, telefone, servicos, barbeiro, is_bloqueio=False):
    if not db: return False
    data_para_id = data_obj.strftime('%Y-%m-%d')
    chave_base = f"{data_para_id}_{horario}_{barbeiro}"
    
    # Lógica de Bloqueio
    if is_bloqueio:
        chave_agendamento = f"{chave_base}_BLOQUEADO"
        nome = "Bloqueado"
    else:
        chave_agendamento = chave_base

    try:
        data_para_salvar = datetime.combine(data_obj, datetime.min.time())
        db.collection('agendamentos').document(chave_agendamento).set({
            'nome': nome, 'telefone': telefone, 'servicos': servicos, 'barbeiro': barbeiro,
            'data': data_para_salvar, 'horario': horario, 'status': "Confirmado",
            'data_agendamento': firestore.SERVER_TIMESTAMP
        })
        return True
    except Exception as e:
        print(f"Erro ao salvar: {e}")
        return False

def bloquear_horario(data_obj, horario, barbeiro, motivo="BLOQUEADO"):
    if not db: return False
    data_para_id = data_obj.strftime('%Y-%m-%d')
    chave_bloqueio = f"{data_para_id}_{horario}_{barbeiro}_BLOQUEADO" if motivo == "BLOQUEADO" else f"{data_para_id}_{horario}_{barbeiro}"
    try:
        # CORREÇÃO: Converte o objeto 'date' para 'datetime' antes de salvar
        data_para_salvar = datetime.combine(data_obj, datetime.min.time())
        db.collection('agendamentos').document(chave_bloqueio).set({
            'nome': motivo, 'telefone': "INTERNO", 'servicos': [], 
            'barbeiro': barbeiro, 'data': data_para_salvar, 'horario': horario
        })
        return True
    except Exception as e:
        st.error(f"Erro ao bloquear horário: {e}")
        return False
        
# ADICIONE ESTA FUNÇÃO JUNTO COM AS OUTRAS FUNÇÕES DE BACKEND

def desbloquear_horario(data_obj, horario_agendado, barbeiro):
    """
    Remove o documento de bloqueio (_BLOQUEADO) referente a um agendamento de Corte+Barba.
    """
    if not db: return
    try:
        # Calcula o horário seguinte que foi bloqueado
        horario_dt = datetime.strptime(horario_agendado, '%H:%M') + timedelta(minutes=30)
        horario_seguinte_str = horario_dt.strftime('%H:%M')
        
        # Cria o ID do documento de bloqueio no formato correto
        data_para_id = data_obj.strftime('%Y-%m-%d')
        chave_bloqueio = f"{data_para_id}_{horario_seguinte_str}_{barbeiro}_BLOQUEADO"
        
        # Deleta o documento
        bloqueio_ref = db.collection('agendamentos').document(chave_bloqueio)
        if bloqueio_ref.get().exists:
            bloqueio_ref.delete()
    except Exception as e:
        # Apenas avisa no console, não precisa mostrar erro para o usuário
        print(f"Aviso: Não foi possível desbloquear o horário seguinte. {e}")

def verificar_disponibilidade_especifica(data_obj, horario, barbeiro):
    """ Verifica de forma eficiente se um único horário está livre. """
    if not db: return False
    data_para_id = data_obj.strftime('%Y-%m-%d')
    id_padrao = f"{data_para_id}_{horario}_{barbeiro}"
    id_bloqueado = f"{data_para_id}_{horario}_{barbeiro}_BLOQUEADO"
    try:
        doc_padrao_ref = db.collection('agendamentos').document(id_padrao)
        doc_bloqueado_ref = db.collection('agendamentos').document(id_bloqueado)
        
        # Se qualquer um dos dois documentos existir, o horário não está livre.
        if doc_padrao_ref.get().exists or doc_bloqueado_ref.get().exists:
            return False # Indisponível
        return True # Disponível
    except Exception:
        return False

def cancelar_agendamento(data_obj, horario, barbeiro):
    if not db: return None
    data_para_id = data_obj.strftime('%Y-%m-%d')
    chave_agendamento = f"{data_para_id}_{horario}_{barbeiro}"
    agendamento_ref = db.collection('agendamentos').document(chave_agendamento)
    try:
        doc = agendamento_ref.get()
        if doc.exists:
            agendamento_data = doc.to_dict()
            agendamento_ref.delete()
            return agendamento_data
        return None
    except Exception as e:
        st.error(f"Erro ao cancelar agendamento: {e}")
        return None

def fechar_horario(data_obj, horario, barbeiro):
    if not db: return False
    data_para_id = data_obj.strftime('%Y-%m-%d')
    chave_bloqueio = f"{data_para_id}_{horario}_{barbeiro}"
    try:
        # CORREÇÃO: Converte o objeto 'date' para 'datetime' antes de salvar
        data_para_salvar = datetime.combine(data_obj, datetime.min.time())
        db.collection('agendamentos').document(chave_bloqueio).set({
            'nome': "Fechado", 'telefone': "INTERNO", 'servicos': [],
            'barbeiro': barbeiro, 'data': data_para_salvar, 'horario': horario
        })
        return True
    except Exception as e:
        st.error(f"Erro ao fechar horário: {e}")
        return False
    # ADICIONE ESTA NOVA FUNÇÃO NO SEU BLOCO DE FUNÇÕES DE BACKEND

# NO SEU ARQUIVO agn.py, SUBSTITUA ESTA FUNÇÃO:

def desbloquear_horario_especifico(data_obj, horario, barbeiro):
    """
    Remove um agendamento/bloqueio específico, tentando apagar tanto o ID
    padrão quanto o ID com sufixo _BLOQUEADO para garantir a limpeza.
    """
    if not db: return False
    
    data_para_id = data_obj.strftime('%Y-%m-%d')
    
    # Define os dois possíveis nomes de documento que podem estar ocupando o horário
    chave_padrao = f"{data_para_id}_{horario}_{barbeiro}"
    chave_bloqueado = f"{data_para_id}_{horario}_{barbeiro}_BLOQUEADO"
    
    ref_padrao = db.collection('agendamentos').document(chave_padrao)
    ref_bloqueado = db.collection('agendamentos').document(chave_bloqueado)
    
    try:
        # Tenta apagar os dois documentos. O Firestore não gera erro se o documento não existir.
        # Isso garante que tanto um agendamento normal quanto um bloqueio órfão sejam removidos.
        ref_padrao.delete()
        ref_bloqueado.delete()
        
        return True # Retorna sucesso, pois a intenção é deixar o horário livre.
        
    except Exception as e:
        st.error(f"Erro ao tentar desbloquear horário: {e}")
        return False
        
def remover_acentos(s):
    """
    Remove acentos de uma string, convertendo-a para uma forma 
    normalizada e removendo caracteres 'non-spacing mark'.
    (Usa o módulo 'unicodedata' já importado no topo do ficheiro)
    """
    if not isinstance(s, str):
        s = str(s)
        
    nfkd_form = unicodedata.normalize('NFD', s)
    return "".join([c for c in nfkd_form if unicodedata.category(c) != 'Mn'])
    
# --- O "DEF PERARDO 2.0" (O TRADUTOR DE TEXTO) ---
# --- (Esta é a sua função, que começa na linha 92) ---
def parsear_comando(comando):
    # Normalização (remover acentos e converter para minúsculas)
    comando_normalizado = remover_acentos(comando.lower())
    
    # --- "IMPLANTE TRIPLO" (A CURA DOS 3 BUGS DE VOZ) ---
    # (Adicionado na linha 95 - ANTES do Regex)
    
    # 1. Cura o "Bug do Juni r" (Erro do Microfone)
    comando_normalizado = comando_normalizado.replace("juni r", "junior")
    
    # 2. Cura o "Bug do Aloísio" (Erro de Ortografia)
    # (Transforma a "voz" (Aloísio) no "código" (Aluizio))
    comando_normalizado = comando_normalizado.replace("aloisio", "aluizio")
    comando_normalizado = comando_normalizado.replace("aloísio", "aluizio")
    comando_normalizado = re.sub(r'\balu\b', 'aluizio', comando_normalizado)
    # --- FIM DO IMPLANTE ---

    # Lista de barbeiros conhecidos (normalizada)
    barbeiros_conhecidos = [remover_acentos(b.lower()) for b in barbeiros]

    # --- TENTATIVA 1: Regex Padrão (Nome às HH:MM com Barbeiro) ---
    padrao_completo = re.compile(r"(.+?)\s+(?:as|às|a|no|na)\s+(\d{1,2}:\d{2})\s+(?:com|como|cm|c|co)\s+(.+)", re.IGNORECASE)
    match = padrao_completo.search(comando_normalizado)
    if match:
        nome_cliente = match.group(1).strip()
        horario = match.group(2).strip()
        nome_barbeiro = match.group(3).strip()
        
        try:
            horario_obj = datetime.strptime(horario, "%H:%M")
            horario_formatado = horario_obj.strftime("%H:%M")
        except ValueError:
            return None 

        # --- "IMPLANTE ANTI-O" (A CURA GERAL) ---
        # (Cura o Bug 1 DEPOIS do Regex)
        if nome_cliente.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_cliente = nome_cliente.split(' ', 1)[1] 
        if nome_barbeiro.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_barbeiro = nome_barbeiro.split(' ', 1)[1]
        # --- FIM DO IMPLANTE ---

        if nome_barbeiro in barbeiros_conhecidos:
            idx = barbeiros_conhecidos.index(nome_barbeiro)
            nome_barbeiro_original = barbeiros[idx]
            return {'nome': nome_cliente.title(), 'horário': horario_formatado, 'barbeiro': nome_barbeiro_original}

    # --- TENTATIVA 2: Regex (Nome às HH com Barbeiro) ---
    padrao_hora_cheia = re.compile(r"(.+?)\s+(?:as|às|a|no|na)\s+(\d{1,2})\s*(?:h|horas)?\s+(?:com|como|cm|c|co)\s+(.+)", re.IGNORECASE)
    match = padrao_hora_cheia.search(comando_normalizado)
    if match:
        nome_cliente = match.group(1).strip()
        horario = match.group(2).strip()
        nome_barbeiro = match.group(3).strip()
        
        horario_formatado = f"{int(horario):02d}:00"

        # --- "IMPLANTE ANTI-O" (A CURA GERAL) ---
        if nome_cliente.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_cliente = nome_cliente.split(' ', 1)[1] 
        if nome_barbeiro.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_barbeiro = nome_barbeiro.split(' ', 1)[1]
        # --- FIM DO IMPLANTE ---
        
        if nome_barbeiro in barbeiros_conhecidos:
            idx = barbeiros_conhecidos.index(nome_barbeiro)
            nome_barbeiro_original = barbeiros[idx]
            return {'nome': nome_cliente.title(), 'horário': horario_formatado, 'barbeiro': nome_barbeiro_original}

    # --- TENTATIVA 3: Regex (Nome, Barbeiro às HH:MM) ---
    padrao_barbeiro_antes = re.compile(r"(.+?)\s*,\s*(.+?)\s+(?:as|às|a|no|na)\s+(\d{1,2}:\d{2})", re.IGNORECASE)
    match = padrao_barbeiro_antes.search(comando_normalizado)
    if match:
        nome_cliente = match.group(1).strip()
        nome_barbeiro = match.group(2).strip()
        horario = match.group(3).strip()

        try:
            horario_obj = datetime.strptime(horario, "%H:%M")
            horario_formatado = horario_obj.strftime("%H:%M")
        except ValueError:
            return None

        # --- "IMPLANTE ANTI-O" (A CURA GERAL) ---
        if nome_cliente.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_cliente = nome_cliente.split(' ', 1)[1] 
        if nome_barbeiro.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_barbeiro = nome_barbeiro.split(' ', 1)[1]
        # --- FIM DO IMPLANTE ---

        if nome_barbeiro in barbeiros_conhecidos:
            idx = barbeiros_conhecidos.index(nome_barbeiro)
            nome_barbeiro_original = barbeiros[idx]
            return {'nome': nome_cliente.title(), 'horário': horario_formatado, 'barbeiro': nome_barbeiro_original}

    # --- TENTATIVA 4: Regex (Nome, Barbeiro às HH) ---
    padrao_barbeiro_antes_hora_cheia = re.compile(r"(.+?)\s*,\s*(.+?)\s+(?:as|às|a|no|na)\s+(\d{1,2})\s*(?:h|horas)?", re.IGNORECASE)
    match = padrao_barbeiro_antes_hora_cheia.search(comando_normalizado)
    if match:
        nome_cliente = match.group(1).strip()
        nome_barbeiro = match.group(2).strip()
        horario = match.group(3).strip()
        
        horario_formatado = f"{int(horario):02d}:00"

        # --- "IMPLANTE ANTI-O" (A CURA GERAL) ---
        if nome_cliente.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_cliente = nome_cliente.split(' ', 1)[1] 
        if nome_barbeiro.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_barbeiro = nome_barbeiro.split(' ', 1)[1]
        # --- FIM DO IMPLANTE ---
        
        if nome_barbeiro in barbeiros_conhecidos:
            idx = barbeiros_conhecidos.index(nome_barbeiro)
            nome_barbeiro_original = barbeiros[idx]
            return {'nome': nome_cliente.title(), 'horário': horario_formatado, 'barbeiro': nome_barbeiro_original}

    # --- TENTATIVA 5: Regex (Barbeiro às HH:MM com Nome) ---
    padrao_invertido = re.compile(r"(.+?)\s+(?:as|às|a|no|na)\s+(\d{1,2}:\d{2})\s+(?:com|como|cm|c|co)\s+(.+)", re.IGNORECASE)
    match = padrao_invertido.search(comando_normalizado)
    if match:
        nome_barbeiro = match.group(1).strip()
        horario = match.group(2).strip()
        nome_cliente = match.group(3).strip()

        try:
            horario_obj = datetime.strptime(horario, "%H:%M")
            horario_formatado = horario_obj.strftime("%H:%M")
        except ValueError:
            None

        # --- "IMPLANTE ANTI-O" (A CURA GERAL) ---
        if nome_cliente.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_cliente = nome_cliente.split(' ', 1)[1] 
        if nome_barbeiro.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_barbeiro = nome_barbeiro.split(' ', 1)[1]
        # --- FIM DO IMPLANTE ---

        if nome_barbeiro in barbeiros_conhecidos:
            idx = barbeiros_conhecidos.index(nome_barbeiro)
            nome_barbeiro_original = barbeiros[idx]
            return {'nome': nome_cliente.title(), 'horário': horario_formatado, 'barbeiro': nome_barbeiro_original}

    return None
# --- (Esta é o fim da sua função, linha 205) ---

# --- INICIALIZAÇÃO DO ESTADO DA SESSÃO ---
if 'view' not in st.session_state:
    st.session_state.view = 'main' # 'main', 'agendar', 'cancelar'
    st.session_state.selected_data = None
    st.session_state.agendamento_info = {}
if 'dados_voz' not in st.session_state:
    st.session_state.dados_voz = None
if 'chat_error' not in st.session_state:
    st.session_state.chat_error = None

# --- LÓGICA DE NAVEGAÇÃO E EXIBIÇÃO (MODAIS) ---

# ---- MODAL DE AGENDAMENTO ----
if st.session_state.view == 'agendar':
    # Todo o código abaixo está corretamente indentado ("dentro" do if)
    info = st.session_state.agendamento_info
    
    # Pegamos o objeto de data para as funções
    data_obj = info['data_obj']
    # Criamos a string de data para mostrar na tela
    data_str_display = data_obj.strftime('%d/%m/%Y')
    
    horario = info['horario']
    barbeiro = info['barbeiro']
    
    st.header("Confirmar Agendamento")
    st.subheader(f"🗓️ {data_str_display} às {horario} com {barbeiro}")

    with st.container(border=True):
        nome_cliente = st.text_input("Nome do Cliente*", key="cliente_nome")
        
        # Sua lista de serviços original
        servicos = ["Tradicional", "Social", "Degradê", "Pezim", "Navalhado", "Barba", "Abordagem de visagismo", "Consultoria de visagismo"]
        servicos_selecionados = st.multiselect("Serviços", servicos, key="servicos_selecionados")

        # Sua validação de Visagismo (mantida)
        is_visagismo = any(s in servicos_selecionados for s in ["Abordagem de visagismo", "Consultoria de visagismo"])
        if is_visagismo and barbeiro == 'Aluizio':
            st.error("Serviços de visagismo são apenas com Lucas Borges.")
        else:
            cols = st.columns(3)
            if cols[0].button("✅ Confirmar Agendamento", type="primary", use_container_width=True):
                if not nome_cliente:
                    st.error("O nome do cliente é obrigatório!")
                else:
                    with st.spinner("Processando..."):
                        
                        is_bloqueio = nome_cliente.strip().lower() == 'bloqueado'
                        
                        # 2. Lógica de Corte+Barba (SÓ corre se NÃO for bloqueio)
                        precisa_bloquear_proximo = False
                        if "Barba" in servicos_selecionados and any(c in servicos_selecionados for c in ["Tradicional", "Social", "Degradê", "Navalhado"]) and not is_bloqueio:
                            horario_seguinte_dt = datetime.strptime(horario, '%H:%M') + timedelta(minutes=30)
                            horario_seguinte_str = horario_seguinte_dt.strftime('%H:%M')
                            
                            # (Assumindo que você tem esta função 'verificar_disponibilidade_especifica' no seu código)
                            if verificar_disponibilidade_especifica(data_obj, horario_seguinte_str, barbeiro):
                                precisa_bloquear_proximo = True
                            else:
                                st.error("Não é possível agendar Corte+Barba. O horário seguinte não está disponível.")
                                st.stop() # Pára a execução

                        # 3. Chamada de salvar (AGORA COM 'is_bloqueio')
                        if salvar_agendamento(data_obj, horario, nome_cliente, "INTERNO", servicos_selecionados, barbeiro, is_bloqueio=is_bloqueio):
                            
                            if precisa_bloquear_proximo:
                                # (Assumindo que você tem esta função 'bloquear_horario' no seu código)
                                bloquear_horario(data_obj, horario_seguinte_str, barbeiro, "BLOQUEADO")

                            # 4. Mensagem de sucesso "inteligente"
                            st.success("Horário bloqueado com sucesso!" if is_bloqueio else f"Agendamento para {nome_cliente} confirmado!")
                            
                            # 5. Só envia e-mail se NÃO for um bloqueio
                            if not is_bloqueio:
                                assunto_email = f"Novo Agendamento: {nome_cliente} em {data_str_display}"
                                mensagem_email = (
                                    f"Agendamento interno:\n\nCliente: {nome_cliente}\nData: {data_str_display}\n"
                                    f"Horário: {horario}\nBarbeiro: {barbeiro}\n"
                                    f"Serviços: {', '.join(servicos_selecionados) if servicos_selecionados else 'Nenhum'}"
                                )
                                # (Assumindo que você tem esta função 'enviar_email' no seu código)
                                enviar_email(assunto_email, mensagem_email)
                            
                            # --- FIM DA "INTEGRAÇÃO" ---

                            st.cache_data.clear()
                            st.session_state.view = 'agenda' # (O seu código usa 'agenda', mantive)
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("Falha ao salvar. Tente novamente.")
    
    # Botão de voltar, também indentado corretamente
    if st.button("⬅️ Voltar para a Agenda"):
        st.session_state.view = 'agenda'
        st.rerun()


# ---- MODAL DE CANCELAMENTO ----
# SUBSTITUA TODA A SUA SEÇÃO 'cancelar' POR ESTA:

elif st.session_state.view == 'cancelar':
    info = st.session_state.agendamento_info
    
    # --- LÓGICA CORRIGIDA PARA PEGAR OS DADOS ---
    # Pegamos o OBJETO de data para usar nas funções
    data_obj = info['data_obj']
    # Criamos a STRING de data formatada apenas para mostrar na tela
    data_str_display = data_obj.strftime('%d/%m/%Y')
    
    horario = info['horario']
    barbeiro = info['barbeiro']
    
    # Acessamos os dados de forma segura com .get() para evitar qualquer erro
    dados = info.get('dados', {})
    nome = dados.get('nome', 'Ocupado')

    # --- INTERFACE DO MODAL DE GERENCIAMENTO ---
    st.header("Gerenciar Horário")
    st.subheader(f"🗓️ {data_str_display} às {horario} com {barbeiro}")
    st.markdown("---")

    # Mostra os detalhes do horário de forma inteligente
    if nome not in ["Fechado", "BLOQUEADO"]:
        # Se for um agendamento de cliente, mostramos todos os detalhes
        st.write(f"**Cliente:** {nome}")
        st.write(f"**Telefone:** {dados.get('telefone', 'N/A')}")
        st.write(f"**Serviços:** {', '.join(dados.get('servicos', []))}")
    else:
        # Se for um bloqueio interno ("Fechado" ou "BLOQUEADO"), apenas informamos o status
        st.info(f"O horário está marcado como: **{nome}**")

    st.markdown("---")
    st.warning("Tem certeza de que deseja liberar este horário?")

    cols = st.columns(2)
    # Botão para confirmar o cancelamento/liberação
    if cols[0].button("✅ Sim, Liberar Horário", type="primary", use_container_width=True):
        with st.spinner("Processando..."):
            
            # Chamamos a função de backend com os dados corretos (data_obj)
            dados_cancelados = cancelar_agendamento(data_obj, horario, barbeiro)
            
            if dados_cancelados:
                # Se o horário foi liberado com sucesso, verificamos se precisa desbloquear o seguinte
                servicos = dados_cancelados.get('servicos', [])
                if "Barba" in servicos and any(c in servicos for c in ["Tradicional", "Social", "Degradê", "Navalhado"]):
                    desbloquear_horario(data_obj, horario, barbeiro)

                st.success("Horário liberado com sucesso!")
                
                assunto_email = f"Cancelamento/Liberação: {nome} em {data_str_display}"
                mensagem_email = f"O agendamento para {nome} às {horario} com {barbeiro} foi cancelado/liberado."
                
                # Enviamos o e-mail com os dados corretos
                enviar_email(assunto_email, mensagem_email)
                
                # Voltamos para a tela da agenda
                st.session_state.view = 'agenda'
                time.sleep(2)
                st.rerun()
            else:
                st.error("Não foi possível liberar. O horário pode já ter sido removido.")

    # Botão para voltar para a agenda
    if cols[1].button("⬅️ Voltar para a Agenda", use_container_width=True):
        st.session_state.view = 'agenda'
        st.rerun()
        
elif st.session_state.view == 'confirmar_chat':
    st.header("Confirmar Agendamento por Chat/Voz?")
    
    try:
        # 1. Buscamos os dados do 'confirmacao_chat_info' (que salvamos no Passo 1)
        dados = st.session_state.confirmacao_chat_info
        nome = dados['nome']
        horario = dados['horario']
        barbeiro = dados['barbeiro']
        data_obj = dados['data_obj']

        st.subheader(f"🗓️ Data: {data_obj.strftime('%d/%m/%Y')}")

        # Usamos um container para ficar visualmente parecido com os outros modais
        with st.container(border=True):
            st.write(f"**Cliente:** `{nome}`")
            st.write(f"**Horário:** `{horario}`")
            st.write(f"**Barbeiro:** `{barbeiro}`")
        
        st.markdown("---")
        
        col_confirm, col_cancel = st.columns(2)
        
        if col_confirm.button("✅ Confirmar Agendamento", key="btn_confirm_chat", type="primary", use_container_width=True):
            # Lógica de salvar
            if salvar_agendamento(data_obj, horario, nome, "INTERNO (Voz)", ["(Voz)"], barbeiro, is_bloqueio=False):
                st.success(f"Agendado! {nome} às {horario} com {barbeiro}.")
                st.balloons()
                st.cache_data.clear()

                try:
                    data_str_email = data_obj.strftime('%d/%m/%Y')
                    assunto_email = f"Novo Agendamento (via Chat): {nome} em {data_str_email}"
                    mensagem_email = (
                        f"Agendamento via Chat/Voz:\n\nCliente: {nome}\nData: {data_str_email}\n"
                        f"Horário: {horario}\nBarbeiro: {barbeiro}\n"
                        f"Serviços: (Chat/Voz)"
                    )
                    enviar_email(assunto_email, mensagem_email)
                    st.info("Notificação interna enviada.")
                except Exception as e:
                    st.warning(f"Agendamento salvo, mas falha ao enviar notificação interna: {e}")
                
                # Limpa os dados e VOLTA PARA A AGENDA
                st.session_state.confirmacao_chat_info = None
                st.session_state.view = 'agenda' 
                time.sleep(3) # Damos 3s para ler o status
                st.rerun()
            else:
                # --- (CORREÇÃO) ---
                # Se falhar, apenas mostre o erro.
                # NÃO volte para a agenda. Deixe o usuário ver o erro.
                st.error("Falha ao salvar no banco de dados. O horário pode estar ocupado.")
                # (O 'st.rerun()' e a volta para a agenda foram removidos daqui)

        if col_cancel.button("❌ Cancelar (Voltar para Agenda)", key="btn_cancel_chat", use_container_width=True):
            # 3. Apenas limpa os dados e VOLTA PARA A AGENDA
            st.session_state.confirmacao_chat_info = None
            st.session_state.view = 'agenda'
            st.rerun()

    except (KeyError, TypeError):
        # Se algo der errado (ex: usuário recarregou a página com F5)
        st.error("Erro nos dados da sessão. Voltando para a agenda...")
        st.session_state.confirmacao_chat_info = None
        st.session_state.view = 'agenda'
        time.sleep(2)
        st.rerun()

# ---- NOVO MODAL PARA FECHAR HORÁRIOS ----
elif st.session_state.view == 'fechar':
    st.header("🔒 Fechar Horários em Lote")

    # --- CORREÇÃO PRINCIPAL AQUI ---
    # Pegamos o OBJETO de data que foi salvo na sessão
    data_obj_para_fechar = st.session_state.get('data_obj_selecionada')
    
    # Se, por algum motivo, o objeto de data não estiver na sessão, voltamos para a agenda
    if not data_obj_para_fechar:
        st.error("Data não selecionada. Voltando para a agenda.")
        st.session_state.view = 'agenda'
        time.sleep(2)
        st.rerun()

    # Criamos a string de data APENAS para mostrar na tela
    data_str_display = data_obj_para_fechar.strftime('%d/%m/%Y')
    st.subheader(f"Data selecionada: {data_str_display}")

    # Lista de horários para os seletores
    horarios_tabela = [f"{h:02d}:{m:02d}" for h in range(8, 20) for m in (0, 30)]

    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            horario_inicio = st.selectbox("Horário de Início", options=horarios_tabela, key="fecha_inicio")
        with col2:
            horario_fim = st.selectbox("Horário Final", options=horarios_tabela, key="fecha_fim", index=len(horarios_tabela)-1)

        barbeiro_fechar = st.selectbox("Selecione o Barbeiro", options=barbeiros, key="fecha_barbeiro")

        st.warning("Atenção: Esta ação irá sobrescrever quaisquer agendamentos existentes no intervalo selecionado.", icon="⚠️")

        btn_cols = st.columns(2)
        if btn_cols[0].button("✔️ Confirmar Fechamento", type="primary", use_container_width=True):
            try:
                start_index = horarios_tabela.index(horario_inicio)
                end_index = horarios_tabela.index(horario_fim)

                if start_index > end_index:
                    st.error("O horário de início deve ser anterior ao horário final.")
                else:
                    with st.spinner(f"Fechando horários para {barbeiro_fechar}..."):
                        horarios_para_fechar = horarios_tabela[start_index:end_index+1]
                        sucesso_total = True
                        for horario in horarios_para_fechar:
                            # --- USAMOS data_obj_para_fechar AQUI ---
                            if not fechar_horario(data_obj_para_fechar, horario, barbeiro_fechar):
                                sucesso_total = False
                                break
                        
                        if sucesso_total:
                            st.success("Horários fechados com sucesso!")
                            st.cache_data.clear()
                            st.session_state.view = 'agenda' # <-- Corrigido para 'agenda'
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("Ocorreu um erro ao fechar um ou mais horários.")
            except ValueError:
                st.error("Horário selecionado inválido.")

        if btn_cols[1].button("⬅️ Voltar", use_container_width=True):
            st.session_state.view = 'agenda' # <-- Corrigido para 'agenda'
            st.rerun()
            
# --- TELA PRINCIPAL (GRID DE AGENDAMENTOS) ---
# --- TELA PRINCIPAL (VISUAL DE TABELA EXCEL) ---
else:
    # 1. Ajuste de scroll para o topo (se necessário)
    if st.session_state.get('scroll_to_top', False):
        st.markdown("<script>window.location.href = '#top_anchor';</script>", unsafe_allow_html=True)
        st.session_state.scroll_to_top = False

    # 2. Cabeçalho e Logo
    cols_logo = st.columns([1, 2, 1])
    with cols_logo[1]:
        st.image("https://i.imgur.com/zJTASJk.png", width=350)

    # 3. Inputs: Data e Chat
    c_data, c_chat = st.columns([1, 2])
    with c_data:
        data_selecionada = st.date_input(
            "📅 Data",
            value=datetime.today(),
            min_value=datetime.today().date(),
            key="data_input"
        )
    with c_chat:
        st.write("") # Espaço para alinhar verticalmente
        st.write("") 
        prompt = st.chat_input("🎤 Comando (Ex: João às 10h com Aluizio)")

    # 4. Lógica do Chat (Processamento)
    if prompt:
        st.session_state.chat_error = None
        st.session_state.dados_voz = None
        with st.spinner("Processando... 🧠"):
            dados = parsear_comando(prompt)
        
        if dados:
            st.session_state.confirmacao_chat_info = {
                'nome': dados['nome'], 'horario': dados['horário'],
                'barbeiro': dados['barbeiro'], 'data_obj': datetime.today().date()
            }
            st.session_state.view = 'confirmar_chat'
            st.rerun()
        else:
            st.session_state.chat_error = "Não entendi. Tente 'Nome às XXh com Barbeiro'."
            st.session_state.scroll_to_top = True
            st.rerun()

    if st.session_state.chat_error:
        st.error(st.session_state.chat_error, icon="🚨")

    # 5. Ferramentas (Bloquear / Desbloquear) - Mantendo a lógica funcional
    with st.expander("🛠️ Ferramentas (Fechar/Desbloquear Horários)"):
        tab_bloq, tab_desbloq = st.tabs(["🔒 Bloquear", "🔓 Desbloquear"])
        
        # Aba Bloquear
        with tab_bloq:
            with st.form("form_fechar_horario", clear_on_submit=True):
                horarios_ops = [f"{h:02d}:{m:02d}" for h in range(8, 20) for m in (0, 30)]
                c1, c2, c3 = st.columns(3)
                horario_inicio = c1.selectbox("Início", options=horarios_ops, key="fecha_inicio")
                horario_fim = c2.selectbox("Fim", options=horarios_ops, key="fecha_fim", index=len(horarios_ops)-1)
                barbeiro_fechar = c3.selectbox("Barbeiro", options=barbeiros, key="fecha_barbeiro")

                if st.form_submit_button("Confirmar Fechamento", use_container_width=True):
                    try:
                        idx_i = horarios_ops.index(horario_inicio)
                        idx_f = horarios_ops.index(horario_fim)
                        if idx_i > idx_f: st.error("Início maior que fim")
                        else:
                            for h in horarios_ops[idx_i:idx_f+1]: fechar_horario(data_selecionada, h, barbeiro_fechar)
                            st.success("Fechado!"); time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"Erro: {e}")

        # Aba Desbloquear
        with tab_desbloq:
             with st.form("form_desbloquear", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                h_ini_d = c1.selectbox("Início", options=horarios_ops, key="desb_ini")
                h_fim_d = c2.selectbox("Fim", options=horarios_ops, key="desb_fim", index=len(horarios_ops)-1)
                barb_d = c3.selectbox("Barbeiro", options=barbeiros, key="desb_barb")

                if st.form_submit_button("Confirmar Desbloqueio", use_container_width=True):
                    try:
                        idx_i = horarios_ops.index(h_ini_d)
                        idx_f = horarios_ops.index(h_fim_d)
                        for h in horarios_ops[idx_i:idx_f+1]: desbloquear_horario_especifico(data_selecionada, h, barb_d)
                        st.success("Desbloqueado!"); time.sleep(1); st.rerun()
                    except: pass

    st.divider()

    # ==============================================================================
    # 📅 TABELA ESTILO EXCEL (CLICÁVEL E MOBILE) - NOVO CÓDIGO
    # ==============================================================================
    
    data_obj = data_selecionada
    data_str = data_obj.strftime('%d/%m/%Y')
    data_para_id = data_obj.strftime('%Y-%m-%d')
    ocupados_map = buscar_agendamentos_do_dia(data_obj)

    # --- CABEÇALHO DA TABELA ---
    # Colunas coladas (proporção ajustada para mobile)
    cols_head = st.columns([1.3, 2.5, 2.5]) 
    cols_head[0].markdown("<div class='header-cell'>Horário</div>", unsafe_allow_html=True)
    cols_head[1].markdown(f"<div class='header-cell'>{barbeiros[0]}</div>", unsafe_allow_html=True)
    cols_head[2].markdown(f"<div class='header-cell'>{barbeiros[1]}</div>", unsafe_allow_html=True)

    # --- LOOP DE HORÁRIOS (07:00 as 20:00) ---
    horarios_tabela = [f"{h:02d}:{m:02d}" for h in range(8, 20) for m in (0, 30)]

    for horario in horarios_tabela:
        # Cria a linha visualmente colada (graças ao CSS global)
        row = st.columns([1.3, 2.5, 2.5])
        
        # 1. Célula da Hora (Texto Dourado/Escuro)
        with row[0]:
            st.markdown(f"<div class='time-cell'>{horario}</div>", unsafe_allow_html=True)

        # 2. Células dos Barbeiros (Botões Nativos)
        for i, barbeiro in enumerate(barbeiros):
            col_idx = i + 1
            
            # --- REGRAS DE STATUS ---
            status = "livre"
            label_botao = "Livre"
            dados_agendamento = {}
            is_disabled = False
            
            dia_mes = data_obj.day
            mes_ano = data_obj.month
            dia_semana = data_obj.weekday()
            is_intervalo_especial = (mes_ano == 12 and 14 <= dia_mes <= 31) 
            hora_int = int(horario.split(':')[0])
            
            id_padrao = f"{data_para_id}_{horario}_{barbeiro}"
            id_bloqueado = f"{data_para_id}_{horario}_{barbeiro}_BLOQUEADO"

            # A. Verifica Banco de Dados
            encontrou = False
            if id_padrao in ocupados_map:
                dados_agendamento = ocupados_map[id_padrao]
                nome = dados_agendamento.get("nome", "Ocupado")
                if nome == "Fechado": status, label_botao, is_disabled = "fechado", "Fechado", True
                elif nome == "Almoço": status, label_botao, is_disabled = "almoco", "Almoço", True
                else: status, label_botao = "ocupado", nome
                encontrou = True
            elif id_bloqueado in ocupados_map:
                status, label_botao, is_disabled = "fechado", "Bloqueado", True
                encontrou = True

            # B. Verifica Regras Fixas (Se não achou no banco)
            if not encontrou and not is_intervalo_especial:
                if horario in ["07:00", "07:30"]: status, label_botao, is_disabled = "fechado", "SDJ", True
                elif horario == "08:00" and barbeiro == "Lucas Borges": status, label_botao, is_disabled = "fechado", "Indisp.", True
                elif dia_semana == 6: status, label_botao, is_disabled = "fechado", "Fechado", True
                elif dia_semana < 5 and hora_int in [12, 13]: status, label_botao, is_disabled = "almoco", "Almoço", True

            # --- DEFINIÇÃO VISUAL (TIPO DO BOTÃO) ---
            # Secondary = Verde (definido no CSS) | Primary = Vermelho (definido no CSS)
            tipo_botao = "secondary" 
            if status == "ocupado":
                tipo_botao = "primary"
            
            # Se status for "livre", o texto fica "Livre" (curto para mobile)
            if status == "livre":
                label_botao = "Livre"

            # --- RENDERIZA O BOTÃO ---
            with row[col_idx]:
                key_btn = f"btn_{data_str}_{horario}_{barbeiro}"
                
                clicou = st.button(
                    label_botao, 
                    key=key_btn, 
                    disabled=is_disabled, 
                    type=tipo_botao,
                    use_container_width=True # Fundamental para o layout tabela
                )

                if clicou:
                    if status == 'livre':
                        st.session_state.view = 'agendar'
                        st.session_state.agendamento_info = {
                            'data_obj': data_obj, 'horario': horario, 'barbeiro': barbeiro
                        }
                        st.rerun()
                    elif status == 'ocupado':
                        st.session_state.view = 'cancelar'
                        st.session_state.agendamento_info = {
                            'data_obj': data_obj, 'horario': horario, 'barbeiro': barbeiro,
                            'dados': dados_agendamento
                        }
                        st.rerun()



