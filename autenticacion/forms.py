from django import forms
from captcha.fields import CaptchaField

class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=100, 
        widget=forms.TextInput(attrs={'placeholder': 'Nombre', 'required': True})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Email', 
            'required': True,
            'pattern': "[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$",
            'title': "Por favor ingresa un email válido"
        })
    )
    subject = forms.CharField(
        max_length=200, 
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Asunto'})
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={'placeholder': 'Mensaje', 'required': True})
    )
    captcha = CaptchaField(
        error_messages={'invalid': 'Texto de verificación incorrecto, inténtalo de nuevo.'}
    )
