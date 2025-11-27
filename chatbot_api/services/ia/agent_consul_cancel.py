import os
import json
from groq import Groq
from chatbot_api.services.services_agents.prompts_agents import prompt_consul_cancel
from chatbot_api.services.services_agents.consulta_services import ConsultaService
from chatbot_api.services.services_agents.tool_reset import finalizar_user, REROUTE_COMPLETED_STATUS
from chatbot_api.services.redis_client import delete_history, delete_session_state

# 2. Definição Unificada das Tools
TOOLS_CANCEL = [
    {
        "type": "function",
        "function": {
            "name": "finalizar_user",
            "description": "Função utilizada para resetar sessão/voltar ao menu. Deve ser chamada se o usuário mudar de assunto ou pedir para sair.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": { "type": "string", "description": "ID do usuário." },
                    "history_str": { "type": "string", "description": "Histórico para re-roteamento." },
                },
                "required": ["history_str", "chat_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancelar_consulta",
            "description": "Cancela uma consulta existente baseada no número identificador (ID UX).",
            "parameters": {
                "type": "object",
                "properties": {
                    "numero_consulta": {
                        "type": "integer",
                        "description": "O número da consulta (ex: 1, 2) que aparece na lista [1]."
                    }
                },
                "required": ["numero_consulta"]
            }
        }
    }
]

class Agent_cancel:
    def __init__(self):
        try:
            self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        except Exception as e:
            raise EnvironmentError("GROQ_API_KEY não configurada.") from e
    
    def generate_cancel(self, history_str: str, chat_id: str) -> str:
        
        # --- Prepara Dados (Lógica de Negócio) ---
        lista_consultas = ConsultaService.listar_agendamentos(chat_id)
        
        if lista_consultas:
            formatted_list = []
            for item in lista_consultas:
                formatted_list.append(
                    f"[{item['appointment_number']}] - Data: {item['data']} às {item['hora']}"
                )
            consultas_str = "\n".join(formatted_list)
        else:
            consultas_str = "Nenhuma consulta agendada."
        
        # --- Monta Prompt ---
        system_prompt = f"""
        {prompt_consul_cancel}
        
        --- DADOS EM TEMPO REAL ---
        Aqui estão as consultas atuais deste usuário:
        {consultas_str} 
        ---------------------------
        """
        
        mensagens = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": history_str}
        ]
        
        try:
            # --- Chamada LLM ---
            chat_completion = self.client.chat.completions.create(
                messages=mensagens,
                model="llama-3.3-70b-versatile",
                temperature=0.1,
                tools=TOOLS_CANCEL, # Schema atualizado
                tool_choice="auto"
            )
            
            response_message = chat_completion.choices[0].message
            
            # --- Processamento de Tools ---
            if response_message.tool_calls:
                mensagens.append(response_message) # Adiciona contexto para a próxima volta (se houver)

                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    
                    if function_name == "finalizar_user":
                        args['history_str'] = history_str
                        args['chat_id'] = chat_id    
                        result_output = finalizar_user(**args)
                        if result_output.startswith(f"{REROUTE_COMPLETED_STATUS}|"):
                            return result_output
                        
                        tool_content = result_output

                    elif function_name == "cancelar_consulta":
                        numero = args.get("numero_consulta")
                        tool_content = ConsultaService.cancelar_agendamento_por_id_ux(chat_id, numero)
                        if tool_content:
                            delete_session_state(chat_id)
                            delete_history(chat_id)
                            return f"{REROUTE_COMPLETED_STATUS}|Sua consulta foi cancelada com sucesso! Qualquer duvida é só chamar!"
                    
                    else:
                        tool_content = "Erro: Ferramenta desconhecida."

                    mensagens.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": str(tool_content)
                    })
                    
                final_response = self.client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=mensagens
                )
                return final_response.choices[0].message.content

            return response_message.content
            
        except Exception as e:
            print(f"Erro no Agent Cancel: {e}")
            return "Desculpe, tive um problema técnico. Tente digitar 'menu' para reiniciar."