from django.core.management.base import BaseCommand
#from core.models import Agendamento
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from django.core.management.base import BaseCommand
from django.utils import timezone

from agendaflow.core.cron_lembretes import enviar_lembretes_automaticos
from agendaflow.core.services.reminder_service import ReminderService


#from core.services.reminder_service import ReminderService


class Command(BaseCommand):
    help = 'Envia lembretes automáticos para pacientes'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando envio de lembretes...'))

        try:
            ReminderService.processar_lembretes_do_dia()
            self.stdout.write(
                self.style.SUCCESS('Lembretes processados com sucesso!')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Erro ao processar lembretes: {str(e)}')
            )


from django.core.management.base import BaseCommand
from datetime import date
#from core.views import enviar_lembretes_automaticos  # ajuste o import

class Command(BaseCommand):
    help = 'Envia lembretes de consulta automaticamente'

    def handle(self, *args, **options):
        total = enviar_lembretes_automaticos()
        self.stdout.write(
            self.style.SUCCESS(f'✅ {total} lembretes enviados com sucesso!')
        )

# Para executar: python manage.py enviar_lembretes
























#EMAIL_HOST = 'smtp.gmail.com'
#EMAIL_PORT = 587
#EMAIL_HOST_USER = 'businessgbraga@gmail.com'
#EMAIL_HOST_PASSWORD = 'gssmquujbduzehtk'
#FROM_EMAIL = EMAIL_HOST_USER

#def enviar_email(destinatario, assunto, mensagem):
 #   msg = MIMEMultipart()
 #   msg['From'] = FROM_EMAIL
  #  msg['To'] = destinatario
  #  msg['Subject'] = assunto

   # msg.attach(MIMEText(mensagem, 'html'))

   # with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as servidor:
     #   servidor.starttls()
     #   servidor.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
   #     servidor.send_message(msg)

#class Command(BaseCommand):
 #   help = 'Envia lembretes de agendamento por e-mail para os clientes com agendamento amanhã'

 #   def handle(self, *args, **kwargs):
  #      data_alvo = datetime.now().date() + timedelta(days=1)
   #     agendamentos = Agendamento.objects.filter(data=data_alvo)

    #    enviados = 0
     #   for ag in agendamentos:
      #      if ag.cliente and ag.cliente.email:
       #         nome = ag.cliente.nome
        #        profissional = ag.profissional.nome
         #       horario = ag.hora.strftime("%H:%M")
          #      servico = ag.servico.nome
           #     data_formatada = ag.data.strftime("%d/%m/%Y")

            #    mensagem = f"""
             #   <p>Olá, <strong>{nome}</strong>! 🌟</p>
              #  <p>Estamos te lembrando que você tem um agendamento para <strong>{servico}</strong> amanhã:</p>
               # <ul>
                #    <li><strong>Data:</strong> {data_formatada}</li>
                 #   <li><strong>Hora:</strong> {horario}</li>
                  #  <li><strong>Profissional:</strong> {profissional}</li>
              #  </ul>
               # <p>Se precisar reagendar, é só entrar em contato.</p>
              #  <p>Te esperamos! 💆‍♀️💅</p>
               # """
              #  try:
                #    enviar_email(ag.cliente.email, "📅 Lembrete: Seu agendamento é amanhã!", mensagem)
               #     enviados += 1
                 #   self.stdout.write(f"E-mail enviado para {nome}")
              #  except Exception as e:
              #    self.stderr.write(f"Erro ao enviar para {nome}: {e}")
   #     self.stout.write(self.style.SUCCESS(f"Total de lembretes enviados: {enviados}"))
