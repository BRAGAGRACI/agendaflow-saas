from datetime import timedelta

from django import forms
from django.contrib.auth.models import User

from .models import Agendamento, Cliente, Servico, Profissional, Prontuario, Estabelecimento, InsightIA
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Estabelecimento
import re

class CadastroEstabelecimentoForm(forms.Form):
    nome = forms.CharField(label='Nome do Responsável')
    nome_estabelecimento = forms.CharField(label='Nome do Estabelecimento')
    email = forms.EmailField(label='E-mail (usado como login)')
    telefone = forms.CharField(label='Telefone')
    senha = forms.CharField(label='Senha', widget=forms.PasswordInput())
    confirmar_senha = forms.CharField(label='Confirmar Senha', widget=forms.PasswordInput())

    def clean(self):
        cleaned_data = super().clean()
        senha = cleaned_data.get('senha')
        confirmar = cleaned_data.get('confirmar_senha')
        email = cleaned_data.get('email')

        if senha and confirmar and senha != confirmar:
            raise ValidationError('As senhas não coincidem.')

        if User.objects.filter(username=email).exists():
            raise ValidationError('Já existe um usuário com este e-mail.')

        return cleaned_data

    def save(self):
        cleaned_data = self.cleaned_data

        # Cria o usuário com e-mail como username
        user = User.objects.create_user(
            username=cleaned_data['email'],  # e-mail como username
            email=cleaned_data['email'],
            first_name=cleaned_data['nome'],
            password=cleaned_data['senha']
        )

        # Cria o estabelecimento vinculado ao usuário
        estabelecimento = Estabelecimento.objects.create(
            nome=cleaned_data['nome_estabelecimento'],
            responsavel=cleaned_data['nome'],
            telefone=cleaned_data['telefone'],
            email=cleaned_data['email'],
            senha=user.password,  # só pra exibir, nunca use isso pra login
            usuario=user
        )

        return estabelecimento


from .models import Agendamento, Cliente, Profissional, Servico, Produto


class AgendamentoForm(forms.ModelForm):
    metodo_pagamento = forms.ChoiceField(
        choices=[
            ('', 'Não pagar agora'),
            ('BOLETO', 'Boleto'),
            ('PIX', 'PIX'),
            ('CARTAO', 'Cartão'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Agendamento
        fields = ['data', 'hora', 'duracao', 'valor', 'forma_pagamento', 'status', 'metodo_pagamento']
        exclude = ['estabelecimento', 'cliente', 'profissional', 'servico', 'valor_profissional', 'produtos']
        widgets = {
            'data': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'hora': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'duracao': forms.NumberInput(attrs={'class': 'form-control'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'forma_pagamento': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'metodo_pagamento': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean_duracao(self):
        valor = self.cleaned_data.get('duracao')
        if valor in [None, '']:
            return None
        try:
            return int(valor)
        except (ValueError, TypeError):
            raise forms.ValidationError('Duração deve ser um número inteiro (minutos).')


class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = ['nome','codigo', 'quantidade', 'preco_unitario']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo': forms.NumberInput(attrs={'class': 'form-control'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control'}),
            'preco_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


#class AgendamentoForm(forms.ModelForm):
 #   class Meta:
  #      model = Agendamento
   #     fields = ['cliente', 'profissional', 'servico', 'data', 'hora', 'duracao', 'valor', 'status']
    #    widgets = {
     #       'data': forms.DateInput(attrs={'type': 'date'}),
      #      'hora': forms.TimeInput(attrs={'type': 'time'}),
        #  }

class ProntuarioForm(forms.ModelForm):
    profissional = forms.ModelChoiceField(
        queryset=Profissional.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Profissional",
        empty_label=None,
        required=True
    )

    class Meta:
        model = Prontuario
        fields = [  'cliente', 'profissional', 'agendamento', 'observacoes',
            'descricao', 'tags', 'imagem', 'anexo', 'situacao']
        widgets = {
            'observacoes': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'tags': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'imagem': forms.FileInput(attrs={'class': 'form-control'}),
            'anexo': forms.FileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'observacoes': 'Observações',
            'tags': 'Tags',
            'descricao': 'Anotações e Evolução',
            'arquivos': 'Arquivos',
            'imagem': 'Imagem',
            'anexo': 'Anexo',
        }
        help_texts = {
            'tags': 'Separe as tags por vírgulas (ex.: botox, pele, laser).',
        }

    def clean_profissional(self):
        profissional = self.cleaned_data.get('profissional')
        if not profissional:
            raise forms.ValidationError("Você deve selecionar um profissional.")
        return profissional

class InsightIAForm(forms.ModelForm):
    class Meta:
        model = InsightIA
        fields = ['descricao', 'tags', 'sugestao_ia', 'modelo_usado']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'tags': forms.TextInput(attrs={'class': 'form-control'}),
            'sugestao_ia': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'readonly': 'readonly'}),
        }


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        exclude = ['estabelecimento']
        fields = '__all__'
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'cpf': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'nascimento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'endereco': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


# forms.py
from django import forms
from datetime import timedelta
from .models import Servico


class ServicoForm(forms.ModelForm):
    duracao_horas = forms.IntegerField(
        min_value=0,
        max_value=23,
        initial=0,
        label="Horas",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0'
        })
    )
    duracao_minutos = forms.IntegerField(
        min_value=0,
        max_value=59,
        initial=30,
        label="Minutos",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '30'
        })
    )

    class Meta:
        model = Servico
        exclude = ['estabelecimento', 'duracao']  # Excluímos duracao porque vamos usar os campos customizados
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome do serviço'
            }),
            'especialidade': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Especialidade (opcional)'
            }),
            'valor': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descrição do serviço (opcional)'
            }),
            'valor_padrao': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': '0.00'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Tornar campos obrigatórios
        self.fields['nome'].required = True
        self.fields['valor'].required = True

        # Se é um serviço existente e tem duração, preenche os campos
        if self.instance.pk and self.instance.duracao:
            total_seconds = self.instance.duracao.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            self.fields['duracao_horas'].initial = hours
            self.fields['duracao_minutos'].initial = minutes

    def clean(self):
        cleaned_data = super().clean()
        horas = cleaned_data.get('duracao_horas', 0)
        minutos = cleaned_data.get('duracao_minutos', 0)

        # Validar se a duração não é zero
        if horas == 0 and minutos == 0:
            raise forms.ValidationError("A duração deve ser maior que zero.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Converter horas e minutos para o formato esperado pelo modelo
        horas = self.cleaned_data.get('duracao_horas', 0)
        minutos = self.cleaned_data.get('duracao_minutos', 0)

        # Verificar o tipo do campo duracao no modelo
        duracao_field = instance._meta.get_field('duracao')

        if hasattr(duracao_field, 'get_internal_type'):
            field_type = duracao_field.get_internal_type()

            if field_type == 'DurationField':
                # Se for DurationField, usar timedelta
                instance.duracao = timedelta(hours=horas, minutes=minutos)
            elif field_type in ['TimeField', 'CharField']:
                # Se for TimeField ou CharField, converter para string no formato HH:MM
                from datetime import time
                duracao_time = time(hour=horas, minute=minutos)
                instance.duracao = duracao_time.strftime('%H:%M')
            else:
                # Tentar como string no formato HH:MM:SS
                total_seconds = (horas * 3600) + (minutos * 60)
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                instance.duracao = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        else:
            # Fallback: tentar como string HH:MM
            instance.duracao = f"{horas:02d}:{minutos:02d}"

        if commit:
            instance.save()
        return instance

#class ServicoForm(forms.ModelForm):
 #   class Meta:
  #      model = Servico
   #     exclude = ['estabelecimento']
    #    fields = '__all__'
     #   widgets = {
      #      'nome': forms.TextInput(attrs={'class': 'form-control'}),
       #     'especialidade': forms.TextInput(attrs={'class': 'form-control'}),
        #    'duracao': forms.NumberInput(attrs={'class': 'form-control'}),
         #   'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
          #  'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
           # 'valor_padrao': forms.NumberInput(attrs={'class': 'form-control'}),
       # }




#class ProfissionalForm(forms.ModelForm):
 #   class Meta:
  #      model = Profissional
   #     fields = '__all__'
    #    widgets = {
     #       'nome': forms.TextInput(attrs={'class': 'form-control'}),
      #      'especialidade': forms.TextInput(attrs={'class': 'form-control'}),
       #     'percentual_comissao': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        #    'email': forms.EmailInput(attrs={'class': 'form-control'}),
        #}

class ProfissionalForm(forms.ModelForm):
    class Meta:
        model = Profissional
        fields = ['nome', 'cpf', 'cnpj', 'telefone', 'especialidade', 'email', 'endereco', 'percentual_comissao']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'cpf': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '000.000.000-00'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00.000.000/0000-00'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(00) 00000-0000'}),
            'especialidade': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'endereco': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'percentual_comissao': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}
            ),
        }
        labels = {
            'nome': 'Nome',
            'cpf': 'CPF',
            'cnpj': 'CNPJ',
            'telefone': 'Telefone',
            'especialidade': 'Especialidade',
            'email': 'E-mail',
            'endereco': 'Endereço',
            'percentual_comissao': 'Percentual de Comissão (%)',
        }

    # CORREÇÃO: Estava com erro de digitação (__init__ não init)
    def __init__(self, *args, **kwargs):
        self.estabelecimento = kwargs.pop('estabelecimento', None)
        super().__init__(*args, **kwargs)

    def clean_cpf(self):
        """Limpa e valida o CPF"""
        cpf = self.cleaned_data.get('cpf')
        if cpf:
            # Remove todos os caracteres não numéricos
            cpf_limpo = re.sub(r'\D', '', cpf)

            # Verifica se tem 11 dígitos
            if len(cpf_limpo) != 11:
                raise ValidationError('CPF deve conter 11 dígitos.')

            # Verifica se todos os dígitos são iguais (CPF inválido)
            if len(set(cpf_limpo)) == 1:
                raise ValidationError('CPF inválido.')

            # Validação do CPF
            def validar_cpf(cpf):
                # Calcula primeiro dígito verificador
                soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
                resto = soma % 11
                digito1 = 0 if resto < 2 else 11 - resto

                # Calcula segundo dígito verificador
                soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
                resto = soma % 11
                digito2 = 0 if resto < 2 else 11 - resto

                return cpf[-2:] == f"{digito1}{digito2}"

            if not validar_cpf(cpf_limpo):
                raise ValidationError('CPF inválido.')

            return cpf_limpo
        return cpf

    def clean_cnpj(self):
        """Limpa e valida o CNPJ"""
        cnpj = self.cleaned_data.get('cnpj')
        if cnpj:
            # Remove todos os caracteres não numéricos
            cnpj_limpo = re.sub(r'\D', '', cnpj)

            # Verifica se tem 14 dígitos
            if len(cnpj_limpo) != 14:
                raise ValidationError('CNPJ deve conter 14 dígitos.')

            # Verifica se todos os dígitos são iguais (CNPJ inválido)
            if len(set(cnpj_limpo)) == 1:
                raise ValidationError('CNPJ inválido.')

            return cnpj_limpo
        return cnpj

    def clean_telefone(self):
        """Limpa o telefone"""
        telefone = self.cleaned_data.get('telefone')
        if telefone:
            # Remove todos os caracteres não numéricos
            telefone_limpo = re.sub(r'\D', '', telefone)
            return telefone_limpo
        return telefone

    def clean(self):
        cleaned_data = super().clean()

        # Verifica se o estabelecimento foi passado
        if not self.estabelecimento:
            raise ValidationError('Erro interno: Nenhum estabelecimento associado ao formulário.')

        # Verifica limite de profissionais
        limite_profissionais = self.estabelecimento.plano.max_profissionais
        profissionais_atuais = self.estabelecimento.profissional_set.filter(ativo=True).count()

        if not self.instance.pk and profissionais_atuais >= limite_profissionais:
            raise ValidationError(
                f'Limite de {limite_profissionais} profissionais atingido para o plano '
                f'{self.estabelecimento.plano.nome}. Atualize seu plano para adicionar mais profissionais.'
            )

        # Verifica se pelo menos CPF ou CNPJ foi informado
        cpf = cleaned_data.get('cpf')
        cnpj = cleaned_data.get('cnpj')
        if not cpf and not cnpj:
            raise ValidationError('É necessário informar pelo menos um CPF ou CNPJ.')

        return cleaned_data

    def clean_percentual_comissao(self):
        """Valida o percentual de comissão"""
        percentual = self.cleaned_data.get('percentual_comissao')
        if percentual is not None and (percentual < 0 or percentual > 100):
            raise ValidationError("O percentual de comissão deve estar entre 0 e 100.")
        return percentual



