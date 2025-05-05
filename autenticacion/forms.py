from django import forms
from captcha.fields import CaptchaField

class ContactForm(forms.Form):
    nombre = forms.CharField(
        max_length=100, 
        widget=forms.TextInput(attrs={
            'placeholder': 'Nombre', 
            'required': True,
            'class': 'form-control'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Email', 
            'required': True,
            'class': 'form-control',
            'pattern': "[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$",
            'title': "Por favor ingresa un email válido"
        })
    )
    telefono = forms.CharField(
        max_length=20, 
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Teléfono (opcional)', 
            'class': 'form-control'
        })
    )
    mensaje = forms.CharField(
        widget=forms.Textarea(attrs={
            'placeholder': 'Mensaje', 
            'required': True,
            'class': 'form-control',
            'rows': 5
        })
    )
    captcha = CaptchaField(
        error_messages={'invalid': 'Texto de verificación incorrecto, inténtalo de nuevo.'}
    )
