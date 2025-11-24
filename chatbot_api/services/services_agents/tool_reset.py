from chatbot_api.services.redis_client import delete_session_date

REROUTE_COMPLETED_STATUS = "REROUTE_COMPLETED"

def finalizar_user(history_str: str,chat_id: str):
    from chatbot_api.services.ia.ia_core import agent_service
    sucess = delete_session_date(chat_id)
    try:
        print(sucess)      
        service_agent = agent_service()
        response = service_agent.router(history_str, chat_id)
        return f"{REROUTE_COMPLETED_STATUS}|{response}"

    except Exception as e:
            print(f"Erro no re-roteamento após finalização: {e}")
            return "ERROR: Falha no serviço de re-roteamento após reset."
    