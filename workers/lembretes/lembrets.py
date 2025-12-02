import os
import sys
import logging
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot.settings')
django.setup()


import time
from datetime import datetime, timedelta, timezone
from workers.lembretes.redis_lembrets import lembrete_ja_enviado
from chatbot_api.services.metrics import registrar_evento

from google.oauth2. service_account import Credentials
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
    credentials = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_PATH,
        scopes=['https://www.googleapis.com/auth/calendar']
    )
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
        timeMin=start_check.isoformat(),
        timeMax=end_check.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    return events_result.get('items', [])

def send_whatsapp_message(phone_number, message):
    """
    Envia mensagem WhatsApp via WAHA.
    """
    try:
        waha = Waha()
        waha.send_whatsapp_message(phone_number, message)
    except Exception as e:
        logger.error(f"❌ Erro ao enviar mensagem WhatsApp: {e}")
        raise

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
    return None

def main():
    logger.info("🚀 Reminder worker iniciado")
    service = get_google_service()
    
    while True:
        try:
            events = buscar_eventos(service)
            
            for event in events:
                event_id = event.get("id")
                payload = event.get("summary")
                start = event["start"]. get("dateTime", "")
                
                phone_and_name = extract_phone_and_name(payload)

                # Validação de dados essenciais
                if not phone_and_name or not event_id or not start:
                    log_msg = f"Evento {event_id} pulado. "
                    if not event_id:
                        log_msg += "Motivo: ID ausente. "
                    if not start:
                        log_msg += "Motivo: Data/Hora ausente. "
                    if not phone_and_name:
                        log_msg += f"Motivo: Resumo fora do padrão.  Resumo: {payload}"
                    logger.warning(log_msg)
                    continue

                nome = phone_and_name["nome"]
                cliente_id = phone_and_name["cliente_id"]

                if lembrete_ja_enviado(event_id, TTL_TWO_HOURS):
                    logger.info(f"ℹ️ Lembrete já enviado para evento: {event_id}")
                    continue

                try:
                    dt_obj = datetime.fromisoformat(start)
                    hora_formatada = dt_obj.strftime("%H:%M")
                except ValueError:
                    logger.error(f"❌ Erro de formato de data no evento {event_id}: {start}")
                    hora_formatada = "em breve"

                message = f"Olá {nome}, sua consulta será às {hora_formatada}. Este é um lembrete automático portanto não precisa responder, esperamos por voce!"
                
                try:
                    send_whatsapp_message(cliente_id, message)

                    result = registrar_evento(
                        cliente_id=cliente_id,
                        event_id=event_id,
                        tipo_metrica='lembrete',
                        status='success',
                        detalhes=f"Lembrete para {nome} às {hora_formatada}"
                    )
                    
                    if result['status'] == 'success':
                        logger.info(f"✅ Lembrete enviado e registrado | Cliente: {cliente_id}")
                    else:
                        logger.error(f"❌ Erro ao registrar métrica: {result. get('error')}")
                    
                except Exception as e:
                    # ❌ REGISTRAR FALHA (PostgreSQL)
                    result = registrar_evento(
                        cliente_id=cliente_id,
                        event_id=event_id,
                        tipo_metrica='lembrete',
                        status='failed',
                        detalhes=f"Erro ao enviar: {str(e)}"
                    )
                    
                    logger.error(f"❌ Erro ao enviar lembrete para {cliente_id}: {e}")

            time.sleep(1200)  # 20 minutos
            
        except Exception as e:
            logger.error(f"❌ Erro crítico no worker: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()