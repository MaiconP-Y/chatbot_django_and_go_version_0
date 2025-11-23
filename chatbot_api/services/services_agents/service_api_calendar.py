import os
import datetime
from datetime import datetime, timedelta, timezone
import logging

# --- IMPORTAÇÕES NECESSÁRIAS PARA O GOOGLE API ---
# Em um ambiente real, você precisa dessas bibliotecas:
# pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except ImportError:
    # Mocks para o ambiente onde as libs não estão instaladas
    logging.warning("Bibliotecas Google API não encontradas. Usando mocks para compilação.")
    class service_account:
        @staticmethod
        def Credentials(): pass
    def build(): pass

BR_TIMEZONE = timezone(timedelta(hours=-3))
# Configuração de Log
logging.basicConfig(level=logging.INFO)

# --- DEPENDÊNCIAS FALTANTES/MOCADAS ---
class ToolException(Exception):
    """Exceção customizada para erros de ferramenta."""
    pass

def validar_dia(data_formatada: str) -> str | None:
    """Função mock para simular a validação se o dia é útil/válido (ex: não é feriado)."""
    return None

def gerar_horarios_disponiveis() -> list[str]:
    """
    Gera uma lista de slots de 60 minutos (HH:MM) dentro do horário de trabalho (7:00h às 19:00h).
    """
    horarios = []
    start_time = datetime.strptime("07:00", "%H:%M")
    end_time = datetime.strptime("20:00", "%H:%M")
    
    current_time = start_time
    while current_time < end_time:
        horarios.append(current_time.strftime("%H:%M"))
        current_time += timedelta(minutes=60)
        
    return horarios

def is_slot_busy(slot_time_str: str, busy_blocks: list, data: str, duration_minutos: int) -> bool:
    """Verifica se o slot de agendamento (HH:MM) se sobrepõe a qualquer bloco ocupado."""
    # Assume fuso -03:00 para consistência
    
    # Tentativa de criar datetime com o offset, se a biblioteca `zoneinfo` não estiver disponível.
    # O fuso aqui deve ser o mesmo usado na chamada freebusy, que é 'America/Sao_Paulo' (-03:00)
    #slot_start_naive = datetime.strptime(f"{data}T{slot_time_str}:00", "%Y-%m-%dT%H:%M:%S")
    
    slot_start_dt = datetime.strptime(f"{data}T{slot_time_str}:00", "%Y-%m-%dT%H:%M:%S").replace(tzinfo=BR_TIMEZONE)
    
    slot_end_dt = slot_start_dt + timedelta(minutes=duration_minutos)
    
    for block in busy_blocks:
        try:
            # O horário retornado pela API FreeBusy JÁ ESTÁ em formato ISO 8601 com Z (UTC) ou offset.
            busy_start_dt = datetime.fromisoformat(block['start'])
            busy_end_dt = datetime.fromisoformat(block['end'])
        except ValueError:
            continue 

        # Condição de sobreposição: [Start1 < End2] AND [End1 > Start2]
        if slot_start_dt < busy_end_dt and slot_end_dt > busy_start_dt:
            return True
            
    return False


# --- CONFIGURAÇÃO DO GOOGLE CALENDAR ---
# Variáveis de ambiente
GOOGLE_CALENDAR_ID = os.environ.get('GOOGLE_CALENDAR_ID', 'maiconwantuil@gmail.com')
# O escopo necessário para ler a disponibilidade e criar eventos
CALENDAR_SCOPE = ['https://www.googleapis.com/auth/calendar'] 
# Caminho para o arquivo JSON de credenciais
GOOGLE_CREDENTIALS_PATH = os.environ.get('GOOGLE_CREDENTIALS_PATH', 'caminho/para/o/seu-arquivo-de-credenciais.json')
calendar_id = GOOGLE_CALENDAR_ID 


class ServicesCalendar:
    
    service = None 
    
    @staticmethod
    def inicializar_servico():
        """
        Inicializa o objeto de serviço do Google Calendar com credenciais de serviço.
        Chame esta função APENAS UMA VEZ antes de qualquer outra chamada de API.
        """
        if ServicesCalendar.service:
            logging.info("Serviço do Google Calendar já inicializado.")
            return True
            
        logging.info(f"Tentando inicializar serviço com arquivo em: {GOOGLE_CREDENTIALS_PATH}")
        
        try:
            # Carrega as credenciais a partir do arquivo JSON
            credentials = service_account.Credentials.from_service_account_file(
                GOOGLE_CREDENTIALS_PATH, 
                scopes=CALENDAR_SCOPE
            )
            
            # Constrói o objeto de serviço
            ServicesCalendar.service = build('calendar', 'v3', credentials=credentials)
            logging.info("Serviço do Google Calendar inicializado com sucesso.")
            return True
            
        except Exception as e:
            logging.error(f"ERRO DE INICIALIZAÇÃO E AUTENTICAÇÃO: {e}")
            logging.error("Verifique se o GOOGLE_CREDENTIALS_PATH e o arquivo JSON estão corretos.")
            # Retorna False para indicar falha na inicialização
            return False

    @staticmethod
    def buscar_eventos_do_dia(service, data: str) -> list:
        """
        Busca todos os eventos ocupados no dia especificado (Método events().list()).
        Mantido para fins de teste de eventos brutos, mas freebusy é preferível.
        """
        # ... (Implementação de buscar_eventos_do_dia - Sem alteração)
        try:
            time_min = f'{data}T07:00:00-03:00'
            time_max = f'{data}T20:00:00-03:00'

            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            return events_result.get('items', [])
            
        except Exception as e:
            return []


    @staticmethod
    def buscar_horarios_disponiveis(service, data: str, duracao_minutos: int = 60):
        """
        Calcula os horários disponíveis (livres) usando o endpoint freebusy do Google.
        
        Retorna um dicionário estruturado:
        - Sucesso: {'status': 'SUCCESS', 'available_slots': ['07:00', '08:00', ...]}
        - Erro:    {'status': 'ERROR', 'message': 'Mensagem de erro detalhada.'}
        """
        try:
            # 1. Validação de data
            try:
                data_obj = datetime.strptime(data, "%Y-%m-%d")
            except ValueError:
                return {"status": "ERROR", "message": f"Formato inválido para a data: '{data}'. Use 'YYYY-MM-DD'."}

            data_formatada = data_obj.strftime("%d-%m-%Y")
            mensagem_erro = validar_dia(data_formatada)
            if mensagem_erro:
                return {"status": "ERROR", "message": mensagem_erro}

            # 2. Definição do intervalo de tempo (07:00 a 20:00)
            time_min = f'{data}T07:00:00-03:00'
            time_max = f'{data}T20:00:00-03:00'
            
            # 3. CHAMADA AO FREEBUSY
            query_body = {
                "timeMin": time_min,
                "timeMax": time_max,
                "items": [{"id": calendar_id}]
            }

            freebusy_response = service.freebusy().query(body=query_body).execute()
            
            # 4. Extrai os blocos ocupados
            busy_blocks = freebusy_response.get('calendars', {}).get(calendar_id, {}).get('busy', [])
            
            # 5. Gera todos os slots possíveis e filtra
            horarios = gerar_horarios_disponiveis() 
            livres = [
                h for h in horarios 
                if not is_slot_busy(h, busy_blocks, data, duracao_minutos)
            ]

            if not livres:
                return {"status": "SUCCESS", "available_slots": [], "message": f"Não há horários disponíveis para {data}."}

            # Retorno estruturado de sucesso
            return {"status": "SUCCESS", "available_slots": livres}
            
        except ToolException as e:
            return {"status": "ERROR", "message": f"Erro na validação da ferramenta: {e}"}
        except Exception as e:
            logging.error(f"Erro inesperado no cálculo de disponibilidade (freebusy): {e}")
            return {"status": "ERROR", "message": f"Erro inesperado ao buscar horários disponíveis: {e}"}


    @staticmethod
    def criar_evento(
        service, 
        start_time_str: str, 
        chat_id: str,
        summary: str = None, 
        time_zone: str = 'America/Sao_Paulo'
    ):
        """
        Cria um novo evento de 1 hora de duração (60 minutos) na agenda principal.
        
        Retorna um dicionário estruturado:
        - Sucesso: {'status': 'SUCCESS', 'event_link': 'link_do_evento', 'start_time': 'YYYY-MM-DDTHH:MM:SS-03:00'}
        - Erro:    {'status': 'ERROR', 'message': 'Mensagem de erro detalhada.'}
        """
        if not service:
            return {"status": "ERROR", "message": "Erro: Objeto de serviço do Google Calendar não inicializado."}

        try:
            # 1. Converte a string de início em objeto datetime
            start_dt = datetime.fromisoformat(start_time_str)
        except ValueError:
            return {"status": "ERROR", "message": f"Formato inválido para start_time_str: '{start_time_str}'. Use o formato ISO 8601 completo (e.g., 'YYYY-MM-DDTHH:MM:SS-03:00')."}

        # 2. Define a duração de 60 minutos
        DURACAO_MINUTOS = 60
        end_dt = start_dt + timedelta(minutes=DURACAO_MINUTOS)
        
        # 3. Formata o horário de término para a API
        end_time_str = end_dt.isoformat()

        # 4. Define o Summary usando o chat_id (conforme solicitação do usuário)
        final_summary = f"Consulta Agendada (1h) - Cliente ID: {chat_id}"


        # Estrutura do evento (sem localização e descrição)
        event_body = {
            'summary': final_summary, 
            'start': {
                'dateTime': start_time_str, 
                'timeZone': time_zone,
            },
            'end': {
                'dateTime': end_time_str,   
                'timeZone': time_zone,
            },
            # Configuração de lembretes (para o dono da agenda - o doutor)
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 10},
                ],
            },
        }

        try:
            event = service.events().insert(
                calendarId=calendar_id, 
                body=event_body,
            ).execute()
            
            logging.info(f"Evento criado: {event.get('htmlLink')}")
            
            # Retorno estruturado de sucesso
            return {
                "status": "SUCCESS", 
                "event_link": event.get('htmlLink'), 
                "event_id": event.get('id'),
                "start_time": start_time_str
            }
            
        except Exception as e:
            logging.error(f"Erro ao criar evento na agenda: {e}")
            # Retorno estruturado de erro
            return {"status": "ERROR", "message": f"Falha ao criar o evento na agenda: {e}"}
        
    @staticmethod
    def deletar_evento(service, event_id: str):
        """
        Deleta um evento do Google Calendar pelo ID.
        """
        if not service:
            return {"status": "ERROR", "message": "Serviço de calendário não inicializado."}
            
        try:
            service.events().delete(
                calendarId=calendar_id, # Variável global definida no topo do arquivo original
                eventId=event_id
            ).execute()
            
            logging.info(f"Evento {event_id} deletado do Google Calendar com sucesso.")
            return {"status": "SUCCESS", "message": "Evento cancelado no Google Calendar."}
            
        except Exception as e:
            logging.error(f"Erro ao deletar evento {event_id}: {e}")
            # Se o erro for 404 (já deletado) ou 410 (gone), consideramos sucesso para não travar o banco
            if "404" in str(e) or "410" in str(e):
                return {"status": "SUCCESS", "message": "Evento já não existia no Google Calendar."}
                
            return {"status": "ERROR", "message": f"Erro ao deletar evento: {e}"}