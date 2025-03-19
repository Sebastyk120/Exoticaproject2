import re
from decimal import Decimal
from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from num2words import num2words

register = template.Library()

@register.filter
def filter_by_id(queryset, id_value):
    """Filter a queryset by ID and return the filtered queryset"""
    try:
        return queryset.filter(id=id_value)
    except (AttributeError, ValueError):
        return []

@register.filter(name='to_int')
def to_int(value):
    try:
        return int(value)
    except ValueError:
        return value

@register.filter
def format_currency(value):
    try:
        formatted_value = '{:,.2f}'.format(float(value)).replace(',', '@').replace('.', ',').replace('@', '.')
        return f"${formatted_value}"
    except (ValueError, TypeError):
        return value

@register.filter
def format_number(value):
    try:
        formatted_value = '{:,.2f}'.format(float(value)).replace(',', '@').replace('.', ',').replace('@', '.')
        return formatted_value
    except (ValueError, TypeError):
        return value

@register.filter
def format_percentage_color_exportacion(value):
    if value is None:
        return ""

    if 0 <= value <= 40:
        color = "red"
    elif 40 < value <= 70:
        color = "orange"
    elif 70 < value <= 100:
        color = "green"
    else:
        color = "black"

    return format_html('<span style="color: {};">{}%</span>', color, value)

@register.filter
def format_percentage_color_nacional(value):
    if value is None:
        return ""

    if 0 <= value <= 40:
        color = "green"
    elif 40 < value <= 70:
        color = "orange"
    elif 70 < value <= 100:
        color = "red"
    else:
        color = "black"

    return format_html('<span style="color: {};">{}%</span>', color, value)


@register.filter
def format_percentage_color_merma(value):
    if value is None:
        return ""

    if 0 <= value <= 5:
        color = "green"
    elif 5 < value <= 10:
        color = "orange"
    elif 10 < value <= 100:
        color = "red"
    else:
        color = "black"

    return format_html('<span style="color: {};">{}%</span>', color, value)

@register.filter
def trend_indicator(value):
    try:
        value = float(value)
        if value > 0:
            return "up"
        elif value < 0:
            return "down"
        else:
            return ""
    except (ValueError, TypeError):
        return ""

@register.filter
def sub(value, arg):
    """Subtract the arg from the value."""
    try:
        return value - arg
    except (ValueError, TypeError):
        try:
            return value - float(arg)
        except (ValueError, TypeError):
            return 0


@register.filter(name='numero_a_letras')
def numero_a_letras(value):
    """Convertir número a texto en español con formato de moneda"""
    if value is None:
        return "Cero pesos"

    try:
        # Redondear a 2 decimales y convertir a string formateado
        value = Decimal(value).quantize(Decimal('0.01'))
        value_str = f"{value:,.2f}"  # Formato con 2 decimales
        
        # Separar parte entera y decimal
        entero_str, decimal_str = value_str.split('.')
        entero = int(entero_str.replace(',', ''))  # Quitar comas de miles
        decimal = int(decimal_str)
        
        # Convertir parte entera a texto
        texto_entero = num2words(entero, lang='es')
        
        # Corregir contracciones gramaticales
        texto_entero = re.sub(r'(\buno)(?= mil\b)', r'un', texto_entero, flags=re.IGNORECASE)
        texto_entero = re.sub(r'(\bciento un\b)', r'ciento un', texto_entero, flags=re.IGNORECASE)
        
        # Formatear texto final
        if decimal > 0:
            return f"{texto_entero.capitalize()} pesos colombianos con {decimal:02d} centavos."
        else:
            return f"{texto_entero.capitalize()} pesos colombianos."
            
    except Exception as e:
        return f"Error: {str(e)}"

@register.filter(name='abs')
def abs_value(value):
    """Return the absolute value of a number"""
    try:
        return abs(value)
    except (ValueError, TypeError):
        return value
    
@register.filter(name='multiply')
def multiply(value, arg):
    """Multiplies the value by the argument"""
    try:
        return value * arg
    except (ValueError, TypeError):
        return 0
        
@register.filter(name='add')
def add_values(value, arg):
    """Add two values together"""
    try:
        return value + arg
    except (ValueError, TypeError):
        return 0