from chatbot_api.services.redis_client import delete_session_state, delete_history, add_message_to_history

REROUTE_COMPLETED_STATUS = "REROUTE_COMPLETED"

def finalizar_user(history_str: str, chat_id: str):
    from chatbot_api.services.ia.ia_core import agent_service
    delete_session_state(chat_id) 
    delete_history(chat_id)
    history_lines = history_str.split('\n')
    last_user_message_content = "menu"
    
    for line in reversed(history_lines):
        if line.startswith("[User]:"):
            last_user_message_content = line.replace("[User]:", "", 1).strip()
            print(last_user_message_content)
            break
            
    clean_context_for_router = f"User: {last_user_message_content}"
    print(history_str)
    try:    
        service_agent = agent_service()
        
        # 🎯 CHAMADA LIMPA: Passa step_decode=None (padrão) e o sinal de re-roteamento
        response = service_agent.router(clean_context_for_router, chat_id, reroute_signal="__FORCE_ROUTE_INTENT__")
        
        if response == "Ok, solicitação detectada com sucesso. Um de nossos agentes entrará em contato com você em breve. A partir de agora, nosso bot LLM não processará mais suas mensagens.":
             return response

             
        if last_user_message_content:
            add_message_to_history(chat_id, "User", last_user_message_content) 
        final_bot_response = response.split('|', 1)[1] if response.startswith(REROUTE_COMPLETED_STATUS) else response
        add_message_to_history(chat_id, "Bot", final_bot_response)
        return f"{REROUTE_COMPLETED_STATUS}|{response}"

    except Exception as e:
            print(f"Erro no re-roteamento após finalização: {e}")
            return "ERROR: Falha no serviço de re-roteamento após reset."