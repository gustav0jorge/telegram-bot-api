
import os
import time
import json
import requests

from dotenv import load_dotenv


# ==========================================
# CONFIGURAÇÕES INICIAIS
# ==========================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GENIUS_TOKEN = os.getenv("GENIUS_ACCESS_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN não encontrado no arquivo .env")

if not GENIUS_TOKEN:
    raise ValueError("GENIUS_ACCESS_TOKEN não encontrado no arquivo .env")


# URLs das APIs
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
GENIUS_URL = "https://api.genius.com"


# Cache temporário das músicas pesquisadas
musicas_cache = {}


# ==========================================
# CONFIGURAÇÃO DA API GENIUS
# ==========================================

genius_session = requests.Session()

genius_session.headers.update({
    "Authorization": f"Bearer {GENIUS_TOKEN}",
    "Accept": "application/json"
})


# ==========================================
# PESQUISAR MÚSICAS NO GENIUS
# ==========================================

def pesquisar_musica(nome):
    """Pesquisa músicas na API do Genius."""

    url = f"{GENIUS_URL}/search"

    params = {
        "q": nome
    }

    try:

        response = genius_session.get(
            url,
            params=params,
            timeout=20
        )

        response.raise_for_status()

        dados = response.json()

        resultados = dados["response"]["hits"]

        musicas = []

        for item in resultados:

            musica = item["result"]

            dados_musica = {
                "titulo": musica.get("title", "Não informado"),
                "artista": musica.get("artist_names", "Não informado"),
                "url": musica.get("url", ""),
                "id": musica.get("id")
            }

            musicas.append(dados_musica)

        return musicas

    except requests.exceptions.HTTPError as erro:

        print("Erro HTTP na API Genius:", erro)

    except requests.exceptions.RequestException as erro:

        print("Erro de conexão com Genius:", erro)

    except (KeyError, ValueError) as erro:

        print("Erro ao interpretar resposta do Genius:", erro)

    return []


# ==========================================
# BUSCAR MÚSICA PELO ID
# ==========================================

def buscar_musica_por_id(musica_id):
    """Busca os detalhes de uma música pelo ID."""

    url = f"{GENIUS_URL}/songs/{musica_id}"

    try:

        response = genius_session.get(
            url,
            timeout=20
        )

        response.raise_for_status()

        dados = response.json()["response"]["song"]

        return {
            "titulo": dados.get("title", "Não informado"),
            "artista": dados.get("artist_names", "Não informado"),
            "url": dados.get("url", ""),
            "id": dados.get("id")
        }

    except requests.exceptions.RequestException as erro:

        print("Erro ao buscar música:", erro)

    except (KeyError, ValueError) as erro:

        print("Erro ao interpretar música:", erro)

    return None


# ==========================================
# CONFIGURAÇÃO DA API TELEGRAM
# ==========================================

def enviar_mensagem(chat_id, texto, teclado=None):
    """Envia mensagens para o usuário."""

    url = f"{TELEGRAM_URL}/sendMessage"

    dados = {
        "chat_id": chat_id,
        "text": texto,
        "disable_web_page_preview": True
    }

    if teclado:
        dados["reply_markup"] = teclado

    try:

        response = requests.post(
            url,
            json=dados,
            timeout=20
        )

        response.raise_for_status()

        resultado = response.json()

        if not resultado.get("ok"):
            print("Erro retornado pelo Telegram:", resultado)

        return resultado

    except requests.exceptions.RequestException as erro:

        print("Erro ao enviar mensagem:", erro)

    return None


# ==========================================
# RESPONDER AOS CLIQUES DOS BOTÕES
# ==========================================

def responder_callback(callback_id):
    """Confirma o recebimento do clique."""

    url = f"{TELEGRAM_URL}/answerCallbackQuery"

    dados = {
        "callback_query_id": callback_id
    }

    try:

        response = requests.post(
            url,
            json=dados,
            timeout=20
        )

        response.raise_for_status()

    except requests.exceptions.RequestException as erro:

        print("Erro ao responder callback:", erro)


# ==========================================
# CRIAR BOTÕES DE ESCOLHA
# ==========================================

def criar_teclado(musicas):
    """Cria um botão para cada música encontrada."""

    teclado = {
        "inline_keyboard": []
    }

    for musica in musicas:

        musica_id = musica["id"]

        nome_botao = (
            f"{musica['titulo']} - {musica['artista']}"
        )

        # Limita o texto do botão
        nome_botao = nome_botao[:60]

        teclado["inline_keyboard"].append([
            {
                "text": nome_botao,
                "callback_data": f"musica:{musica_id}"
            }
        ])

    return teclado


# ==========================================
# PROCESSAR PESQUISA
# ==========================================

def processar_pesquisa(chat_id, texto):
    """Pesquisa músicas e apresenta os resultados."""

    enviar_mensagem(
        chat_id,
        f"🔎 Pesquisando: {texto}..."
    )

    resultados = pesquisar_musica(texto)

    if not resultados:

        enviar_mensagem(
            chat_id,
            "❌ Nenhuma música encontrada.\n\n"
            "Tente pesquisar com outro nome."
        )

        return

    # Limita a quantidade de resultados
    resultados = resultados[:5]

    resposta = "🎵 RESULTADOS ENCONTRADOS\n\n"

    for i, musica in enumerate(resultados, start=1):

        resposta += (
            f"🎶 Resultado {i}\n"
            f"📌 Música: {musica['titulo']}\n"
            f"👤 Artista: {musica['artista']}\n\n"
        )

        # Armazena a música para recuperar posteriormente
        musicas_cache[str(musica["id"])] = musica

    resposta += "👇 Escolha uma música abaixo:"

    # Cria os botões interativos
    teclado = criar_teclado(resultados)

    enviar_mensagem(
        chat_id,
        resposta,
        teclado
    )


# ==========================================
# PROCESSAR MÚSICA SELECIONADA
# ==========================================

def processar_escolha(callback):
    """Processa a escolha de uma música pelo usuário."""

    callback_id = callback["id"]

    # Confirma o clique no botão
    responder_callback(callback_id)

    dados = callback.get("data", "")

    if not dados.startswith("musica:"):
        return

    # Recupera o ID da música
    musica_id = dados.split(":", 1)[1]

    chat = callback.get("message", {}).get("chat")

    if not chat:
        return

    chat_id = chat["id"]

    # Recupera a música do cache
    musica = musicas_cache.get(musica_id)

    # Se não estiver no cache, consulta a API novamente
    if not musica:

        musica = buscar_musica_por_id(musica_id)

    if not musica:

        enviar_mensagem(
            chat_id,
            "❌ Não foi possível encontrar essa música."
        )

        return

    # Monta a resposta
    resposta = (
        "🎵 MÚSICA SELECIONADA\n\n"
        f"📌 Título: {musica['titulo']}\n"
        f"👤 Artista: {musica['artista']}\n\n"
        "📖 Para consultar a letra completa, "
        "acesse a página oficial da música no Genius:\n\n"
        f"🔗 {musica['url']}"
    )

    enviar_mensagem(chat_id, resposta)


# ==========================================
# PROCESSAR ATUALIZAÇÕES DO TELEGRAM
# ==========================================

def processar_atualizacao(atualizacao):
    """Identifica o tipo de atualização recebida."""

    # Verifica se é um clique em botão
    if "callback_query" in atualizacao:

        processar_escolha(
            atualizacao["callback_query"]
        )

        return

    # Verifica se é uma mensagem
    if "message" not in atualizacao:
        return

    mensagem = atualizacao["message"]

    chat = mensagem.get("chat")

    if not chat:
        return

    chat_id = chat["id"]

    texto = mensagem.get("text", "").strip()

    if not texto:

        enviar_mensagem(
            chat_id,
            "Por favor, envie o nome de uma música ou artista. 🎵"
        )

        return

    # Comando /start
    if texto == "/start" or texto.startswith("/start@"):

        enviar_mensagem(
            chat_id,
            "🎵 Bem-vindo ao Music Bot!\n\n"
            "Pesquise músicas e artistas utilizando "
            "a API do Genius.\n\n"
            "Envie o nome de uma música ou artista "
            "para começar!\n\n"
            "Exemplo: Bohemian Rhapsody"
        )

        return

    # Comando /help
    if texto == "/help" or texto.startswith("/help@"):

        enviar_mensagem(
            chat_id,
            "🎵 COMO UTILIZAR O BOT\n\n"
            "1. Envie o nome de uma música ou artista.\n"
            "2. Escolha uma música nos botões apresentados.\n"
            "3. Receba os detalhes e o link da letra.\n\n"
            "Comandos disponíveis:\n"
            "/start - Iniciar o bot\n"
            "/help - Exibir ajuda"
        )

        return

    # Realiza a pesquisa
    processar_pesquisa(chat_id, texto)


# ==========================================
# RECEBER ATUALIZAÇÕES
# ==========================================

def receber_mensagens(offset=None):
    """Recebe mensagens e cliques dos botões."""

    url = f"{TELEGRAM_URL}/getUpdates"

    params = {
        "timeout": 30,
        "allowed_updates": json.dumps([
            "message",
            "callback_query"
        ])
    }

    if offset is not None:
        params["offset"] = offset

    try:

        response = requests.get(
            url,
            params=params,
            timeout=35
        )

        response.raise_for_status()

        dados = response.json()

        if dados.get("ok"):
            return dados.get("result", [])

        print("Erro na API Telegram:", dados)

    except requests.exceptions.RequestException as erro:

        print("Erro ao receber atualizações:", erro)

    return []


# ==========================================
# INICIALIZAÇÃO DO BOT
# ==========================================

def iniciar_bot():

    print("=" * 45)
    print("MUSIC BOT INICIADO COM SUCESSO!")
    print("=" * 45)

    offset = None

    while True:

        try:

            mensagens = receber_mensagens(offset)

            for atualizacao in mensagens:

                # Evita processar a mesma atualização novamente
                offset = atualizacao["update_id"] + 1

                try:

                    processar_atualizacao(atualizacao)

                except Exception as erro:

                    print(
                        "Erro ao processar atualização:",
                        erro
                    )

        except KeyboardInterrupt:

            print("\nBot encerrado pelo usuário.")
            break

        except Exception as erro:

            print("Erro inesperado:", erro)

            time.sleep(3)


# ==========================================
# EXECUÇÃO DO PROGRAMA
# ==========================================

if __name__ == "__main__":
    iniciar_bot()
