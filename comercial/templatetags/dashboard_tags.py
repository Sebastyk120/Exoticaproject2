from django import template
import random

register = template.Library()

@register.filter
def random_percentage(value):
    """Genera un porcentaje aleatorio para las tendencias (solo para visualización)"""
    # Usamos el valor como semilla para conseguir resultados consistentes
    random.seed(value)
    return round(random.uniform(0.5, 9.5), 1)
