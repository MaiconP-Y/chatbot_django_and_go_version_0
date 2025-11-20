import os
import datetime
from datetime import datetime, timedelta
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
    slot_start_dt = datetime.strptime(f"{data}T{slot_time_str}:00-03:00", "%Y-%m-%dT%H:%M:%S%z")
    slot_end_dt = slot_start_dt + timedelta(minutes=duration_minutos)
    
    for block in busy_blocks:
        try:
            busy_start_dt = datetime.strptime(block['start'], "%Y-%m-%dT%H:%M:%S%z")
            busy_end_dt = datetime.strptime(block['end'], "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            continue 

        # Condição de sobreposição
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
            print(events_result)
            logging.info(events_result)
            return events_result.get('items', [])
            
        except Exception as e:
            return []


    @staticmethod
    def buscar_horarios_disponiveis(service, data: str, duracao_minutos: int = 60) -> str | list[str]:
        """
        Calcula os horários disponíveis (livres) usando o endpoint freebusy do Google.
        """
        # ... (Implementação de buscar_horarios_disponiveis - Sem alteração)
        try:
            # 1. Validação de data
            try:
                data_obj = datetime.strptime(data, "%Y-%m-%d")
            except ValueError:
                raise ToolException(f"Formato inválido para a data: '{data}'. Use 'YYYY-MM-DD'.")

            data_formatada = data_obj.strftime("%d-%m-%Y")
            mensagem_erro = validar_dia(data_formatada)
            if mensagem_erro:
                raise ToolException(mensagem_erro)

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
                return f"Não há horários disponíveis para {data}."

            return livres
            
        except ToolException as e:
            return f"Erro na validação: {e}"
        except Exception as e:
            logging.error(f"Erro inesperado no cálculo de disponibilidade (freebusy): {e}")
            return f"Erro ao buscar horários disponíveis: {e}"


    @staticmethod
    def criar_evento(
        service, 
        start_time_str: str, 
        chat_id: str,
        summary: str = None, 
        time_zone: str = 'America/Sao_Paulo'
    ) -> str:
        """
        Cria um novo evento de 1 hora de duração (60 minutos) na agenda principal.
        
        O 'summary' do evento usa o 'chat_id' para identificação do cliente.
        
        Args:
            service: O objeto de serviço do Google Calendar autenticado.
            start_time_str: Data e hora de início no formato 'YYYY-MM-DDTHH:MM:SS-03:00'.
            chat_id: ID único do chat (ex: ID do WhatsApp) para identificação.
            time_zone: Fuso horário (padrão é São Paulo).
            
        Returns:
            O link HTML do evento criado.
        """
        if not service:
            raise ToolException("Erro: Objeto de serviço do Google Calendar não inicializado.")

        try:
            # 1. Converte a string de início em objeto datetime
            # A string deve incluir o fuso horário (ex: -03:00) para funcionar corretamente.
            start_dt = datetime.fromisoformat(start_time_str)
        except ValueError:
            raise ToolException(f"Formato inválido para start_time_str: '{start_time_str}'. Use o formato ISO 8601 completo (e.g., 'YYYY-MM-DDTHH:MM:SS-03:00').")

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
            return event.get('htmlLink')
            
        except Exception as e:
            logging.error(f"Erro ao criar evento na agenda: {e}")
            raise ToolException(f"Falha ao criar o evento na agenda: {e}")