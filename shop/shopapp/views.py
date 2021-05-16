from django.shortcuts import render
from django.views.generic import DetailView, View
from .models import Category, Customer, Cart, CartProduct, Order, Product
from .mixins import CartMixin
from django.http import HttpResponseRedirect, JsonResponse
from django.contrib import messages
from .forms import OrderForm, LoginForm, RegistrationForm
from .number import recalc_cart
from django.db import transaction
import stripe
from django.contrib.auth import authenticate, login
from django.shortcuts import render
from requests import request


class BaseView(CartMixin, View):
    def get(self, request, *args, **kwargs):
        search_query = request.GET.get('search', '')
        if search_query:
            product = Product.objects.filter(slug=search_query)
        else:
            products = Product.objects.all()
        categories = Category.objects.all()
        products = Product.objects.all()
        context = {
            'categories': categories,
            'products': products,
            'cart': self.cart,
        }
        return render(request, 'base.html', context)


class ProductDetailView(CartMixin, DetailView):
    # Записываем аргументы,которые нам необходимы
    context_object_name = 'product'  # Так как он общий, можно записать 'product'.имя переменной контекста можно
    # задать вручную. Для этой цели служит атрибут context_object_name, который определяет имя переменной в контексте
    template_name = 'product_detail.html'  # Мы можем явно указать в представлении, какой шаблон мы хотим
    # использовать. Для этого мы должны добавить в представление атрибут template_name, с указанием имени шаблона.
    slug_url_kwarg = 'slug'  # Имя переданного ключевого аргумента(именованной группы) в URLConf, содержащего

    # значение слага(slug). По умолчанию, slug_url_kwarg это 'slug'.

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cart'] = self.cart
        return context


# Задаем url для Категорий товаров
class CategoryDetailView(CartMixin, DetailView):
    model = Category
    queryset = Category.objects.all()
    context_object_name = 'category'
    template_name = 'category_detail.html'
    slug_url_kwarg = 'slug'

    # Отображение корзины , как в категориях ,так и на странице самого товара
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cart'] = self.cart
        return context


# Создаем корзину для товаров
class CartView(CartMixin, View):
    def get(self, request, *args, **kwargs):
        categories = Category.objects.all()
        context = {
            'cart': self.cart,
            'categories': categories,
        }
        return render(request, 'cart.html', context)


# Для добавления товара в корзину
class AddToCartView(CartMixin, View):

    def get(self, request, *args, **kwargs):
        # Вводим product_slug, чтобы он был в переменных
        product_slug = kwargs.get('slug')
        # Так как за каждым покупателем закреплена корзина ,нам нужно взять покупателя,корзину и ввести аргумент по
        # которому мы бедм брать корзину. У покупателя может быть много корзин,но активная одна. Определяем ,
        # что это за модель для нашего товара Получаем продукт
        product = Product.objects.get(slug=product_slug)
        # Создаем cart_product.А ткаже распоковываем картедж и смотрим создан ли объект
        cart_product, created = CartProduct.objects.get_or_create(
            user=self.cart.owner, cart=self.cart, product=product
        )
        # Доб в корзину,если мы не нашли cart product повторно
        if created:
            self.cart.products.add(cart_product)
        # Информация о корзине добавляется ,когда в нее что-то закидывают
        recalc_cart(self.cart)
        # Вывод сообщения о добавлении товара
        messages.add_message(request, messages.INFO, "Товар успешно добавлен в корзину")
        return HttpResponseRedirect('/cart/')  # После добавления товар направлен в корзину


# Удаление товара.
class DeleteFromCartView(CartMixin, View):

    def get(self, request, *args, **kwargs):
        product_slug = kwargs.get('slug')
        product = Product.objects.get(slug=product_slug)
        cart_product = CartProduct.objects.get(
            user=self.cart.owner, cart=self.cart, product=product
        )
        self.cart.products.remove(cart_product)
        cart_product.delete()  # Удаляем из базы.
        recalc_cart(self.cart)
        # Вывод сообщения об удалении товара
        messages.add_message(request, messages.INFO, "Товар успешно удален из корзины")
        return HttpResponseRedirect('/cart/')


# Изменение количества товаров
class ChangeQTYView(CartMixin, View):
    def post(self, request, *args, **kwargs):
        product_slug = kwargs.get('slug')
        product = Product.objects.get(slug=product_slug)
        cart_product = CartProduct.objects.get(
            user=self.cart.owner, cart=self.cart, product=product
        )
        # Присваеваем карт продукту количечества ,то значение которое к нам приходит из нашего тела запроса
        qty = int(request.POST.get('qty'))
        cart_product.qty = qty
        cart_product.save()
        recalc_cart(self.cart)
        # Вывод сообщения об изменении количества товара в корзине
        messages.add_message(request, messages.INFO, "Количество товара успешно изменено")
        return HttpResponseRedirect('/cart/')


class ZakazView(CartMixin, View):
    def get(self, request, *args, **kwargs):
        # Онлайн оплата товара
        stripe.api_key = "sk_test_51Ik9YkK9zYwYIfYZXq3rnaxw62EpvkOekIEfRFzyb5osrb64d4XR3o0n6zPt1Lm3GZL8wEa0osbzwcrAFgjuAN7000J80gwXFX"
        intent = stripe.PaymentIntent.create(
            amount=int(self.cart.final_price * 100),
            currency='rub',
            # Verify your integration in this guide by including this parameter
            metadata={'integration_check': 'accept_a_payment'},
        )
        categories = Category.objects.all()
        form = OrderForm(request.POST or None)
        context = {
            'cart': self.cart,
            'categories': categories,
            'form': form,
            'client_secret': intent.client_secret
        }
        return render(request, 'zakaz.html', context)


# Обрабодчик заказов
class MakeOrderView(CartMixin, View):
    # Если что-то пройдет не корректно,все откатится назад.
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        form = OrderForm(request.POST or None)
        customer = Customer.objects.get(user=request.user)
        # Чтобы django работал с формой без конфликтов,ее нужно проваледировать
        # Для этого мы берем спец.метод is_valid()
        if form.is_valid():
            # Что-то вроде инстенса,который нужно заполнить
            new_order = form.save(commit=False)
            new_order.customer = customer  # Заполняем поля ,которые создали в модели заказа
            new_order.first_name = form.cleaned_data['first_name']
            new_order.last_name = form.cleaned_data['last_name']
            new_order.phone = form.cleaned_data['phone']
            new_order.address = form.cleaned_data['address']
            new_order.buying_type = form.cleaned_data['buying_type']
            new_order.order_date = form.cleaned_data['order_date']
            new_order.comment = form.cleaned_data['comment']
            new_order.save()
            # Корзина.Меняем статус эта корзина закреплена за пользователем
            self.cart.in_order = True
            self.cart.save()
            new_order.cart = self.cart  # В наш new_order помещаем корзину
            new_order.save()
            customer.orders.add(new_order)
            messages.add_message(request, messages.INFO,
                                 'Спасибо за заказ.')  # Обовещение об успешном добавлении заказака
            return HttpResponseRedirect('/')
        return HttpResponseRedirect('/zakaz/')


# Оплата заказа онлайн
class PayedOnlineOrderView(CartMixin, View):
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        customer = Customer.objects.get(user=request.user)
        new_order = Order()
        new_order.customer = customer
        new_order.first_name = customer.user.first_name
        new_order.last_name = customer.user.last_name
        new_order.phone = customer.phone
        new_order.address = customer.address
        new_order.buying_type = Order.BUYING_TYPE_SELF
        new_order.save()
        self.cart.in_order = True
        self.cart.save()
        new_order.cart = self.cart
        new_order.status = Order.STATUS_PAYED
        new_order.save()
        customer.orders.add(new_order)
        # Нужно вернуть JsonResponse
        return JsonResponse({"status": "payed"})


class LoginView(CartView, View):
    # Используем get и post.Get-чтобы отрисовать форму,a post чтобы отправить на нее какие-то данные
    def get(self, request, *args, **kwargs):
        # Создаем инстанс нашей формы
        form = LoginForm(request.POST or None)
        categories = Category.objects.all()
        context = {'form': form, 'categories': categories, 'cart': self.cart}
        return render(request, 'login.html', context)

    def post(self, request, *args, **kwargs):
        form = LoginForm(request.POST or None)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(username=username, password=password)
            if user:
                login(request, user)
                return HttpResponseRedirect('/')
        context = {'form': form, 'cart': self.cart}
        return render(request, 'login.html', context)


class RegistrationView(CartMixin, View):
    def get(self, request, *args, **kwargs):
        form = RegistrationForm(request.POST or None)
        categories = Category.objects.all()
        context = {'form': form, 'categories': categories, 'cart': self.cart}
        return render(request, 'registration.html', context)

    def post(self, request, *args, **kwargs):
        form = RegistrationForm(request.POST or None)
        if form.is_valid():
            new_user = form.save(commit=False)
            new_user.username = form.cleaned_data['username']
            new_user.email = form.cleaned_data['email']
            new_user.first_name = form.cleaned_data['first_name']
            new_user.last_name = form.cleaned_data['last_name']
            new_user.save()
            new_user.set_password(form.cleaned_data['password'])
            new_user.save()
            Customer.objects.create(
                user=new_user,
                phone=form.cleaned_data['phone'],
                address=form.cleaned_data['address']
            )
            user = authenticate(username=form.cleaned_data['username'], password=form.cleaned_data['password'])
            login(request, user)
            return HttpResponseRedirect('/')
        context = {'form': form, 'cart': self.cart}
        return render(request, 'registration.html', context)


# Профиль пользователя
class ProfileView(CartMixin, View):
    def get(self, request, *args, **kwargs):
        # Находим себя
        customer = Customer.objects.get(user=request.user)
        # Находим заказ.order_by('-created_at')-заказы будут показаны в убыв.порядке
        orders = Order.objects.filter(customer=customer).order_by('-created_at')
        # Категории
        categories = Category.objects.all()
        return render(
            request,
            'profile.html',
            {'orders': orders, 'cart': self.cart, 'categories': categories}
        )
