# Arquivo: chatbot_api/services/ia/agent_consul_cancel.py
import os
import json
from groq import Groq
from chatbot_api.services.services_agents.prompts_agents import prompt_consul_cancel
from chatbot_api.services.services_agents.consulta_services import ConsultaService

# Definição das Ferramentas (Tools)
TOOLS_CANCEL = [
    {
        "type": "function",
        "function": {
            "name": "cancelar_consulta",
            "description": "Cancela uma consulta existente baseada no número identificador (ID UX) fornecido na lista.",
            "parameters": {
                "type": "object",
                "properties": {
                    "numero_consulta": {
                        "type": "integer",
                        "description": "O número da consulta (ex: 1, 2, 3) que aparece na lista [1]."
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
        
        lista_consultas = ConsultaService.listar_agendamentos(chat_id)
        
        # --- NOVO: ETAPA DE FORMATAÇÃO PARA O LLM ---
        if lista_consultas:
            formatted_list = []
            for item in lista_consultas:
                # Cria a string no formato que o prompt espera: [NÚMERO] - Data: DD/MM/AAAA às HH:MM
                formatted_list.append(
                    f"[{item['appointment_number']}] - Data: {item['data']} às {item['hora']}"
                )
            consultas_str = "\n".join(formatted_list)
        else:
            consultas_str = "Nenhuma consulta agendada."
        # ---------------------------------------------

        # 2. Injeta os dados no prompt do sistema
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
            # 3. Chamada LLM com Tools
            chat_completion = self.client.chat.completions.create(
                messages=mensagens,
                model="llama-3.3-70b-versatile",
                temperature=0.1,
                tools=TOOLS_CANCEL,
                tool_choice="auto"
            )
            
            response_message = chat_completion.choices[0].message
            
            if response_message.tool_calls:
                tool_call = response_message.tool_calls[0]
                function_name = tool_call.function.name
                
                if function_name == "cancelar_consulta":
                    args = json.loads(tool_call.function.arguments)
                    numero = args.get("numero_consulta")
                    
                    # Executa a lógica de negócio
                    # **Nota:** Certifique-se de que ConsultaService implementa essa função.
                    resultado = ConsultaService.cancelar_agendamento_por_id_ux(chat_id, numero)
                    
                    # Retorna o resultado para a IA finalizar o diálogo
                    mensagens.append(response_message)
                    mensagens.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": resultado
                    })
                    
                    final_response = self.client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=mensagens
                    )
                    return final_response.choices[0].message.content

            # Se não chamou ferramenta (apenas conversa)
            return response_message.content
            
        except Exception as e:
            print(f"Erro no Agent Cancel: {e}")
            return "Desculpe, tive um problema técnico ao verificar seus agendamentos."