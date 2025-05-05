from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Fruta(models.Model):
    nombre = models.CharField(max_length=20, unique=True)
    descripcion = models.TextField(verbose_name="Descripción", blank=True, null=True)
    imagen = models.ImageField(upload_to='frutas/', verbose_name="Imagen", blank=True, null=True)
    
    # Campos adicionales para SEO
    meta_description = models.CharField(max_length=160, blank=True, null=True, 
                                       help_text="Descripción corta para motores de búsqueda (máx. 160 caracteres)")
    beneficios = models.TextField(blank=True, null=True, help_text="Beneficios nutricionales o para la salud")
    origen = models.CharField(max_length=100, blank=True, null=True, help_text="País o región de origen")
    slug = models.SlugField(max_length=50, unique=True, blank=True, null=True, 
                           help_text="URL amigable para el producto (se genera automáticamente)")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última actualización")

    def __str__(self):
        return self.nombre
        
    def save(self, *args, **kwargs):
        # Generar slug automáticamente si no existe
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['nombre']
        verbose_name = "Fruta"
        verbose_name_plural = "Frutas"



class Presentacion(models.Model):
    fruta = models.ForeignKey(Fruta, on_delete=models.CASCADE)
    kilos = models.DecimalField(validators=[MinValueValidator(0.1), MaxValueValidator(15.1)], max_digits=10, decimal_places=2, verbose_name='Kilos')

    def __str__(self):
        return f"{self.fruta} - {self.kilos} Kg"

    class Meta:
        verbose_name = "Presentaciónes"
        unique_together = ('fruta', 'kilos')
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

    def get_precio_usd(self):
        return f"{self.precio_usd:.2f}"


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
    
    def get_precio_euro(self):
        return f"{self.precio_euro:.2f}"



