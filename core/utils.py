from django.core.mail import send_mail
from googleapiclient.discovery import build
from google.oauth2 import service_account
from datetime import datetime, timedelta
#SERVICE_ACCOUNT_FILE = 'caminho/certo/credenciais_google.json'
#from __future__ import absolute_import
#import os
#from celery import Celery

#os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
#app = Celery('core')
#app.config_from_object('django.conf:settings', namespace='CELERY')
#app.autodiscover_tasks()

###########################
# ENVIO DE EMAIL ✅
###########################

def enviar_email_lembrete(agendamento):
    assunto = f'Lembrete de consulta com {agendamento.profissional.nome}'
    mensagem = f'''
Olá {agendamento.cliente.nome},

Este é um lembrete da sua consulta de {agendamento.servico.nome} marcada para hoje às {agendamento.hora.strftime("%H:%M")}.

Nos vemos em breve!
'''

    if agendamento.cliente.email:
        send_mail(
            assunto,
            mensagem,
            'sistema@agendamestre.com',
            [agendamento.cliente.email]
        )


###########################
# ENVIO DE WHATSAPP/SMS ✉️
###########################

def enviar_whatsapp(numero, mensagem):
    # Integração com API de WhatsApp, tipo Z-API, Twilio etc.
    print(f"WhatsApp para {numero}: {mensagem}")  # debug


def enviar_sms(numero, mensagem):
    # Integração com serviço SMS (Twilio, TotalVoice etc.)
    print(f"SMS para {numero}: {mensagem}")  # debug


###########################
# GOOGLE CALENDAR 🗓️
###########################

#SCOPES = ['https://www.googleapis.com/auth/calendar']
#SERVICE_ACCOUNT_FILE = 'credenciais_google.json'  # caminho do seu JSON

# Carrega credenciais do serviço
#credentials = service_account.Credentials.from_service_account_file(
   # SERVICE_ACCOUNT_FILE, scopes=SCOPES
#)
#calendar_service = build('calendar', 'v3', credentials=credentials)


def adicionar_evento_google(agendamento):
    evento = {
        'summary': f'{agendamento.servico.nome} - {agendamento.cliente.nome}',
        'start': {
            'dateTime': agendamento.data_hora_inicio().isoformat(),
            'timeZone': 'America/Sao_Paulo'
        },
        'end': {
            'dateTime': agendamento.data_hora_fim().isoformat(),
            'timeZone': 'America/Sao_Paulo'
        },
        'description': f"Profissional: {agendamento.profissional.nome}\nValor: R${agendamento.valor}",
    }

   # evento_criado = calendar_service.events().insert(calendarId='primary', body=evento).execute()
  #  return evento_criado.get('id')

import openai
from django.conf import settings

def gerar_sugestao_ia(situacao=None):
    openai.api_key = settings.OPENAI_API_KEY
    prompt = f"""
        Você é um assistente de saúde. Analise a seguinte situação do paciente e sugira uma hipótese clínica preliminar (somente sugestão, não é diagnóstico):

        Situação: {situacao}

        Resposta:
        """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"Erro ao gerar sugestão: {str(e)}"


# validar CNPJ

def validar_cnpj(cnpj):
    """
    Valida CNPJ usando o algoritmo oficial
    Args:
        cnpj (str): CNPJ com ou sem formatação
    Returns:
        bool: True se válido, False se inválido
    """
    if not cnpj:
        return False

    # Remove caracteres não numéricos
    cnpj = ''.join(filter(str.isdigit, cnpj))

    # Verifica se tem 14 dígitos
    if len(cnpj) != 14:
        return False

    # Verifica se não são todos os dígitos iguais
    if cnpj == cnpj[0] * 14:
        return False

    # Algoritmo de validação do CNPJ
    def calcular_digito(cnpj_base, pesos):
        soma = sum(int(digit) * peso for digit, peso in zip(cnpj_base, pesos))
        resto = soma % 11
        return 0 if resto < 2 else 11 - resto

    # Primeiro dígito verificador
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    digito1 = calcular_digito(cnpj[:12], pesos1)

    # Segundo dígito verificador
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    digito2 = calcular_digito(cnpj[:13], pesos2)

    # Verifica se os dígitos calculados conferem
    return cnpj[-2:] == f"{digito1}{digito2}"


def formatar_cnpj(cnpj):
    """
    Formata CNPJ para o padrão XX.XXX.XXX/XXXX-XX
    """
    if not cnpj:
        return ""

    cnpj = ''.join(filter(str.isdigit, cnpj))
    if len(cnpj) == 14:
        return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    return cnpj


def validar_cpf(cpf):
    """
    Valida CPF usando o algoritmo oficial
    """
    if not cpf:
        return False

    cpf = ''.join(filter(str.isdigit, cpf))

    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    # Primeiro dígito
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto

    # Segundo dígito
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto

    return cpf[-2:] == f"{digito1}{digito2}"


import uuid
import time
from datetime import datetime
import random
import string


def gerar_reference_id():
    """
    Gera um reference_id único para transações do PagSeguro
    Formato: AGENDAFLOW_TIMESTAMP_RANDOM
    """
    # Timestamp atual
    timestamp = int(time.time())

    # Gerar string aleatória de 6 caracteres
    random_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    # Combinar para formar o reference_id
    reference_id = f"AGENDAFLOW_{timestamp}_{random_string}"

    return reference_id


def gerar_reference_id_simples():
    """
    Versão mais simples usando apenas contador sequencial
    Formato: AGENDAFLOW_GEN_NUMERO
    """
    from django.core.cache import cache

    # Usar cache para manter contador
    counter = cache.get('reference_counter', 1)
    cache.set('reference_counter', counter + 1, timeout=None)

    return f"AGENDAFLOW_GEN_{counter}"


def gerar_reference_id_uuid():
    """
    Versão usando UUID (mais única, mas mais longa)
    Formato: AGENDAFLOW_UUID_CURTO
    """
    # Gerar UUID e pegar apenas os primeiros 8 caracteres
    short_uuid = str(uuid.uuid4()).replace('-', '')[:8].upper()

    return f"AGENDAFLOW_{short_uuid}"


def gerar_reference_id_data():
    """
    Versão usando data e hora atual
    Formato: AGENDAFLOW_YYYYMMDD_HHMMSS_RND
    """
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    time_str = now.strftime("%H%M%S")
    random_num = random.randint(100, 999)

    return f"AGENDAFLOW_{date_str}_{time_str}_{random_num}"


# Função principal que será usada (você pode escolher qual implementação usar)
def gerar_reference_id():
    """
    Função principal para gerar reference_id
    Usa a implementação com timestamp por ser mais confiável
    """
    return gerar_reference_id_simples()  # Mudei para a versão mais simples



# utils.py - Funções auxiliares para verificação de limites
from django.shortcuts import redirect
from django.contrib import messages
from .models import Estabelecimento

def verificar_limites_estabelecimento(request):
    """
    Função auxiliar para verificar se o estabelecimento existe e está configurado
    """
    try:
        estabelecimento = request.user.estabelecimento
        return estabelecimento
    except Estabelecimento.DoesNotExist:
        messages.error(request, "Você precisa cadastrar um estabelecimento primeiro.")
        return None

def verificar_limite_funcionalidade(estabelecimento, funcionalidade):
    """
    Verifica se o estabelecimento tem acesso a uma funcionalidade específica
    """
    funcionalidades_map = {
        'integracao_pagseguro': estabelecimento.plano.tem_integracao_pagseguro,
        'controle_estoque': estabelecimento.plano.tem_controle_estoque,
        'insights_ia': estabelecimento.plano.tem_insights_ia,
        'lembrete_automatico': estabelecimento.plano.tem_lembrete_automatico,
        'suporte_whatsapp': estabelecimento.plano.suporte_whatsapp,
    }
    return funcionalidades_map.get(funcionalidade, False)



from django.http import HttpResponseForbidden
from .models import Assinatura



def verificar_limites(request):
    if not request.user.is_authenticated:
        return HttpResponseForbidden("Usuário não autenticado.")

    try:
        assinatura = Assinatura.objects.filter(estabelecimento__usuario=request.user, status='ativo').latest(
            'data_inicio')
        if not assinatura.esta_ativa():
            return HttpResponseForbidden("Assinatura expirada. Renove seu plano.")

        plano = assinatura.plano
        # Verificação do limite de profissionais
        if hasattr(request, 'profissionais_count') and request.profissionais_count > plano.max_profissionais:
            return HttpResponseForbidden(
                f"Limite de {plano.max_profissionais} profissionais excedido. Atualize seu plano.")

        request.plano_ativo = plano
    except Assinatura.DoesNotExist:
        return HttpResponseForbidden("Nenhuma assinatura ativa encontrada.")

    return None