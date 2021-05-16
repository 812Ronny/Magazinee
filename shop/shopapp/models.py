from django.db import models  # Для моделей
from django.contrib.auth import \
    get_user_model  # Вместо того, чтобы ссылаться Userнапрямую, вы должны ссылаться на модель пользователя, используя django.contrib.auth.get_user_model(). Этот метод вернет текущую активную модель пользователя - пользовательскую модель пользователя, если она указана, или User иначе.
from django.contrib.contenttypes.models import ContentType  # Content Type-микрофрейворк,который видит все наши модели.
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys
from django.urls import reverse  # Для построения url у объектво
from django.utils import timezone

# Этим мы говорим ,что нам нужет именно тот User,который лежит в AUTH_USER_MODEL
User = get_user_model()


class MinResolutionErrorException(Exception):
    pass


class MaxResolutionErrorException(Exception):
    pass


# Категория
class Category(models.Model):
    name = models.CharField(max_length=255,
                            verbose_name='Имя категории')  # Имя категории max_length-максимальная длина
    # verbose_name-название
    slug = models.SlugField(unique=True)  # -Категории/Телефоны/-slug-указывает на конеч точку(Телефоны)

    # Представляем категорию в админке
    def __str__(self):
        return self.name

    def get_absolute_url(self):
        # Передаем имя пути в url.А также ищем slug категории.
        return reverse('category_detail', kwargs={'slug': self.slug})


# Продукт,наш товар который мы продаем
class Product(models.Model):
    MIN_RESOLUTION = (1000, 1000)  # Минимальный размер фотографии
    category = models.ForeignKey(Category, verbose_name='Категория',
                                 on_delete=models.CASCADE)  # ForeignKey-Отношения многие-к-одному. Требуются два
    # позиционных аргумента: класс, к которому относится модель, и опция on_delete.
    title = models.CharField(max_length=255,
                             verbose_name='Наименование')  # CharField-Строковое поле, для строк малого и большого
    # размера
    slug = models.SlugField(
        unique=True)  # Slug - газетный термин. Слаг - это короткая метка для чего-либо, содержащая только буквы,
    # цифры, подчеркивания или дефисы. Они обычно используются в URL.unique-оставить объект пустым
    image = models.ImageField(
        verbose_name='Изображение')  # ImageField-Объект хранения или вызываемый объект, который возвращает объект
    # хранения.
    description = models.TextField(verbose_name='Описание',
                                   null=True)  # TextField-Для больших объемов текста null=True-может быть путым
    price = models.DecimalField(max_digits=12, decimal_places=2,
                                verbose_name='Цена')  # DecimalField-Десятичное число с фиксированной точностью,
    # представленное в Python экземпляром Decimal. Он проверяет ввод с помощью DecimalValidator
    available = models.BooleanField(default=True)

    def __str__(self):
        return self.title

    def get_model_name(self):
        return self.__class__.__name__.lower()

    def get_absolute_name(self):
        return reverse('product_detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        image = self.image
        img = Image.open(image)  # Изображение открываем через библотеку PIL
        new_img = img.convert('RGB')  # Генерирует в RGB
        resized_new_img = new_img.resize((1000, 1000), Image.ANTIALIAS)  # Обрезает фотографию
        filestream = BytesIO()  # Преобразовывваем в поток данных,в байты
        resized_new_img.save(filestream, 'JPEG', quality=90)  # Сохраняем полученое изображение в filestream
        filestream.seek(0)  # Метод seek() - это встроенный метод в Python, он используется для установки текущей
        # позиции в файле (или указателя файла)
        name = '{}.{}'.format(*self.image.name.split('.'))
        print(self.image.name, name)
        self.image = InMemoryUploadedFile(  # Аргументы Сначала файл,название поле,имя файла,формат и размер
            filestream, 'ImageField', name, 'jpeg/image', sys.getsizeof(filestream), None
        )
        super().save(*args, **kwargs)


# Промежуточный продукт,который относится к корзине
class CartProduct(models.Model):
    # Для удобного добавления продуктов
    # Мы будем создавать CartProduct.Например у нас есть 2 карт продукта ,но у их разные модели
    # ,но используются они в CartProduct с одним внешним ключом.
    user = models.ForeignKey('Customer', verbose_name='Покупатель',
                             on_delete=models.CASCADE)  # on_delete=models.CASCADE-Для удаления ,чтобы удалить все
    # связи. ОБЯЗАТЕЛЬНО ИСПОЛЬЗЫВАТЬ !!!!!!
    cart = models.ForeignKey('Cart', verbose_name='Корзина', on_delete=models.CASCADE,
                             related_name='related_products')  # related_name-узнать к чем относится.Атрибут
    # related_name указывает имя обратного отношения от модели User обратно к вашей модели.
    product = models.ForeignKey(Product, verbose_name='Товар', on_delete=models.CASCADE)
    qty = models.PositiveIntegerField(default=1)  # Дефолтное занчение
    final_price = models.DecimalField(max_digits=12, decimal_places=2,
                                      verbose_name='Общая цена')  # max_digits-Количество чисел из которых состоит сумма
    # decimal_places-цифры после запятой

    def __str__(self):
        return "Продукт: {} (для корзины)".format(self.product.title)

    # При измен цены ,мы столкнулись с тем ,что система думает ,что это новый товар и добавляет его.
    # Когда у нас создается новый карт продук,мы в наш final_price:
    def save(self, *args, **kwargs):
        self.final_price = self.qty * self.product.price
        super().save(*args, **kwargs)


# Корзина
class Cart(models.Model):
    objects = None
    owner = models.ForeignKey('Customer', null=True, verbose_name='Владелец', on_delete=models.CASCADE)
    products = models.ManyToManyField(CartProduct, blank=True,
                                      related_name='related_cart')  # ManyToManyField-Для определения связи
    # многие-ко-многим. blank=True если вы хотите разрешить пустые значения в формах, т.к. параметр null влияет
    # только на сохранение в базе данных.
    total_products = models.PositiveIntegerField(default=0)
    final_price = models.DecimalField(max_digits=12, default=0, decimal_places=2, verbose_name='Общая цена')
    in_order = models.BooleanField(default=False)  # С помощью этого закрепляем корзину за пользователем и не торогаем
    for_anonymous_user = models.BooleanField(default=False)  # Корзина для людей без регистрации

    def __str__(self):
        return str(self.id)


# Покупатель
class Customer(models.Model):
    user = models.ForeignKey(User, verbose_name='Пользователь', on_delete=models.CASCADE)
    phone = models.CharField(max_length=20, verbose_name='Номер телефона', null=True, blank=True)
    address = models.CharField(max_length=255, verbose_name='Адрес', null=True, blank=True)
    orders = models.ManyToManyField('Order', blank=True, verbose_name='Заказы покупателя', related_name='related_order')

    def __str__(self):
        return "Покупатель: {} {}".format(self.user.first_name, self.user.last_name)


# Заказ
class Order(models.Model):
    STATUS_NEW = 'new'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_READY = 'is_ready'
    STATUS_COMPLETED = 'completed'
    STATUS_PAYED = 'payed'

    # Самовывоз
    BUYING_TYPE_SELF = 'self'
    # Доставка
    BUYING_TYPE_DELIVERY = 'delivery'

    STATUS_CHOICES = (
        (STATUS_PAYED, 'Оплачено'),
        (STATUS_NEW, 'Новый заказ'),
        (STATUS_IN_PROGRESS, 'Заказ в обработке'),
        (STATUS_READY, 'Заказ готов'),
        (STATUS_COMPLETED, 'Заказ выполнен')
    )

    BUYING_TYPE_CHOICES = (
        (BUYING_TYPE_SELF, 'Самовывоз'),
        (BUYING_TYPE_DELIVERY, 'Доставка')
    )

    customer = models.ForeignKey(Customer, verbose_name='Покупатель', on_delete=models.CASCADE)
    first_name = models.CharField(max_length=255, verbose_name='Имя')
    last_name = models.CharField(max_length=255, verbose_name='Фамилия')
    phone = models.CharField(max_length=20, verbose_name='Телефон')
    electon_address = models.CharField(max_length=255, verbose_name='Электронный адрес')
    cart = models.ForeignKey(Cart, verbose_name='Корзина', on_delete=models.CASCADE, null=True, blank=True)
    address = models.CharField(max_length=1024, verbose_name='Адрес', null=True, blank=True)
    status = models.CharField(
        max_length=255,
        verbose_name='Статус заказ',
        choices=STATUS_CHOICES,
        default=STATUS_NEW
    )
    buying_type = models.CharField(
        max_length=255,
        verbose_name='Тип заказа',
        choices=BUYING_TYPE_CHOICES,
        default=BUYING_TYPE_SELF
    )
    comment = models.TextField(verbose_name='Комментарий к заказу', null=True, blank=True)
    created_at = models.DateTimeField(auto_now=True, verbose_name='Дата создания заказа')
    order_date = models.DateField(verbose_name='Дата получения заказа', default=timezone.now)

    def __str__(self):
        return str(self.id)
