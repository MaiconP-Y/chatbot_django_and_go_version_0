from google.oauth2 import service_account
from googleapiclient.discovery import build
import os

SCOPES = ['https://www.googleapis.com/auth/calendar']

google_credentials = os.environ.get("GOOGLE_CREDENTIALS_PATH")
calendar_id = os.environ.get("GOOGLE_CALENDAR_ID")

credentials = service_account.Credentials.from_service_account_file(
    google_credentials,
    scopes=SCOPES
)

service = build('calendar', 'v3', credentials=credentials)


class ServicesCalendar:

    def criar_servico_calendar():
        credentials = service_account.Credentials.from_service_account_file(
            google_credentials,  
            scopes=SCOPES
        )
        service = build('calendar', 'v3', credentials=credentials)
        return service
    
    def criar_evento(nome_paciente, data_inicio, data_fim):
        event = {
            'summary': f'Consulta de Quiropraxia - {nome_paciente}',
            'start': {
                'dateTime': data_inicio,
                'timeZone': 'America/Sao_Paulo',
            },
            'end': {
                'dateTime': data_fim,
                'timeZone': 'America/Sao_Paulo',
            },
        }
        return event

    def inserir_evento(service, event):
        created_event = service.events().insert(
            calendarId=calendar_id,  # seu email de agenda
            body=event
        ).execute()
        return created_event

    def buscar_eventos_do_dia(service, data: str):
        try:
            time_min = f"{data}T07:00:00-03:00"
            time_max = f"{data}T20:00:00-03:00" 

            eventos = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            return eventos.get('items', [])
        
        except Exception as e:
            print("Erro ao buscar eventos:", e)
            return []
        
    def cancelar_consulta(id_evento: str) -> bool:
        try:
            service.events().delete(
                calendarId=calendar_id,
                eventId=id_evento,
                sendUpdates='none'
            ).execute()
            return True  # ✅ sempre retorna booleano
        except Exception as e:  
            return False