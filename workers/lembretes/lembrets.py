import os
import logging
import time
from datetime import datetime, timedelta, timezone
from workers.lembretes.redis_lembrets import lembrete_ja_enviado

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from chatbot_api.services.waha_api import Waha
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("reminder-worker")

TTL_TWO_HOURS = 7200
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")

def get_google_service():
    credentials = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH, scopes=['https://www.googleapis.com/auth/calendar'])
    return build('calendar', 'v3', credentials=credentials)

def buscar_eventos(service, antecedencia_horas=2):
    """
    Busca eventos que vão acontecer daqui a antecedencia_horas até antecedencia_horas + 20 minutos.
    """
    now = datetime.now(timezone.utc)
    start_check = now + timedelta(hours=antecedencia_horas)
    end_check = start_check + timedelta(minutes=20)

    events_result = service.events().list(
        calendarId=GOOGLE_CALENDAR_ID,
        # **CORREÇÃO:** Remova o '+'Z' extra. O objeto 'start_check' já tem o fuso +00:00.
        timeMin=start_check.isoformat(), 
        timeMax=end_check.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return events_result.get('items', [])

def send_whatsapp_message(phone_number, message):
    """
    Placeholder - aqui chame sua função real do WhatsApp (WAHA ou worker).
    """
    try:
        
        waha = Waha()
        waha.send_whatsapp_message(phone_number, message)

    except Exception as e:
            logger.error(f"Erro crítico no worker(send_message): {e}")

def extract_phone_and_name(payload):
    """
    Extrai o nome e o Cliente ID do resumo (summary) do evento.
    Padrão esperado: Nome: <Nome> - Cliente ID: <Cliente ID>
    """
    padrao = r"Nome:\s*(.+?)\s*-\s*Cliente ID:\s*(.+)"
    match = re.search(padrao, payload)
    if match:
        nome = match.group(1).strip()
        cliente_id = match.group(2).strip()
        return {"nome": nome, "cliente_id": cliente_id}
    # Retorna None se o padrão não for encontrado
    return None 


def main():
    logger.info("Reminder worker iniciado")
    service = get_google_service()
    while True:
        try:
            events = buscar_eventos(service)
            for event in events:
                event_id = event.get("id")
                # 🌟 ORDEM CORRIGIDA: Pega o payload ANTES de usá-lo na função
                payload = event.get("summary")
                start = event["start"].get("dateTime", "")
                
                phone_and_name = extract_phone_and_name(payload)

                # Validação de dados essenciais
                if not phone_and_name or not event_id or not start:
                    # Log mais detalhado do porquê o evento foi pulado
                    log_msg = f"Evento {event_id} pulado. "
                    if not event_id:
                        log_msg += "Motivo: ID ausente. "
                    if not start:
                        log_msg += "Motivo: Data/Hora ausente. "
                    if not phone_and_name:
                        log_msg += f"Motivo: Resumo fora do padrão/Dados de contato ausentes. Resumo: {payload}"
                    logger.warning(log_msg)
                    continue

                # Acesso seguro aos dados após a validação
                nome = phone_and_name["nome"] 
                cliente_id = phone_and_name["cliente_id"]

                if lembrete_ja_enviado(event_id, TTL_TWO_HOURS):
                    logger.info(f"Lembrete já enviado para evento: {event_id}")
                    continue

                try:
                    dt_obj = datetime.fromisoformat(start) 
                    hora_formatada = dt_obj.strftime("%H:%M")
                except ValueError:
                    logger.error(f"Erro de formato de data no evento {event_id}: {start}")
                    hora_formatada = "em breve"

                message = f"Olá {nome}! Sua consulta será às {hora_formatada}. Este é um lembrete automático. Esperamos por voce, esse lembrete é automatizado, portanto não precisa responder. Obtigado pela atenção."
                send_whatsapp_message(cliente_id, message)
                logger.info(f"Lembrete enviado para {cliente_id} (Nome: {nome})")

            time.sleep(1200) 
        except Exception as e:
            logger.error(f"Erro crítico no worker de lembretes: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()