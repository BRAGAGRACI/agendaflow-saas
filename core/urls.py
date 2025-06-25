from django.urls import path, include
from . import views
from django.contrib.auth import views as auth_views
from django.urls import path




urlpatterns = [

    path('', views.apresentacao, name='home'),  # Página de boas-vindas
    path('apresentacao/', views.apresentacao, name='apresentacao'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('cadastro/', views.cadastro_estabelecimento, name='cadastro_estabelecimento'),
    path("exportar-excel/", views.exportar_estabelecimentos_excel, name="exportar_excel"),
    path("redirecionar/", views.redirecionar_pos_login, name="redirecionar_pos_login"),

    # Planos
    path('planos/', views.planos_view, name='planos'),
    path('upgrade-plano/<str:plano_nome>/', views.upgrade_plano, name='upgrade_plano'),
    path('escolher-plano/<int:plano_id>/', views.escolher_plano, name='escolher_plano'),
    path('dashboard/excluir-plano/<int:plano_id>/', views.excluir_plano, name='excluir_plano'),

    path('painel_administrador/', views.painel_administrador, name='painel_administrador'),
    path('painel/editar-plano/', views.editar_plano_valor, name='editar_plano_valor'),
    path('painel/editar-assinatura/', views.editar_assinatura_valor, name='editar_assinatura_valor'),
    path('painel/toggle-status/', views.toggle_status_estabelecimento, name='toggle_status_estabelecimento'),
    path('painel/criar-plano/', views.criar_plano, name='criar_plano'),

    # AGENDA
    path('agenda/', views.agenda, name='agenda'),  # Agenda completa
    path('agenda/diaria/', views.agenda_diaria, name='agenda_diaria'),  # Agenda diária
    path('agendamentos/', views.listar_agendamentos, name='listar_agendamentos'),
    path('agendamento/<int:pk>/editar/', views.editar_agendamento, name='editar_agendamento'),
    path('agendamento/<int:pk>/cancelar/', views.cancelar_agendamento, name='cancelar_agendamento'),
    path('agendamento/<int:agendamento_id>/baixar-pdf/', views.baixar_prontuario_pdf, name='baixar_prontuario_pdf'),
    path('agendamentos/<int:agendamento_id>/salvar-prontuario/', views.salvar_prontuario, name='salvar_prontuario'),
    path('agendamento/<int:agendamento_id>/pdf/', views.baixar_prontuario_pdf, name='baixar_prontuario_pdf'),


    # CLIENTES
    path('clientes/novo/', views.cadastrar_cliente, name='cadastro_cliente'),
    path('clientes/', views.listar_cliente, name='lista_cliente'),
    path('clientes/adicionar/', views.adicionar_cliente, name='adicionar_cliente'),
    path('clientes/editar/<int:id>/', views.editar_cliente, name='editar_cliente'),
    path('clientes/excluir/<int:id>/', views.excluir_cliente, name='excluir_cliente'),
    path('clientes/exportar/', views.exportar_clientes, name='exportar_clientes'),

    # SERVIÇOS
    path('servicos/novo/', views.cadastrar_servico, name='cadastro_servico'),
    path('servicos/', views.listar_servico, name='lista_servico'),
    path('servicos/adicionar/', views.adicionar_servico, name='adicionar_servico'),
    path('servicos/editar/<int:id>/', views.editar_servico, name='editar_servico'),
    path('servicos/excluir/<int:id>/', views.excluir_servico, name='excluir_servico'),
    path('servicos/exportar/', views.exportar_servicos, name='exportar_servicos'),


    # PROFISSIONAIS
    path('profissionais/novo/', views.cadastro_profissional, name='cadastro_profissional'),
    path('profissionais/', views.lista_profissional, name='lista_profissional'),
    path('profissionais/editar/<int:id>/', views.editar_profissional, name='editar_profissional'),
    path('profissionais/editar/<int:pk>/', views.editar_profissional, name='editar_profissional'),
    path('profissionais/excluir/<int:id>/', views.excluir_profissional, name='excluir_profissional'),
    path('profissionais/exportar/', views.exportar_profissionais, name='exportar_profissionais'),

    # Verificações AJAX
    path('api/verificar-limite-profissionais/', views.verificar_limite_profissionais,name='verificar_limite_profissionais'),


    # AGENDAMENTO
    path('agendamentos/novo/', views.novo_agendamento, name='novo_agendamento'),


    # PRONTUÁRIOS
    path('prontuarios/<int:cliente_id>/', views.lista_prontuarios, name='lista_prontuarios'),
    path('prontuarios/<int:cliente_id>/novo/', views.novo_prontuario, name='novo_prontuario'),
    path('prontuarios/<int:cliente_id>/novo/<int:agendamento_id>/', views.novo_prontuario, name='novo_prontuario'),

    # FINANCEIRO
    path('dashboard-financeiro/', views.dashboard_financeiro, name='dashboard_financeiro'),
    path('exportar-financeiro/excel/', views.exportar_financeiro_excel, name='exportar_financeiro_excel'),
    path('exportar-financeiro/pdf/', views.exportar_financeiro_pdf, name='exportar_financeiro_pdf'),

    # LOGIN
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    path("gerar-sugestao-ia/<int:insight_id>/", views.gerar_sugestao_ia, name="gerar_sugestao_ia"),

    path("gerar-insight/", views.gerar_insight, name="gerar_insight"),
    path('agendamento/<int:agendamento_id>/gerar_insight/', views.gerar_insight, name='gerar_insight'),

    path('horarios-vagos/', views.listar_horarios_vagos, name='listar_horarios_vagos'),
    path('horarios-vagos/pdf/', views.gerar_pdf_horarios_vagos, name='gerar_pdf_horarios_vagos'),

    # VENDA
    path('estoque/', views.gerenciar_estoque, name='gerenciar_estoque'),
    path('produtos/cadastrar/', views.cadastrar_produto, name='cadastro_produto'),
    path('produtos/editar/<int:id>/', views.editar_produto, name='editar_produto'),
    path('produtos/excluir/<int:id>/', views.excluir_produto, name='excluir_produto'),
    path('controle-estoque/', views.controle_estoque, name='controle_estoque'),
    path('nova/venda/', views.nova_venda, name='nova_venda'),
    path('vendas/nota/<int:venda_id>/pdf/', views.gerar_nota_venda_pdf, name='gerar_nota_venda_pdf'),


    # URL principal de pagamento
    path('pagamento/', views.pagamento, name='pagamento'),
    path('pagamento/<int:agendamento_id>/', views.pagamento, name='pagamento_agendamento'),

    # URLs específicas por método de pagamento
    path('pagamento/cartao/', views.pagamento_cartao, name='pagamento_cartao'),
    path('pagamento/pix/', views.pagamento_pix, name='pagamento_pix'),
    path('pagamento/boleto/', views.pagamento_boleto, name='pagamento_boleto'),

    # URLs para funcionalidades específicas
    path('pagamento/processar-cartao/', views.processar_pagamento_cartao, name='processar_pagamento_cartao'),
    path('pagamento/verificar-pix/<str:transaction_id>/', views.verificar_status_pix, name='verificar_status_pix'),
    path('pagamento/boleto-pdf/<str:transaction_id>/', views.download_boleto_pdf, name='download_boleto_pdf'),

    # API para verificar status
    path('pagamento/status/<str:transaction_id>/', views.verificar_status_pagamento, name='verificar_status_pagamento'),

    # Webhook do PagBank
    path('pagamento/webhook/pagbank/', views.webhook_pagbank, name='webhook_pagbank'),

    # Histórico de pagamentos
    path('pagamento/historico/', views.historico_pagamentos, name='historico_pagamentos'),


    path('police/', views.police, name='police'),


    # 🚀 SISTEMA DE LEMBRETES / Sistema email personalizado
    path('email-config/<int:estabelecimento_id>/', views.configurar_email_estabelecimento, name='configurar_email_estabelecimento'),
    path('email-teste-personalizado/', views.teste_email_personalizado, name='teste_email_personalizado'),
    path('email-massa-personalizado/<int:estabelecimento_id>/', views.envio_massa_personalizado, name='envio_massa_personalizado'),



]








