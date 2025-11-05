from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from .models import Fruta, Presentacion, ListaPreciosImportacion, ListaPreciosVentas
from importacion.models import Exportador
from comercial.models import Cliente, Cotizacion, DetalleCotizacion, EmailLog
from decimal import Decimal
import json
import datetime
from django.conf import settings
import base64
from comercial.views_enviar_correos import send_email_with_mailjet

@login_required
def frutas_view(request):
    frutas = Fruta.objects.all()
    return render(request, 'frutas.html', {'frutas': frutas})

@login_required
def create_fruta(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        if nombre:
            Fruta.objects.create(nombre=nombre)
        return redirect('frutas_view')
    return JsonResponse({'status': 'error'})

# Vista para gestionar las presentaciones (solo visualización y creación)
@login_required
def presentaciones_view(request):
    presentaciones = Presentacion.objects.all().order_by('fruta__nombre', 'kilos')
    frutas = Fruta.objects.all().order_by('nombre')
    return render(request, 'presentaciones.html', {
        'presentaciones': presentaciones,
        'frutas': frutas
    })

@login_required
def create_presentacion(request):
    if request.method == 'POST':
        fruta_id = request.POST.get('fruta')
        kilos = request.POST.get('kilos')
        
        if fruta_id and kilos:
            try:
                fruta = Fruta.objects.get(id=fruta_id)
                Presentacion.objects.create(
                    fruta=fruta,
                    kilos=kilos
                )
                messages.success(request, 'Presentación creada con éxito.')
            except Exception as e:
                messages.error(request, f'Error al crear presentación: {str(e)}')
        else:
            messages.error(request, 'Datos incompletos. Por favor, complete todos los campos.')
        
        return redirect('presentaciones_view')
    
    return JsonResponse({'status': 'error'})

@login_required
def lista_precios_importacion(request):
    # Get all necessary data
    frutas = Fruta.objects.all().order_by('nombre')
    presentaciones = Presentacion.objects.all().order_by('fruta__nombre', 'kilos')
    exportadores = Exportador.objects.all().order_by('nombre')
    
    # Base queryset
    precios_queryset = ListaPreciosImportacion.objects.select_related('presentacion', 'presentacion__fruta', 'exportador').all()
    
    # Apply filters
    if 'search' in request.GET and request.GET['search']:
        search_term = request.GET['search']
        precios_queryset = precios_queryset.filter(
            Q(presentacion__fruta__nombre__icontains=search_term) |
            Q(presentacion__kilos__icontains=search_term) |
            Q(exportador__nombre__icontains=search_term)
        )
    
    if 'fruta' in request.GET and request.GET['fruta']:
        fruta_id = request.GET['fruta']
        precios_queryset = precios_queryset.filter(presentacion__fruta_id=fruta_id)
    
    if 'exportador' in request.GET and request.GET['exportador']:
        exportador_id = request.GET['exportador']
        precios_queryset = precios_queryset.filter(exportador_id=exportador_id)
    
    if 'fecha_desde' in request.GET and request.GET['fecha_desde']:
        fecha_desde = request.GET['fecha_desde']
        precios_queryset = precios_queryset.filter(fecha__gte=fecha_desde)
    
    if 'fecha_hasta' in request.GET and request.GET['fecha_hasta']:
        fecha_hasta = request.GET['fecha_hasta']
        precios_queryset = precios_queryset.filter(fecha__lte=fecha_hasta)
    
    # Paginate results
    paginator = Paginator(precios_queryset, 25)  # Show 10 items per page
    page_number = request.GET.get('page', 1)
    precios = paginator.get_page(page_number)
    
    context = {
        'precios': precios,
        'frutas': frutas,
        'presentaciones': presentaciones,
        'exportadores': exportadores,
    }
    
    return render(request, 'lista_precios_importacion.html', context)

@login_required
def crear_precio_importacion(request):
    if request.method == 'POST':
        presentacion_id = request.POST.get('presentacion')
        precio_usd = request.POST.get('precio_usd')
        exportador_id = request.POST.get('exportador')
        
        try:
            # Validate inputs
            if not all([presentacion_id, precio_usd, exportador_id]):
                messages.error(request, 'Todos los campos son requeridos.')
                return redirect('lista_precios_importacion')
            
            precio_decimal = Decimal(precio_usd)
            if precio_decimal <= 0 or precio_decimal > 100:
                messages.error(request, 'El precio debe estar entre 0.1 y 100 USD.')
                return redirect('lista_precios_importacion')
                
            presentacion = Presentacion.objects.get(id=presentacion_id)
            exportador = Exportador.objects.get(id=exportador_id)
            
            # Check if the combination already exists (unique_together constraint)
            existing = ListaPreciosImportacion.objects.filter(
                presentacion=presentacion,
                exportador=exportador
            ).first()
            
            if existing:
                # Update existing record
                existing.precio_usd = precio_decimal
                existing.save()
                messages.success(request, 'Precio actualizado correctamente.')
            else:
                # Create new record
                ListaPreciosImportacion.objects.create(
                    presentacion=presentacion,
                    precio_usd=precio_decimal,
                    exportador=exportador
                )
                messages.success(request, 'Precio creado correctamente.')
            
        except Presentacion.DoesNotExist:
            messages.error(request, 'La presentación seleccionada no existe.')
        except Exportador.DoesNotExist:
            messages.error(request, 'El exportador seleccionado no existe.')
        except ValueError:
            messages.error(request, 'El valor del precio no es válido.')
        except Exception as e:
            messages.error(request, f'Error al guardar el precio: {str(e)}')
            
    return redirect('lista_precios_importacion')

@login_required
def editar_precio_importacion(request, precio_id):
    precio = get_object_or_404(ListaPreciosImportacion, id=precio_id)
    
    if request.method == 'POST':
        presentacion_id = request.POST.get('presentacion')
        precio_usd = request.POST.get('precio_usd')
        exportador_id = request.POST.get('exportador')
        
        try:
            # Validate inputs
            if not all([presentacion_id, precio_usd, exportador_id]):
                messages.error(request, 'Todos los campos son requeridos.')
                return redirect('lista_precios_importacion')
            
            precio_decimal = Decimal(precio_usd)
            if precio_decimal <= 0 or precio_decimal > 100:
                messages.error(request, 'El precio debe estar entre 0.1 y 100 USD.')
                return redirect('lista_precios_importacion')
                
            presentacion = Presentacion.objects.get(id=presentacion_id)
            exportador = Exportador.objects.get(id=exportador_id)
            
            # Check if this combination already exists for another record
            existing = ListaPreciosImportacion.objects.filter(
                presentacion=presentacion,
                exportador=exportador
            ).exclude(id=precio_id).first()
            
            if existing:
                messages.error(request, 'Ya existe un precio para esta combinación de presentación y exportador.')
            else:
                precio.presentacion = presentacion
                precio.precio_usd = precio_decimal
                precio.exportador = exportador
                precio.save()
                messages.success(request, 'Precio actualizado correctamente.')
            
        except Presentacion.DoesNotExist:
            messages.error(request, 'La presentación seleccionada no existe.')
        except Exportador.DoesNotExist:
            messages.error(request, 'El exportador seleccionado no existe.')
        except ValueError:
            messages.error(request, 'El valor del precio no es válido.')
        except Exception as e:
            messages.error(request, f'Error al actualizar el precio: {str(e)}')
            
    return redirect('lista_precios_importacion')

@login_required
def lista_precios_ventas(request):
    # Get all necessary data
    frutas = Fruta.objects.all().order_by('nombre')
    presentaciones = Presentacion.objects.all().order_by('fruta__nombre', 'kilos')
    clientes = Cliente.objects.all().order_by('nombre')
    
    # Base queryset
    precios_queryset = ListaPreciosVentas.objects.select_related('presentacion', 'presentacion__fruta', 'cliente').all()
    
    # Apply filters
    if 'search' in request.GET and request.GET['search']:
        search_term = request.GET['search']
        precios_queryset = precios_queryset.filter(
            Q(presentacion__fruta__nombre__icontains=search_term) |
            Q(presentacion__kilos__icontains=search_term) |
            Q(cliente__nombre__icontains=search_term)
        )
    
    if 'fruta' in request.GET and request.GET['fruta']:
        fruta_id = request.GET['fruta']
        precios_queryset = precios_queryset.filter(presentacion__fruta_id=fruta_id)
    
    if 'cliente' in request.GET and request.GET['cliente']:
        cliente_id = request.GET['cliente']
        precios_queryset = precios_queryset.filter(cliente_id=cliente_id)
    
    if 'fecha_desde' in request.GET and request.GET['fecha_desde']:
        fecha_desde = request.GET['fecha_desde']
        precios_queryset = precios_queryset.filter(fecha__gte=fecha_desde)
    
    if 'fecha_hasta' in request.GET and request.GET['fecha_hasta']:
        fecha_hasta = request.GET['fecha_hasta']
        precios_queryset = precios_queryset.filter(fecha__lte=fecha_hasta)
    
    # Paginate results
    paginator = Paginator(precios_queryset, 25)  # Show 10 items per page
    page_number = request.GET.get('page', 1)
    precios = paginator.get_page(page_number)
    
    context = {
        'precios': precios,
        'frutas': frutas,
        'presentaciones': presentaciones,
        'clientes': clientes,
    }
    
    return render(request, 'lista_precios_ventas.html', context)

@login_required
def crear_precio_ventas(request):
    if request.method == 'POST':
        presentacion_id = request.POST.get('presentacion')
        precio_euro = request.POST.get('precio_euro')
        cliente_id = request.POST.get('cliente')
        
        try:
            # Validate inputs
            if not all([presentacion_id, precio_euro, cliente_id]):
                messages.error(request, 'Todos los campos son requeridos.')
                return redirect('lista_precios_ventas')
            
            precio_decimal = Decimal(precio_euro)
            if precio_decimal <= 0 or precio_decimal > 100:
                messages.error(request, 'El precio debe estar entre 0.1 y 100 Euros.')
                return redirect('lista_precios_ventas')
                
            presentacion = Presentacion.objects.get(id=presentacion_id)
            cliente = Cliente.objects.get(id=cliente_id)
            
            # Check if the combination already exists (unique_together constraint)
            existing = ListaPreciosVentas.objects.filter(
                presentacion=presentacion,
                cliente=cliente
            ).first()
            
            if existing:
                # Update existing record
                existing.precio_euro = precio_decimal
                existing.save()
                messages.success(request, 'Precio actualizado correctamente.')
            else:
                # Create new record
                ListaPreciosVentas.objects.create(
                    presentacion=presentacion,
                    precio_euro=precio_decimal,
                    cliente=cliente
                )
                messages.success(request, 'Precio creado correctamente.')
            
        except Presentacion.DoesNotExist:
            messages.error(request, 'La presentación seleccionada no existe.')
        except Cliente.DoesNotExist:
            messages.error(request, 'El cliente seleccionado no existe.')
        except ValueError:
            messages.error(request, 'El valor del precio no es válido.')
        except Exception as e:
            messages.error(request, f'Error al guardar el precio: {str(e)}')
            
    return redirect('lista_precios_ventas')

@login_required
def editar_precio_ventas(request, precio_id):
    precio = get_object_or_404(ListaPreciosVentas, id=precio_id)
    
    if request.method == 'POST':
        presentacion_id = request.POST.get('presentacion')
        precio_euro = request.POST.get('precio_euro')
        cliente_id = request.POST.get('cliente')
        
        try:
            # Validate inputs
            if not all([presentacion_id, precio_euro, cliente_id]):
                messages.error(request, 'Todos los campos son requeridos.')
                return redirect('lista_precios_ventas')
            
            precio_decimal = Decimal(precio_euro)
            if precio_decimal <= 0 or precio_decimal > 100:
                messages.error(request, 'El precio debe estar entre 0.1 y 100 Euros.')
                return redirect('lista_precios_ventas')
                
            presentacion = Presentacion.objects.get(id=presentacion_id)
            cliente = Cliente.objects.get(id=cliente_id)
            
            # Check if this combination already exists for another record
            existing = ListaPreciosVentas.objects.filter(
                presentacion=presentacion,
                cliente=cliente
            ).exclude(id=precio_id).first()
            
            if existing:
                messages.error(request, 'Ya existe un precio para esta combinación de presentación y cliente.')
            else:
                precio.presentacion = presentacion
                precio.precio_euro = precio_decimal
                precio.cliente = cliente
                precio.save()
                messages.success(request, 'Precio actualizado correctamente.')
            
        except Presentacion.DoesNotExist:
            messages.error(request, 'La presentación seleccionada no existe.')
        except Cliente.DoesNotExist:
            messages.error(request, 'El cliente seleccionado no existe.')
        except ValueError:
            messages.error(request, 'El valor del precio no es válido.')
        except Exception as e:
            messages.error(request, f'Error al actualizar el precio: {str(e)}')
            
    return redirect('lista_precios_ventas')

@login_required
def lista_cotizaciones(request):
    """
    View to display a list of all quotations with filters
    """
    cotizaciones = Cotizacion.objects.all()
    
    # Apply filters
    if 'cliente' in request.GET and request.GET['cliente']:
        cliente_id = request.GET['cliente']
        cotizaciones = cotizaciones.filter(cliente_id=cliente_id)
    
    if 'estado' in request.GET and request.GET['estado']:
        estado = request.GET['estado']
        cotizaciones = cotizaciones.filter(estado=estado)
    
    if 'fecha_desde' in request.GET and request.GET['fecha_desde']:
        fecha_desde = request.GET['fecha_desde']
        cotizaciones = cotizaciones.filter(fecha_emision__gte=fecha_desde)
    
    if 'fecha_hasta' in request.GET and request.GET['fecha_hasta']:
        fecha_hasta = request.GET['fecha_hasta']
        cotizaciones = cotizaciones.filter(fecha_emision__lte=fecha_hasta)
    
    # Paginate results
    paginator = Paginator(cotizaciones, 25)
    page_number = request.GET.get('page', 1)
    cotizaciones_page = paginator.get_page(page_number)
    
    clientes = Cliente.objects.all().order_by('nombre')
    
    context = {
        'cotizaciones': cotizaciones_page,
        'clientes': clientes,
        'estados': Cotizacion.ESTADO_CHOICES,
    }
    
    return render(request, 'lista_cotizaciones.html', context)

@login_required
def cotizacion_cliente(request, cliente_id):
    """
    View to create a quotation for an existing customer
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    
    # Get all prices for this customer
    precios = ListaPreciosVentas.objects.filter(
        cliente=cliente
    ).select_related('presentacion', 'presentacion__fruta')

    # Formatear los precios para que usen punto como separador decimal
    for precio in precios:
        precio.precio_euro = str(precio.precio_euro).replace(',', '.')
      # Generate unique quote number in YY-XX format (same as in model)
    year_short = datetime.datetime.now().strftime('%y')
    last_quote = Cotizacion.objects.filter(numero__startswith=f"{year_short}-").order_by('-id').first()
    if last_quote:
        try:
            prev = int(last_quote.numero.split('-')[-1])
        except Exception:
            prev = 0
        seq = prev + 1
    else:
        seq = 1
    quotation_number = f"{year_short}-{seq:02d}"
    
    # Calculate validity date (15 days from now)
    quotation_date = datetime.date.today()
    valid_until = quotation_date + datetime.timedelta(days=15)
    
    context = {
        'customer': cliente,
        'precios': precios,
        'quotation_number': quotation_number,
        'quotation_date': quotation_date,
        'valid_until': valid_until,
        'tax_rate': 4,  # Default tax rate
        'current_year': datetime.datetime.now().year,
        'is_new_customer': False,
    }
    
    return render(request, 'cotizacion_precios_ventas.html', context)

@login_required
def cotizacion_prospecto(request):
    """
    View to create a quotation for a new prospect
    """
    # Get all presentations for pricing
    presentaciones = Presentacion.objects.all().select_related('fruta').order_by('fruta__nombre', 'kilos')
      # Generate unique quote number in YY-XX format (same as in model)
    year_short = datetime.datetime.now().strftime('%y')
    last_quote = Cotizacion.objects.filter(numero__startswith=f"{year_short}-").order_by('-id').first()
    if last_quote:
        try:
            prev = int(last_quote.numero.split('-')[-1])
        except Exception:
            prev = 0
        seq = prev + 1
    else:
        seq = 1
    quotation_number = f"{year_short}-{seq:02d}"
    
    # Set prospect data if provided
    prospect_name = request.GET.get('nombre', '')
    prospect_email = request.GET.get('email', '')
    prospect_address = request.GET.get('direccion', '')
    prospect_phone = request.GET.get('telefono', '')
    
    # Calculate validity date (15 days from now)
    quotation_date = datetime.date.today()
    valid_until = quotation_date + datetime.timedelta(days=15)
    
    context = {
        'presentaciones': presentaciones,
        'quotation_number': quotation_number,
        'quotation_date': quotation_date,
        'valid_until': valid_until,
        'tax_rate': 4,  # Default tax rate
        'current_year': datetime.datetime.now().year,
        'is_new_customer': True,
        'prospect_name': prospect_name,
        'prospect_email': prospect_email,
        'prospect_address': prospect_address,
        'prospect_phone': prospect_phone,
    }
    
    return render(request, 'cotizacion_precios_ventas.html', context)

@login_required
def ver_cotizacion(request, cotizacion_id):
    """
    View to display a saved quotation
    """
    cotizacion = get_object_or_404(Cotizacion, id=cotizacion_id)
    detalles = DetalleCotizacion.objects.filter(cotizacion=cotizacion).select_related('presentacion', 'presentacion__fruta')

    # Formatear los precios unitarios para que usen punto como separador decimal
    for detalle in detalles:
        detalle.precio_unitario = str(detalle.precio_unitario).replace(',', '.')

    context = {
        'cotizacion': cotizacion,
        'detalles': detalles,
        'current_year': datetime.datetime.now().year,
        'quotation_number': cotizacion.numero,
        'quotation_date': cotizacion.fecha_emision,
        'valid_until': cotizacion.fecha_validez,
    }
    
    # Si la cotización es para un cliente existente
    if cotizacion.cliente:
        context['customer'] = cotizacion.cliente
        context['is_new_customer'] = False
    # Si es para un prospecto
    else:
        context['prospect_name'] = cotizacion.prospect_nombre
        context['prospect_email'] = cotizacion.prospect_email
        context['prospect_address'] = cotizacion.prospect_direccion
        context['prospect_phone'] = cotizacion.prospect_telefono
        context['is_new_customer'] = True

    return render(request, 'cotizacion_precios_ventas.html', context)

from django.db import transaction
from django.views.decorators.http import require_http_methods

@login_required
@require_http_methods(["POST"])
def enviar_cotizacion(request):
    """
    Handles saving and/or sending a quotation.
    This view can:
    1. Save a quotation and return a PDF for download.
    2. Save a quotation and send it via email.
    """
    try:
        quotation_data = json.loads(request.POST.get('quotation_data', '{}'))
        save_quotation = request.POST.get('save_quotation') == 'true'
        download_pdf = request.POST.get('download_pdf') == 'true'

        cotizacion = None
        
        with transaction.atomic():
            # Siempre se guarda o se actualiza la cotización
            numero_cotizacion = quotation_data.get('quotation_number')
            
            # Intentar encontrar una cotización existente por número para actualizarla
            try:
                cotizacion = Cotizacion.objects.get(numero=numero_cotizacion)
                # Si existe, se actualiza en lugar de crear una nueva
                cotizacion.detalles.all().delete() # Eliminar detalles antiguos para reemplazarlos
            except Cotizacion.DoesNotExist:
                cotizacion = Cotizacion(numero=numero_cotizacion)

            # Asignar datos del cliente o prospecto
            if quotation_data.get('client') and quotation_data['client'].get('id'):
                cotizacion.cliente = get_object_or_404(Cliente, id=quotation_data['client']['id'])
                cotizacion.prospect_nombre = None
                cotizacion.prospect_email = None
                cotizacion.prospect_direccion = None
                cotizacion.prospect_telefono = None
            elif quotation_data.get('prospect'):
                prospect_info = quotation_data['prospect']
                cotizacion.prospect_nombre = prospect_info.get('name', '')
                cotizacion.prospect_email = prospect_info.get('email', '')
                cotizacion.prospect_direccion = prospect_info.get('address', '')
                cotizacion.prospect_telefono = prospect_info.get('phone', '')
                cotizacion.cliente = None

            cotizacion.fecha_validez = datetime.date.today() + datetime.timedelta(days=15)
            cotizacion.terminos = quotation_data.get('terms', '')
            cotizacion.notas = quotation_data.get('notes', '')
            
            # Si se envía por correo, el estado cambia a 'enviada'
            if not download_pdf:
                cotizacion.estado = 'enviada'
            else:
                cotizacion.estado = 'borrador'

            cotizacion.save()

            # Guardar detalles
            for item in quotation_data.get('items', []):
                DetalleCotizacion.objects.create(
                    cotizacion=cotizacion,
                    presentacion=get_object_or_404(Presentacion, id=item.get('presentation_id')),
                    precio_unitario=Decimal(item.get('unit_price', 0))
                )

        # Generar el PDF para descarga o envío
        if download_pdf:
            messages.success(request, f'Cotización #{cotizacion.numero} guardada y descargada correctamente.')
            return redirect('lista_cotizaciones')

        # Lógica de envío de correo (si no es solo descarga)
        pdf_data = request.POST.get('pdf_data', '')
        if not pdf_data:
            messages.error(request, 'No se pudo generar el PDF para el envío.')
            return redirect('lista_cotizaciones')

        pdf_content = base64.b64decode(pdf_data.replace('data:application/pdf;base64,', ''))
        
        recipients = request.POST.getlist('recipients')
        if not recipients and 'recipient_email' in request.POST:
            recipients = [request.POST['recipient_email']]

        email_subject = request.POST.get('email_subject', f'Oferta Comercial - {cotizacion.numero}')
        email_message = request.POST.get('email_message', '')

        success, error_message, _ = send_email_with_mailjet(
            subject=email_subject,
            body=email_message,
            to_emails=recipients,
            attachments=[(f'Cotizacion_{cotizacion.numero}.pdf', pdf_content, 'application/pdf')],
            proceso='cotizacion',
            usuario=request.user,
            cotizacion=cotizacion,
            cliente=cotizacion.cliente
        )

        if success:
            messages.success(request, f'Cotización #{cotizacion.numero} enviada a {", ".join(recipients)}.')
        else:
            messages.error(request, f'No se pudo enviar la cotización: {error_message}')
            # Si falla el envío, el estado debería revertirse o manejarse
            cotizacion.estado = 'borrador'
            cotizacion.save()

    except json.JSONDecodeError:
        messages.error(request, 'Error al procesar los datos de la cotización.')
    except Exception as e:
        messages.error(request, f'Ocurrió un error inesperado: {str(e)}')

    return redirect('lista_cotizaciones')
