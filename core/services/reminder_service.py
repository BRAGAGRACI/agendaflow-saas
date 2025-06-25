from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from ..models import HistoricoLembrete


class ReminderService:

    @staticmethod
    def enviar_lembrete_email(agendamento, configuracao):
        """Envia lembrete por email"""
        try:
            # Verificar se tem email
            if not hasattr(agendamento.cliente, 'email') or not agendamento.cliente.email:
                return False, "Cliente não possui email cadastrado"

            # Template
            if not configuracao.template_email:
                mensagem = f"Olá {agendamento.cliente.nome}! Lembrete: você tem consulta marcada para {agendamento.data.strftime('%d/%m/%Y')} às {agendamento.hora.strftime('%H:%M')} na {agendamento.estabelecimento.nome}."
            else:
                mensagem = configuracao.template_email.format(
                    nome_paciente=agendamento.cliente.nome,
                    data_consulta=agendamento.data.strftime('%d/%m/%Y'),
                    hora_consulta=agendamento.hora.strftime('%H:%M'),
                    nome_clinica=agendamento.estabelecimento.nome
                )

            # Enviar email
            send_mail(
                subject=f'Lembrete de Consulta - {agendamento.estabelecimento.nome}',
                message=mensagem,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[agendamento.cliente.email],
                fail_silently=False,
            )

            # CORREÇÃO: Registrar sucesso com estabelecimento direto
            HistoricoLembrete.objects.create(
                estabelecimento=agendamento.estabelecimento,  # Campo direto
                tipo='email',
                status='enviado',
                mensagem_enviada=mensagem
            )

            return True, f"Email enviado com sucesso para {agendamento.cliente.email}"

        except Exception as e:
            # CORREÇÃO: Registrar erro com estabelecimento direto
            try:
                HistoricoLembrete.objects.create(
                    estabelecimento=agendamento.estabelecimento,  # Campo direto
                    tipo='email',
                    status='erro',
                    mensagem_enviada=mensagem if 'mensagem' in locals() else '',
                    erro_detalhes=str(e)
                )
            except Exception as save_error:
                print(f"Erro ao salvar histórico: {save_error}")

            return False, f"Erro ao enviar email: {str(e)}"

    @staticmethod
    def enviar_lembrete_whatsapp_web(agendamento, configuracao):
        """SIMULAÇÃO de WhatsApp para teste"""
        try:
            # Verificar se tem telefone
            if not hasattr(agendamento.cliente, 'telefone') or not agendamento.cliente.telefone:
                return False, "Cliente não possui telefone cadastrado"

            # Template
            if not configuracao.template_whatsapp:
                mensagem = f"Olá {agendamento.cliente.nome}! Lembrete: consulta em {agendamento.data.strftime('%d/%m/%Y')} às {agendamento.hora.strftime('%H:%M')}."
            else:
                mensagem = configuracao.template_whatsapp.format(
                    nome_paciente=agendamento.cliente.nome,
                    data_consulta=agendamento.data.strftime('%d/%m/%Y'),
                    hora_consulta=agendamento.hora.strftime('%H:%M'),
                    nome_clinica=agendamento.estabelecimento.nome
                )

            # CORREÇÃO: SIMULAÇÃO - registrar como enviado com estabelecimento direto
            HistoricoLembrete.objects.create(
                estabelecimento=agendamento.estabelecimento,  # Campo direto
                tipo='whatsapp',
                status='enviado',
                mensagem_enviada=mensagem
            )

            return True, f"WhatsApp SIMULADO para {agendamento.cliente.telefone} - Mensagem: {mensagem[:50]}..."

        except Exception as e:
            # CORREÇÃO: Registrar erro com estabelecimento direto
            try:
                HistoricoLembrete.objects.create(
                    estabelecimento=agendamento.estabelecimento,  # Campo direto
                    tipo='whatsapp',
                    status='erro',
                    mensagem_enviada=mensagem if 'mensagem' in locals() else '',
                    erro_detalhes=str(e)
                )
            except Exception as save_error:
                print(f"Erro ao salvar histórico: {save_error}")

            return False, f"Erro: {str(e)}"

    @staticmethod
    def processar_lembretes_do_dia():
        """Processa todos os lembretes que devem ser enviados hoje"""
        hoje = timezone.now().date()

        # Buscar todas as configurações ativas
        configuracoes = ConfiguracaoLembrete.objects.filter(ativo=True)

        for config in configuracoes:
            # Calcular data dos agendamentos que devem receber lembrete
            data_agendamento = hoje + timedelta(days=config.dias_antecedencia)

            # CORREÇÃO: Buscar agendamentos com campos corretos
            agendamentos = Agendamento.objects.filter(
                estabelecimento=config.estabelecimento,  # Campo correto
                data=data_agendamento,  # Campo correto: 'data'
                # status='agendado'  # Adicione se tiver campo de status
            )

            for agendamento in agendamentos:
                # Verificar se já foi enviado lembrete hoje
                ja_enviado = HistoricoLembrete.objects.filter(
                    estabelecimento=agendamento.estabelecimento,  # Campo correto
                    data_envio__date=hoje,
                    status='enviado'
                ).exists()

                if not ja_enviado:
                    # Tentar enviar por email primeiro
                    if hasattr(agendamento.cliente, 'email') and agendamento.cliente.email:
                        ReminderService.enviar_lembrete_email(agendamento, config)

                    # Tentar enviar por WhatsApp se tiver telefone
                    if hasattr(agendamento.cliente, 'telefone') and agendamento.cliente.telefone:
                        ReminderService.enviar_lembrete_whatsapp_web(agendamento, config)