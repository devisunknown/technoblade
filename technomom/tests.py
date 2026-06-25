from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from .models import Category, Customer, Order, Product
from .views import CART_SESSION_KEY


def _test_image():
    buffer = BytesIO()
    Image.new("RGB", (100, 100), color="green").save(buffer, format="JPEG")
    buffer.seek(0)
    return SimpleUploadedFile("test.jpg", buffer.read(), content_type="image/jpeg")


class CartTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name="Test Product",
            price=Decimal("25.00"),
            stock=4,
            is_active=True,
        )

    def test_add_to_cart_stores_quantity_in_session(self):
        response = self.client.post(reverse("add_to_cart", args=[self.product.id]), {"quantity": 2})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session[CART_SESSION_KEY][str(self.product.id)], 2)

    def test_add_to_cart_caps_quantity_at_stock(self):
        self.client.post(reverse("add_to_cart", args=[self.product.id]), {"quantity": 20})

        self.assertEqual(self.client.session[CART_SESSION_KEY][str(self.product.id)], self.product.stock)

    def test_update_cart_zero_removes_item(self):
        session = self.client.session
        session[CART_SESSION_KEY] = {str(self.product.id): 2}
        session.save()

        self.client.post(reverse("update_cart", args=[self.product.id]), {"quantity": 0})

        self.assertNotIn(str(self.product.id), self.client.session[CART_SESSION_KEY])


class CheckoutTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name="Checkout Product",
            price=Decimal("10.00"),
            stock=5,
            is_active=True,
        )

    def test_checkout_creates_order_and_reduces_stock(self):
        session = self.client.session
        session[CART_SESSION_KEY] = {str(self.product.id): 2}
        session.save()

        response = self.client.post(
            reverse("checkout"),
            {
                "full_name": "Nana Berkoh",
                "email": "nana@example.com",
                "phone": "0240000000",
                "address": "Accra",
                "location": "Accra",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Customer.objects.count(), 1)

        order = Order.objects.get()
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.total_amount, Decimal("35.00"))

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(self.client.session[CART_SESSION_KEY], {})


class AddProductTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="storeadmin",
            password="adminpass123",
            is_staff=True,
        )
        self.category = Category.objects.create(id=1, name="Electronics")

    def test_add_product_requires_staff_login(self):
        response = self.client.get(reverse("add_product"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("adminlog"), response.url)

    def test_add_product_get_renders_form(self):
        self.client.login(username="storeadmin", password="adminpass123")
        response = self.client.get(reverse("add_product"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add Product")
        self.assertContains(response, "Save Product")

    def test_add_product_post_creates_product(self):
        self.client.login(username="storeadmin", password="adminpass123")
        response = self.client.post(
            reverse("add_product"),
            {
                "name": "Wireless Mouse",
                "category": self.category.id,
                "description": "Ergonomic wireless mouse",
                "price": "45.00",
                "stock": "12",
                "is_active": "on",
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admindash"))

        product = Product.objects.get(name="Wireless Mouse")
        self.assertEqual(product.category, self.category)
        self.assertEqual(product.price, Decimal("45.00"))
        self.assertEqual(product.stock, 12)
        self.assertTrue(product.is_active)
        self.assertEqual(product.slug, "wireless-mouse")

    def test_add_product_post_with_image(self):
        self.client.login(username="storeadmin", password="adminpass123")
        response = self.client.post(
            reverse("add_product"),
            {
                "name": "Desk Lamp",
                "description": "LED desk lamp",
                "price": "80.00",
                "stock": "5",
                "is_active": "on",
                "image": _test_image(),
            },
        )

        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(name="Desk Lamp")
        self.assertTrue(product.image.name.startswith("products/"))
