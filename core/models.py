import calendar
from datetime import datetime, timedelta, date
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.timezone import now
from django.contrib.auth.models import User
from decimal import Decimal
from django.core.exceptions import ValidationError


from openai import OpenAI

STATUS_AGENDAMENTO = (
    ('confirmado', 'Confirmado'),
    ('aguardando', 'Aguardando'),
    ('nao_compareceu', 'Não Compareceu'),
)

PLANO_CHOICES = [
    ('basico', 'Basico'),
    ('profissional', 'Profissional'),
    ('empresarial', 'Empresarial'),
    ('enterprise', 'Enterprise'),
]



# Função now para compatibilidade
def now():
    return timezone.now()

class Plano(models.Model):
    PLANOS_CHOICES = [
        ('basico', 'Básico'),
        ('profissional', 'Profissional'),
        ('empresarial', 'Empresarial'),
        ('enterprise', 'Enterprise'),
    ]
    nome = models.CharField(max_length=100, choices=PLANOS_CHOICES)
    valor = models.DecimalField(max_digits=10, decimal_places=2, default=1)  # Este campo deve existir
    valor_mensal = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    valor_anual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_profissionais = models.PositiveIntegerField(default=2, help_text="Número máximo de profissionais permitidos")
    tem_integracao_pagseguro = models.BooleanField(default=False)
    tem_lembrete_automatico = models.BooleanField(default=False)
    tem_dashbaord_financeiro = models.BooleanField(default=False)  # Corrigido de 'dashbaord' para 'dashboard'
    tem_controle_estoque = models.BooleanField(default=False)
    tem_agendamento_ilimitado = models.BooleanField(default=False)
    tem_insights_ia = models.BooleanField(default=False)
    suporte_whatsapp = models.BooleanField(default=False)
    suporte_email = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.get_nome_display()

    class Meta:
        verbose_name = "Plano"
        verbose_name_plural = "Planos"


class Estabelecimento(models.Model):
    nome = models.CharField(max_length=100)
    cnpj = models.CharField(max_length=18, blank=True, null=True)
    responsavel = models.CharField(max_length=100, default="")
    telefone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    senha = models.CharField(max_length=128, default="")
    endereco = models.TextField(blank=True, null=True)
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='estabelecimento')
    ativo = models.BooleanField(default=True)
    data_cadastro = models.DateTimeField(default=now)
    plano = models.ForeignKey(Plano, on_delete=models.CASCADE, verbose_name="Plano", null=True, blank=True)  # Removido default, adicionado null=True
    ip_cadastro = models.GenericIPAddressField(null=True, blank=True)

    def get_assinatura_ativa(self):
        return self.assinatura_set.filter(
            status='ativo',
            data_validade__gte=timezone.now().date()
        ).select_related('plano').first()

    def tem_recurso(self, recurso):
        assinatura = self.get_assinatura_ativa()
        if not assinatura:
            return False
        plano_nome = assinatura.plano.nome.lower()
        recursos_por_plano = {
            'basico': ['agendamento', 'dashboard_financeiro', 'suporte_email', 'suporte_whatsapp'],
            'profissional': ['agendamento', 'dashboard_financeiro', 'integracao_pagseguro', 'suporte_email',
                             'suporte_whatsapp'],
            'empresarial': ['agendamento', 'integracao_pagseguro', 'controle_estoque', 'suporte_email',
                            'suporte_whatsapp', 'dashboard_financeiro', 'lembretes_automaticos'],
            'enterprise': ['agendamento', 'suporte_email', 'integracao_pagseguro', 'controle_estoque',
                           'suporte_whatsapp', 'dashboard_financeiro', 'lembretes_automaticos', 'insights_ia'],
        }
        return recurso in recursos_por_plano.get(plano_nome, [])

    def pode_adicionar_profissional(self):
        profissionais_atuais = self.profissional_set.filter(ativo=True).count()
        return profissionais_atuais < self.plano.max_profissionais if self.plano else False

    def profissionais_restantes(self):
        profissionais_atuais = self.profissional_set.filter(ativo=True).count()
        return max(0, self.plano.max_profissionais - profissionais_atuais) if self.plano else 0

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Estabelecimento"
        verbose_name_plural = "Estabelecimentos"


class Assinatura(models.Model):
    STATUS_CHOICES = [
        ('ativo', 'Ativo'),
        ('inativo', 'Inativo'),
        ('suspenso', 'Suspenso'),
        ('cancelado', 'Cancelado'),
        ('teste', 'Teste'),
    ]

    estabelecimento = models.ForeignKey(Estabelecimento, on_delete=models.CASCADE)
    plano = models.ForeignKey(Plano, on_delete=models.CASCADE)
    valor_pago = models.DecimalField(max_digits=8, decimal_places=2)
    data_pagamento = models.DateField(auto_now_add=True)
    data_validade = models.DateField(null=True, blank=True)
    data_inicio = models.DateTimeField(default=now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ativo')
    tipo = models.CharField(max_length=20, default='teste')

    def __str__(self):
        return f"{self.estabelecimento} - {self.plano}"

    def esta_ativa(self):
        return self.data_validade and self.data_validade >= date.today()

    class Meta:
        verbose_name = "Assinatura"
        verbose_name_plural = "Assinaturas"

class Cliente(models.Model):
    estabelecimento = models.ForeignKey(Estabelecimento, on_delete=models.CASCADE)
    nome = models.CharField(max_length=100)
    cpf = models.CharField(max_length=14, blank=True, null=True)
    telefone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    nascimento = models.DateField(blank=True, null=True)
    endereco = models.TextField(blank=True, null=True)


    @property
    def idade(self):
        if self.nascimento:
            return date.today().year - self.nascimento.year - (
                (date.today().month, date.today().day) < (self.nascimento.month, self.nascimento.day)
            )
        return "-"

    def __str__(self):
        return self.nome

class Servico(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    duracao = models.TimeField(null=True, blank=True)
    valor = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor (R$)", null=True, blank=True)
    estabelecimento = models.ForeignKey(Estabelecimento, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.nome

class Profissional(models.Model):
    estabelecimento = models.ForeignKey(Estabelecimento, on_delete=models.CASCADE)
    nome = models.CharField(max_length=100)
    cpf = models.CharField(max_length=14, blank=True, null=True)
    cnpj = models.CharField(max_length=18, blank=True, null=True)
    telefone = models.CharField(max_length=11, blank=True, null=True)
    especialidade = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    endereco = models.TextField(blank=True, null=True)
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    percentual_comissao = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return self.nome

    def clean(self):
        # Validações adicionais, se necessário (ex.: formato de CPF/CNPJ)
        if self.cpf and not self.cpf.isdigit():
            raise ValidationError("CPF deve conter apenas números.")
        if self.cnpj and not self.cnpj.isdigit():
            raise ValidationError("CNPJ deve conter apenas números.")
        if self.percentual_comissao is not None and (self.percentual_comissao < 0 or self.percentual_comissao > 100):
            raise ValidationError("O percentual de comissão deve estar entre 0 e 100.")

    class Meta:
        verbose_name = "Profissional"
        verbose_name_plural = "Profissionais"

class Produto(models.Model):
    nome = models.CharField(max_length=100)
    codigo = models.CharField(max_length=50, unique=True, blank=True)
    quantidade = models.PositiveIntegerField(default=0)
    estoque_minimo = models.PositiveIntegerField(default=0)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estabelecimento = models.ForeignKey('Estabelecimento', on_delete=models.CASCADE)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} ({self.quantidade} )"

    def verificar_estoque_baixo(self):
        return self.quantidade <= self.estoque_minimo


class Agendamento(models.Model):
    estabelecimento = models.ForeignKey(Estabelecimento, on_delete=models.CASCADE)
    FORMA_PAGAMENTO_CHOICES = [
        ('pix', 'Pix'),
        ('dinheiro', 'Dinheiro'),
        ('debito', 'Cartão de Débito'),
        ('credito', 'Cartão de Crédito'),
        ('convenio', 'Convênio'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    profissional = models.ForeignKey(Profissional, on_delete=models.CASCADE)
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE)
    data = models.DateField()
    hora = models.TimeField()
    produtos = models.ManyToManyField(Produto, through='AgendamentoProduto', blank=True)
    duracao = models.IntegerField(null=True, blank=True)
    valor = models.DecimalField(max_digits=8, decimal_places=2)
    percentual_comissao = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, default=0)
    valor_profissional = models.DecimalField(max_digits=10, decimal_places=2)
    forma_pagamento = models.CharField(max_length=20, choices=FORMA_PAGAMENTO_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_AGENDAMENTO, default='aguardando')
    lembrete_enviado = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.profissional and self.profissional.percentual_comissao:
            self.valor_profissional = self.valor * (self.profissional.percentual_comissao / 100)
        else:
            self.valor_profissional = 0
        super().save(*args, **kwargs)

    def data_hora_inicio(self):
        return datetime.combine(self.data, self.hora)

    def data_hora_fim(self):
        if self.duracao:
            return self.data_hora_inicio() + timedelta(minutes=self.duracao)
        return self.data_hora_inicio()

    def __str__(self):
        return f"{self.servico.nome} - {self.cliente.nome} - {self.data} {self.hora}"


class AgendamentoProduto(models.Model):
    agendamento = models.ForeignKey('Agendamento', on_delete=models.CASCADE)
    produto = models.ForeignKey('Produto', on_delete=models.CASCADE)
    quantidade: int = models.PositiveIntegerField(default=1)

class BloqueioHorario(models.Model):
    data = models.DateField()
    hora = models.TimeField()
    motivo = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return f"Bloqueado em {self.data} às {self.hora}"

class ListaEspera(models.Model):
    estabelecimento = models.ForeignKey(Estabelecimento, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE)
    data_pedido = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.cliente.nome} esperando {self.servico.nome}"

class Prontuario(models.Model):
    estabelecimento = models.ForeignKey(Estabelecimento, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    profissional = models.ForeignKey(Profissional, on_delete=models.CASCADE)
    agendamento = models.ForeignKey(Agendamento, on_delete=models.SET_NULL, null=True, blank=True)
    data = models.DateTimeField(auto_now_add=True)
    observacoes = models.TextField()
    arquivos = models.FileField(upload_to='prontuarios/', null=True, blank=True)
    tags = models.CharField(max_length=255, blank=True, help_text="Ex: 'botox, pele, laser'")
    descricao = models.TextField("Anotações, evolução do atendimento, observações...")
    imagem = models.ImageField(upload_to='prontuarios/imagens/', blank=True, null=True)
    anexo = models.FileField(upload_to='prontuarios/', blank=True, null=True)
    situacao = models.TextField(max_length=100)
    sugestao_ia = models.TextField(blank=True, null=True)
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return f"Prontuário de {self.cliente.nome} - {self.data.strftime('%d/%m/%Y') if self.data else 'Sem data'}"

class MovimentacaoEstoque(models.Model):
    TIPO_MOVIMENTACAO = (
        ('ENTRADA', 'Entrada'),
        ('SAIDA', 'Saída'),
    )
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPO_MOVIMENTACAO)
    quantidade = models.PositiveIntegerField()
    data = models.DateTimeField(auto_now_add=True)
    observacao = models.TextField(blank=True)

    def __str__(self):
        return f"{self.tipo} - {self.produto.nome} ({self.quantidade} un.)"


class AgendamentoRecorrente(models.Model):
    estabelecimento = models.ForeignKey(Estabelecimento, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    profissional = models.ForeignKey(Profissional, on_delete=models.CASCADE)
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE)
    produto: Produto = models.ForeignKey('Produto', on_delete=models.CASCADE, default=1)
    dia_da_semana = models.IntegerField(choices=[(i, calendar.day_name[i]) for i in range(7)])
    hora = models.TimeField()
    duracao = models.DurationField()
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.cliente.nome} - {self.get_dia_da_semana_display()} às {self.hora}"

class AgendamentoRecorrenteProduto(models.Model):
    agendamento_recorrente: int = models.ForeignKey('AgendamentoRecorrente', on_delete=models.CASCADE)
    produto: Produto = models.ForeignKey('Produto', on_delete=models.CASCADE)
    quantidade: int = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.produto.nome} ({self.quantidade} un.) para {self.agendamento_recorrente}"

class LancamentoFinanceiro(models.Model):
    estabelecimento = models.ForeignKey(Estabelecimento, on_delete=models.CASCADE)
    agendamento = models.ForeignKey(Agendamento, on_delete=models.CASCADE, null=True, blank=True)
    data = models.DateField(auto_now_add=True)
    tipo = models.CharField(max_length=10, choices=[('entrada', 'Entrada'), ('saida', 'Saída')])
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    descricao = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.tipo.capitalize()} - R$ {self.valor} - {self.data.strftime('%d/%m/%Y') if self.data else 'Sem data'}"


class Pagamento(models.Model):
    STATUS_CHOICES = (
        ('PENDENTE', 'Pendente'),
        ('APROVADO', 'Aprovado'),
        ('CANCELADO', 'Cancelado'),
    )
    agendamento = models.ForeignKey(Agendamento, on_delete=models.CASCADE)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    metodo = models.CharField(max_length=50)  # Ex.: Boleto, PIX, Cartão
    codigo_transacao = models.CharField(max_length=100, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Pagamento {self.id} - {self.agendamento} ({self.status})"


class Venda(models.Model):
    cliente = models.ForeignKey('Cliente', null=True, blank=True, on_delete=models.SET_NULL)
    estabelecimento = models.ForeignKey('Estabelecimento', on_delete=models.CASCADE)
    forma_pagamento = models.CharField(max_length=50, blank=True)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Venda #{self.id} - {self.cliente.nome if self.cliente else "Sem cliente"}'

class VendaProduto(models.Model):
    venda = models.ForeignKey(Venda, on_delete=models.CASCADE, related_name='produtos')
    produto = models.ForeignKey('Produto', on_delete=models.CASCADE)
    quantidade = models.PositiveIntegerField()
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f'{self.produto.nome} x{self.quantidade} (Venda #{self.venda.id})'


class PagamentoTransacao(models.Model):
    METODO_CHOICES = [
        ('CREDIT_CARD', 'Cartão de Crédito'),
        ('DEBIT_CARD', 'Cartão de Débito'),
        ('PIX', 'PIX'),
        ('BOLETO', 'Boleto'),
        ('MONEY', 'Dinheiro'),
        ('BANK_TRANSFER', 'Transferência Bancária'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pendente'),
        ('PROCESSING', 'Processando'),
        ('PAID', 'Pago'),
        ('FAILED', 'Falhou'),
        ('CANCELLED', 'Cancelado'),
        ('REFUNDED', 'Estornado'),
    ]

    # Campos existentes (mantidos)
    estabelecimento = models.ForeignKey('Estabelecimento', on_delete=models.CASCADE, null=True, blank=True)
    cliente = models.ForeignKey('Cliente', on_delete=models.SET_NULL, null=True, blank=True)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    agendamento = models.ForeignKey('Agendamento', on_delete=models.SET_NULL, null=True, blank=True)
    produto = models.ForeignKey('Produto', on_delete=models.SET_NULL, null=True, blank=True)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    metodo = models.CharField(max_length=50, choices=METODO_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    codigo_transacao = models.CharField(max_length=100, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    descricao = models.CharField(max_length=255, blank=True, null=True, default='Pagamento AgendaFlow')

    # Novos campos (serão adicionados na migração)
    valor_desconto = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    valor_taxa = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    valor_liquido = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Dados do pagamento
    gateway_transacao_id = models.CharField(max_length=255, blank=True, null=True)
    gateway_resposta = models.JSONField(blank=True, null=True)

    # Campos para cartão (dados mascarados)
    cartao_ultimos_digitos = models.CharField(max_length=4, blank=True, null=True)
    cartao_bandeira = models.CharField(max_length=50, blank=True, null=True)

    # PIX
    pix_qr_code = models.TextField(blank=True, null=True)
    pix_chave_destino = models.CharField(max_length=255, blank=True, null=True)

    # Boleto
    boleto_codigo_barras = models.CharField(max_length=255, blank=True, null=True)
    boleto_linha_digitavel = models.CharField(max_length=255, blank=True, null=True)
    boleto_vencimento = models.DateField(blank=True, null=True)

    # Controle
    tentativas_pagamento = models.PositiveIntegerField(default=0)
    data_vencimento = models.DateTimeField(blank=True, null=True)
    observacoes = models.TextField(blank=True, null=True)

    # Dados de auditoria
    ip_origem = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)

    # ⭐ NOVOS CAMPOS ADICIONADOS (serão criados na migração) ⭐
    reference_id = models.CharField('Reference ID', max_length=255, blank=True, null=True, unique=True)
    dados_resposta = models.JSONField('Dados da Resposta API', blank=True, null=True)
    def save(self, *args, **kwargs):
        """Método save corrigido - conversão adequada de tipos"""

        # ⭐ CORREÇÃO: Converter todos os valores para Decimal antes da operação ⭐
        if self.valor_liquido is None:
            # Garantir que valor_total seja Decimal
            valor_total_decimal = Decimal(str(self.valor_total)) if not isinstance(self.valor_total,
                                                                                   Decimal) else self.valor_total

            # Garantir que valor_desconto seja Decimal
            valor_desconto_decimal = self.valor_desconto if isinstance(self.valor_desconto, Decimal) else Decimal(
                str(self.valor_desconto))

            # Garantir que valor_taxa seja Decimal
            valor_taxa_decimal = self.valor_taxa if isinstance(self.valor_taxa, Decimal) else Decimal(
                str(self.valor_taxa))

            # Agora fazer o cálculo com todos os valores em Decimal
            self.valor_liquido = valor_total_decimal - valor_desconto_decimal - valor_taxa_decimal

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Transação {self.id} - R$ {self.valor_total} ({self.get_status_display()})"

    class Meta:
        verbose_name = "Transação de Pagamento"
        verbose_name_plural = "Transações de Pagamento"
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['status', 'criado_em']),
            models.Index(fields=['codigo_transacao']),
            models.Index(fields=['gateway_transacao_id']),
        ]

    @property
    def is_paid(self):
        """Verifica se o pagamento está pago"""
        return self.status == 'PAID'

    def marcar_como_pago(self):
        """Marca a transação como paga e atualiza o agendamento se existir"""
        self.status = 'PAID'
        self.save()

        if self.agendamento:
            self.agendamento.pago = True
            self.agendamento.save()

        return True


class PagBankTransaction(models.Model):
    agendamento = models.ForeignKey(Agendamento, on_delete=models.CASCADE)
    transaction_id = models.CharField(max_length=100, unique=True)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    status_pagamento = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pendente'),
        ('PAID', 'Pago'),
        ('CANCELLED', 'Cancelado'),
    ])
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Transação PagBank"
        verbose_name_plural = "Transações PagBank"


class ConfiguracaoLembrete(models.Model):
    """Configurações de lembrete por tenant/clínica"""
    estabelecimento = models.ForeignKey('Estabelecimento', on_delete=models.CASCADE)  # Substitua pelo seu model de tenant
    ativo = models.BooleanField(default=True)
    dias_antecedencia = models.IntegerField(default=1)  # Quantos dias antes enviar
    horario_envio = models.TimeField(default='09:00')  # Horário para enviar os lembretes
    template_whatsapp = models.TextField(
        default="Olá {nome_paciente}! Lembramos que você tem consulta marcada para {data_consulta} às {hora_consulta} na {nome_clinica}. Para cancelar ou reagendar, entre em contato conosco."
    )
    template_email = models.TextField(
        default="Olá {nome_paciente}! Este é um lembrete de sua consulta marcada para: Data: {data_consulta} Horário: {hora_consulta} Local: {nome_clinica} Para cancelar ou reagendar, entre em contato conosco. Atenciosamente, Equipe {nome_clinica}"
    )

    def __str__(self):
        return f"Configuração de Lembrete - {self.estabelecimento.nome}"


class HistoricoLembrete(models.Model):
    """Histórico de lembretes enviados"""
    TIPO_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('email', 'E-mail'),
        ('sms', 'SMS'),
    ]

    STATUS_CHOICES = [
        ('enviado', 'Enviado'),
        ('erro', 'Erro'),
        ('pendente', 'Pendente'),
    ]

    estabelecimento = models.ForeignKey('Estabelecimento', on_delete=models.CASCADE)  # Substitua pelo seu model de consulta
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente')
    mensagem_enviada = models.TextField()
    data_envio = models.DateTimeField(auto_now_add=True)
    erro_detalhes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Lembrete {self.tipo} - {self.estabelecimento.Agendamento.nome} - {self.status}"


class InsightIA(models.Model):
    prontuario = models.OneToOneField(Prontuario, on_delete=models.CASCADE)
    descricao = models.TextField()
    tags = models.CharField(max_length=255, help_text="Separe as tags por vírgulas")
    sugestao_ia = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    modelo_usado = models.CharField(max_length=100, default="gpt-4", blank=True)

    def __str__(self):
        return f"Insight IA para {self.prontuario}"


class ConfiguracaoEmail(models.Model):
    estabelecimento = models.OneToOneField(Estabelecimento, on_delete=models.CASCADE)

    # Configurações do Email
    email_usuario = models.EmailField(help_text="Email do estabelecimento (ex: clinica@gmail.com)")
    email_senha = models.CharField(max_length=200, help_text="Senha de app do Gmail")
    email_smtp = models.CharField(max_length=100, default="smtp.gmail.com")
    email_porta = models.IntegerField(default=587)
    email_use_tls = models.BooleanField(default=True, help_text="Usar TLS/SSL")

    # Configurações por Provedor
    PROVEDOR_CHOICES = [
        ('gmail', 'Gmail'),
        ('outlook', 'Outlook/Hotmail'),
        ('yahoo', 'Yahoo'),
        ('outro', 'Outro'),
    ]
    provedor = models.CharField(max_length=20, choices=PROVEDOR_CHOICES, default='gmail')
    # Templates
    template_assunto = models.CharField(max_length=200, default="Lembrete de Consulta - {nome_clinica}")
    template_corpo = models.TextField(
        default="Olá {nome_paciente}! Lembrete: você tem consulta marcada para {data_consulta} às {hora_consulta} na {nome_clinica}. Atenciosamente, Equipe {nome_clinica}")


    # Configurações
    ativo = models.BooleanField(default=False)
    dias_antecedencia = models.IntegerField(default=1)
    horario_envio = models.TimeField(default="09:00")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ultimo_teste = models.DateTimeField(null=True, blank=True)
    status_ultimo_teste = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Email Config - {self.estabelecimento.nome} ({self.email_usuario})"

