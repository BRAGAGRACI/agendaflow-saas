@login_required
def envio_massa_async_view(request, estabelecimento_id):
    """Envio em massa usando Celery (background)"""
    if request.method == 'POST':
        data_selecionada = request.POST.get('data_envio')

        # Iniciar task do Celery em background
        enviar_massa_async.delay(estabelecimento_id, data_selecionada)

        messages.success(request, '✅ Envio em massa iniciado em background! Verifique o histórico em alguns minutos.')
        return redirect('teste_simples')