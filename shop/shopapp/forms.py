from django import forms
from .models import Order
from django.contrib.auth.models import User


class OrderForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['order_date'].label = 'Дата получения заказа'

    order_date = forms.DateField(widget=forms.TextInput(attrs={'type': 'date'}))

    class Meta:
        model = Order
        fields = (
            'first_name', 'last_name', 'phone', 'electon_address', 'address', 'buying_type', 'order_date', 'comment'
        )

# Авторизация
# Класс будет унаследован от ModelForm,так как мы используем модель User.
class LoginForm(forms.ModelForm):
    # Закрываем пороль звездачками
    password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        # Будет унаследован от существующего метода __init__ в формах
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Логин'
        self.fields['password'].label = 'Пароль'

    # Проверить логин с поролем
    def clean(self):
        username = self.cleaned_data['username']
        password = self.cleaned_data['password']
        if not User.objects.filter(username=username).exists():
            raise forms.ValidationError(
                f'Пользователь с логином {username} не был найден.Проверьте правильность написания логина')
        # Если пользователь найден нужно проверить правильность пороля
        user = User.objects.filter(username=username).first()
        if user:
            if not user.check_password(password):
                raise forms.ValidationError("Неверно введеный пороль")
        # Если проверки успешны
        return self.cleaned_data

    class Meta:
        model = User
        fields = ['username', 'password']


# Регистрация
class RegistrationForm(forms.ModelForm):

    # Подтверждение,что пользователь правильно ввел пароль при решистрации
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    password = forms.CharField(widget=forms.PasswordInput)
    phone=forms.CharField(required=False)
    address = forms.CharField(required=False)
    email = forms.EmailField(required=True)


    def __init__(self, *args, **kwargs):
        # Будет унаследован от существующего метода __init__ в формах
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Логин'
        self.fields['password'].label = 'Пароль'
        self.fields['confirm_password'].label = 'Подтверждение пороля'
        self.fields['phone'].label = 'Номер телефона'
        self.fields['first_name'].label = 'Ваше имя'
        self.fields['last_name'].label = 'Ваша фамилия'
        self.fields['address'].label = 'Адрес'
        self.fields['email'].label = 'Электронная почта'


    def clean_email(self):
        email=self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(f'Данный почтовый адрес уже был зарегистрирован ранее.')
        return email


    def clean_username(self):
        username=self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise  forms.ValidationError(f'Имя {username} занято')
        return username

    def clean(self):
        password = self.cleaned_data['password']
        confirm_password = self.cleaned_data['confirm_password']
        if password != confirm_password:
            raise forms.ValidationError('Пароли не совпадают')
        return self.cleaned_data

    class Meta:
        model = User
        fields = ['username', 'password','confirm_password', 'first_name', 'last_name', 'address', 'email']
