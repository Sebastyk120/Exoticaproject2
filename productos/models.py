from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Fruta(models.Model):
    nombre = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.nombre

    class Meta:
        ordering = ['nombre']



class Presentacion(models.Model):
    fruta = models.ForeignKey(Fruta, on_delete=models.CASCADE)
    kilos = models.DecimalField(validators=[MinValueValidator(0.1), MaxValueValidator(15.1)], max_digits=10, decimal_places=2, verbose_name='Kilos')

    def __str__(self):
        return f"{self.fruta} - {self.kilos} Kg"

    class Meta:
        verbose_name = "Presentaciónes"
        ordering = ['fruta__nombre']


class ListaPreciosImportacion(models.Model):
    presentacion = models.ForeignKey(Presentacion, on_delete=models.CASCADE)
    precio_usd = models.DecimalField(validators=[MinValueValidator(0.1), MaxValueValidator(100)], max_digits=10, decimal_places=2, verbose_name='Precio USD')
    exportador = models.ForeignKey('importacion.Exportador', on_delete=models.CASCADE, verbose_name='Exportador')
    fecha = models.DateField(auto_now=True, verbose_name='Fecha Ultima Actualización')

    class Meta:
        verbose_name = "Lista de Precios Exportador"
        verbose_name_plural = "Listas de Precio Exportador"
        ordering = ['exportador', 'presentacion']
        unique_together = ('presentacion', 'exportador')

    def __str__(self):
        return f"{self.presentacion} - {self.precio_usd} - {self.fecha}"



class ListaPreciosVentas(models.Model):
    presentacion = models.ForeignKey(Presentacion, on_delete=models.CASCADE)
    precio_euro = models.DecimalField(validators=[MinValueValidator(0.1), MaxValueValidator(100)], max_digits=10, decimal_places=2, verbose_name='Precio Euro')
    cliente = models.ForeignKey('comercial.Cliente', on_delete=models.CASCADE, verbose_name='Cliente')
    fecha = models.DateField(auto_now=True, verbose_name='Fecha Ultima Actualización')

    class Meta:
        verbose_name = "Lista de Precios Cliente"
        verbose_name_plural = "Listas de Precio Clientes"
        ordering = ['cliente', 'presentacion']
        unique_together = ('presentacion', 'cliente')

    def __str__(self):
        return f"{self.presentacion} - {self.precio_euro} - {self.fecha}"



