from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import Cliente

def clientes_view(request):
    clientes = Cliente.objects.all().order_by('nombre')
    return render(request, 'clientes/clientes.html', {'clientes': clientes})

def add_client(request):
    if request.method == 'POST':
        try:
            # Validar campos requeridos
            required_fields = ['nombre', 'email', 'domicilio', 'dias_pago']
            for field in required_fields:
                if not request.POST.get(field):
                    raise ValidationError(f'El campo {field} es requerido')

            # Crear el cliente
            cliente = Cliente.objects.create(
                nombre=request.POST['nombre'],
                ciudad=request.POST.get('ciudad', ''),
                email=request.POST['email'],
                email2=request.POST.get('email2', ''),
                telefono=request.POST.get('telefono', ''),
                dias_pago=request.POST['dias_pago'],
                domicilio=request.POST['domicilio'],
                cif=request.POST.get('cif', '')
            )
            messages.success(request, 'Cliente agregado exitosamente')
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error al agregar el cliente: {str(e)}')
    return redirect('clientes')

def get_client(request, client_id):
    try:
        cliente = get_object_or_404(Cliente, id=client_id)
        data = {
            'id': cliente.id,
            'nombre': cliente.nombre,
            'ciudad': cliente.ciudad,
            'email': cliente.email,
            'email2': cliente.email2,
            'telefono': cliente.telefono,
            'dias_pago': cliente.dias_pago,
            'domicilio': cliente.domicilio,
            'cif': cliente.cif
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

def edit_client(request, client_id):
    if request.method == 'POST':
        try:
            cliente = get_object_or_404(Cliente, id=client_id)
            
            # Validar campos requeridos
            required_fields = ['nombre', 'email', 'domicilio', 'dias_pago']
            for field in required_fields:
                if not request.POST.get(field):
                    raise ValidationError(f'El campo {field} es requerido')

            # Actualizar el cliente
            cliente.nombre = request.POST['nombre']
            cliente.ciudad = request.POST.get('ciudad', '')
            cliente.email = request.POST['email']
            cliente.email2 = request.POST.get('email2', '')
            cliente.telefono = request.POST.get('telefono', '')
            cliente.dias_pago = request.POST['dias_pago']
            cliente.domicilio = request.POST['domicilio']
            cliente.cif = request.POST.get('cif', '')
            
            cliente.save()
            messages.success(request, 'Cliente actualizado exitosamente')
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error al actualizar el cliente: {str(e)}')
    return redirect('clientes')
