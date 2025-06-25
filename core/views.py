import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from django.contrib.auth.decorators import  user_passes_test
from django.template.loader import get_template, render_to_string
from django.contrib.auth import authenticate, login, logout
import csv
from . import forms
from .forms import ClienteForm, ProfissionalForm, ServicoForm, AgendamentoForm, ProntuarioForm, CadastroEstabelecimentoForm
from django.core.mail import send_mail
from .models import Prontuario, ConfiguracaoEmail
from django.http import  HttpRequest, HttpResponseRedirect
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from django.urls import reverse
from django.db.models import Sum, Count, F
from django.templatetags.static import static
from pagseguro.api import PagSeguroApi, PagSeguroItem
from .models import  Profissional, Servico, AgendamentoProduto
from .forms import AgendamentoForm
from pagseguro.api import PagSeguroApi
from .models import Cliente, Produto, Venda, MovimentacaoEstoque, VendaProduto, PagBankTransaction
from .forms import ProdutoForm
from django.db.models import Sum, F, DecimalField, FloatField
from django.db.models.functions import Coalesce, Cast
from .models import Agendamento, Produto, Venda
from django.db.models import Q
from django.utils.dateparse import parse_date
from django.template.loader import render_to_string
from .models import Cliente  # Adicione esta importação
from .models import PagamentoTransacao
from .models import Venda
from django.dispatch import receiver
from .models import PagBankTransaction
from .models import Assinatura
from .utils import verificar_limites
from django.http import  HttpResponseForbidden
from .utils import gerar_sugestao_ia, validar_cpf, gerar_reference_id
from .models import Estabelecimento, Profissional, Plano
from .forms import ProfissionalForm
from .decorators import plano_required, pode_adicionar_profissional, tem_controle_estoque, tem_insights_ia
from .utils import verificar_limites_estabelecimento
import json
import requests
import re
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction
from django.conf import settings
import io
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from calendar import monthrange
from django.shortcuts import render
import time as time_module
from datetime import time
from datetime import timedelta
from .models import HistoricoLembrete
from openpyxl import Workbook
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from reportlab.lib.pagesizes import A4
import logging
import os
from datetime import datetime
import openai
from django.core.exceptions import PermissionDenied
openai.api_key = settings.OPENAI_API_KEY

logger = logging.getLogger(__name__)


# 🔹 Painel administrador (superuser ou dono de estabelecimento)
# Configurar logger

def check_admin_or_estabelecimento(user):
    return user.is_superuser or hasattr(user, 'estabelecimento')


@user_passes_test(check_admin_or_estabelecimento, login_url='login')
def painel_administrador(request):
    context = {}

    # Obter estabelecimentos
    estabelecimentos = Estabelecimento.objects.all()
    total = estabelecimentos.count()
    ativos = estabelecimentos.filter(ativo=True).count()
    inativos = estabelecimentos.filter(ativo=False).count()

    context.update({
        "estabelecimentos": estabelecimentos,
        "total": total,
        "ativos": ativos,
        "inativos": inativos,
    })

    # Processar filtros de data
    inicio = request.GET.get("inicio")
    fim = request.GET.get("fim")
    hoje = timezone.now().date()

    assinaturas_filtradas = Assinatura.objects.all()
    if inicio and fim:
        try:
            inicio_data = datetime.strptime(inicio, "%Y-%m-%d").date()
            fim_data = datetime.strptime(fim, "%Y-%m-%d").date()
            if inicio_data > fim_data:
                messages.error(request, "A data de início não pode ser posterior à data de fim.")
                return HttpResponseRedirect(request.path)
            if fim_data > hoje:
                messages.warning(request, "A data de fim foi ajustada para hoje, pois não pode ser futura.")
                fim_data = hoje
            assinaturas_filtradas = Assinatura.objects.filter(
                data_pagamento__range=(inicio_data, fim_data)
            ).select_related('estabelecimento', 'plano')
        except ValueError:
            messages.error(request, "Formato de data inválido. Use o formato AAAA-MM-DD.")
            inicio = None
            fim = None

    # Calcular faturamento total
    total_faturamento = assinaturas_filtradas.aggregate(total=Sum("valor_pago"))["total"] or 0
    if total_faturamento == 0:
        total_faturamento = sum(ass.plano.valor or 0 for ass in assinaturas_filtradas if ass.plano) or 0

    context.update({
        "total_faturamento": total_faturamento,
        "data_inicio": inicio,
        "data_fim": fim,
        "assinaturas_ativas": Assinatura.objects.filter(data_validade__gte=hoje).count(),
        "assinaturas_vencidas": Assinatura.objects.filter(data_validade__lt=hoje).count(),
    })

    # Informações dos planos COM FATURAMENTO MENSAL
    planos = Plano.objects.all()
    planos_info = []

    for plano in planos:
        qtd_assinaturas = Assinatura.objects.filter(plano=plano).count()
        # Calcular faturamento mensal
        faturamento_mensal = Assinatura.objects.filter(
            plano=plano,
            estabelecimento__ativo=True  # Só contar clínicas ativas
        ).aggregate(total=Sum('valor_pago'))['total'] or 0

        planos_info.append({
            "id": plano.id,
            "nome": plano.nome,
            "valor": plano.valor,
            "qtd": qtd_assinaturas,
            "faturamento_mensal": faturamento_mensal,  # ← CAMPO ADICIONADO
        })

    context["planos"] = planos_info
    context["planos_pagamentos"] = assinaturas_filtradas

    # Agendamentos por clínica
    agendamentos_por_clinica = Agendamento.objects.values(
        "estabelecimento__nome"
    ).annotate(total=Count("id")).order_by("-total")
    context["agendamentos_por_clinica"] = agendamentos_por_clinica

    return render(request, "painel_administrador.html", context)
@csrf_exempt
@user_passes_test(check_admin_or_estabelecimento, login_url='login')
def criar_plano(request):
    if request.method == 'POST':
        nome = request.POST.get('nome')
        valor = request.POST.get('valor')
        max_profissionais = request.POST.get('max_profissionais')

        try:
            plano = Plano.objects.create(
                nome=nome,
                valor=Decimal(valor),
                max_profissionais=int(max_profissionais)
            )
            messages.success(request, f'Plano {plano.nome} criado com sucesso!')
        except Exception as e:
            messages.error(request, f'Erro ao criar plano: {str(e)}')

    return redirect('painel_administrador')

@csrf_exempt
@user_passes_test(check_admin_or_estabelecimento, login_url='login')
def editar_plano_valor(request):
    if request.method == 'POST':
        plano_id = request.POST.get('plano_id')
        valor = request.POST.get('valor')

        try:
            plano = Plano.objects.get(id=plano_id)
            plano.valor = Decimal(valor)
            plano.save()
            messages.success(request, f'Valor do plano {plano.nome} atualizado com sucesso!')
        except Exception as e:
            messages.error(request, f'Erro ao atualizar plano: {str(e)}')

    return redirect('painel_administrador')

@csrf_exempt
@user_passes_test(check_admin_or_estabelecimento, login_url='login')
def editar_assinatura_valor(request):
    if request.method == 'POST':
        assinatura_id = request.POST.get('assinatura_id')
        valor_pago = request.POST.get('valor_pago')

        try:
            assinatura = Assinatura.objects.get(id=assinatura_id)
            assinatura.valor_pago = Decimal(valor_pago)
            assinatura.save()
            messages.success(request, f'Valor da assinatura de {assinatura.estabelecimento.nome} atualizado!')
        except Exception as e:
            messages.error(request, f'Erro ao atualizar assinatura: {str(e)}')

    return redirect('painel_administrador')

@csrf_exempt
@user_passes_test(check_admin_or_estabelecimento, login_url='login')
def toggle_status_estabelecimento(request):
    if request.method == 'POST':
        estabelecimento_id = request.POST.get('estabelecimento_id')
        novo_status = request.POST.get('novo_status') == 'true'

        try:
            estabelecimento = Estabelecimento.objects.get(id=estabelecimento_id)
            estabelecimento.ativo = novo_status
            estabelecimento.save()

            status_text = "ativado" if novo_status else "suspenso"
            messages.success(request, f'Estabelecimento {estabelecimento.nome} foi {status_text}!')
        except Exception as e:
            messages.error(request, f'Erro ao alterar status: {str(e)}')

    return redirect('painel_administrador')

@login_required
def upgrade_plano(request, plano_nome):
    """View para fazer upgrade do plano"""
    estabelecimento = verificar_limites_estabelecimento(request)
    if not estabelecimento:
        return redirect('cadastro_estabelecimento')

    try:
        novo_plano = Plano.objects.get(nome=plano_nome, ativo=True)
    except Plano.DoesNotExist:
        messages.error(request, "Plano não encontrado.")
        return redirect('planos')

    if request.method == 'POST':
        # Aqui você implementaria a lógica de pagamento
        # Por agora, vamos apenas atualizar o plano
        estabelecimento.plano = novo_plano
        estabelecimento.save()

        messages.success(
            request,
            f"Parabéns! Seu plano foi atualizado para {novo_plano.get_nome_display()} com sucesso!"
        )
        return redirect('dashboard')

    context = {
        'estabelecimento': estabelecimento,
        'plano_atual': estabelecimento.plano,
        'novo_plano': novo_plano,
    }

    return render(request, 'upgrade_plano.html', context)


@login_required
def redirecionar_pos_login(request):
    if request.user.is_superuser:
        return redirect('painel_administrador')
    else:
        return redirect('dashboard')  # ou onde os usuários normais devem ir


# Exportar pra Excel
@user_passes_test(lambda u: u.is_superuser)
def exportar_estabelecimentos_excel(request):
    estabelecimentos = Estabelecimento.objects.all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Estabelecimentos"

    # Cabeçalhos
    ws.append(['Nome', 'Email', 'Telefone', 'Status'])

    # Dados
    for est in estabelecimentos:
        ws.append([
            est.nome,
            est.email,
            est.telefone,
            "Ativo" if est.ativo else "Inativo"
        ])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=estabelecimentos.xlsx'
    wb.save(response)
    return response

# HOME E DASHBOARD

def apresentacao(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    # Clientes fictícios para o carrossel
    clientes_ficticios = [
        {
            'nome': 'Clínica BellaVida',
            'descricao': 'Especializada em estética avançada, a BellaVida aumentou seus agendamentos em 40% com o AgendaFlow.',
            'imagem': static('images/consultorio1.jpg'),
            'link': '#'
        },
        {
            'nome': 'Salão Estilo & Charme',
            'descricao': 'Transformando looks com agendamentos rápidos e eficientes, graças ao AgendaFlow.',
            'imagem': static('images/consultorio2.jpg'),
            'link': '#'
        },
        {
            'nome': 'Consultório Dr. Saúde',
            'descricao': 'Clínica médica que reduziu no-shows em 50% com nossos lembretes automáticos.',
            'imagem': static('images/consultorio3.jpg'),
            'link': '#'
        }
    ]

    context = {
        'clientes': clientes_ficticios,
        'plano_selecionado': request.GET.get('plano', '').lower()
    }
    return render(request, 'apresentacao.html', context)


def home(request):
    return render(request, 'home.html')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        senha = request.POST.get('password')
        user = authenticate(request, username=username, password=senha)

        if user:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Usuário ou senha inválidos.')

    return render(request, 'login.html')


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')



@login_required(login_url='login')
def dashboard(request):
    """Dashboard principal com informações do plano"""
    estabelecimento = verificar_limites_estabelecimento(request)
    if not estabelecimento:
        return redirect('cadastro_estabelecimento')

    # DEBUG: Vamos ver o que está acontecendo
    print(f"Estabelecimento: {estabelecimento}")
    print(f"Tipo do estabelecimento.plano: {type(estabelecimento.plano)}")
    print(f"Valor do estabelecimento.plano: {estabelecimento.plano}")

    # Estatísticas do estabelecimento
    total_profissionais = estabelecimento.profissional_set.filter(ativo=True).count()

    # Vamos tratar o erro temporariamente
    try:
        limite_profissionais = estabelecimento.plano.max_profissionais
        plano_atual = estabelecimento.plano
    except AttributeError as e:
        print(f"Erro ao acessar plano: {e}")
        # Buscar o plano corretamente se necessário
        from .models import Plano
        try:
            plano_atual = Plano.objects.get(nome=estabelecimento.plano)
            limite_profissionais = plano_atual.max_profissionais
        except:
            # Plano padrão se não encontrar
            plano_atual = None
            limite_profissionais = 2

    profissionais_restantes = max(0, limite_profissionais - total_profissionais)

    # Verificar se está próximo do limite
    proximo_limite = (total_profissionais / limite_profissionais) >= 0.8 if limite_profissionais > 0 else False

    context = {
        'estabelecimento': estabelecimento,
        'plano_atual': plano_atual,
        'total_profissionais': total_profissionais,
        'limite_profissionais': limite_profissionais,
        'profissionais_restantes': profissionais_restantes,
        'proximo_limite': proximo_limite,
    }

    return render(request, 'dashboard.html', context)


def login_redirect(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')


# 🔹 Redirecionamento pós-login
@login_required
def redirecionar_pos_login(request):
    if request.user.is_superuser:
        return redirect('painel_administrador')
    else:
        return redirect('dashboard')


def police(request):
   return render(request, 'police.html')


# 🔹 Cadastro de Estabelecimento
def cadastro_estabelecimento(request):
    planos = Plano.objects.all()

    if request.method == 'POST':
        form = CadastroEstabelecimentoForm(request.POST)
        if form.is_valid():
            estabelecimento = form.save()
            # Login automático
            login(request, estabelecimento.usuario)  # ou login(request, usuario) dependendo do seu form

            plano_id = request.POST.get('plano')
            if plano_id:
                plano = Plano.objects.get(id=plano_id)
                Assinatura.objects.create(
                    estabelecimento=estabelecimento,
                    plano=plano,
                    data_inicio=timezone.now(),
                    data_validade=timezone.now() + timedelta(days=7), # Período de teste de 7 dias
                    status='ativo',
                    tipo='teste',
                    valor_pago="0.00"
                )

            messages.success(request, "Cadastro realizado com sucesso!")
            return redirect('dashboard')
        else:
            for erro in form.errors.values():
                messages.error(request, erro)
    else:
        form = CadastroEstabelecimentoForm()

    return render(request, 'cadastro_estabelecimento.html', {'form': form, 'planos': planos})
    # após salvar o estabelecimento e criar o usuário:
    login(request, estabelecimento.usuario)
    return redirect('dashboard')


@login_required
def configurar_estabelecimento(request):
    try:
        estabelecimento = request.user.estabelecimento
        return redirect('cadastro_profissional')  # Já tem estabelecimento
    except Estabelecimento.DoesNotExist:
        if request.method == 'POST':
            form = CadastroEstabelecimentoForm(request.POST)
            if form.is_valid():
                estabelecimento = form.save(commit=False)
                estabelecimento.usuario = request.user
                estabelecimento.save()
                messages.success(request, 'Estabelecimento configurado com sucesso!')
                return redirect('cadastro_profissional')
        else:
            form = CadastroEstabelecimentoForm()
        return render(request, 'configurar_estabelecimento.html', {'form': form})

def clean(self):
        cleaned_data = super().clean()
        cpf = cleaned_data.get('cpf')
        cnpj = cleaned_data.get('cnpj')
        if not cpf and not cnpj:
            raise forms.ValidationError('É necessário informar pelo menos um CPF ou CNPJ.')
        return cleaned_data

@login_required
def verificar_estabelecimento(request):
    """Verifica se o usuário tem um estabelecimento cadastrado"""
    try:
        return request.user.estabelecimento
    except Estabelecimento.DoesNotExist:
        messages.error(request, "Você precisa cadastrar um estabelecimento primeiro.")
        return None


# Função auxiliar para pegar o IP
def get_client_ip(request: HttpRequest):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
def validar_forca_senha(senha):
    erros = []
    if len(senha) < 8:
        erros.append("A senha deve ter pelo menos 8 caracteres.")
    if not re.search(r"[A-Z]", senha):
        erros.append("A senha deve conter pelo menos uma letra maiúscula.")
    if not re.search(r"\d", senha):
        erros.append("A senha deve conter pelo menos um número.")
    if not re.search(r"[\W_]", senha):
        erros.append("A senha deve conter pelo menos um caractere especial.")
    return erros

@login_required
def dashboard_financeiro(request):
    try:
        estabelecimento = request.user.estabelecimento
    except AttributeError:
        return render(request, 'dashboard_financeiro.html', {'error': 'Usuário não vinculado a um estabelecimento.'})

    # Filtros de data
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    if data_inicio and data_fim:
        try:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').replace(tzinfo=timezone.get_current_timezone())
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d').replace(
                tzinfo=timezone.get_current_timezone()) + timedelta(days=1)
        except ValueError:
            data_inicio = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            data_fim = data_inicio + timedelta(days=1)
    else:
        data_inicio = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        data_fim = data_inicio + timedelta(days=1)

    # Faturamento do dia (agendamentos + vendas)
    faturamento_dia_agendamentos = Agendamento.objects.filter(
        estabelecimento=estabelecimento,
        data__gte=timezone.now().replace(hour=0, minute=0, second=0, microsecond=0),
        data__lt=timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    ).aggregate(total=Coalesce(Sum('valor'), Decimal('0.00'), output_field=DecimalField()))['total']

    faturamento_dia_vendas = Venda.objects.filter(
        estabelecimento=estabelecimento,
        criado_em__gte=timezone.now().replace(hour=0, minute=0, second=0, microsecond=0),
        criado_em__lt=timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    ).aggregate(total=Coalesce(Sum('valor_total'), Decimal('0.00'), output_field=DecimalField()))['total']

    faturamento_dia = faturamento_dia_agendamentos + faturamento_dia_vendas

    # Faturamento do período (serviços + vendas)
    faturamento_servicos = Agendamento.objects.filter(
        estabelecimento=estabelecimento,
        data__gte=data_inicio,
        data__lt=data_fim
    ).aggregate(total=Coalesce(Sum('valor'), Decimal('0.00'), output_field=DecimalField()))['total']

    faturamento_vendas = Venda.objects.filter(
        estabelecimento=estabelecimento,
        criado_em__gte=data_inicio,
        criado_em__lt=data_fim
    ).aggregate(total=Coalesce(Sum('valor_total'), Decimal('0.00'), output_field=DecimalField()))['total']

    faturamento_periodo = faturamento_servicos + faturamento_vendas

    # Faturamento vendas de produtos
    faturamento_vendas_produtos = faturamento_vendas

    # Custos com produtos
    # NOTA: Usando preco_unitario como proxy para custo, pois preco_custo não existe no modelo Produto.
    custos_produtos = Venda.objects.filter(
        estabelecimento=estabelecimento,
        criado_em__gte=data_inicio,
        criado_em__lt=data_fim
    ).aggregate(
        total_custo=Coalesce(Sum(F('produtos__produto__preco_unitario') * F('produtos__quantidade')), Decimal('0.00'),
                             output_field=DecimalField())
    )['total_custo']

    # Total de agendamentos
    total_consultas = Agendamento.objects.filter(
        estabelecimento=estabelecimento,
        data__gte=data_inicio,
        data__lt=data_fim
    ).count()

    # Produtos com baixo estoque
    produtos_baixo_estoque = Produto.objects.filter(
        estabelecimento=estabelecimento,
        quantidade__lte=10
    ).count()

    # Relatório de profissionais
    profissionais_periodo = Agendamento.objects.filter(
        estabelecimento=estabelecimento,
        data__gte=data_inicio,
        data__lt=data_fim
    ).values('profissional__nome').annotate(
        valor_total=Coalesce(Sum('valor'), Decimal('0.00'), output_field=DecimalField()),
        comissao_total=Coalesce(
            Sum(
                F('valor') * Cast(F('profissional__percentual_comissao'), output_field=DecimalField()) / Decimal(
                    '100.00')
            ),
            Decimal('0.00'),
            output_field=DecimalField()
        )
    ).order_by('-valor_total')

    total_profissional = sum(prof['valor_total'] for prof in profissionais_periodo) or Decimal('1.00')
    for prof in profissionais_periodo:
        prof['percentual'] = (prof['valor_total'] / total_profissional) * 100

    # Pagamentos por forma - Serviços (Agendamentos)
    pagamentos_por_forma_servicos = Agendamento.objects.filter(
        estabelecimento=estabelecimento,
        data__gte=data_inicio,
        data__lt=data_fim
    ).values('forma_pagamento').annotate(
        total=Coalesce(Sum('valor'), Decimal('0.00'), output_field=DecimalField())
    ).order_by('forma_pagamento')
    total_pagamentos_servicos = sum(item['total'] for item in pagamentos_por_forma_servicos)

    # Pagamentos por forma - Vendas de Produtos
    pagamentos_por_forma_vendas = Venda.objects.filter(
        estabelecimento=estabelecimento,
        criado_em__gte=data_inicio,
        criado_em__lt=data_fim
    ).values('forma_pagamento').annotate(
        total=Coalesce(Sum('valor_total'), Decimal('0.00'), output_field=DecimalField())
    ).order_by('forma_pagamento')
    total_pagamentos_vendas = sum(item['total'] for item in pagamentos_por_forma_vendas)

    context = {
        'faturamento_dia': faturamento_dia,
        'faturamento_dia_vendas': faturamento_dia_vendas,
        'faturamento_periodo': faturamento_periodo,
        'faturamento_vendas_produtos': faturamento_vendas_produtos,
        'faturamento_servicos': faturamento_servicos,
        'custos_produtos': custos_produtos,
        'total_consultas': total_consultas,
        'produtos_baixo_estoque': produtos_baixo_estoque,
        'profissionais_periodo': profissionais_periodo,
        'pagamentos_por_forma_servicos': pagamentos_por_forma_servicos,
        'total_pagamentos_servicos': total_pagamentos_servicos,
        'pagamentos_por_forma_vendas': pagamentos_por_forma_vendas,
        'total_pagamentos_vendas': total_pagamentos_vendas,
        'data_inicio': data_inicio.strftime('%Y-%m-%d') if isinstance(data_inicio, datetime) else data_inicio,
        'data_fim': (data_fim - timedelta(days=1)).strftime('%Y-%m-%d') if isinstance(data_fim, datetime) else data_fim,
    }

    return render(request, 'dashboard_financeiro.html', context)


def exportar_financeiro_excel(request):
    # Filtros de data
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    if data_inicio and data_fim:
        try:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').replace(tzinfo=timezone.get_current_timezone())
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d').replace(
                tzinfo=timezone.get_current_timezone()) + timedelta(days=1)
        except ValueError:
            data_inicio = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            data_fim = data_inicio + timedelta(days=1)
    else:
        data_inicio = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        data_fim = data_inicio + timedelta(days=1)

    # Criar workbook
    wb = Workbook()

    # Aba de Agendamentos
    ws_agendamentos = wb.active
    ws_agendamentos.title = "Financeiro"

    ws_agendamentos.append(['Data', 'Cliente', 'Serviço', 'Profissional', 'Valor', 'Forma de Pagamento'])

    agendamentos = Agendamento.objects.filter(
        estabelecimento=request.user.estabelecimento,
        data__gte=data_inicio,
        data__lt=data_fim
    ).select_related('cliente', 'servico', 'profissional')

    for ag in agendamentos:
        ws_agendamentos.append([
            ag.data.strftime('%d/%m/%Y'),
            ag.cliente.nome,
            ag.servico.nome,
            ag.profissional.nome,
            float(ag.valor),
            ag.forma_pagamento,
        ])

    # Calcular valor total dos agendamentos
    valor_total_agendamentos = sum(ag.valor for ag in agendamentos) or Decimal('0.00')
    ws_agendamentos.append([])
    ws_agendamentos.append(['Valor Total', '', '', '', float(valor_total_agendamentos), ''])

    # Aba de Vendas
    ws_vendas = wb.create_sheet(title="Vendas")
    ws_vendas.append(['Data', 'Cliente', 'Produtos', 'Valor Total', 'Forma de Pagamento'])

    vendas = Venda.objects.filter(
        estabelecimento=request.user.estabelecimento,
        criado_em__gte=data_inicio,
        criado_em__lt=data_fim
    ).select_related('cliente').prefetch_related('produtos__produto')

    for venda in vendas:
        produtos = ", ".join([vp.produto.nome for vp in venda.produtos.all()])
        ws_vendas.append([
            venda.criado_em.strftime('%d/%m/%Y'),
            venda.cliente.nome if venda.cliente else "Não especificado",
            produtos,
            float(venda.valor_total),
            venda.forma_pagamento,
        ])

    # Calcular valor total das vendas
    valor_total_vendas = sum(venda.valor_total for venda in vendas) or Decimal('0.00')
    ws_vendas.append([])
    ws_vendas.append(['Valor Total', '', '', float(valor_total_vendas), ''])

    # Configurar resposta HTTP
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=financeiro_{timezone.now().strftime("%Y%m%d")}.xlsx'
    wb.save(response)
    return response


@login_required
def exportar_financeiro_pdf(request):
    # Configurar resposta HTTP para o PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="financeiro_{timezone.now().strftime("%Y%m%d")}.pdf"'

    # Criar o documento PDF
    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm
    )
    elements = []
    styles = getSampleStyleSheet()

    # Título do relatório
    title = Paragraph(
        f"Relatório Financeiro - {request.user.estabelecimento.nome}",
        styles['Title']
    )
    elements.append(title)
    elements.append(Spacer(1, 0.5 * cm))

    # Subtítulo com data de geração
    data_geracao = Paragraph(
        f"Gerado em: {timezone.now().strftime('%d/%m/%Y %H:%M')}",
        styles['Normal']
    )
    elements.append(data_geracao)
    elements.append(Spacer(1, 1 * cm))

    # Filtros de data
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    if data_inicio and data_fim:
        try:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').replace(tzinfo=timezone.get_current_timezone())
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d').replace(
                tzinfo=timezone.get_current_timezone()) + timedelta(days=1)
        except ValueError:
            data_inicio = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            data_fim = data_inicio + timedelta(days=1)
    else:
        data_inicio = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        data_fim = data_inicio + timedelta(days=1)

    # Tabela de Agendamentos
    elements.append(Paragraph("Agendamentos", styles['Heading2']))
    elements.append(Spacer(1, 0.2 * cm))

    agendamentos = Agendamento.objects.filter(
        estabelecimento=request.user.estabelecimento,
        data__gte=data_inicio,
        data__lt=data_fim
    ).select_related('cliente', 'servico', 'profissional')

    # Calcular o valor total dos agendamentos
    valor_total_agendamentos = sum(ag.valor for ag in agendamentos) or Decimal('0.00')

    # Cabeçalho da tabela de agendamentos
    data_agendamentos = [['Data', 'Cliente', 'Serviço', 'Profissional', 'Valor', 'Pagamento']]

    # Preencher a tabela com agendamentos
    for ag in agendamentos:
        data_agendamentos.append([
            ag.data.strftime('%d/%m/%Y'),
            ag.cliente.nome,
            ag.servico.nome,
            ag.profissional.nome,
            f"R$ {ag.valor:.2f}",
            ag.forma_pagamento.capitalize()
        ])

    # Criar a tabela de agendamentos
    table_agendamentos = Table(data_agendamentos, colWidths=[3 * cm, 5 * cm, 4 * cm, 4 * cm, 2.5 * cm, 3.5 * cm])
    table_agendamentos.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a00e0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
    ]))
    elements.append(table_agendamentos)
    elements.append(Spacer(1, 0.5 * cm))

    # Adicionar valor total dos agendamentos
    total_agendamentos = Paragraph(
        f"<b>Valor Total Agendamentos:</b> R$ {valor_total_agendamentos:.2f}",
        styles['Normal']
    )
    elements.append(total_agendamentos)
    elements.append(Spacer(1, 1 * cm))

    # Tabela de Vendas
    elements.append(Paragraph("Vendas", styles['Heading2']))
    elements.append(Spacer(1, 0.2 * cm))

    vendas = Venda.objects.filter(
        estabelecimento=request.user.estabelecimento,
        criado_em__gte=data_inicio,
        criado_em__lt=data_fim
    ).select_related('cliente').prefetch_related('produtos__produto')

    # Calcular o valor total das vendas
    valor_total_vendas = sum(venda.valor_total for venda in vendas) or Decimal('0.00')

    # Cabeçalho da tabela de vendas
    data_vendas = [['Data', 'Cliente', 'Produtos', 'Valor Total', 'Pagamento']]

    # Preencher a tabela com vendas
    for venda in vendas:
        produtos = ", ".join([vp.produto.nome for vp in venda.produtos.all()])
        data_vendas.append([
            venda.criado_em.strftime('%d/%m/%Y'),
            venda.cliente.nome if venda.cliente else "Não especificado",
            produtos,
            f"R$ {venda.valor_total:.2f}",
            venda.forma_pagamento.capitalize()
        ])

    # Criar a tabela de vendas
    table_vendas = Table(data_vendas, colWidths=[3 * cm, 5 * cm, 6 * cm, 2.5 * cm, 3.5 * cm])
    table_vendas.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a00e0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
    ]))
    elements.append(table_vendas)
    elements.append(Spacer(1, 0.5 * cm))

    # Adicionar valor total das vendas
    total_vendas = Paragraph(
        f"<b>Valor Total Vendas:</b> R$ {valor_total_vendas:.2f}",
        styles['Normal']
    )
    elements.append(total_vendas)

    # Função para adicionar rodapé
    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.drawString(2 * cm, 1 * cm, f"Página {doc.page}")
        canvas.drawRightString(19 * cm, 1 * cm, f"Gerado por {request.user.estabelecimento.nome}")
        canvas.restoreState()

    # Gerar o PDF
    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)
    return response

# CLIENTES
@login_required
def cadastrar_cliente(request):
    try:
        estabelecimento = request.user.estabelecimento
    except Estabelecimento.DoesNotExist:
        messages.error(request, "Você precisa cadastrar um estabelecimento primeiro.")
        return redirect('cadastro_estabelecimento')

    form = ClienteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cliente = form.save(commit=False)
        cliente.estabelecimento = estabelecimento
        cliente.save()
        return redirect('lista_cliente')

    return render(request, 'cadastro_cliente.html', {'form': form, 'titulo': 'Cadastrar Cliente'})

def listar_cliente(request):
    query = request.GET.get('q', '')
    clientes = Cliente.objects.filter(estabelecimento=request.user.estabelecimento)
    if query:
        clientes = clientes.filter(nome__icontains=query)
    return render(request, 'lista_cliente.html', {'clientes': clientes, 'query': query})

def adicionar_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente adicionado com sucesso!')
            return redirect('lista_cliente')
    else:
        form = ClienteForm()
    return render(request, 'adicionar_cliente.html', {'form': form})

def editar_cliente(request, id):
    cliente = get_object_or_404(Cliente, id=id)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente atualizado com sucesso!')
            return redirect('lista_cliente')
    else:
        form = ClienteForm(instance=cliente)
    return render(request, 'editar_cliente.html', {'form': form})

def excluir_cliente(request, id):
    cliente = get_object_or_404(Cliente, id=id)
    cliente.delete()
    messages.success(request, 'Cliente excluído com sucesso!')
    return redirect('lista_cliente')



# PROFISSIONAIS
@login_required
@plano_required(pode_adicionar_profissional)
def cadastro_profissional(request):
    # Tentar obter o estabelecimento associado ao usuário logado
    try:
        estabelecimento = request.user.estabelecimento
    except Estabelecimento.DoesNotExist:
        messages.error(
            request,
            'Nenhum estabelecimento associado ao seu usuário. Por favor, configure um estabelecimento.'
        )
        return redirect('configurar_estabelecimento')

    # Verificar limite de profissionais
    limite_profissionais = estabelecimento.plano.max_profissionais
    profissionais_atuais = estabelecimento.profissional_set.filter(ativo=True).count()
    pode_adicionar = profissionais_atuais < limite_profissionais

    if not pode_adicionar:
        messages.warning(
            request,
            'Limite de profissionais atingido! Faça upgrade do seu plano.'
        )
        return redirect('lista_profissional')

    if request.method == 'POST':
        # CORREÇÃO: Passar o estabelecimento para o formulário
        form = ProfissionalForm(request.POST, estabelecimento=estabelecimento)
        if form.is_valid():
            # Criar o profissional, mas não salvar ainda
            profissional = form.save(commit=False)
            # Associar ao estabelecimento
            profissional.estabelecimento = estabelecimento
            # Salvar o profissional
            profissional.save()

            messages.success(request, 'Profissional cadastrado com sucesso!')
            return redirect('lista_profissional')
        else:
            # CORREÇÃO: Mostrar erros do formulário de forma mais limpa
            for field, errors in form.errors.items():
                field_name = form.fields[field].label if field in form.fields else field
                for error in errors:
                    messages.error(request, f"{field_name}: {error}")
    else:
        # CORREÇÃO: Passar o estabelecimento para o formulário também no GET
        form = ProfissionalForm(estabelecimento=estabelecimento)

    context = {
        'form': form,
        'titulo': 'Cadastrar Profissional',
        'estabelecimento': estabelecimento,
        'plano_atual': estabelecimento.plano.nome,
        'limite_profissionais': limite_profissionais,
        'profissionais_restantes': limite_profissionais - profissionais_atuais,
        'pode_adicionar': pode_adicionar,
    }

    return render(request, 'cadastro_profissional.html', context)


@login_required
def adicionar_profissional(request):
    resultado = verificar_limites(request)
    if resultado:
        return resultado

    estabelecimento = request.user.estabelecimento
    profissionais = Profissional.objects.filter(estabelecimento=estabelecimento)
    if request.method == "POST":
        if profissionais.count() >= request.plano_ativo.max_profissionais:
            return HttpResponseForbidden(f"Limite de {request.plano_ativo.max_profissionais} profissionais atingido. Atualize seu plano.")
        # Lógica para criar o profissional (ex.: via formulário)
        # Exemplo: Profissional.objects.create(estabelecimento=estabelecimento, nome=request.POST['nome'])
        return redirect('dashboard')

    return render(request, 'adicionar_profissional.html', {'profissionais': profissionais})


@login_required
def lista_profissional(request):
    estabelecimento = verificar_estabelecimento(request)
    if not estabelecimento:
        return redirect('cadastro_estabelecimento')

    profissionais = Profissional.objects.filter(
        estabelecimento=estabelecimento,
        ativo=True
    ).order_by('nome')

    context = {
        'profissionais': profissionais,
        'estabelecimento': estabelecimento,
        'pode_adicionar': estabelecimento.pode_adicionar_profissional(),
        'profissionais_restantes': estabelecimento.profissionais_restantes(),
        'limite_profissionais': estabelecimento.plano.max_profissionais,
        'plano_atual': estabelecimento.plano.get_nome_display(),
    }

    return render(request, 'lista_profissional.html', context)


def editar_profissional(request, id):
    profissional = get_object_or_404(Profissional, id=id)

    if request.method == 'POST':
        form = ProfissionalForm(request.POST, instance=profissional)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profissional atualizado com sucesso!')
            return redirect('lista_profissional')
        else:
            messages.error(request, 'Erro ao atualizar o profissional. Verifique os dados e tente novamente.')
    else:
        form = ProfissionalForm(instance=profissional)

    return render(request, 'editar_profissional.html', {
        'form': form,
        'profissional': profissional,
        'titulo': 'Editar Profissional'
    })


def excluir_profissional(request, id):
    profissional = get_object_or_404(Profissional, id=id)
    profissional.delete()
    messages.success(request, 'Profissional excluído com sucesso!')
    return redirect('lista_profissional')

# SERVIÇOS
@login_required
def cadastrar_servico(request):
    """View para criar serviços usando formulário"""

    if request.method == 'POST':
        form = ServicoForm(request.POST)

        if form.is_valid():
            try:
                # Debug
                print("=== DEBUG CRIAÇÃO SERVIÇO ===")
                print(f"Dados limpos: {form.cleaned_data}")

                # Salvar o serviço
                servico = form.save(commit=False)
                servico.estabelecimento = request.user.estabelecimento  # ajuste conforme sua estrutura
                servico.save()

                print(f"✅ Serviço criado: {servico.id}")
                messages.success(request, '✅ Serviço criado com sucesso!')
                return redirect('lista_servico')  # ajuste o nome da URL conforme necessário

            except Exception as e:
                print(f"❌ ERRO: {str(e)}")
                messages.error(request, f'❌ Erro ao criar serviço: {str(e)}')
        else:
            # Se o formulário não é válido, mostrar os erros
            print("❌ FORMULÁRIO INVÁLIDO:")
            for field, errors in form.errors.items():
                print(f"  {field}: {errors}")
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        # GET request - criar formulário vazio
        form = ServicoForm()

    # Passar dados para o template
    context = {
        'form': form,
        'titulo': 'Cadastrar Novo Serviço'
    }

    return render(request, 'cadastro_servico.html', context)

def formatar_duracao(valor):
    """Função para formatar duração em diferentes formatos"""
    if not valor:
        return None

    # Se já é um objeto time, retornar
    if isinstance(valor, time):
        return valor

    # Converter para string se necessário
    valor_str = str(valor).strip()


    # Formato HH:MM ou H:MM
    if ':' in valor_str:
        try:
            partes = valor_str.split(':')
            if len(partes) == 2:
                horas = int(partes[0])
                minutos = int(partes[1])

                # Validar
                if 0 <= horas <= 23 and 0 <= minutos <= 59:
                    return time(hour=horas, minute=minutos)
        except ValueError:
            pass

    # Apenas números - assumir minutos
    elif valor_str.isdigit():
        try:
            total_minutos = int(valor_str)
            if total_minutos <= 1440:  # Máximo 24 horas
                horas = total_minutos // 60
                minutos = total_minutos % 60
                return time(hour=horas, minute=minutos)
        except ValueError:
            pass

    # Formato decimal (horas)
    else:
        try:
            horas_float = float(valor_str)
            if 0 <= horas_float <= 24:
                horas = int(horas_float)
                minutos = int((horas_float - horas) * 60)
                return time(hour=horas, minute=minutos)
        except ValueError:
            pass

    return None


def listar_servico(request):
    query = request.GET.get('q', '')
    servicos = Servico.objects.filter(estabelecimento=request.user.estabelecimento)
    if query:
        servicos = servicos.filter(nome__icontains=query)
    return render(request, 'lista_servico.html', {'servicos': servicos, 'query': query})

def adicionar_servico(request):
    if request.method == 'POST':
        form = ServicoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Serviço adicionado com sucesso!')
            return redirect('lista_servico')
    else:
        form = ServicoForm()
    return render(request, 'adicionar_servico.html', {'form': form})


def editar_servico(request, id):
    servico = get_object_or_404(Servico, id=id)
    if request.method == 'POST':
        form = ServicoForm(request.POST, instance=servico)
        if form.is_valid():
            form.save()
            messages.success(request, 'Serviço atualizado com sucesso!')
            return redirect('lista_servico')
    else:
        form = ServicoForm(instance=servico)
    return render(request, 'editar_servico.html', {'form': form, 'servico': servico})

def excluir_servico(request, id):
    servico = get_object_or_404(Servico, id=id)
    servico.delete()
    messages.success(request, 'Serviço excluído com sucesso!')
    return redirect('lista_servico')


@login_required
@plano_required(tem_controle_estoque)
def controle_estoque(request):
    """Exemplo de view que requer controle de estoque"""
    estabelecimento = verificar_estabelecimento(request)
    if not estabelecimento:
        return redirect('cadastro_estabelecimento')

    # Sua lógica de controle de estoque aqui
    return render(request, 'controle_estoque.html')


@login_required
def verificar_limite_profissionais(request):
    """View AJAX para verificar limite de profissionais"""
    estabelecimento = verificar_estabelecimento(request)
    if not estabelecimento:
        return JsonResponse({'error': 'Estabelecimento não encontrado'}, status=404)

    return JsonResponse({
        'pode_adicionar': estabelecimento.pode_adicionar_profissional(),
        'profissionais_atuais': estabelecimento.profissional_set.count(),
        'limite_profissionais': estabelecimento.plano.max_profissionais,
        'profissionais_restantes': estabelecimento.profissionais_restantes(),
        'plano_nome': estabelecimento.plano.get_nome_display(),
    })


@login_required
def planos_view(request):
    """View para mostrar os planos disponíveis"""
    planos = Plano.objects.filter(ativo=True).order_by('max_profissionais')

    estabelecimento = None
    plano_atual = None
    try:
        estabelecimento = request.user.estabelecimento
        plano_atual = estabelecimento.plano
    except Estabelecimento.DoesNotExist:
        pass

    context = {
        'planos': planos,
        'estabelecimento': estabelecimento,
        'plano_atual': plano_atual,
    }

    return render(request, 'planos.html', context)  # ← Adicionado .html


@login_required
def escolher_plano(request, plano_id):
    """View para o usuário escolher um plano"""
    plano = get_object_or_404(Plano, id=plano_id, ativo=True)

    try:
        estabelecimento = request.user.estabelecimento
        estabelecimento.plano = plano
        estabelecimento.save()
        messages.success(request, f'Plano {plano.nome} selecionado com sucesso!')
    except Estabelecimento.DoesNotExist:
        messages.error(request, 'Você precisa cadastrar um estabelecimento primeiro.')
        return redirect('cadastrar_estabelecimento')

    return redirect('planos')

# AGENDAMENTOS

@login_required
def agenda(request):
    """View de agenda corrigida - sem conflito de imports"""

    # Obter ano e mês dos parâmetros
    ano = request.GET.get('ano', timezone.now().year)
    mes = request.GET.get('mes', timezone.now().month)

    try:
        ano = int(ano)
        mes = int(mes)
        if not (1 <= mes <= 12):
            mes = timezone.now().month
        data_atual = datetime(ano, mes, 1)
    except ValueError:
        data_atual = timezone.now().replace(day=1)

    # Número de dias no mês
    num_dias = monthrange(data_atual.year, data_atual.month)[1]

    # Filtro por profissional
    profissional = request.GET.get('profissional')
    agendamentos = Agendamento.objects.filter(
        estabelecimento=request.user.estabelecimento,
        data__year=data_atual.year,
        data__month=data_atual.month
    )

    logger.info(f"Total de agendamentos antes do filtro por profissional: {agendamentos.count()}")

    if profissional:
        agendamentos = agendamentos.filter(profissional__nome=profissional)
        logger.info(f"Total de agendamentos após filtro por profissional '{profissional}': {agendamentos.count()}")

    agendamentos = agendamentos.order_by('data', 'hora')
    logger.info(
        f"Agendamentos: {[(ag.data, ag.hora.strftime('%H:%M'), ag.profissional.nome if ag.profissional else 'Nenhum') for ag in agendamentos]}")

    # LÓGICA DE HORÁRIOS CORRIGIDA
    if agendamentos.exists():
        # Pega todos os horários únicos dos agendamentos
        horarios_agendamentos = set(ag.hora for ag in agendamentos)

        # Converte para lista e ordena
        horarios_unicos = sorted(list(horarios_agendamentos))

        # Cria a lista de horários no formato (time, string)
        horarios = [(h, h.strftime("%H:%M")) for h in horarios_unicos]

        logger.info(f"Horários únicos encontrados: {[h[1] for h in horarios]}")
    else:
        # Se não há agendamentos, usa horário comercial padrão
        hora_inicio = 8
        hora_fim = 19
        horarios = []
        for h in range(hora_inicio, hora_fim):
            # ⬅️ CORRIGIDO: usando time() da datetime, não time()
            horarios.append((time(h, 0), f"{h:02d}:00"))
            horarios.append((time(h, 30), f"{h:02d}:30"))

        logger.info(f"Horários padrão gerados: {[h[1] for h in horarios]}")

    # Calcular mês anterior e próximo
    mes_anterior = data_atual.replace(day=1) - timedelta(days=1)
    mes_anterior = mes_anterior.replace(day=1)
    mes_proximo = (data_atual.replace(day=1) + timedelta(days=32)).replace(day=1)

    # Profissionais
    profissionais_queryset = Agendamento.objects.filter(
        estabelecimento=request.user.estabelecimento
    ).values('profissional__nome').distinct()

    profissionais = [p['profissional__nome'] for p in profissionais_queryset]
    cor_profissionais = {nome: idx % 9 for idx, nome in enumerate(profissionais)}

    context = {
        'agendamentos': agendamentos,
        'horarios': horarios,
        'data_atual': data_atual,
        'mes_anterior': mes_anterior,
        'mes_proximo': mes_proximo,
        'profissionais': profissionais_queryset,
        'num_dias': num_dias,
        'cor_profissionais': cor_profissionais,
    }

    return render(request, 'agenda.html', context)


def agenda_diaria(request):
    data_atual = timezone.localdate()
    agendamentos = Agendamento.objects.filter(
        data=data_atual,
        estabelecimento=request.user.estabelecimento
    ).order_by('hora')

    return render(request, 'agenda_diaria.html', {
        'agendamentos': agendamentos,
        'data': data_atual
    })


@login_required
def novo_agendamento(request):
    try:
        estabelecimento = request.user.estabelecimento
    except AttributeError:
        messages.error(request, "Seu usuário não está vinculado a um estabelecimento.")
        return redirect('painel_administrador')

    # Função auxiliar para converter duração para minutos
    def duracao_para_minutos(duracao):
        if not duracao:
            return 0
        try:
            if hasattr(duracao, 'total_seconds'):
                # É um timedelta
                return int(duracao.total_seconds() / 60)
            elif hasattr(duracao, 'hour'):
                # É um time object
                return duracao.hour * 60 + duracao.minute
            elif isinstance(duracao, str):
                # É uma string no formato HH:MM
                if ':' in duracao:
                    parts = duracao.split(':')
                    hours = int(parts[0])
                    minutes = int(parts[1]) if len(parts) > 1 else 0
                    return hours * 60 + minutes
                else:
                    return int(duracao)
            elif isinstance(duracao, (int, float)):
                return int(duracao)
            else:
                return 0
        except (ValueError, AttributeError):
            return 0

    # Dados para autocomplete com tratamento de erros
    try:
        clientes_data = [
            {'id': c.id, 'nome': c.nome}
            for c in Cliente.objects.filter(estabelecimento=estabelecimento)
        ]
    except Exception as e:
        print(f"Erro ao carregar clientes: {e}")
        clientes_data = []

    try:
        profissionais_data = [
            {
                'id': p.id,
                'nome': p.nome,
                'percentual': float(p.percentual_comissao or 0)
            }
            for p in Profissional.objects.filter(estabelecimento=estabelecimento)
        ]
    except Exception as e:
        print(f"Erro ao carregar profissionais: {e}")
        profissionais_data = []

    try:
        servicos_data = []
        for s in Servico.objects.filter(estabelecimento=estabelecimento):
            try:
                servicos_data.append({
                    'id': s.id,
                    'nome': s.nome,
                    'duracao': duracao_para_minutos(s.duracao),
                    'valor': float(s.valor or 0)
                })
            except Exception as e:
                print(f"Erro ao processar serviço {s.id}: {e}")
                # Adicionar com valores padrão
                servicos_data.append({
                    'id': s.id,
                    'nome': s.nome,
                    'duracao': 30,  # 30 minutos padrão
                    'valor': 0.0
                })
    except Exception as e:
        print(f"Erro ao carregar serviços: {e}")
        servicos_data = []

    try:
        produtos_data = [
            {
                'id': p.id,
                'nome': p.nome,
                'quantidade': p.quantidade,
                'preco': float(p.preco_unitario or 0)
            }
            for p in Produto.objects.filter(estabelecimento=estabelecimento)
        ]
    except Exception as e:
        print(f"Erro ao carregar produtos: {e}")
        produtos_data = []

    # Debug dos dados
    print("=== DEBUG DADOS AGENDAMENTO ===")
    print(f"Clientes encontrados: {len(clientes_data)}")
    print(f"Profissionais encontrados: {len(profissionais_data)}")
    print(f"Serviços encontrados: {len(servicos_data)}")
    print(f"Produtos encontrados: {len(produtos_data)}")

    if servicos_data:
        print(f"Primeiro serviço: {servicos_data[0]}")
    if profissionais_data:
        print(f"Primeiro profissional: {profissionais_data[0]}")

    if request.method == 'POST':
        print("=== DEBUG POST AGENDAMENTO ===")
        print(f"POST data: {dict(request.POST)}")

        form = AgendamentoForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Validação de cliente
                cliente_nome = request.POST.get('cliente', '').strip()
                print(f"Buscando cliente: '{cliente_nome}'")
                cliente = Cliente.objects.filter(nome__iexact=cliente_nome, estabelecimento=estabelecimento).first()
                if not cliente:
                    print(f"Cliente não encontrado: '{cliente_nome}'")
                    messages.error(request, f'Cliente "{cliente_nome}" não encontrado.')
                    return render(request, 'novo_agendamento.html', {
                        'form': form,
                        'clientes_data': clientes_data,
                        'profissionais_data': profissionais_data,
                        'servicos_data': servicos_data,
                        'produtos_data': produtos_data,
                    })

                # Validação de profissional
                profissional_nome = request.POST.get('profissional', '').strip()
                print(f"Buscando profissional: '{profissional_nome}'")
                profissional = Profissional.objects.filter(nome__iexact=profissional_nome,
                                                           estabelecimento=estabelecimento).first()
                if not profissional:
                    print(f"Profissional não encontrado: '{profissional_nome}'")
                    messages.error(request, f'Profissional "{profissional_nome}" não encontrado.')
                    return render(request, 'novo_agendamento.html', {
                        'form': form,
                        'clientes_data': clientes_data,
                        'profissionais_data': profissionais_data,
                        'servicos_data': servicos_data,
                        'produtos_data': produtos_data,
                    })

                # Validação de serviço
                servico_nome = request.POST.get('servico', '').strip()
                print(f"Buscando serviço: '{servico_nome}'")
                servico = Servico.objects.filter(nome__iexact=servico_nome, estabelecimento=estabelecimento).first()
                if not servico:
                    print(f"Serviço não encontrado: '{servico_nome}'")
                    messages.error(request, f'Serviço "{servico_nome}" não encontrado.')
                    return render(request, 'novo_agendamento.html', {
                        'form': form,
                        'clientes_data': clientes_data,
                        'profissionais_data': profissionais_data,
                        'servicos_data': servicos_data,
                        'produtos_data': produtos_data,
                    })

                # Criar agendamento
                agendamento = form.save(commit=False)
                agendamento.cliente = cliente
                agendamento.profissional = profissional
                agendamento.servico = servico
                agendamento.estabelecimento = estabelecimento

                # Calcular comissão do profissional
                if agendamento.valor and profissional.percentual_comissao:
                    agendamento.valor_profissional = agendamento.valor * (profissional.percentual_comissao / 100)
                else:
                    agendamento.valor_profissional = 0

                print(
                    f"Salvando agendamento: Cliente={cliente.nome}, Profissional={profissional.nome}, Serviço={servico.nome}")
                agendamento.save()
                form.save_m2m()

                # Processar produtos
                produtos_selecionados = request.POST.get('produtos_selecionados', '[]')
                print(f"Produtos selecionados: {produtos_selecionados}")
                try:
                    produtos_selecionados = json.loads(produtos_selecionados)
                    for item in produtos_selecionados:
                        produto_id = item['id']
                        quantidade = int(item['quantidade'])
                        produto = Produto.objects.get(id=produto_id, estabelecimento=estabelecimento)
                        if produto.quantidade >= quantidade:
                            produto.quantidade -= quantidade
                            produto.save()
                            MovimentacaoEstoque.objects.create(
                                produto=produto,
                                tipo='SAIDA',
                                quantidade=quantidade,
                                observacao=f'Usado no agendamento {agendamento.id}'
                            )
                            AgendamentoProduto.objects.create(
                                agendamento=agendamento,
                                produto=produto,
                                quantidade=quantidade
                            )
                        else:
                            messages.error(request, f'Estoque insuficiente para {produto.nome}.')
                            agendamento.delete()
                            return render(request, 'novo_agendamento.html', {
                                'form': form,
                                'clientes_data': clientes_data,
                                'profissionais_data': profissionais_data,
                                'servicos_data': servicos_data,
                                'produtos_data': produtos_data,
                            })
                except (ValueError, KeyError, Produto.DoesNotExist) as e:
                    print(f"Erro ao processar produtos: {e}")
                    messages.error(request, f'Erro ao processar produtos: {str(e)}')
                    agendamento.delete()
                    return render(request, 'novo_agendamento.html', {
                        'form': form,
                        'clientes_data': clientes_data,
                        'profissionais_data': profissionais_data,
                        'servicos_data': servicos_data,
                        'produtos_data': produtos_data,
                    })

                # Processar pagamento PagBank
                if agendamento.forma_pagamento == 'PAGBANK':
                    try:
                        agendamento.save()
                        return redirect('iniciar_checkout', agendamento_id=agendamento.id)
                    except Exception as e:
                        logger.error(f"Erro ao iniciar checkout PagBank: {e}")
                        messages.error(request, "Erro ao processar pagamento PagBank.")
                        agendamento.delete()
                        return render(request, 'novo_agendamento.html', {
                            'form': form,
                            'clientes_data': clientes_data,
                            'profissionais_data': profissionais_data,
                            'servicos_data': servicos_data,
                            'produtos_data': produtos_data,
                        })

                print(f"✅ Agendamento criado com sucesso! ID: {agendamento.id}")
                messages.success(request, 'Agendamento criado com sucesso!')
                return redirect('listar_agendamentos')
        else:
            print(f"❌ Formulário inválido: {form.errors}")
            messages.error(request, 'Erro ao criar o agendamento. Verifique os dados.')
    else:
        form = AgendamentoForm()

    return render(request, 'novo_agendamento.html', {
        'form': form,
        'clientes_data': clientes_data,
        'profissionais_data': profissionais_data,
        'servicos_data': servicos_data,
        'produtos_data': produtos_data,
    })


def listar_agendamentos(request):
    agendamentos = Agendamento.objects.select_related('cliente', 'profissional', 'servico') \
        .filter(estabelecimento=request.user.estabelecimento) \
        .order_by('data', 'hora')

    # Filtros
    q = request.GET.get('q')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    horario = request.GET.get('horario')
    status = request.GET.get('status')
    pagamento = request.GET.get('pagamento')

    # Filtro por texto (cliente, profissional ou serviço)
    if q:
        agendamentos = agendamentos.filter(
            Q(cliente__nome__icontains=q) |
            Q(profissional__nome__icontains=q) |
            Q(servico__nome__icontains=q)
        )

    # Filtro por data de início
    if data_inicio:
        try:
            data_inicio_parsed = parse_date(data_inicio)
            if data_inicio_parsed:
                agendamentos = agendamentos.filter(data__gte=data_inicio_parsed)
        except:
            pass  # Ignora se não conseguir fazer parse da data

    # Filtro por data fim
    if data_fim:
        try:
            data_fim_parsed = parse_date(data_fim)
            if data_fim_parsed:
                agendamentos = agendamentos.filter(data__lte=data_fim_parsed)
        except:
            pass  # Ignora se não conseguir fazer parse da data

    # Filtro por horário
    if horario:
        try:
            horario_parsed = datetime.strptime(horario, '%H:%M').time()
            agendamentos = agendamentos.filter(hora=horario_parsed)
        except:
            pass  # Ignora se não conseguir fazer parse do horário

    # Filtro por status
    if status:
        agendamentos = agendamentos.filter(status=status)

    # Filtro por forma de pagamento
    if pagamento:
        agendamentos = agendamentos.filter(forma_pagamento=pagamento)

    # Para cada agendamento, anexa .prontuario_obj (ou None)
    for ag in agendamentos:
        ag.prontuario_obj = Prontuario.objects.filter(agendamento=ag).first()

    return render(request, 'listar_agendamentos.html', {
        'agendamentos': agendamentos,
    })



@login_required
def cadastrar_produto(request):
    try:
        estabelecimento = request.user.estabelecimento
    except AttributeError:
        messages.error(request, "Seu usuário não está vinculado a um estabelecimento.")
        return redirect('dashboard')

    # Dados para listagem de produtos
    produtos_data = [
        {
            'id': p.id,
            'nome': p.nome,
            'quantidade': p.quantidade,
            'preco': float(p.preco_unitario or 0),
            'codigo': p.codigo or ''
        }
        for p in Produto.objects.filter(estabelecimento=estabelecimento)
    ]
    logger.info(f"Produtos data em cadastrar_produto: {produtos_data}")

    if request.method == 'POST':
        form = ProdutoForm(request.POST)
        if form.is_valid():
            produto = form.save(commit=False)
            produto.estabelecimento = estabelecimento
            produto.save()
            messages.success(request, 'Produto cadastrado com sucesso!')
            return redirect('gerenciar_estoque')
        else:
            messages.error(request, 'Erro ao cadastrar o produto. Verifique os dados.')
    else:
        form = ProdutoForm()

    return render(request, 'cadastro_produto.html', {
        'form': form,
        'produtos_data': produtos_data
    })


def editar_produto(request, id):
    print(f"Editar chamado para ID: {id}, Método: {request.method}")

    # CORREÇÃO 1: Usar o modelo correto (Produto ao invés de Servico)
    produto = get_object_or_404(Produto, id=id)

    if request.method == 'POST':
        # CORREÇÃO 2: Usar ProdutoForm ao invés de ServicoForm
        form = ProdutoForm(request.POST, instance=produto)
        if form.is_valid():
            form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                print("Edição bem-sucedida via AJAX")
                return JsonResponse({'success': True})
            messages.success(request, 'Produto atualizado com sucesso!')
            return redirect('nova_venda')  # CORREÇÃO 3: Redirect para a página correta
        elif request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            print("Formulário inválido via AJAX")
            form_html = render_to_string('form_produto.html', {'form': form, 'produto_id': id}, request=request)
            return JsonResponse({'success': False, 'form_html': form_html})
    else:
        # CORREÇÃO 4: Usar ProdutoForm ao invés de ServicoForm
        form = ProdutoForm(instance=produto)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        print("Carregando formulário via AJAX")
        form_html = render_to_string('form_produto.html', {'form': form, 'produto_id': id}, request=request)
        return JsonResponse({'form_html': form_html})

    return render(request, 'editar_produto.html', {'form': form, 'produto': produto})


def excluir_produto(request, id):
    print(f"Excluir chamado para ID: {id}, Método: {request.method}")

    # CORREÇÃO 5: Usar o modelo correto (Produto ao invés de Servico)
    produto = get_object_or_404(Produto, id=id)

    if request.method == 'POST':
        produto.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            print("Exclusão bem-sucedida via AJAX")
            return JsonResponse({'success': True})
        messages.success(request, 'Produto excluído com sucesso!')
        return redirect('nova_venda')  # CORREÇÃO 6: Redirect para a página correta

    return redirect('nova_venda')

# PRONTUÁRIOS
@login_required
def lista_prontuarios(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    prontuarios = Prontuario.objects.filter(cliente=cliente).order_by('-data')
    return render(request, 'lista_prontuarios.html', {'cliente': cliente, 'prontuarios': prontuarios})


def novo_prontuario(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == 'POST':
        form = ProntuarioForm(request.POST, request.FILES)
        if form.is_valid():
            prontuario = form.save(commit=False)
            prontuario.criado_por = request.user
            prontuario.sugestao_ia = gerar_sugestao_ia(prontuario.situacao)
            prontuario.cliente = cliente

            # Depuração: Verificar os valores antes de salvar
            print("Cliente:", prontuario.cliente)
            print("Profissional:", prontuario.profissional)
            # Garantir que o profissional foi selecionado
            if not prontuario.profissional:
                messages.error(request, "Por favor, selecione um profissional.")
                return render(request, 'novo_prontuario.html', {'form': form, 'cliente': cliente})
            prontuario.save()
            messages.success(request, "Prontuário criado com sucesso!")
            return redirect('lista_prontuarios', cliente_id=cliente.id)
        else:
            messages.error(request, "Erro ao criar o prontuário. Verifique os dados e tente novamente.")
    else:
        form = ProntuarioForm(initial={'cliente': cliente})

    return render(request, 'novo_prontuario.html', {'form': form, 'cliente': cliente})



@login_required
def listar_horarios_vagos(request):
    # Obter filtros da requisição GET
    profissional_id = request.GET.get('profissional')
    periodo = request.GET.get('periodo', 'semana')  # Padrão: semana
    data_inicio = request.GET.get('data_inicio')

    # Definir data inicial (padrão: hoje)
    data_inicio = parse_date(data_inicio) if data_inicio else timezone.now().date()

    # Definir período (semana ou mês)
    if periodo == 'mes':
        data_fim = data_inicio + timedelta(days=30)
    else:  # semana
        data_fim = data_inicio + timedelta(days=6)

    # Filtrar profissionais do estabelecimento
    profissionais = Profissional.objects.filter(estabelecimento=request.user.estabelecimento)
    profissional = None
    if profissional_id:
        profissional = Profissional.objects.filter(
            id=profissional_id,
            estabelecimento=request.user.estabelecimento
        ).first()

    # Definir horários de funcionamento (ajuste conforme seu modelo)
    HORARIO_INICIO = time(8, 0)  # 8:00
    HORARIO_FIM = time(18, 0)  # 18:00
    INTERVALO = 30  # Intervalos de 30 minutos

    # Gerar lista de horários vagos
    horarios_vagos = []
    current_date = data_inicio
    while current_date <= data_fim:
        # Considerar apenas dias úteis (segunda a sexta, ajuste se necessário)
        if current_date.weekday() < 5:
            current_time = datetime.combine(current_date, HORARIO_INICIO)
            end_time = datetime.combine(current_date, HORARIO_FIM)

            while current_time < end_time:
                slot_time = current_time.time()
                # Verificar se o horário está ocupado
                if profissional:
                    agendamento_exists = Agendamento.objects.filter(
                        profissional=profissional,
                        data=current_date,
                        hora=slot_time
                    ).exists()
                else:
                    agendamento_exists = False

                if not agendamento_exists:
                    horarios_vagos.append({
                        'data': current_date,
                        'hora': slot_time,
                        'profissional': profissional
                    })

                current_time += timedelta(minutes=INTERVALO)

        current_date += timedelta(days=1)

    return render(request, 'listar_horarios_vagos.html', {
        'horarios_vagos': horarios_vagos,
        'profissionais': profissionais,
        'profissional_filtro': profissional_id,
        'data_inicio': data_inicio.strftime('%Y-%m-%d'),
        'periodo': periodo,
    })



# EXPORTAÇÃO CSV
def exportar_clientes(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="clientes.csv"'
    writer = csv.writer(response)
    writer.writerow(['Nome', 'Email', 'Telefone'])
    for cliente in Cliente.objects.all():
        writer.writerow([cliente.nome, cliente.email, cliente.telefone])
    return response

def exportar_profissionais(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="profissionais.csv"'
    writer = csv.writer(response)
    writer.writerow(['Nome', 'Especialidade'])
    for profissional in Profissional.objects.all():
        writer.writerow([profissional.nome, profissional.especialidade])
    return response

def exportar_servicos(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="servicos.csv"'
    writer = csv.writer(response)
    writer.writerow(['Nome', 'Especialidade'])
    for servico in Servico.objects.all():
        writer.writerow([servico.nome, servico.especialidade])
    return response


def exportar_agendamentos(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="agendamentos.csv"'
    writer = csv.writer(response)
    writer.writerow(['Data', 'Hora', 'Cliente', 'Profissional', 'Serviço', 'Valor', 'Comissão Profissional', 'Status'])
    for agendamento in Agendamento.objects.all().order_by('data', 'hora'):
        writer.writerow([
            agendamento.data,
            agendamento.hora,
            agendamento.cliente.nome,
            agendamento.profissional.nome,
            agendamento.servico.nome,
            agendamento.valor,
            agendamento.valor_profissional,
            agendamento.status
        ])
    return response


def editar_agendamento(request, pk):
    agendamento = get_object_or_404(Agendamento, pk=pk)
    clientes = Cliente.objects.all()
    profissionais = Profissional.objects.all()
    servicos = Servico.objects.all()

    if request.method == 'POST':
        request.POST = request.POST.copy()
        agendamento.cliente_id = request.POST.get('cliente')
        agendamento.profissional_id = request.POST.get('profissional')
        agendamento.servico_id = request.POST.get('servico')
        agendamento.data = request.POST.get('data')
        agendamento.hora = request.POST.get('hora')
        agendamento.status = request.POST.get('status')
        agendamento.forma_pagamento = request.POST.get('forma_pagamento')
        agendamento.save()
        return redirect('listar_agendamentos')
        # Resolver nomes para IDs
        cliente_nome = request.POST.get('cliente')
        if cliente_nome:
            cliente = Cliente.objects.filter(nome__iexact=cliente_nome.strip()).first()
            if cliente:
                request.POST['cliente'] = str(cliente.id)
            else:
                messages.error(request, 'Cliente não encontrado.')
                return render(request, 'editar_agendamento.html', {'form': AgendamentoForm(request.POST, instance=agendamento), 'agendamento': agendamento})

        profissional_nome = request.POST.get('profissional')
        if profissional_nome:
            profissional = Profissional.objects.filter(nome__iexact=profissional_nome.strip()).first()
            if profissional:
                request.POST['profissional'] = str(profissional.id)
            else:
                messages.error(request, 'Profissional não encontrado.')
                return render(request, 'editar_agendamento.html', {'form': AgendamentoForm(request.POST, instance=agendamento), 'agendamento': agendamento})

        servico_nome = request.POST.get('servico')
        if servico_nome:
            servico = Servico.objects.filter(nome__iexact=servico_nome.strip()).first()
            if servico:
                request.POST['servico'] = str(servico.id)
            else:
                messages.error(request, 'Serviço não encontrado.')
                return render(request, 'editar_agendamento.html', {'form': AgendamentoForm(request.POST, instance=agendamento), 'agendamento': agendamento})

        form = AgendamentoForm(request.POST, instance=agendamento)
        if form.is_valid():
            agendamento = form.save(commit=False)

            # Reatribuir objetos diretamente (opcional, mas seguro)
            agendamento.cliente = cliente
            agendamento.profissional = profissional
            agendamento.servico = servico

            # Atualiza valor do profissional, se aplicável
            if agendamento.valor and profissional and profissional.percentual_comissao:
                agendamento.valor_profissional = agendamento.valor * (profissional.percentual_comissao / 100)
            else:
                agendamento.valor_profissional = 0

            agendamento.save()
            messages.success(request, 'Agendamento atualizado com sucesso!')
            return redirect('listar_agendamentos')
        else:
            messages.error(request, 'Erro ao atualizar o agendamento.')
    else:
        form = AgendamentoForm(instance=agendamento)

    # Dados para o JavaScript
    servicos_data = [
        {
            'id': s.id,
            'nome': s.nome,
            'duracao': int((s.duracao.hour * 3600 + s.duracao.minute * 60 + s.duracao.second) // 60) if s.duracao else 0,
            'valor': float(s.valor or 0)
        } for s in Servico.objects.all()
    ]

    profissionais_data = [
        {
            'id': p.id,
            'nome': p.nome,
            'percentual': float(p.percentual_comissao or 0)
        } for p in Profissional.objects.all()
    ]

    clientes_data = [
        {'id': c.id, 'nome': c.nome}
        for c in Cliente.objects.all()
    ]

    return render(request, 'editar_agendamento.html', {
        'form': form,
        'agendamento': agendamento,
        'servicos_data': json.dumps(servicos_data),
        'profissionais_data': json.dumps(profissionais_data),
        'clientes_data': json.dumps(clientes_data),
    })

def cancelar_agendamento(request, pk):
    agendamento = get_object_or_404(Agendamento, pk=pk)
    agendamento.delete()
    messages.success(request, 'Agendamento cancelado com sucesso.')
    return redirect('listar_agendamentos')


def criar_cliente(request):
    if request.method == "POST":
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save(commit=False)
            cliente.estabelecimento = request.user.estabelecimento
            cliente.save()
            return redirect('lista_clientes')


def lista_clientes(request):
    estabelecimento = request.user.estabelecimento
    clientes = Cliente.objects.filter(estabelecimento=estabelecimento)
    return render(request, 'core/clientes.html', {'clientes': clientes})


def __init__(self, *args, **kwargs):
    estabelecimento = kwargs.pop('estabelecimento', None)
    super().__init__(*args, **kwargs)

    if estabelecimento:
        self.fields['cliente'].queryset = Cliente.objects.filter(estabelecimento=estabelecimento)
        self.fields['profissional'].queryset = Profissional.objects.filter(estabelecimento=estabelecimento)
        self.fields['servico'].queryset = Servico.objects.filter(estabelecimento=estabelecimento)


def baixar_prontuario_pdf(request, agendamento_id):
    ag = get_object_or_404(Agendamento, id=agendamento_id)
    prontuario = Prontuario.objects.filter(agendamento=ag).first()

    # Buffer em memória
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Margens
    margin_left = 2 * cm
    margin_right = width - 2 * cm
    y = height - 2 * cm

    # ===== FUNÇÃO AUXILIAR PARA TEXTO CENTRALIZADO =====
    def draw_centered_text(canvas, y_pos, text, font="Helvetica", size=12):
        canvas.setFont(font, size)
        text_width = canvas.stringWidth(text, font, size)
        x_centered = (width - text_width) / 2
        canvas.drawString(x_centered, y_pos, text)
        return y_pos

    # ===== CABEÇALHO =====
    p.setFillColor(colors.HexColor("#007bff"))
    y = draw_centered_text(p, y, "📋 PRONTUÁRIO MÉDICO", "Helvetica-Bold", 18)
    y -= 0.7 * cm

    p.setFillColor(colors.black)
    y = draw_centered_text(p, y, f"{ag.cliente.nome}", "Helvetica-Bold", 14)
    y -= 0.5 * cm

    p.setFillColor(colors.grey)
    now = datetime.now()
    y = draw_centered_text(p, y, f"Gerado em {now.strftime('%d/%m/%Y às %H:%M')}", "Helvetica", 10)
    y -= 1 * cm

    # Linha separadora
    p.setStrokeColor(colors.HexColor("#007bff"))
    p.setLineWidth(2)
    p.line(margin_left, y, margin_right, y)
    y -= 1.5 * cm

    # ===== FUNÇÃO PARA CRIAR SEÇÕES =====
    def criar_secao(titulo, y_pos):
        # Verificar se há espaço na página
        if y_pos < 5 * cm:
            p.showPage()
            y_pos = height - 2 * cm

        # Fundo da seção
        p.setFillColor(colors.HexColor("#f0f8ff"))
        p.rect(margin_left, y_pos - 0.8 * cm, margin_right - margin_left, 0.6 * cm, fill=1, stroke=1)

        # Título da seção
        p.setFillColor(colors.HexColor("#007bff"))
        p.setFont("Helvetica-Bold", 12)
        p.drawString(margin_left + 0.3 * cm, y_pos - 0.5 * cm, titulo)

        p.setFillColor(colors.black)
        return y_pos - 1.2 * cm

    # ===== FUNÇÃO PARA QUEBRAR TEXTO EM LINHAS =====
    def quebrar_texto(texto, max_chars=80):
        if not texto:
            return [""]
        linhas = []
        for linha in str(texto).split('\n'):
            while len(linha) > max_chars:
                pos_quebra = linha.rfind(' ', 0, max_chars)
                if pos_quebra == -1:
                    pos_quebra = max_chars
                linhas.append(linha[:pos_quebra])
                linha = linha[pos_quebra:].lstrip()
            linhas.append(linha)
        return linhas

    # ===== DADOS DO PACIENTE =====
    y = criar_secao("👤 DADOS DO PACIENTE", y)

    p.setFont("Helvetica", 10)
    col1_x = margin_left + 0.3 * cm
    col2_x = width / 2 + 0.5 * cm

    # Dados básicos do paciente
    dados_esquerda = [
        f"Nome Completo: {ag.cliente.nome}",
        f"CPF: {getattr(ag.cliente, 'cpf', 'Não informado') or 'Não informado'}",
        f"Data de Nascimento: {ag.cliente.nascimento.strftime('%d/%m/%Y') if ag.cliente.nascimento else 'Não informado'}",
        f"Idade: {getattr(ag.cliente, 'idade', 'Não informada')} anos" if hasattr(ag.cliente,
                                                                                  'idade') else "Idade: Não informada",
    ]

    dados_direita = [
        f"Email: {getattr(ag.cliente, 'email', 'Não informado') or 'Não informado'}",
        f"Telefone: {getattr(ag.cliente, 'telefone', 'Não informado') or 'Não informado'}",
        f"Endereço: {getattr(ag.cliente, 'endereco', 'Não informado') or 'Não informado'}",
        ""  # Linha vazia para balancear
    ]

    # Desenhar dados em duas colunas
    for i, (esq, dir) in enumerate(zip(dados_esquerda, dados_direita)):
        if y < 3 * cm:
            p.showPage()
            y = height - 2 * cm
        p.drawString(col1_x, y, esq)
        if dir.strip():
            p.drawString(col2_x, y, dir)
        y -= 0.5 * cm

    y -= 0.5 * cm

    # ===== DADOS DO ATENDIMENTO =====
    y = criar_secao("🏥 DADOS DO ATENDIMENTO", y)

    dados_atendimento_esq = [
        f"Data: {ag.data.strftime('%d/%m/%Y')}",
        f"Horário: {ag.hora.strftime('%H:%M') if ag.hora else 'Não informado'}",
        f"Profissional: {prontuario.profissional.nome if prontuario and hasattr(prontuario, 'profissional') and prontuario.profissional else ag.profissional.nome}",
    ]

    dados_atendimento_dir = [
        f"Serviço: {ag.servico.nome}",
        f"Status: {ag.status.replace('_', ' ').title()}",
        f"Pagamento: {ag.forma_pagamento.replace('_', ' ').title() if ag.forma_pagamento else 'Não informado'}",
    ]

    for i, (esq, dir) in enumerate(zip(dados_atendimento_esq, dados_atendimento_dir)):
        if y < 3 * cm:
            p.showPage()
            y = height - 2 * cm
        p.drawString(col1_x, y, esq)
        p.drawString(col2_x, y, dir)
        y -= 0.5 * cm

    y -= 0.5 * cm

    # ===== PRONTUÁRIO MÉDICO =====
    if prontuario:
        y = criar_secao("📝 PRONTUÁRIO MÉDICO", y)

        # Anotações
        if hasattr(prontuario, 'descricao') and prontuario.descricao:
            if y < 4 * cm:
                p.showPage()
                y = height - 2 * cm

            p.setFont("Helvetica-Bold", 10)
            p.drawString(col1_x, y, "Anotações / Evolução:")
            y -= 0.5 * cm

            p.setFont("Helvetica", 9)
            linhas = quebrar_texto(prontuario.descricao, 85)
            for linha in linhas:
                if y < 2 * cm:
                    p.showPage()
                    y = height - 2 * cm
                p.drawString(col1_x, y, linha)
                y -= 0.4 * cm
            y -= 0.3 * cm

        # Observações
        if hasattr(prontuario, 'observacoes') and prontuario.observacoes:
            if y < 4 * cm:
                p.showPage()
                y = height - 2 * cm

            p.setFont("Helvetica-Bold", 10)
            p.drawString(col1_x, y, "Observações:")
            y -= 0.5 * cm

            p.setFont("Helvetica", 9)
            linhas = quebrar_texto(prontuario.observacoes, 85)
            for linha in linhas:
                if y < 2 * cm:
                    p.showPage()
                    y = height - 2 * cm
                p.drawString(col1_x, y, linha)
                y -= 0.4 * cm
            y -= 0.3 * cm

        # Tags
        if hasattr(prontuario, 'tags') and prontuario.tags:
            if y < 2 * cm:
                p.showPage()
                y = height - 2 * cm
            p.setFont("Helvetica-Bold", 10)
            p.drawString(col1_x, y, f"Tags: {prontuario.tags}")
            y -= 0.6 * cm

        # Data do registro
        if hasattr(prontuario, 'data') and prontuario.data:
            if y < 2 * cm:
                p.showPage()
                y = height - 2 * cm
            p.setFont("Helvetica", 9)
            p.setFillColor(colors.grey)
            p.drawString(col1_x, y, f"Registrado em: {prontuario.data.strftime('%d/%m/%Y às %H:%M')}")
            p.setFillColor(colors.black)
            y -= 0.8 * cm

        # Anexos (apenas informar se existem)
        anexos = []
        if hasattr(prontuario, 'imagem') and prontuario.imagem:
            anexos.append("Imagem anexada")
        if hasattr(prontuario, 'anexo') and prontuario.anexo:
            try:
                nome_arquivo = prontuario.anexo.name.split('/')[-1] if hasattr(prontuario.anexo,
                                                                               'name') else "Documento anexado"
                anexos.append(f"Arquivo: {nome_arquivo}")
            except:
                anexos.append("Documento anexado")

        if anexos:
            y = criar_secao("📎 ANEXOS", y)
            for anexo in anexos:
                if y < 2 * cm:
                    p.showPage()
                    y = height - 2 * cm
                p.setFont("Helvetica", 10)
                p.drawString(col1_x, y, f"• {anexo}")
                y -= 0.5 * cm

    else:
        y = criar_secao("📝 PRONTUÁRIO MÉDICO", y)
        p.setFont("Helvetica", 10)
        p.setFillColor(colors.grey)
        p.drawString(col1_x, y, "Nenhum prontuário médico foi registrado para este atendimento.")
        p.setFillColor(colors.black)
        y -= 1 * cm

    # ===== RODAPÉ =====
    # Ir para o final da página
    y = 2.5 * cm

    # Linha separadora
    p.setStrokeColor(colors.grey)
    p.setLineWidth(1)
    p.line(margin_left, y, margin_right, y)
    y -= 0.5 * cm

    # Texto do rodapé
    p.setFont("Helvetica", 8)
    p.setFillColor(colors.grey)

    texto1 = f"Documento gerado automaticamente pelo sistema em {now.strftime('%d/%m/%Y às %H:%M')}"
    draw_centered_text(p, y, texto1, "Helvetica", 8)
    y -= 0.4 * cm

    texto2 = "Este documento contém informações confidenciais e deve ser tratado de acordo com a LGPD"
    draw_centered_text(p, y, texto2, "Helvetica", 8)

    # Finalizar PDF
    p.showPage()
    p.save()

    # Preparar resposta
    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf, content_type='application/pdf')
    nome_arquivo = ag.cliente.nome.replace(" ", "_").replace(".", "")
    response['Content-Disposition'] = f'attachment; filename="prontuario_{nome_arquivo}.pdf"'
    return response
@require_POST
def editar_prontuario(request, agendamento_id):
    ag = get_object_or_404(Agendamento, id=agendamento_id)
    ag.prontuario = request.POST.get('prontuario', '')
    ag.save()
    return redirect('listar_agendamentos')  # ou usa redirect(request.META.get('HTTP_REFERER', '/'))

@require_POST
def salvar_prontuario(request, agendamento_id):
    ag = get_object_or_404(Agendamento, id=agendamento_id)
    cliente = ag.cliente
    profissional = ag.profissional
    estab = ag.estabelecimento

    descricao    = request.POST.get('descricao', '').strip()
    observacoes  = request.POST.get('observacoes', '').strip()
    tags         = request.POST.get('tags', '').strip()
    arquivo      = request.FILES.get('anexo')      # nome de campo no form
    imagem       = request.FILES.get('imagem')

    prontuario, created = Prontuario.objects.get_or_create(
        agendamento=ag,
        defaults={
            'cliente': cliente,
            'profissional': profissional,
            'estabelecimento': estab,
            'descricao': descricao,
            'observacoes': observacoes,
            'tags': tags,
            'arquivos': arquivo,
            'imagem': imagem,
        }
    )

    if not created:
        prontuario.descricao   = descricao
        prontuario.observacoes = observacoes
        prontuario.tags        = tags
        if arquivo:  prontuario.arquivos = arquivo
        if imagem:   prontuario.imagem   = imagem
        prontuario.save()

    messages.success(request, "Prontuário salvo com sucesso!")
    return redirect('listar_agendamentos')


from xhtml2pdf import pisa

def exportar_painel_pdf(request, contexto=None):
    # (mesma lógica de filtragem da view acima)
    # Renderiza o mesmo contexto do painel

    template = get_template('painel_pdf.html')
    html = template.render(contexto)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="painel_admin.pdf"'
    pisa.CreatePDF(html, dest=response)
    return response


def listar_estabelecimentos(request):
    estabelecimentos = Estabelecimento.objects.all().order_by('-criado_em')
    return render(request, 'estabelecimentos/lista.html', {'estabelecimentos': estabelecimentos})


@receiver(post_save, sender=User)
def criar_estabelecimento_automatico(sender, instance, created, **kwargs):
    if created and instance.is_superuser:
        if not hasattr(instance, 'estabelecimento'):
            Estabelecimento.objects.create(
                usuario=instance,
                nome='Administrador',
                plano='empresarial',
                ativo=True
            )


@receiver(post_save, sender=User)
def criar_estabelecimento_para_superuser(sender, instance, created, **kwargs):
    if created and instance.is_superuser:
        if not hasattr(instance, 'estabelecimento'):
            Estabelecimento.objects.create(
                nome="Administrador",
                email=instance.email,
                usuario=instance,
                plano='empresarial',  # ou qualquer padrão
                ativo=True,
            )


@login_required
def gerar_pdf_horarios_vagos(request):
    # Obter filtros da requisição GET
    profissional_id = request.GET.get('profissional')
    periodo = request.GET.get('periodo', 'semana')
    data_inicio = request.GET.get('data_inicio')

    # Definir data inicial (padrão: hoje)
    data_inicio = parse_date(data_inicio) if data_inicio else timezone.now().date()

    # Definir período
    if periodo == 'mes':
        data_fim = data_inicio + timedelta(days=30)
    else:
        data_fim = data_inicio + timedelta(days=6)

    # Filtrar profissionais
    profissionais = Profissional.objects.filter(estabelecimento=request.user.estabelecimento)
    profissional = None
    if profissional_id:
        profissional = Profissional.objects.filter(
            id=profissional_id,
            estabelecimento=request.user.estabelecimento
        ).first()

    # Definir horários de funcionamento (ajuste conforme necessário)
    HORARIO_INICIO = time(8, 0)
    HORARIO_FIM = time(18, 0)
    INTERVALO = 30

    # Gerar lista de horários vagos
    horarios_vagos = []
    current_date = data_inicio
    while current_date <= data_fim:
        if current_date.weekday() < 5:
            current_time = datetime.combine(current_date, HORARIO_INICIO)
            end_time = datetime.combine(current_date, HORARIO_FIM)

            while current_time < end_time:
                slot_time = current_time.time()
                if profissional:
                    agendamento_exists = Agendamento.objects.filter(
                        profissional=profissional,
                        data=current_date,
                        hora=slot_time
                    ).exists()
                else:
                    agendamento_exists = False

                if not agendamento_exists:
                    horarios_vagos.append({
                        'data': current_date,
                        'hora': slot_time,
                        'profissional': profissional
                    })

                current_time += timedelta(minutes=INTERVALO)

        current_date += timedelta(days=1)

    # Configurar resposta HTTP para o PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="horarios_vagos_{data_inicio.strftime("%Y%m%d")}.pdf"'

    # Criar o documento PDF
    doc = SimpleDocTemplate(response, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # Título do PDF
    title = Paragraph(f"Horários Disponíveis - {request.user.estabelecimento.nome}", styles['Title'])
    elements.append(title)

    # Subtítulo com filtros
    filtro_texto = f"Período: {'Mensal' if periodo == 'mes' else 'Semanal'} | Data Início: {data_inicio.strftime('%d/%m/%Y')}"
    if profissional:
        filtro_texto += f" | Profissional: {profissional.nome}"
    elements.append(Paragraph(filtro_texto, styles['Normal']))
    elements.append(Paragraph("<br/>", styles['Normal']))  # Espaço

    # Dados da tabela
    data = [['Data', 'Hora', 'Profissional']]
    for slot in horarios_vagos:
        data.append([
            slot['data'].strftime('%d/%m/%Y'),
            slot['hora'].strftime('%H:%M'),
            slot['profissional'].nome if slot['profissional'] else 'Qualquer'
        ])

    # Criar tabela
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)

    # Gerar o PDF
    doc.build(elements)
    return response

def editar_plano(request, plano_id):
    plano = get_object_or_404(Plano, id=plano_id)
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        valor = request.POST.get('valor', '').strip()

        # Validação do campo nome
        if not nome:
            messages.error(request, 'O campo Nome do Plano é obrigatório.')
            return render(request, 'editar_plano.html', {'plano': plano})

        try:
            plano.nome = nome
            if valor:
                plano.valor = float(valor)
            else:
                plano.valor = None  # Mantém "Sob consulta"
            plano.save()
            messages.success(request, 'Plano atualizado com sucesso!')
            return redirect('painel_administrador')
        except ValueError:
            messages.error(request, 'Valor inválido. Use um número válido (ex.: 500.00).')
            return render(request, 'editar_plano.html', {'plano': plano})
    return render(request, 'editar_plano.html', {'plano': plano})
def excluir_plano(request, plano_id):
    plano = get_object_or_404(Plano, id=plano_id)
    if Assinatura.objects.filter(plano=plano).exists():
        messages.error(request, 'Não é possível excluir o plano porque ele está associado a assinaturas.')
        return redirect('dashboard_financeiro')
    if request.method == 'POST':
        plano.delete()
        messages.success(request, 'Plano excluído com sucesso!')
        return redirect('dashboard_financeiro')
    return render(request, 'confirmar_exclusao_plano.html', {'plano': plano})


@login_required
def nova_venda(request):
    try:
        estabelecimento = request.user.estabelecimento
    except AttributeError:
        messages.error(request, "Seu usuário não está vinculado a um estabelecimento.")
        return redirect('dashboard')

    clientes_data = [{'id': c.id, 'nome': c.nome} for c in Cliente.objects.filter(estabelecimento=estabelecimento)]
    produtos_data = [
        {'id': p.id, 'nome': p.nome, 'quantidade': p.quantidade, 'preco': float(p.preco_unitario or 0)}
        for p in Produto.objects.filter(estabelecimento=estabelecimento)
    ]
    vendas_data = [
        {
            'id': v.id,
            'cliente': {'nome': v.cliente.nome} if v.cliente else None,
            'criado_em': v.criado_em,
            'valor_total': float(v.valor_total),
            'forma_pagamento': v.forma_pagamento
        }
        for v in Venda.objects.filter(estabelecimento=estabelecimento).order_by('-criado_em')
    ]
    logger.info(f"Produtos data em nova_venda: {produtos_data}")

    if request.method == 'POST':
        with transaction.atomic():
            cliente_nome = request.POST.get('cliente', '').strip()
            cliente = None
            if cliente_nome:
                cliente = Cliente.objects.filter(nome__iexact=cliente_nome, estabelecimento=estabelecimento).first()
                if not cliente:
                    return JsonResponse({'success': False, 'message': 'Cliente não encontrado.'})

            produtos_selecionados = request.POST.get('produtos_selecionados', '[]')
            metodo_pagamento = request.POST.get('metodo_pagamento', '')
            logger.info(f"Produtos selecionados: {produtos_selecionados}")

            try:
                produtos_selecionados = json.loads(produtos_selecionados)
                if not produtos_selecionados:
                    return JsonResponse({'success': False, 'message': 'Selecione pelo menos um produto.'})

                venda = Venda.objects.create(
                    cliente=cliente,
                    estabelecimento=estabelecimento,
                    forma_pagamento=metodo_pagamento,
                    valor_total=0
                )

                total = 0
                for item in produtos_selecionados:
                    produto_id = item['id']
                    quantidade = int(item['quantidade'])
                    produto = Produto.objects.get(id=produto_id, estabelecimento=estabelecimento)
                    if produto.quantidade >= quantidade:
                        produto.quantidade -= quantidade
                        produto.save()
                        MovimentacaoEstoque.objects.create(
                            produto=produto,
                            tipo='SAIDA',
                            quantidade=quantidade,
                            observacao=f'Venda {venda.id}'
                        )
                        VendaProduto.objects.create(
                            venda=venda,
                            produto=produto,
                            quantidade=quantidade,
                            preco_unitario=produto.preco_unitario
                        )
                        total += quantidade * produto.preco_unitario
                    else:
                        venda.delete()
                        return JsonResponse({'success': False, 'message': f'Estoque insuficiente para {produto.nome}.'})

                venda.valor_total = total
                venda.save()

                if metodo_pagamento == 'PAGBANK':
                    try:
                        item = PagSeguroItem(
                            id=str(venda.id),
                            description=f'Venda de produtos #{venda.id}',
                            amount=float(total),
                            quantity=1
                        )
                        pagseguro = PagSeguroApi(
                            email=settings.PAGSEGURO_EMAIL,
                            token=settings.PAGSEGURO_TOKEN,
                            sandbox=settings.PAGSEGURO_SANDBOX
                        )
                        pagseguro.add_item(item)
                        checkout = pagseguro.checkout()
                        if checkout['success']:
                            PagBankTransaction.objects.create(
                                venda=venda,
                                codigo_transacao=checkout['code'],
                                status='AGUARDANDO',
                                valor=total
                            )
                            return JsonResponse({'success': True, 'redirect_url': checkout['redirect_url']})
                        else:
                            logger.error(f"Erro no checkout PagBank: {checkout}")
                            venda.delete()
                            return JsonResponse({'success': False, 'message': 'Erro ao processar pagamento PagBank.'})
                    except Exception as e:
                        logger.error(f"Erro ao iniciar PagBank: {e}")
                        venda.delete()
                        return JsonResponse({'success': False, 'message': 'Erro ao processar PagBank.'})

                # Retornar URL do PDF para download
                pdf_url = reverse('gerar_nota_venda_pdf', kwargs={'venda_id': venda.id})
                return JsonResponse({'success': True, 'pdf_url': pdf_url})
            except (ValueError, KeyError, Produto.DoesNotExist) as e:
                logger.error(f"Erro ao processar venda: {e}")
                return JsonResponse({'success': False, 'message': 'Erro ao processar produtos.'})

    return render(request, 'nova_venda.html', {
        'clientes_data': clientes_data,
        'produtos_data': produtos_data,
        'vendas_data': vendas_data,
        'form': ProdutoForm()
    })


@login_required
def gerar_nota_venda_pdf(request, venda_id):
    logger.info(f"Tentando gerar PDF para venda_id: {venda_id}")
    try:
        venda = Venda.objects.get(id=venda_id, estabelecimento=request.user.estabelecimento)
        logger.info(f"Venda encontrada: {venda.id}")
    except Venda.DoesNotExist:
        logger.error(f'Venda {venda_id} não encontrada.')
        messages.error(request, 'Venda não encontrada.')
        return redirect('nova_venda')

    # Configurar resposta HTTP para o PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="nota_venda_{venda.id}_{timezone.now().strftime("%Y%m%d")}.pdf"'

    # Criar o documento PDF
    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm
    )
    elements = []
    styles = getSampleStyleSheet()

    # Título da nota
    title = Paragraph(
        f"Nota de Venda - {request.user.estabelecimento.nome}",
        styles['Title']
    )
    elements.append(title)
    elements.append(Spacer(1, 0.5 * cm))

    # Informações do estabelecimento
    empresa_info = [
        Paragraph(f"CNPJ: {request.user.estabelecimento.cnpj or 'Não informado'}", styles['Normal']),
        Paragraph(f"E-mail: {request.user.estabelecimento.email or 'contato@estabelecimento.com'}", styles['Normal']),
    ]
    for info in empresa_info:
        elements.append(info)
    elements.append(Spacer(1, 0.5 * cm))

    # Informações da venda
    venda_info = [
        Paragraph(f"<b>Número da Venda:</b> {venda.id}", styles['Normal']),
        Paragraph(f"<b>Data:</b> {venda.criado_em.strftime('%d/%m/%Y %H:%M')}", styles['Normal']),
        Paragraph(f"<b>Cliente:</b> {venda.cliente.nome if venda.cliente else 'Sem cliente'}", styles['Normal']),
    ]
    for info in venda_info:
        elements.append(info)
    elements.append(Spacer(1, 1 * cm))

    # Dados da tabela de produtos
    data = [['Produto', 'Quantidade', 'Preço Unitário (R$)', 'Total (R$)']]
    for item in venda.produtos.all():
        data.append([
            item.produto.nome,
            str(item.quantidade),
            f"R$ {item.preco_unitario:.2f}",
            f"R$ {(item.quantidade * item.preco_unitario):.2f}"
        ])

    # Criar a tabela
    table = Table(data, colWidths=[6 * cm, 3 * cm, 4 * cm, 4 * cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a00e0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.5 * cm))

    # Adicionar valor total
    total_paragraph = Paragraph(
        f"<b>Total da Venda:</b> R$ {venda.valor_total:.2f}",
        styles['Normal']
    )
    elements.append(total_paragraph)
    elements.append(Spacer(1, 0.5 * cm))

    # Adicionar data de geração
    data_geracao = Paragraph(
        f"Gerado em: {timezone.now().strftime('%d/%m/%Y %H:%M')}",
        styles['Normal']
    )
    elements.append(data_geracao)

    # Função para adicionar rodapé
    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.drawString(2 * cm, 1 * cm, f"Página {doc.page}")
        canvas.drawRightString(19 * cm, 1 * cm, f"Gerado por {request.user.estabelecimento.nome}")
        canvas.restoreState()

    # Gerar o PDF
    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)
    logger.info(f"PDF gerado com sucesso: nota_venda_{venda.id}.pdf")
    return response


@login_required
def gerenciar_estoque(request):
    estabelecimento = request.user.estabelecimento
    produtos = Produto.objects.filter(estabelecimento=estabelecimento)

    if request.method == 'POST':
        if 'adicionar_produto' in request.POST:
            nome = request.POST.get('nome')
            codigo = request.POST.get('codigo')
            quantidade = request.POST.get('quantidade')
            estoque_minimo = request.POST.get('estoque_minimo')
            preco_unitario = request.POST.get('preco_unitario')

            try:
                produto = Produto(
                    nome=nome,
                    codigo=codigo or None,
                    quantidade=int(quantidade),
                    estoque_minimo=int(estoque_minimo),
                    preco_unitario=float(preco_unitario) if preco_unitario else None,
                    estabelecimento=estabelecimento
                )
                produto.save()
                MovimentacaoEstoque.objects.create(
                    produto=produto,
                    tipo='ENTRADA',
                    quantidade=int(quantidade),
                    observacao='Adição inicial'
                )
                messages.success(request, 'Produto adicionado com sucesso!')
            except ValueError:
                messages.error(request, 'Dados inválidos. Verifique os campos.')

        elif 'movimentar_estoque' in request.POST:
            produto_id = request.POST.get('produto_id')
            tipo = request.POST.get('tipo')
            quantidade = request.POST.get('quantidade_mov')
            observacao = request.POST.get('observacao')

            try:
                produto = get_object_or_404(Produto, id=produto_id, estabelecimento=estabelecimento)
                quantidade = int(quantidade)
                if tipo == 'SAIDA' and produto.quantidade < quantidade:
                    messages.error(request, 'Estoque insuficiente!')
                else:
                    produto.quantidade += quantidade if tipo == 'ENTRADA' else -quantidade
                    produto.save()
                    MovimentacaoEstoque.objects.create(
                        produto=produto,
                        tipo=tipo,
                        quantidade=quantidade,
                        observacao=observacao
                    )
                    messages.success(request, 'Movimentação registrada!')
            except ValueError:
                messages.error(request, 'Quantidade inválida.')

        return redirect('gerenciar_estoque')

    return render(request, 'gerenciar_estoque.html', {'produtos': produtos})

 # INTEGRACAO COM A PAGBANK
def validar_cpf(cpf):
    """Valida CPF brasileiro"""
    if not cpf:
        return False

    cpf = re.sub(r'[^0-9]', '', cpf)

    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    # Primeiro dígito
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    primeiro_digito = (soma * 10) % 11
    if primeiro_digito == 10:
        primeiro_digito = 0

    if int(cpf[9]) != primeiro_digito:
        return False

    # Segundo dígito
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    segundo_digito = (soma * 10) % 11
    if segundo_digito == 10:
        segundo_digito = 0

    return int(cpf[10]) == segundo_digito


def validar_cnpj(cnpj):
    """Valida CNPJ brasileiro"""
    if not cnpj:
        return False

    cnpj = re.sub(r'[^0-9]', '', cnpj)

    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False

    # Primeiro dígito
    multiplicadores = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * multiplicadores[i] for i in range(12))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto

    if int(cnpj[12]) != digito1:
        return False

    # Segundo dígito
    multiplicadores = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * multiplicadores[i] for i in range(13))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto

    return int(cnpj[13]) == digito2


def limpar_documento(documento):
    """Remove caracteres não numéricos"""
    if not documento:
        return None
    return re.sub(r'[^0-9]', '', documento)


def preparar_telefone(telefone):
    """Prepara telefone para a API"""
    if not telefone:
        return "98", "984890275"

    telefone_limpo = re.sub(r'[^0-9]', '', telefone)

    if telefone_limpo.startswith('0') and len(telefone_limpo) == 12:
        telefone_limpo = telefone_limpo[1:]

    if len(telefone_limpo) == 11:
        return telefone_limpo[:2], telefone_limpo[2:]
    elif len(telefone_limpo) == 10:
        return telefone_limpo[:2], telefone_limpo[2:]
    else:
        return "98", "984890275"


def get_pagbank_config():
    """Retorna configurações do PagBank - VERSÃO CORRIGIDA"""
    return {
        'token': settings.PAGBANK.get('TOKEN', ''),
        'public_key': settings.PAGBANK.get('PUBLIC_KEY', ''),
        'sandbox': settings.PAGBANK.get('SANDBOX', True),
        'api_url': settings.PAGBANK.get('API_URL', 'https://sandbox.api.pagseguro.com'),
        'email': settings.PAGBANK.get('EMAIL', '')
    }


def create_pagbank_payment(payment_data):
    """Cria pagamento no PagBank"""
    config = get_pagbank_config()
    url = f"{config['api_url']}/orders"

    headers = {
        'accept': 'application/json',
        'Authorization': f"Bearer {config['token']}",
        'content-type': 'application/json'
    }

    try:
        logger.info(f"Enviando para PagBank: {url}")
        logger.info(f"Data: {json.dumps(payment_data, indent=2)}")

        response = requests.post(url, json=payment_data, headers=headers, timeout=30)

        logger.info(f"Status: {response.status_code}")
        logger.info(f"Response: {response.text}")

        if response.status_code in [200, 201]:
            return {
                'success': True,
                'data': response.json(),
                'status_code': response.status_code
            }
        else:
            return {
                'success': False,
                'error': response.text,
                'status_code': response.status_code
            }

    except requests.exceptions.RequestException as e:
        logger.error(f"Erro na requisição PagBank: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'status_code': 0
        }

def create_pagbank_order(payment_data):
    """Cria uma ordem de pagamento no PagBank"""
    headers = {
        'Authorization': f'Bearer {settings.PAGBANK_TOKEN}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'x-idempotency-key': f"KEY-{int(time.time() * 1000)}"
    }

    # URL da API
    if settings.PAGBANK_SANDBOX:
        url = 'https://sandbox.api.pagseguro.com/orders'
    else:
        url = 'https://api.pagseguro.com/orders'

    try:
        response = requests.post(url, json=payment_data, headers=headers)
        response_data = response.json()

        if response.status_code in [200, 201]:
            return {
                'success': True,
                'data': response_data,
                'status_code': response.status_code
            }
        else:
            error_msg = 'Erro desconhecido'
            if 'error_messages' in response_data:
                errors = response_data['error_messages']
                if errors:
                    error_msg = errors[0].get('description', error_msg)

            return {
                'success': False,
                'error': error_msg,
                'error_details': response_data,
                'status_code': response.status_code
            }

    except Exception as e:
        logger.error(f"Erro na requisição PagBank: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'status_code': 500
        }


@login_required
def pagamento(request, agendamento_id=None):
    """View principal de pagamento - VERSÃO CORRIGIDA"""
    try:
        estabelecimento = get_object_or_404(Estabelecimento, usuario=request.user)
    except:
        messages.error(request, "Estabelecimento não encontrado.")
        return redirect('dashboard')

    cliente = None
    agendamento = None

    if agendamento_id:
        agendamento = get_object_or_404(Agendamento, id=agendamento_id, estabelecimento=estabelecimento)
        cliente = agendamento.cliente

    # Verificar configuração do PagBank
    config = get_pagbank_config()

    # Log da configuração para debug
    logger.info(f"Config PagBank - Token: {'Configurado' if config['token'] else 'Não configurado'}")
    logger.info(f"Config PagBank - Public Key: {'Configurado' if config['public_key'] else 'Não configurado'}")

    # Contexto inicial
    contexto = {
        'valor': float(agendamento.valor) if agendamento else 0,
        'descricao': f"Agendamento #{agendamento.id} - {agendamento.servico.nome}" if agendamento else 'Pagamento AgendaFlow',
        'agendamento_id': agendamento_id,
        'cliente_nome': cliente.nome if cliente else '',
        'estabelecimento': estabelecimento,
        'pagbank_public_key': config.get('public_key', ''),
        'metodos_pagamento': [
            {'value': 'CREDIT_CARD', 'label': 'Cartão de Crédito'},
            {'value': 'DEBIT_CARD', 'label': 'Cartão de Débito'},
            {'value': 'PIX', 'label': 'PIX'},
            {'value': 'BOLETO', 'label': 'Boleto Bancário'},
        ]
    }

    if request.method == 'GET':
        return render(request, 'pagamento/pagamento.html', contexto)

    # POST - Processar escolha do método
    metodo = request.POST.get('metodo', '').strip()
    valor_form = request.POST.get('valor', contexto['valor'])
    descricao = request.POST.get('descricao', contexto['descricao']).strip()

    # Validações
    if not metodo:
        messages.error(request, "Selecione um método de pagamento.")
        return render(request, 'pagamento/pagamento.html', contexto)

    try:
        valor = float(valor_form)
        if valor <= 0:
            raise ValueError("Valor deve ser maior que zero")
    except (ValueError, TypeError):
        messages.error(request, "Valor inválido.")
        return render(request, 'pagamento/pagamento.html', contexto)

    # Salvar dados na sessão para próximos passos
    request.session['pagamento_data'] = {
        'metodo': metodo,
        'valor': valor,
        'descricao': descricao,
        'agendamento_id': agendamento_id,
        'cliente_id': cliente.id if cliente else None,
        'estabelecimento_id': estabelecimento.id
    }

    logger.info(f"Pagamento iniciado - Método: {metodo}, Valor: {valor}")

    # Redirecionar conforme método escolhido
    if metodo in ['CREDIT_CARD', 'DEBIT_CARD']:
        return redirect('pagamento_cartao')
    elif metodo == 'PIX':
        return redirect('pagamento_pix')
    elif metodo == 'BOLETO':
        return redirect('pagamento_boleto')
    else:
        messages.error(request, "Método de pagamento não suportado.")
        return render(request, 'pagamento/pagamento.html', contexto)


@login_required
def pagamento_cartao(request):
    """View para pagamento com cartão - TIME CORRIGIDO"""
    try:
        # Recuperar dados da sessão
        pagamento_data = request.session.get('pagamento_data')
        if not pagamento_data:
            messages.error(request, "Sessão expirada. Por favor, inicie o pagamento novamente.")
            return redirect('pagamento')

        estabelecimento = get_object_or_404(Estabelecimento, usuario=request.user)
        config = get_pagbank_config()

        if request.method == 'GET':
            # Exibir formulário do cartão
            contexto = {
                'valor': pagamento_data['valor'],
                'valor_formatado': f"R$ {pagamento_data['valor']:.2f}".replace('.', ','),
                'descricao': pagamento_data['descricao'],
                'metodo': pagamento_data['metodo'],
                'pagbank_public_key': config.get('public_key', ''),
                'status': None  # Indica que ainda não processou
            }
            return render(request, 'pagamento/pagamento_cartao.html', contexto)

        # POST - Processar dados do cartão
        logger.info("Processando pagamento com cartão...")

        # Dados básicos do formulário
        encrypted_card = request.POST.get('encrypted_card', '')
        installments = int(request.POST.get('installments', 1))
        card_name = request.POST.get('card_name', '').strip()

        if not card_name:
            messages.error(request, "Nome no cartão é obrigatório.")
            return redirect('pagamento_cartao')

        # ⬅️ CORRIGIDO: usar time_module.time()
        current_timestamp = int(time_module.time())
        reference_id = f"CARD_{current_timestamp}_{estabelecimento.id}"

        # Buscar cliente e agendamento
        cliente = None
        if pagamento_data.get('cliente_id'):
            try:
                cliente = Cliente.objects.get(id=pagamento_data['cliente_id'])
            except Cliente.DoesNotExist:
                pass

        agendamento = None
        if pagamento_data.get('agendamento_id'):
            try:
                agendamento = Agendamento.objects.get(id=pagamento_data['agendamento_id'])
            except Agendamento.DoesNotExist:
                pass

        # Simular resultado do pagamento
        import random
        resultado_simulado = random.choice(['PAID', 'PENDING', 'FAILED'])

        # Criar transação no banco
        with transaction.atomic():
            pagamento_dados = {
                'usuario': request.user,
                'estabelecimento': estabelecimento,
                'cliente': cliente,
                'agendamento': agendamento,
                'valor_total': Decimal(str(pagamento_data['valor'])),
                'metodo': pagamento_data['metodo'],
                'codigo_transacao': reference_id,
                'status': resultado_simulado,
                'descricao': pagamento_data['descricao'],
            }

            if hasattr(PagamentoTransacao, 'gateway_transacao_id'):
                pagamento_dados['gateway_transacao_id'] = reference_id

            pagamento_transacao = PagamentoTransacao.objects.create(**pagamento_dados)

            # Se aprovado, marcar agendamento como pago
            if resultado_simulado == 'PAID' and agendamento:
                agendamento.pago = True
                agendamento.save()

        # Limpar sessão após sucesso
        del request.session['pagamento_data']

        # Mensagens baseadas no resultado
        if resultado_simulado == 'PAID':
            messages.success(request, "Pagamento aprovado com sucesso! (Simulação)")
        elif resultado_simulado == 'PENDING':
            messages.info(request, "Pagamento em análise. Aguarde confirmação. (Simulação)")
        else:
            messages.error(request, "Pagamento recusado. Tente novamente. (Simulação)")

        # Contexto com resultado
        contexto = {
            'pagamento': pagamento_transacao,
            'transaction_id': reference_id,
            'metodo': pagamento_data['metodo'],
            'valor_formatado': f"R$ {pagamento_data['valor']:.2f}".replace('.', ','),
            'valor': pagamento_data['valor'],
            'descricao': pagamento_data['descricao'],
            'status': resultado_simulado
        }

        return render(request, 'pagamento/pagamento_cartao.html', contexto)

    except Exception as e:
        logger.error(f"Erro no pagamento com cartão: {str(e)}", exc_info=True)
        messages.error(request, "Erro interno no processamento do pagamento.")
        return redirect('pagamento_cartao')

@login_required
def pagamento_pix(request):
    """View para pagamento PIX - TIME CORRIGIDO"""
    try:
        # Recuperar dados da sessão
        pagamento_data = request.session.get('pagamento_data')
        if not pagamento_data:
            messages.error(request, "Sessão expirada. Por favor, inicie o pagamento novamente.")
            return redirect('pagamento')

        estabelecimento = get_object_or_404(Estabelecimento, usuario=request.user)

        # ⬅️ CORRIGIDO: usar time_module.time()
        current_timestamp = int(time_module.time())
        reference_id = f"PIX_{current_timestamp}_{estabelecimento.id}"

        # Buscar cliente e agendamento
        cliente = None
        if pagamento_data.get('cliente_id'):
            try:
                cliente = Cliente.objects.get(id=pagamento_data['cliente_id'])
            except Cliente.DoesNotExist:
                pass

        agendamento = None
        if pagamento_data.get('agendamento_id'):
            try:
                agendamento = Agendamento.objects.get(id=pagamento_data['agendamento_id'])
            except Agendamento.DoesNotExist:
                pass

        # Criar transação no banco
        with transaction.atomic():
            pagamento_dados = {
                'usuario': request.user,
                'estabelecimento': estabelecimento,
                'cliente': cliente,
                'agendamento': agendamento,
                'valor_total': Decimal(str(pagamento_data['valor'])),
                'metodo': 'PIX',
                'codigo_transacao': reference_id,
                'status': 'PENDING',
                'descricao': pagamento_data['descricao'],
            }

            if hasattr(PagamentoTransacao, 'gateway_transacao_id'):
                pagamento_dados['gateway_transacao_id'] = reference_id

            pagamento_transacao = PagamentoTransacao.objects.create(**pagamento_dados)

        # Dados do PIX para o template
        pix_data = {
            'text': f'00020126580014BR.GOV.BCB.PIX01361234567890123456789012345015204000053039865406{str(int(pagamento_data["valor"] * 100)).zfill(4)}5802BR5925AGENDAFLOW PAGAMENTOS6009SAO PAULO610805409006207050300004D5AE71E63040C2E'
        }

        contexto = {
            'pagamento': pagamento_transacao,
            'pix_data': pix_data,
            'valor_formatado': f"R$ {pagamento_data['valor']:.2f}".replace('.', ','),
            'transaction_id': reference_id,
            'valor': pagamento_data['valor'],
            'descricao': pagamento_data['descricao']
        }

        messages.success(request, "PIX gerado com sucesso! (Simulação)")
        return render(request, 'pagamento/pagamento_pix.html', contexto)

    except Exception as e:
        logger.error(f"Erro ao processar PIX: {str(e)}", exc_info=True)
        messages.error(request, "Erro ao gerar PIX. Tente novamente.")
        return redirect('pagamento')

@login_required
def pagamento_boleto(request):
    """View para pagamento Boleto - TIME CORRIGIDO"""
    try:
        # Recuperar dados da sessão
        pagamento_data = request.session.get('pagamento_data')
        if not pagamento_data:
            messages.error(request, "Sessão expirada. Por favor, inicie o pagamento novamente.")
            return redirect('pagamento')

        estabelecimento = get_object_or_404(Estabelecimento, usuario=request.user)

        # ⬅️ CORRIGIDO: usar time_module.time()
        current_timestamp = int(time_module.time())
        reference_id = f"BOLETO_{current_timestamp}_{estabelecimento.id}"

        # Buscar cliente e agendamento
        cliente = None
        if pagamento_data.get('cliente_id'):
            try:
                cliente = Cliente.objects.get(id=pagamento_data['cliente_id'])
            except Cliente.DoesNotExist:
                pass

        agendamento = None
        if pagamento_data.get('agendamento_id'):
            try:
                agendamento = Agendamento.objects.get(id=pagamento_data['agendamento_id'])
            except Agendamento.DoesNotExist:
                pass

        # Criar transação no banco
        with transaction.atomic():
            pagamento_dados = {
                'usuario': request.user,
                'estabelecimento': estabelecimento,
                'cliente': cliente,
                'agendamento': agendamento,
                'valor_total': Decimal(str(pagamento_data['valor'])),
                'metodo': 'BOLETO',
                'codigo_transacao': reference_id,
                'status': 'PENDING',
                'descricao': pagamento_data['descricao'],
            }

            if hasattr(PagamentoTransacao, 'gateway_transacao_id'):
                pagamento_dados['gateway_transacao_id'] = reference_id

            pagamento_transacao = PagamentoTransacao.objects.create(**pagamento_dados)

        # Dados do boleto
        vencimento = (timezone.now().date() + timedelta(days=3)).strftime('%d/%m/%Y')

        contexto = {
            'pagamento': pagamento_transacao,
            'boleto_url': f'/pagamento/boleto-pdf/{reference_id}/',
            'valor_formatado': f"R$ {pagamento_data['valor']:.2f}".replace('.', ','),
            'vencimento': vencimento,
            'transaction_id': reference_id,
            'linha_digitavel': f'12345.67890 12345.678901 12345.678901 1 {current_timestamp}',
            'valor': pagamento_data['valor'],
            'descricao': pagamento_data['descricao']
        }

        messages.success(request, "Boleto gerado com sucesso! (Simulação)")
        return render(request, 'pagamento/pagamento_boleto.html', contexto)

    except Exception as e:
        logger.error(f"Erro ao processar boleto: {str(e)}", exc_info=True)
        messages.error(request, "Erro ao gerar boleto. Tente novamente.")
        return redirect('pagamento')

@login_required
@require_POST
def processar_pagamento_cartao(request):
    """Processa pagamento com cartão de crédito/débito - VERSÃO SIMPLIFICADA"""
    try:
        # Obter dados do formulário
        transaction_id = request.POST.get('transaction_id')
        pay_url = request.POST.get('pay_url')

        logger.info(f"Processando cartão - Transaction ID: {transaction_id}")
        logger.info(f"Pay URL: {pay_url}")

        if not transaction_id or not pay_url:
            return JsonResponse({
                'success': False,
                'message': 'Dados de transação inválidos'
            })

        # Buscar transação no banco
        try:
            transacao = PagamentoTransacao.objects.get(
                codigo_transacao=transaction_id,
                usuario=request.user
            )
        except PagamentoTransacao.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Transação não encontrada'
            })

        # Preparar dados do cartão para a API
        card_data = {
            "payment_method": {
                "type": transacao.metodo,  # CREDIT_CARD ou DEBIT_CARD
                "card": {
                    "number": request.POST.get('card_number', '').replace(' ', ''),
                    "exp_month": request.POST.get('card_month'),
                    "exp_year": request.POST.get('card_year'),
                    "security_code": request.POST.get('card_cvv'),
                    "holder": {
                        "name": request.POST.get('card_name', '').upper()
                    }
                }
            },
            "billing_address": {
                "street": request.POST.get('billing_street'),
                "number": request.POST.get('billing_number'),
                "locality": request.POST.get('billing_city'),
                "region": request.POST.get('billing_state', '').upper(),
                "postal_code": request.POST.get('billing_postal_code', '').replace('-', ''),
                "country": "BRA"
            }
        }

        # Adicionar parcelas se for cartão de crédito
        if transacao.metodo == 'CREDIT_CARD':
            installments = int(request.POST.get('installments', 1))
            card_data["payment_method"]["installments"] = installments

        # Configurar headers para a requisição
        config = get_pagbank_config()
        headers = {
            'accept': 'application/json',
            'Authorization': f"Bearer {config['token']}",
            'content-type': 'application/json'
        }

        logger.info(f"Enviando dados do cartão para: {pay_url}")
        logger.info(
            f"Dados (sem info sensível): Método={transacao.metodo}, Parcelas={card_data.get('payment_method', {}).get('installments', 1)}")

        # Enviar dados do cartão para o PagBank
        response = requests.post(pay_url, json=card_data, headers=headers, timeout=30)

        logger.info(f"Status da resposta: {response.status_code}")
        logger.info(f"Resposta do PagBank: {response.text}")

        if response.status_code in [200, 201]:
            response_data = response.json()

            # Obter status do pagamento
            payment_status = response_data.get('status', 'PENDING')

            # Mapear status para nosso sistema
            if payment_status in ['PAID', 'AUTHORIZED']:
                novo_status = 'PAID'
                success = True
                message = 'Pagamento aprovado com sucesso!'
            elif payment_status in ['DECLINED', 'FAILED']:
                novo_status = 'FAILED'
                success = False
                message = 'Pagamento recusado. Verifique os dados do cartão.'
            else:
                novo_status = 'PENDING'
                success = False
                message = f'Pagamento em análise. Status: {payment_status}'

            # Atualizar transação no banco
            transacao.status = novo_status

            # Salvar resposta da API se o campo existir
            try:
                if hasattr(transacao, 'dados_resposta'):
                    transacao.dados_resposta = response_data
                elif hasattr(transacao, 'gateway_resposta'):
                    transacao.gateway_resposta = response_data
            except:
                pass

            # Salvar últimos dígitos do cartão se o campo existir
            try:
                card_number = request.POST.get('card_number', '').replace(' ', '')
                if len(card_number) >= 4 and hasattr(transacao, 'cartao_ultimos_digitos'):
                    transacao.cartao_ultimos_digitos = card_number[-4:]
                if hasattr(transacao, 'cartao_bandeira'):
                    transacao.cartao_bandeira = detect_card_brand(card_number)
            except:
                pass

            transacao.save()

            # Se pagamento aprovado, atualizar agendamento
            if novo_status == 'PAID' and transacao.agendamento:
                try:
                    transacao.agendamento.pago = True
                    transacao.agendamento.save()
                    logger.info(f"Agendamento {transacao.agendamento.id} marcado como pago")
                except:
                    pass

            return JsonResponse({
                'success': success,
                'message': message,
                'status': novo_status,
                'transaction_id': transaction_id
            })

        else:
            # Tratar erros da API
            error_msg = 'Erro ao processar pagamento'

            try:
                error_data = response.json()
                if 'error_messages' in error_data and error_data['error_messages']:
                    errors = []
                    for err in error_data['error_messages']:
                        description = err.get('description', 'Erro desconhecido')
                        errors.append(description)
                    error_msg = '; '.join(errors)
                elif 'message' in error_data:
                    error_msg = error_data['message']
            except:
                error_msg = f"Erro HTTP {response.status_code}"

            logger.error(f"Erro no pagamento: {response.status_code} - {error_msg}")

            return JsonResponse({
                'success': False,
                'message': error_msg
            })

    except requests.exceptions.Timeout:
        logger.error("Timeout na requisição para PagBank")
        return JsonResponse({
            'success': False,
            'message': 'Timeout na comunicação com o servidor de pagamento. Tente novamente.'
        })

    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de conexão: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Erro de conexão. Verifique sua internet e tente novamente.'
        })

    except Exception as e:
        logger.error(f"Erro inesperado: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Erro interno. Tente novamente ou contate o suporte.'
        })


def detect_card_brand(card_number):
    """Detecta a bandeira do cartão (função auxiliar)"""
    if not card_number:
        return 'UNKNOWN'

    # Remover espaços e manter apenas números
    card_number = re.sub(r'[^0-9]', '', card_number)

    if card_number.startswith('4'):
        return 'VISA'
    elif card_number.startswith(('5', '2')):
        return 'MASTERCARD'
    elif card_number.startswith(('34', '37')):
        return 'AMEX'
    elif card_number.startswith('6'):
        return 'DISCOVER'
    else:
        return 'UNKNOWN'


@login_required
def verificar_status_pix(request, transaction_id):
    """API para verificar status do PIX - TIME CORRIGIDO"""
    try:
        transacao = get_object_or_404(PagamentoTransacao, codigo_transacao=transaction_id, usuario=request.user)

        logger.info(f"Verificando status PIX: {transaction_id}")

        # Simular mudança de status (30% chance)
        import random
        if transacao.status == 'PENDING' and random.randint(1, 10) <= 3:
            transacao.status = 'PAID'
            transacao.save()

            if transacao.agendamento:
                transacao.agendamento.pago = True
                transacao.agendamento.save()

        return JsonResponse({
            'success': True,
            'status': transacao.status,
            'status_display': transacao.status,
            'is_paid': transacao.status == 'PAID',
            'valor': str(transacao.valor_total),
            'message': 'Pagamento PIX aprovado!' if transacao.status == 'PAID' else 'PIX ainda pendente'
        })

    except Exception as e:
        logger.error(f"Erro ao verificar status PIX: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Erro interno'
        }, status=500)


@login_required
def download_boleto_pdf(request, transaction_id):
    """Download do PDF do boleto - TIME CORRIGIDO"""
    try:
        transacao = get_object_or_404(PagamentoTransacao, codigo_transacao=transaction_id, usuario=request.user)

        logger.info(f"Download boleto solicitado: {transaction_id}")

        # Conteúdo simulado do PDF
        pdf_content = f"""
        %PDF-1.4
        1 0 obj
        <<
        /Type /Catalog
        /Pages 2 0 R
        >>
        endobj

        2 0 obj
        <<
        /Type /Pages
        /Kids [3 0 R]
        /Count 1
        >>
        endobj

        3 0 obj
        <<
        /Type /Page
        /Parent 2 0 R
        /MediaBox [0 0 612 792]
        /Contents 4 0 R
        >>
        endobj

        4 0 obj
        <<
        /Length 200
        >>
        stream
        BT
        /F1 12 Tf
        72 720 Td
        (BOLETO BANCARIO - SIMULACAO) Tj
        0 -20 Td
        (Codigo: {transaction_id}) Tj
        0 -20 Td
        (Valor: R$ {transacao.valor_total}) Tj
        0 -20 Td
        (Vencimento: 3 dias) Tj
        0 -20 Td
        (Este é um boleto de teste) Tj
        ET
        endstream
        endobj

        xref
        0 5
        0000000000 65535 f 
        0000000009 00000 n 
        0000000058 00000 n 
        0000000115 00000 n 
        0000000204 00000 n 
        trailer
        <<
        /Size 5
        /Root 1 0 R
        >>
        startxref
        500
        %%EOF
        """

        response = HttpResponse(pdf_content.encode('utf-8'), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="boleto_{transaction_id}.pdf"'

        messages.success(request, f"Boleto {transaction_id} baixado com sucesso! (Simulação)")
        return response

    except Exception as e:
        logger.error(f"Erro ao gerar PDF do boleto: {str(e)}")
        messages.error(request, "Erro ao gerar boleto. Tente novamente.")
        return redirect('pagamento_boleto')

# ==========================================
# VIEW OPCIONAL: Verificar status de qualquer pagamento
# ==========================================

@login_required
def verificar_status_pagamento_geral(request, transaction_id):
    """API para verificar status geral - TIME CORRIGIDO"""
    try:
        transacao = get_object_or_404(PagamentoTransacao, codigo_transacao=transaction_id, usuario=request.user)

        # Simular mudança de status
        import random
        if transacao.status == 'PENDING' and random.randint(1, 100) <= 25:
            transacao.status = 'PAID'
            transacao.save()

            if transacao.agendamento:
                transacao.agendamento.pago = True
                transacao.agendamento.save()

        return JsonResponse({
            'success': True,
            'status': transacao.status,
            'status_display': transacao.status,
            'is_paid': transacao.status == 'PAID',
            'metodo': transacao.metodo,
            'valor': str(transacao.valor_total),
            'updated': True
        })

    except Exception as e:
        logger.error(f"Erro ao verificar status: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Erro interno'
        }, status=500)

@login_required
def debug_pagbank(request):
    """View para debug da configuração PagBank"""
    config = get_pagbank_config()

    context = {
        'config': config
    }

    return render(request, 'pagamento/debug_pagbank.html', context)


@login_required
def test_api_pagbank(request):
    """View para testar API do PagBank"""
    if request.method == 'POST':
        try:
            config = get_pagbank_config()

            # Teste simples da API
            headers = {
                'Authorization': f'Bearer {config["token"]}',
                'Content-Type': 'application/json'
            }

            # Endpoint para testar conectividade
            url = f"{config['api_url']}/public-keys"

            response = requests.get(url, headers=headers, timeout=10)

            return JsonResponse({
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'response': response.text[:500],  # Primeiros 500 caracteres
                'url': url
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })

    return JsonResponse({'error': 'Método não permitido'}, status=405)



@login_required
def verificar_status_pagamento(request, transaction_id):
    """API para verificar status de um pagamento"""
    try:
        # Buscar transação no banco
        transacao = get_object_or_404(PagamentoTransacao, codigo_transacao=transaction_id, usuario=request.user)

        # Consultar status na API do PagBank
        config = get_pagbank_config()
        url = f"{config['api_url']}/orders/{transaction_id}"
        headers = {
            'accept': 'application/json',
            'Authorization': f"Bearer {config['token']}",
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            logger.info(f"Consultando status: {url} - Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()

                # Extrair status das charges
                status_api = 'PENDING'
                if 'charges' in data and data['charges']:
                    status_api = data['charges'][0].get('status', 'PENDING')

                # Mapear status da API para o nosso sistema
                status_mapping = {
                    'PAID': 'PAID',
                    'DECLINED': 'FAILED',
                    'CANCELLED': 'CANCELLED',
                    'AUTHORIZED': 'AUTHORIZED',
                    'WAITING': 'PENDING',
                    'IN_ANALYSIS': 'PROCESSING',
                }

                novo_status = status_mapping.get(status_api, 'PENDING')
                status_mudou = False

                # Atualizar se mudou
                if transacao.status != novo_status:
                    transacao.status = novo_status

                    # Salvar dados da resposta nos campos disponíveis
                    if hasattr(transacao, 'dados_resposta'):
                        transacao.dados_resposta = data
                    elif hasattr(transacao, 'gateway_resposta'):
                        transacao.gateway_resposta = data

                    # Marcar como pago se necessário
                    if novo_status == 'PAID':
                        transacao.save()
                        if transacao.agendamento:
                            transacao.agendamento.pago = True
                            transacao.agendamento.save()
                    else:
                        transacao.save()

                    status_mudou = True
                    logger.info(f"Status da transação {transaction_id} atualizado para {novo_status}")

                return JsonResponse({
                    'success': True,
                    'status': novo_status,
                    'status_display': transacao.get_status_display(),
                    'is_paid': novo_status == 'PAID',
                    'valor': str(transacao.valor_total),
                    'updated': status_mudou
                })
            else:
                logger.error(f"Erro ao consultar API PagBank: {response.status_code}")
                return JsonResponse({
                    'success': False,
                    'error': f'Erro na API: {response.status_code}',
                    'status': transacao.status,
                    'status_display': transacao.get_status_display(),
                    'is_paid': transacao.status == 'PAID'
                })

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro na requisição: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Erro de comunicação com PagBank',
                'status': transacao.status,
                'status_display': transacao.get_status_display(),
                'is_paid': transacao.status == 'PAID'
            })

    except Exception as e:
        logger.error(f"Erro inesperado: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Erro interno do servidor'
        })

@login_required
def historico_pagamentos(request):
    """View para mostrar histórico de pagamentos do usuário - CORRIGIDA"""
    try:
        estabelecimento = get_object_or_404(Estabelecimento, usuario=request.user)

        # Filtros
        status_filter = request.GET.get('status', '')
        metodo_filter = request.GET.get('metodo', '')
        data_inicio = request.GET.get('data_inicio', '')
        data_fim = request.GET.get('data_fim', '')

        transacoes = PagamentoTransacao.objects.filter(estabelecimento=estabelecimento)

        if status_filter:
            transacoes = transacoes.filter(status=status_filter)
        if metodo_filter:
            transacoes = transacoes.filter(metodo=metodo_filter)
        if data_inicio:
            transacoes = transacoes.filter(criado_em__date__gte=data_inicio)
        if data_fim:
            transacoes = transacoes.filter(criado_em__date__lte=data_fim)

        # Estatísticas
        total_transacoes = transacoes.count()
        total_valor = sum(float(t.valor_total) for t in transacoes)
        transacoes_pagas = transacoes.filter(status='PAID').count()
        valor_recebido = sum(float(t.valor_total) for t in transacoes.filter(status='PAID'))

        context = {
            'transacoes': transacoes.order_by('-criado_em')[:50],  # Últimas 50
            'total_transacoes': total_transacoes,
            'total_valor': total_valor,
            'transacoes_pagas': transacoes_pagas,
            'valor_recebido': valor_recebido,
            'taxa_conversao': (transacoes_pagas / total_transacoes * 100) if total_transacoes > 0 else 0,
            'status_choices': PagamentoTransacao.STATUS_CHOICES,
            'metodo_choices': PagamentoTransacao.METODO_CHOICES,
            'estabelecimento': estabelecimento
        }
        return render(request, 'pagamento/historico_pagamentos.html', context)

    except Exception as e:
        logger.error(f"Erro no histórico de pagamentos: {str(e)}")
        messages.error(request, "Erro ao carregar histórico de pagamentos.")
        return redirect('dashboard')

@csrf_exempt
@require_POST
def webhook_pagbank(request):
    """Webhook para receber notificações do PagBank"""
    try:
        if not request.body:
            logger.warning("Webhook recebido com body vazio")
            return JsonResponse({'status': 'error', 'message': 'Body vazio'}, status=400)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON do webhook: {e}")
            return JsonResponse({'status': 'error', 'message': 'JSON inválido'}, status=400)

        logger.info(f'Webhook PagBank recebido: {json.dumps(data, indent=2)}')

        transaction_id = data.get('id')

        # Extrair status das charges
        status = 'PENDING'
        if 'charges' in data and data['charges']:
            status = data['charges'][0].get('status', 'PENDING')

        if not transaction_id:
            logger.warning("Webhook sem transaction_id")
            return JsonResponse({'status': 'error', 'message': 'Missing transaction_id'}, status=400)

        try:
            pagamento = PagamentoTransacao.objects.get(codigo_transacao=transaction_id)

            # Mapear status
            status_mapping = {
                'PAID': 'PAID',
                'DECLINED': 'FAILED',
                'CANCELLED': 'CANCELLED',
                'AUTHORIZED': 'AUTHORIZED',
                'WAITING': 'PENDING',
                'IN_ANALYSIS': 'PROCESSING',
            }

            novo_status = status_mapping.get(status, 'PENDING')

            if pagamento.status != novo_status:
                old_status = pagamento.status
                pagamento.status = novo_status

                # Salvar dados da resposta se o campo existir
                if hasattr(pagamento, 'dados_resposta'):
                    pagamento.dados_resposta = data
                elif hasattr(pagamento, 'gateway_resposta'):
                    pagamento.gateway_resposta = data

                pagamento.save()

                logger.info(f"Status atualizado: {old_status} -> {novo_status} para transação {transaction_id}")

                # Se pagamento aprovado, atualizar agendamento
                if novo_status == 'PAID' and pagamento.agendamento:
                    pagamento.agendamento.pago = True
                    pagamento.agendamento.save()
                    logger.info(f"Agendamento {pagamento.agendamento.id} marcado como pago")

            return JsonResponse({'status': 'success'})

        except PagamentoTransacao.DoesNotExist:
            logger.warning(f"Transação não encontrada: {transaction_id}")
            return JsonResponse({'status': 'error', 'message': 'Transaction not found'}, status=404)

    except Exception as e:
        logger.error(f"Erro no webhook PagBank: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Internal error'}, status=500)


@login_required
@plano_required(tem_insights_ia)
def insights_ia(request):
    """View para insights com IA - disponível apenas nos planos superiores"""
    estabelecimento = verificar_limites_estabelecimento(request)
    if not estabelecimento:
        return redirect('cadastro_estabelecimento')

    # Sua lógica de insights com IA aqui
    context = {
        'estabelecimento': estabelecimento,
        'titulo': 'Insights com Inteligência Artificial'
    }

    return render(request, 'insights_ia.html', context)

@require_POST
@login_required
def gerar_insight(request):
    prontuario_id = request.POST.get('prontuario_id')

    # Verificar plano Premium
    estabelecimento = getattr(request.user, 'estabelecimento', None)
    if not estabelecimento or not estabelecimento.tem_recurso('insights_ia'):
        raise PermissionDenied("Recurso de IA disponível apenas no plano Premium.")

    try:
        prontuario = Prontuario.objects.get(id=prontuario_id)
    except Prontuario.DoesNotExist:
        return JsonResponse({'erro': 'Prontuário não encontrado'}, status=404)

    texto = prontuario.descricao or ''
    if not texto:
        return JsonResponse({'insight': 'Nenhuma anotação encontrada para análise.'})

    try:
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        resposta = client.chat.completions.create(
            model='gpt-4o-mini',  # Modelo mais econômico
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'Você é um assistente médico de IA, projetado para fornecer insights clínicos breves e úteis com base em anotações de prontuários. '
                        'Não substitua o diagnóstico médico, mas ofereça recomendações ou observações úteis para auxiliar o profissional. '
                        'Seja conciso, objetivo e use linguagem profissional.'
                    )
                },
                {
                    'role': 'user',
                    'content': f'Analise o seguinte texto clínico e gere um insight ou recomendação breve:\n\n{texto}'
                }
            ],
            max_tokens=150,
            temperature=0.7,
        )
        insight = resposta.choices[0].message.content.strip()
    except Exception as e:
        print(f'Erro na OpenAI: {e}')
        insight = simular_insight_local(texto)

    prontuario.insight_gerado = insight
    prontuario.save()

    return JsonResponse({'insight': insight})


def simular_insight_local(texto):
    texto = texto.lower()
    if 'botox' in texto:
        return 'Avaliar efeito do botox após 7 dias. Possível retoque em 15 dias.'
    elif 'peeling' in texto:
        return 'Evitar exposição solar por 72 horas. Reaplicar protetor solar e hidratar a pele.'
    elif 'dor' in texto:
        return 'Investigar persistência da dor. Sugerir repouso e acompanhamento.'
    return 'Nenhuma recomendação específica. Manter acompanhamento regular.'





### views codigo envio lembrete email completo

@login_required
def configurar_email_estabelecimento(request, estabelecimento_id):
    """Configurar email específico do estabelecimento"""
    estabelecimento = get_object_or_404(Estabelecimento, id=estabelecimento_id)

    # Verificar se usuário pode editar este estabelecimento
    if estabelecimento.usuario != request.user:
        messages.error(request, '❌ Você não tem permissão para este estabelecimento')
        return redirect('dashboard')

    # Buscar ou criar configuração
    config, created = ConfiguracaoEmail.objects.get_or_create(estabelecimento=estabelecimento)

    if request.method == 'POST':
        # Capturar dados do formulário
        config.email_usuario = request.POST.get('email_usuario', '')
        config.email_senha = request.POST.get('email_senha', '')
        config.provedor = request.POST.get('provedor', 'gmail')
        config.ativo = 'ativo' in request.POST
        config.dias_antecedencia = int(request.POST.get('dias_antecedencia', 1))
        config.horario_envio = request.POST.get('horario_envio', '09:00')
        config.template_assunto = request.POST.get('template_assunto', config.template_assunto)
        config.template_corpo = request.POST.get('template_corpo', config.template_corpo)

        # Configurar SMTP manualmente se "outro"
        if config.provedor == 'outro':
            config.email_smtp = request.POST.get('email_smtp_custom', 'smtp.gmail.com')
            config.email_porta = int(request.POST.get('email_porta_custom', 587))
            config.email_use_tls = 'email_use_tls' in request.POST

        # Validar e testar configuração
        if config.email_usuario and config.email_senha:
            sucesso, mensagem = testar_configuracao_smtp(config)

            if sucesso:
                config.ultimo_teste = timezone.now()
                config.status_ultimo_teste = "Sucesso"
                config.save()
                messages.success(request, f'✅ Configurações salvas e testadas! {mensagem}')
            else:
                config.ultimo_teste = timezone.now()
                config.status_ultimo_teste = f"Erro: {mensagem}"
                config.save()
                messages.error(request, f'❌ Erro na configuração: {mensagem}')
        else:
            config.save()
            messages.warning(request, '⚠️ Configure email e senha para ativar o sistema')

    context = {
        'estabelecimento': estabelecimento,
        'config': config,
    }
    return render(request, 'email_config_estabelecimento.html', context)


def testar_configuracao_smtp(config):
    """Testa configuração SMTP específica"""
    try:
        print(f"🧪 Testando SMTP para {config.email_usuario}")
        print(f"📧 Servidor: {config.email_smtp}:{config.email_porta}")
        print(f"🔒 TLS: {config.email_use_tls}")

        # Criar conexão SMTP
        if config.email_use_tls:
            server = smtplib.SMTP(config.email_smtp, config.email_porta)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(config.email_smtp, config.email_porta)

        # Fazer login
        server.login(config.email_usuario, config.email_senha)
        server.quit()

        print("✅ Teste SMTP bem-sucedido!")
        return True, "Configuração válida"

    except smtplib.SMTPAuthenticationError:
        print("❌ Erro de autenticação")
        return False, "Email ou senha incorretos"
    except smtplib.SMTPConnectError:
        print("❌ Erro de conexão")
        return False, "Não foi possível conectar ao servidor"
    except Exception as e:
        print(f"❌ Erro geral: {str(e)}")
        return False, f"Erro: {str(e)}"


def enviar_email_personalizado(agendamento, config_email):
    """Envia email usando configuração específica do estabelecimento"""
    try:
        if not agendamento.cliente.email:
            return False, "Cliente não possui email"

        print(f"📧 Enviando de {config_email.email_usuario} para {agendamento.cliente.email}")

        # Preparar dados para template
        dados = {
            'nome_paciente': agendamento.cliente.nome,
            'data_consulta': agendamento.data.strftime('%d/%m/%Y'),
            'hora_consulta': agendamento.hora.strftime('%H:%M'),
            'nome_clinica': agendamento.estabelecimento.nome,
        }

        # Formatar mensagem
        assunto = config_email.template_assunto.format(**dados)
        corpo = config_email.template_corpo.format(**dados)

        # Criar mensagem MIME
        msg = MIMEMultipart()
        msg['From'] = config_email.email_usuario
        msg['To'] = agendamento.cliente.email
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))

        # Conectar e enviar
        if config_email.email_use_tls:
            server = smtplib.SMTP(config_email.email_smtp, config_email.email_porta)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(config_email.email_smtp, config_email.email_porta)

        server.login(config_email.email_usuario, config_email.email_senha)
        texto = msg.as_string()
        server.sendmail(config_email.email_usuario, agendamento.cliente.email, texto)
        server.quit()

        # Registrar no histórico
        HistoricoLembrete.objects.create(
            estabelecimento=agendamento.estabelecimento,
            tipo='email',
            status='enviado',
            mensagem_enviada=f"De: {config_email.email_usuario}\nPara: {agendamento.cliente.email}\nAssunto: {assunto}\n\n{corpo}"
        )

        print(f"✅ Email enviado com sucesso!")
        return True, f"Email enviado para {agendamento.cliente.email}"

    except Exception as e:
        print(f"❌ Erro ao enviar: {str(e)}")

        # Registrar erro
        HistoricoLembrete.objects.create(
            estabelecimento=agendamento.estabelecimento,
            tipo='email',
            status='erro',
            mensagem_enviada=f"Tentativa de {config_email.email_usuario} para {getattr(agendamento.cliente, 'email', 'N/A')}",
            erro_detalhes=str(e)
        )

        return False, f"Erro: {str(e)}"


@login_required
def envio_massa_personalizado(request, estabelecimento_id):
    """Envio em massa usando email do próprio estabelecimento"""
    if request.method != 'POST':
        messages.error(request, '❌ Método não permitido')
        return redirect('teste_email_personalizado')

    data_selecionada = request.POST.get('data_envio')
    if not data_selecionada:
        messages.error(request, '❌ Selecione uma data')
        return redirect('teste_email_personalizado')

    estabelecimento = get_object_or_404(Estabelecimento, id=estabelecimento_id)

    # Verificar permissão
    if estabelecimento.usuario != request.user:
        messages.error(request, '❌ Sem permissão')
        return redirect('teste_email_personalizado')

    # Buscar configuração do estabelecimento
    try:
        config = ConfiguracaoEmail.objects.get(estabelecimento=estabelecimento)
    except ConfiguracaoEmail.DoesNotExist:
        messages.error(request, '❌ Configure o sistema de email primeiro!')
        return redirect('configurar_email_estabelecimento', estabelecimento_id=estabelecimento_id)

    if not config.ativo:
        messages.error(request, '❌ Sistema de email está desativado!')
        return redirect('configurar_email_estabelecimento', estabelecimento_id=estabelecimento_id)

    if not config.email_usuario or not config.email_senha:
        messages.error(request, '❌ Configure email e senha primeiro!')
        return redirect('configurar_email_estabelecimento', estabelecimento_id=estabelecimento_id)

    # Converter data
    try:
        data_obj = datetime.strptime(data_selecionada, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, '❌ Data inválida!')
        return redirect('teste_email_personalizado')

    # Buscar agendamentos
    agendamentos = Agendamento.objects.filter(
        estabelecimento=estabelecimento,
        data=data_obj
    )

    if not agendamentos:
        messages.warning(request, f'❌ Nenhum agendamento em {data_obj.strftime("%d/%m/%Y")}')
        return redirect('teste_email_personalizado')

    print(f"📧 ENVIO PERSONALIZADO - {agendamentos.count()} agendamentos")
    print(f"📤 Enviando de: {config.email_usuario}")
    print(f"🏢 Estabelecimento: {estabelecimento.nome}")

    enviados = 0
    erros = 0

    # Testar configuração antes do envio
    sucesso_teste, msg_teste = testar_configuracao_smtp(config)
    if not sucesso_teste:
        messages.error(request, f'❌ Erro na configuração: {msg_teste}')
        return redirect('configurar_email_estabelecimento', estabelecimento_id=estabelecimento_id)

    # Envio em massa
    for i, agendamento in enumerate(agendamentos, 1):
        print(f"📧 [{i}/{agendamentos.count()}] {agendamento.cliente.nome}")

        if agendamento.cliente.email:
            try:
                sucesso, mensagem = enviar_email_personalizado(agendamento, config)

                if sucesso:
                    print(f"✅ {mensagem}")
                    enviados += 1
                else:
                    print(f"❌ {mensagem}")
                    erros += 1

            except Exception as e:
                print(f"❌ Erro: {str(e)}")
                erros += 1
        else:
            print(f"📭 Sem email")
            erros += 1

    print(f"🏁 CONCLUÍDO! ✅ {enviados} enviados, ❌ {erros} erros")

    if enviados > 0:
        messages.success(request,
                         f'🎉 Envio concluído! ✅ {enviados} emails enviados de {config.email_usuario}, ❌ {erros} erros')
    else:
        messages.error(request, f'❌ Nenhum email foi enviado. Verifique as configurações.')

    return redirect('teste_email_personalizado')


@login_required
def teste_email_personalizado(request):
    """Sistema de teste com email personalizado por estabelecimento"""

    estabelecimento = Estabelecimento.objects.filter(usuario=request.user).first()
    if not estabelecimento:
        messages.error(request, '❌ Nenhum estabelecimento encontrado')
        return redirect('dashboard')

    # Buscar/criar configuração
    config, created = ConfiguracaoEmail.objects.get_or_create(estabelecimento=estabelecimento)

    # Buscar agendamentos futuros
    agendamentos = Agendamento.objects.filter(
        estabelecimento=estabelecimento,
        data__gte=timezone.now().date()
    ).order_by('data', 'hora')[:10]

    # Processar teste individual
    if request.method == 'POST':
        acao = request.POST.get('acao')

        # Teste de configuração
        if acao == 'testar_config':
            if config.email_usuario and config.email_senha:
                sucesso, mensagem = testar_configuracao_smtp(config)
                if sucesso:
                    config.ultimo_teste = timezone.now()
                    config.status_ultimo_teste = "Sucesso"
                    config.save()
                    messages.success(request, f'✅ {mensagem}')
                else:
                    config.ultimo_teste = timezone.now()
                    config.status_ultimo_teste = f"Erro: {mensagem}"
                    config.save()
                    messages.error(request, f'❌ {mensagem}')
            else:
                messages.error(request, '❌ Configure email e senha primeiro!')

            return redirect('teste_email_personalizado')

        # Teste individual
        agendamento_id = request.POST.get('agendamento_id')
        if agendamento_id:
            try:
                agendamento = get_object_or_404(Agendamento, id=agendamento_id)

                if not config.ativo:
                    messages.warning(request, '⚠️ Ative o sistema de email primeiro!')
                    return redirect('configurar_email_estabelecimento', estabelecimento_id=estabelecimento.id)

                sucesso, mensagem = enviar_email_personalizado(agendamento, config)

                if sucesso:
                    messages.success(request, f'✅ {mensagem}')
                else:
                    messages.error(request, f'❌ {mensagem}')

            except Exception as e:
                messages.error(request, f'❌ Erro: {str(e)}')

        return redirect('teste_email_personalizado')

    context = {
        'estabelecimento': estabelecimento,
        'agendamentos': agendamentos,
        'config': config,
    }
    return render(request, 'teste_email_personalizado.html', context)
