from django.views.generic import View
from .models import Category, Cart, Customer
from django.views.generic.detail import SingleObjectMixin


class CartMixin(View):
    def dispatch(self, request, *args, **kwargs):
        # Проверка на авторизацию
        if request.user.is_authenticated:
            # Покупатель и корзина
            customer = Customer.objects.filter(user=request.user).first()
            if not customer:
                customer = Customer.objects.create(
                    user=request.user
                )
            cart = Cart.objects.filter(owner=customer, in_order=False).first()
            # Если покупатель найден
            if not cart:
                # Если корзины нет,то нужно создать
                cart = Cart.objects.create(owner=customer)
        # Если не авторизован
        else:
            cart = Cart.objects.filter(for_anonymous_user=True).first()
            if not cart:
                cart = Cart.objects.create(for_anonymous_user=True)
        self.cart = cart
        return super().dispatch(request, *args, **kwargs)
