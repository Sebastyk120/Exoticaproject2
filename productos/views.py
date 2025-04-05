from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from .models import Fruta, Presentacion, ListaPreciosImportacion, ListaPreciosVentas
from importacion.models import Exportador
from comercial.models import Cliente
from decimal import Decimal

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
    paginator = Paginator(precios_queryset, 10)  # Show 10 items per page
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
    paginator = Paginator(precios_queryset, 10)  # Show 10 items per page
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
