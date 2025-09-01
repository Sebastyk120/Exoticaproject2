from django import forms
from captcha.fields import CaptchaField

class ContactForm(forms.Form):
    name = forms.CharField(
        label="Nombre Completo",
        max_length=100, 
        widget=forms.TextInput(attrs={
            'placeholder': 'Nombre Completo', 
            'required': True,
            'class': 'form-control'
        })
    )
    email = forms.EmailField(
        label="Correo Electrónico",
        widget=forms.EmailInput(attrs={
            'placeholder': 'Correo Electrónico', 
            'required': True,
            'class': 'form-control',
            'pattern': r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$",
            'title': "Por favor ingresa un email válido"
        })
    )
    subject = forms.CharField(
        label="Asunto",
        max_length=150,
        widget=forms.TextInput(attrs={
            'placeholder': 'Asunto',
            'required': True,
            'class': 'form-control'
        })
    )
    message = forms.CharField(
        label="Mensaje",
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
