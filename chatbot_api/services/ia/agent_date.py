import os
import json 
from groq import Groq
from chatbot_api.services.services_agents. tool_reset import finalizar_user, REROUTE_COMPLETED_STATUS
from chatbot_api.services.services_agents.prompts_agents import prompt_date_search, prompt_date_confirm
from chatbot_api.services. services_agents.service_api_calendar import ServicesCalendar, validar_data_nao_passada
from chatbot_api. services.services_agents.consulta_services import ConsultaService
from chatbot_api.services.redis_client import delete_history, delete_session_state, update_session_state
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

groq_service = Groq()
services_calendar = ServicesCalendar()
AGENT_DATE_SEARCH = "AGENT_DATE_SEARCH"
AGENT_DATE_CONFIRM = "AGENT_DATE_CONFIRM"
REGISTRATION_TOOL_SCHEMA_SEARCH =[
    {
        "type": "function", 
        "function": {
            "name": "finalizar_user",
            "description": "Função utilizada para resetar seção.  Deve ser chamada se o usuário pedir para cancelar o agendamento ou começar do zero.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "string",
                        "description": "O ID único do chat/usuário do WhatsApp.  Essencial para o registro."
                    },
                    "history_str": { 
                        "type": "string",
                        "description": "O histórico completo da conversa até o momento, para re-roteamento."
                    },
                },
                "required": ["history_str","chat_id"] 
            }
        }
    },
    {
        "type": "function", 
        "function": {
            "name": "ver_horarios_disponiveis",
            "description": "Verifica os horários disponíveis de 60 minutos para o dia em específico.  Retorna uma lista de strings HH:MM ou uma mensagem de erro.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "string",
                        "description": "A data fornecida pelo usuário, formatada obrigatoriamente como YYYY-MM-DD.  Ex: 2025-11-20"
                    }
                },
                "required": ["data"] 
            }
        }
    },
    {
        "type": "function", 
        "function": {
            "name": "exibir_proximos_horarios_flex",
            "description": "Busca e exibe os próximos 11 horários disponíveis no calendário a partir de hoje. Use esta função quando o usuário perguntar 'quais horários disponíveis' ou não especificar uma data.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]
REGISTRATION_TOOL_SCHEMA_CONFIRM = [
    {
        "type": "function", 
        "function": {
            "name": "finalizar_user",
            "description": "Função utilizada para resetar seção.  Deve ser chamada se o usuário pedir para cancelar o agendamento ou começar do zero.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "string",
                        "description": "O ID único do chat/usuário do WhatsApp.  Essencial para o registro."
                    },
                    "history_str": { 
                        "type": "string",
                        "description": "O histórico completo da conversa até o momento, para re-roteamento."
                    },
                },
                "required": ["history_str","chat_id"] 
            }
        }
    },
    {
        "type": "function", 
        "function": {
            "name": "agendar_consulta_1h",
            "description": "Cria um novo evento de 1 hora na agenda.  Esta função DEVE ser chamada APENAS depois que a disponibilidade for verificada e o usuário escolher um horário.",
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
    def __init__(self, router_agent_instance):
        try:
            self.client = Groq(api_key=os.environ. get("GROQ_API_KEY"))
            ServicesCalendar.inicializar_servico()
            self. calendar_services = ServicesCalendar()
            self.router_agent = router_agent_instance
        except Exception as e:
            raise EnvironmentError("A variável GROQ_API_KEY não está configurada. ") from e
    def exibir_proximos_horarios_flex(self) -> str:
        """
        Tool: Busca 11 slots disponíveis usando a estratégia escalonada (4->10->30 dias).
        Formata e retorna a lista legível para o usuário.
        """
        # Obtenção do serviço de forma canônica
        service = ServicesCalendar.service
        
        # 📞 Chamada da função eficiente que criamos (limite = 11)
        resultado_tool = ServicesCalendar.buscar_proximos_disponiveis(
            service=service, 
            limite_slots=11, 
            duracao_minutos=60  # Padrão de 60 minutos
        )

        if resultado_tool.get("status") == "SUCCESS":
            slots_encontrados = resultado_tool.get("available_slots", [])
            
            if not slots_encontrados:
                # ✅ Retorno Direto de Aviso (Go Way: Short-Circuiting)
                return (
                    f"❌ Nossos horários estão lotados nas próximas quatro semanas. "
                    f"Tente novamente em alguns dias."
                )
            else:
                # NOVO CÓDIGO AQUI: AGRUPAMENTO POR DATA
                
                slots_agrupados = {}
                
                # O formato do slot['legivel'] é 'DD/MM - HH:MM' (conforme service_api_calendar.py)
                for slot in slots_encontrados:
                    # Divide em data ('DD/MM') e hora ('HH:MM')
                    parts = slot['legivel'].split(' - ')
                    if len(parts) == 2:
                        data_parte = parts[0] # Ex: '03/12'
                        hora_parte = parts[1] # Ex: '07:00'
                        
                        # Adiciona a hora à lista daquela data específica
                        if data_parte not in slots_agrupados:
                            slots_agrupados[data_parte] = []
                        
                        slots_agrupados[data_parte].append(hora_parte)

                # NOVO CÓDIGO AQUI: FORMATAÇÃO DA STRING FINAL AGRUPADA
                
                slots_str_agrupado = []
                for data, horas in slots_agrupados.items():
                    # Junta as horas separadas por vírgula
                    horas_str = ", ".join(horas)
                    slots_str_agrupado.append(f"""Data {data}:
 {horas_str}""")

                slots_final_output = "\n".join(slots_str_agrupado)
                
                # ✅ Retorno Direto de Sucesso
                return (f"""Encontrei {len(slots_encontrados)} horários disponíveis próximos:\n{slots_final_output}\n\nQual destes horários você gostaria de agendar? (Ex: 'Quero dia 04/12 às 10:00')"""
                )
                
        else:
            # ✅ Retorno de Erro Técnico
            error_message = resultado_tool.get('message', 'Erro desconhecido ao buscar horários.')
            return f"❌ Falha ao buscar horários disponíveis: {error_message}"
    
    def generate_date(self, step_decode: str, history_str: str, chat_id: str, user_name: str) -> str:
        """
        Gera uma resposta da IA, usando a string do histórico completo como a última mensagem do usuário.
        Atua como roteador interno baseado no step_decode (estado atual).
        """
        # 1. Roteamento de Prompt e Ferramentas (A LLM só recebe o que é relevante para o estado)
        if step_decode == AGENT_DATE_SEARCH:
            prompt_content = prompt_date_search
            # Ferramentas: buscar horarios e finalizar (cancelar/resetar)
            tool_schema = REGISTRATION_TOOL_SCHEMA_SEARCH

        elif step_decode == AGENT_DATE_CONFIRM:
            prompt_content = prompt_date_confirm
            # Ferramentas: agendar consulta e finalizar (cancelar/resetar)
            tool_schema = REGISTRATION_TOOL_SCHEMA_CONFIRM
            
        else:
            # Estado desconhecido
            return f"Erro interno: Estado de agendamento ({step_decode}) desconhecido. Por favor, tente novamente."


        mensagens = [
            {
                "role": "system",
                "content": f"O NOME COMPLETO do usuário é: {user_name}. {prompt_content}",
            },
            {
                "role": "user",
                "content": history_str
            }
        ]
        
        try:
            chat_completion = self.client.chat. completions.create(
                messages=mensagens,
                model="llama-3.3-70b-versatile",
                tools=tool_schema, # 🎯 NOVO: Schema dinâmico
                tool_choice="auto",
                temperature=0.0, 
            )

            response_message = chat_completion.choices[0].message
            resposta_ia = response_message.content
            
            if response_message.tool_calls:
                available_functions = {
                    "agendar_consulta_1h": ServicesCalendar.criar_evento,
                    "ver_horarios_disponiveis": ServicesCalendar.buscar_horarios_disponiveis,
                    "finalizar_user": finalizar_user, 
                    "exibir_proximos_horarios_flex": self.exibir_proximos_horarios_flex, # Adicionado
                }
                
                mensagens. append(response_message)
                
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function. name
                    function_to_call = available_functions[function_name]
                    
                    function_args = json.loads(tool_call.function. arguments)

                    if function_name in ["finalizar_user"]:
                        function_args['history_str'] = history_str
                        function_args['chat_id'] = chat_id

                        result_output = finalizar_user(**function_args)
                
                        if result_output. startswith(f"{REROUTE_COMPLETED_STATUS}|"):
                            return result_output
                        
                        tool_content = result_output    
                        
                    elif function_name == "agendar_consulta_1h":
                        function_args['chat_id'] = chat_id
                        function_args['name'] = user_name
                        
                        LIMITE_AGENDAMENTOS_MSG = "Limite de agendamentos atingido. Você pode ter no máximo 2 consultas ativas."

                        resultado_tool = function_to_call(ServicesCalendar. service, **function_args)
                        
                        if isinstance(resultado_tool, dict) and resultado_tool.get("status") == "SUCCESS":
                            gcal_event_id = resultado_tool.get("event_id")
                            start_time_iso = resultado_tool.get("start_time")
                            
                            try:
                                # ... (Criação do agendamento no DB) ...
                                ConsultaService.criar_agendamento_db(
                                    chat_id=chat_id,
                                    google_event_id=gcal_event_id,
                                    start_time_iso=start_time_iso 
                                )

                                dt_obj = datetime.fromisoformat(start_time_iso)
                                data_formatada = dt_obj.strftime("%d/%m/%Y")
                                hora_formatada = dt_obj. strftime("%H:%M")
                                delete_session_state(chat_id)
                                delete_history(chat_id)
                        
                                return (f"""{REROUTE_COMPLETED_STATUS}|Agendamento Confirmado, {user_name}
Sua consulta foi marcada com sucesso para o dia *{data_formatada}* às {hora_formatada}. 
Fique tranquilo(a), enviaremos um lembrete próximo ao dia do evento."""
                                )
                            
                            except ValueError as e:
                                # ... (Tratamento de erro de limite de agendamento) ...
                                error_message = str(e)
                                
                                if LIMITE_AGENDAMENTOS_MSG in error_message:
                                    ServicesCalendar.deletar_evento(
                                        ServicesCalendar.service, 
                                        gcal_event_id
                                    )
                                    return f"{REROUTE_COMPLETED_STATUS}|{LIMITE_AGENDAMENTOS_MSG}"
                                else:
                                    tool_content = f"Erro no salvamento do DB: {error_message}"
                            
                            except Exception as e:
                                tool_content = f"Erro desconhecido ao salvar agendamento: {str(e)}"

                        else:
                            tool_content = f"Erro no agendamento: {resultado_tool. get('message', 'Erro desconhecido')}"

                    
                    # 🎯 NOVO FLUXO: ver_horarios_disponiveis
                    elif function_name == "ver_horarios_disponiveis":
                        data = function_args.get("data")
                        validacao = validar_data_nao_passada(data)
                        
                        if not validacao['valid']:
                            return f"{REROUTE_COMPLETED_STATUS}|Por favor insira uma data do futuro."
                        
                        resultado_tool = ServicesCalendar.buscar_horarios_disponiveis(ServicesCalendar.service, **function_args)
                        
                        # ⚠️ CORREÇÃO 1: Tratar falha na Tool (resultado não é dict ou status não é SUCCESS)
                        if not (isinstance(resultado_tool, dict) and resultado_tool. get("status") == "SUCCESS"):
                            error_message = resultado_tool.get('message', 'Erro desconhecido ao verificar horários.')
                            return f"{REROUTE_COMPLETED_STATUS}|Falha ao verificar horários: {error_message}\n\nInforme uma nova data (AAAA-MM-DD)."
                        
                        # Se chegou aqui, o status é SUCCESS
                        available_slots = resultado_tool.get("available_slots", [])
                        
                        # CORREÇÃO 2: Definir data_formatada após validações
                        try:
                            # Converte YYYY-MM-DD para DD/MM/YYYY
                            data_formatada = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
                        except ValueError:
                            # Caso a data não esteja no formato esperado, usa a string bruta
                            data_formatada = data
                        
                        if not available_slots:
                                # Retorno sem mudança de estado (continua SEARCH, pedindo nova data)
                                return (f"""{REROUTE_COMPLETED_STATUS}|Nenhum horário disponível em **{data_formatada}**.\n\nInforme outra data para verificar (AAAA-MM-DD).""")
                        else:
                            # 🎯 TRANSIÇÃO DE ESTADO! O sucesso da busca muda o fluxo.
                            update_session_state(chat_id, registration_step=AGENT_DATE_CONFIRM) 
                            delete_history(chat_id)
                            slots_str = "\n".join([f"  - {slot}" for slot in available_slots])
                            
                            # Retorno com a nova instrução para o usuário
                            return (f"""Os Horários disponíveis em *{data_formatada}*:
{slots_str}
Qual horário deseja agendar? (Informe o horário no formato HH:MM)"""
                            )         

                    elif function_name == "exibir_proximos_horarios_flex":
                        # Chamada da Tool
                        resultado_tool = self.exibir_proximos_horarios_flex()
                        
                        if resultado_tool.startswith("❌"): # Se for erro ou sem slots
                            # Retorna o erro sem mudar de estado
                            return f"{REROUTE_COMPLETED_STATUS}|{resultado_tool}"
                        delete_history(chat_id)    
                        # 🎯 TRANSIÇÃO DE ESTADO! O sucesso da busca flexível muda o fluxo.
                        update_session_state(chat_id, registration_step=AGENT_DATE_CONFIRM)
                        
                        # Retorna o resultado para o usuário
                        return f"{resultado_tool}"

                    mensagens.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool", 
                            "name": function_name,
                            "content": f"Resultado da Ferramenta {function_name}: {tool_content}"
                        }
                    )
                    
                final_completion = self.client.chat.completions. create(
                    model="llama-3.3-70b-versatile",
                    messages=mensagens 
                )
            
                return final_completion.choices[0].message.content
            
            return resposta_ia
            
        except Exception as e:
            logger.error(f"Erro ao chamar a API da Groq: {e}")
            return "Desculpe, estou tendo problemas técnicos para responder agora."