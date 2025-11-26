from chatbot_api.services.redis_client import delete_session_date, add_message_to_history # IMPORTAR add_message_to_history

REROUTE_COMPLETED_STATUS = "REROUTE_COMPLETED"

def finalizar_user(history_str: str, chat_id: str):
    from chatbot_api.services.ia.ia_core import agent_service
    
    # 1. Limpeza de Estado
    sucess = delete_session_date(chat_id)
    
    # --- Extração da última mensagem do Usuário ---
    history_lines = history_str.split('\n')
    last_user_message_content = "menu" # Mensagem limpa (sem prefixo)
    print(history_lines)
    
    for line in reversed(history_lines):
        if line.startswith("[User]:"):
            # Pega o conteúdo após o prefixo "[User]:" de forma segura
            last_user_message_content = line.replace("[User]:", "", 1).strip()
            print(last_user_message_content)
            break
            
    # 🟢 CONTEXTO FORMATADO para o LLM
    # O Router PRECISA do prefixo "User: " para saber quem está falando.
    clean_context_for_router = f"User: {last_user_message_content}"
    print(history_str)
    try:
        print(sucess)      
        service_agent = agent_service()
        
        # 2. Chama o roteador com o CONTEXTO LIMPO E FORMATADO
        response = service_agent.router(clean_context_for_router, chat_id)
        
        # 3. Adiciona o Histórico
        
        # Adiciona a mensagem do Usuário (usando o conteúdo LIMPO, sem a formatação do router)
        if last_user_message_content:
            add_message_to_history(chat_id, "User", last_user_message_content) 
        
        # Adiciona a resposta do Bot (limpa, sem a flag de controle)
        final_bot_response = response.split('|', 1)[1] if response.startswith(REROUTE_COMPLETED_STATUS) else response
        add_message_to_history(chat_id, "Bot", final_bot_response)

        # 4. Retorna a resposta BRUTA com a flag para o Worker
        return f"{REROUTE_COMPLETED_STATUS}|{response}"

    except Exception as e:
            print(f"Erro no re-roteamento após finalização: {e}")
            return "ERROR: Falha no serviço de re-roteamento após reset."