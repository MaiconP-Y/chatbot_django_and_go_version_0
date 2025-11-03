import os 
import hmac
import hashlib 
import json 
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import logging
from chatbot_api.services.waha_api import Waha
from chatbot_api.services.redis_client import (
    get_session_state, 
    update_session_state,
    add_message_to_history,
    enqueue_user,
    is_user_in_queue,
    publish_new_user,
    check_and_set_message_id
) 

waha = Waha()
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# NOVO: Função de Validação HMAC
# ------------------------------------------------------------------
def validate_hmac(request_body: bytes, hmac_header: str) -> bool:
    """
    Verifica se a assinatura HMAC (SHA512) no cabeçalho 
    corresponde ao body da requisição, usando a chave secreta.
    """
    # 1. Obtém a chave secreta
    secret = os.environ.get("WEBHOOK_HMAC_SECRET")
    if not secret:
        logger.error("❌ WEBHOOK_HMAC_SECRET não configurada no ambiente.")
        return False
    
    # 2. Calcula o HMAC esperado (A chave e o corpo precisam ser bytes)
    expected_hmac = hmac.new(
        key=secret.encode('utf-8'),
        msg=request_body,
        digestmod=hashlib.sha512
    ).hexdigest()
    
    # 3. Compara de forma segura (previne ataques de temporização)
    return hmac.compare_digest(expected_hmac, hmac_header)
# ------------------------------------------------------------------


@csrf_exempt
@require_POST
def webhook(request):
    """
    Webhook otimizado, seguro com validação HMAC.
    """
    # PASSO 1: Capturar o corpo RAW e o cabeçalho HMAC
    # Pegue o corpo da requisição *antes* de tentar decodificar o JSON.
    raw_body = request.body
    # O WAHA usa o cabeçalho 'X-Webhook-Hmac'
    hmac_header = request.headers.get("X-Webhook-Hmac", None)

    # PASSO 2: Realizar a Validação
    if not hmac_header:
        logger.warning("❌ Requisição recusada: Cabeçalho 'X-Webhook-Hmac' ausente.")
        # Retorna 403 Forbidden se o cabeçalho de segurança estiver faltando
        return JsonResponse({"error": "Forbidden: Missing HMAC header"}, status=403) 

    if not validate_hmac(raw_body, hmac_header):
        logger.warning(f"❌ Requisição recusada: Assinatura HMAC inválida. Recebido: {hmac_header[:10]}...")
        # Retorna 403 Forbidden se a assinatura for inválida
        return JsonResponse({"error": "Invalid HMAC signature"}, status=403)
    
    # Se a validação HMAC passou, processamos o corpo da requisição.
    
    try:
        # Usamos o raw_body (que já foi lido) para carregar o JSON
        main_data = json.loads(raw_body)
        message_data = main_data.get("payload", {})
        chat_id = message_data.get("from")
        message = message_data.get("body", "").strip().lower() 
        message_id = message_data.get("id")

        if not message:
             return JsonResponse({"status": "no_message"}, status=200)
        if not check_and_set_message_id(message_id):
                logger.info(f"⏭️ Mensagem {message_id} de {chat_id} duplicada. Ignorando.")
                # Retorna 200 para o WAHA parar de tentar reenviar.
                return JsonResponse({"status": "duplicate", "message_id": message_id}, status=200)
    
        add_message_to_history(chat_id, "User", message)

        session_state = get_session_state(chat_id)
        current_step = session_state.get('step', 'INICIO') if session_state else 'INICIO'
        logger.info(f"Estado de {chat_id}: {current_step}")

        if current_step == "EM_ATENDIMENTO":
            publish_new_user(chat_id) # Worker pega a mensagem e continua a conversa
            return JsonResponse({"status": "success", "step": current_step})

        elif not is_user_in_queue(chat_id): 
            new_step = "IN_QUEUE"
            queue_position = enqueue_user(chat_id)
            resposta = f" Você está na fila. Posição: {queue_position}. Aguarde o atendimento."
            waha.send_whatsapp_message(chat_id, resposta)
            update_session_state(chat_id, step=new_step) # Atualiza o estado
            if queue_position == 1:
                publish_new_user(chat_id) # Notifica o worker para iniciar o processamento
                logger.info("Worker notificado. Novo usuário é o primeiro.")
            return JsonResponse({"status": "success", "step": current_step})
        return JsonResponse({"status": "success", "step": current_step})
                
    
    except Exception as e:
        logger.error(f"❌ Erro no webhook: {e}", exc_info=True)
        return JsonResponse({"error": "Internal server error"}, status=500)