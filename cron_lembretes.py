import os
import sys
import django
from datetime import datetime

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agendaflow.settings')
django.setup()

from django.core.management import call_command

if __name__ == '__main__':
    print(f"[{datetime.now()}] Executando envio de lembretes...")
    call_command('enviar_lembretes')
    print(f"[{datetime.now()}] Envio concluído!")