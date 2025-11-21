import os
import json 
from groq import Groq
from chatbot_api.services.redis_client import delete_session_date, delete_session_state
from chatbot_api.services.services_agents.prompts_agents import prompt_date
# REMOVIDO: from chatbot_api.services.ia.ia_core import agent_service 
from chatbot_api.services.services_agents.service_api_calendar import ServicesCalendar

groq_service = Groq()
services_calendar = ServicesCalendar()

#################### SCHEMA CORRETO PARA TOOL CALLING #############################

REGISTRATION_TOOL_SCHEMA = [
    {
        "type": "function", 
        "function": {
            "name": "delete_session_date",
            "description": "Função utilizada para resetar seção. Deve ser chamada se o usuário pedir para cancelar o agendamento ou começar do zero.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "string",
                        "description": "O ID único do chat/usuário do WhatsApp. Essencial para o registro."
                    },
                },
                "required": ["chat_id"] 
            }
        }
    },
    {
        "type": "function", 
        "function": {
            "name": "ver_horarios_disponiveis",
            "description": "Verifica os horários disponíveis de 60 minutos para o dia em específico. Retorna uma lista de strings HH:MM ou uma mensagem de erro.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "string",
                        "description": "A data fornecida pelo usuário, formatada obrigatoriamente como YYYY-MM-DD. Ex: 2025-11-20"
                    }
                },
                "required": ["data"] 
            }
        }
    },
    {
        "type": "function", 
        "function": {
            "name": "agendar_consulta_1h",
            "description": "Cria um novo evento de 1 hora na agenda. Esta função DEVE ser chamada APENAS depois que a disponibilidade for verificada e o usuário escolher um horário.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_time_str": {
                        "type": "string",
                        "description": "Data e hora de início da consulta, formatada como ISO 8601 completo, incluindo fuso horário. Ex: 2025-11-20T14:00:00-03:00"
                    },
                    "summary": {
                        "type": "string",
                        "description": "Breve título do evento, como 'Agendamento de Consulta de [Nome do Usuário]'"
                    }
                },
                "required": ["start_time_str"] 
            }
        }
    }
]

class Agent_date():
    """
    Classe de serviço dedicada a interagir com a API da Groq, usando o histórico completo (history_str)
    para manter o contexto e delegar ações de registro via Tool Calling.
    """
    def __init__(self, router_agent_instance): # 🟢 RECEBE a instância do roteador
        try:
            self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
            # Inicializa o serviço do Google Calendar (A tool pura)
            ServicesCalendar.inicializar_servico()
            self.calendar_services = ServicesCalendar()
            self.router_agent = router_agent_instance # 🟢 Armazena a instância injetada
        except Exception as e:
            raise EnvironmentError("A variável GROQ_API_KEY não está configurada.") from e
    
    def generate_date(self, history_str: str, chat_id: str, user_name: str) -> str:
        """
        Gera uma resposta da IA, usando a string do histórico completo como a última mensagem do usuário.
        """
        
        mensagens = [
            {
                "role": "system",
                "content": f"O NOME COMPLETO do usuário é: {user_name}. {prompt_date}",
            },
            {
                "role": "user",
                "content": history_str
            }
        ]
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=mensagens,
                model="llama-3.3-70b-versatile",
                tools=REGISTRATION_TOOL_SCHEMA, 
                tool_choice="auto",
                temperature=0.1 , 
            )

            response_message = chat_completion.choices[0].message
            resposta_ia = response_message.content
            
            if response_message.tool_calls:
                # 🛠️ Mapeamento corrigido: Usando a função correta
                available_functions = {
                    "agendar_consulta_1h": ServicesCalendar.criar_evento, # Método estático
                    "ver_horarios_disponiveis": ServicesCalendar.buscar_horarios_disponiveis, # Método estático
                    "delete_session_date": delete_session_date, 
                }
                
                mensagens.append(response_message)
                
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_to_call = available_functions[function_name]
                    
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Se for a tool de reset, injeta o chat_id
                    if function_name == "delete_session_date":
                        function_args['chat_id'] = chat_id 
                        tool_result = function_to_call(**function_args)
                        if tool_result == "SUCCESS_RESET":        
                            return "Para responder eu preciso da sua pergunta novamente. Poderia mandar novamente?"
                        tool_content = "SUCCESS: Seção de agendamento resetada com sucesso."
                    
                    # Para as funções do Calendar, o service deve ser passado como primeiro argumento
                    elif function_name in ["agendar_consulta_1h", "ver_horarios_disponiveis"]:
                        if not ServicesCalendar.service:
                            tool_content = "FALHA: O serviço do Google Calendar não foi inicializado."
                        elif function_name == "agendar_consulta_1h":
                            function_args['chat_id'] = chat_id # <- A CORREÇÃO
                                
                            # Chama o método estático passando o objeto service real e os argumentos
                            tool_content = function_to_call(
                                ServicesCalendar.service, 
                                **function_args
                            )
                        else:
                            # ⚠️ Chama o método estático passando o objeto service real
                            tool_content = function_to_call(
                                ServicesCalendar.service, 
                                **function_args
                            )

                    
                    mensagens.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool", 
                            "name": function_name,
                            "content": f"Resultado da Ferramenta {function_name}: {tool_content}"
                        }
                    )
                    
                final_completion = self.client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=mensagens 
                )
            
                return final_completion.choices[0].message.content
            
            return resposta_ia
            
        except Exception as e:
            print(f"Erro ao chamar a API da Groq: {e}")
            return "Desculpe, estou tendo problemas técnicos para responder agora."
