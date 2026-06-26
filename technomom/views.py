from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
import requests

from .cache_utils import get_categories, get_product_detail, get_product_list
from .forms import AdminSignupForm, CheckoutForm, ProductForm
from .models import Customer, Order, OrderItem, Product

CART_SESSION_KEY = "cart"
DELIVERY_FEE = Decimal("15.00")


def _positive_int(value, default=1):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _cart(request):
    return request.session.setdefault(CART_SESSION_KEY, {})


def _save_cart(request, cart):
    request.session[CART_SESSION_KEY] = cart
    request.session.modified = True


def _cart_lines(cart):
    product_ids = []
    for line_key in cart.keys():
        raw_id = str(line_key).split(":", 1)[0]
        if raw_id.isdigit():
            product_ids.append(int(raw_id))

    products = Product.objects.filter(id__in=product_ids, is_active=True).select_related("category")
    product_map = {str(product.id): product for product in products}
    lines = []

    for line_key, line_data in cart.items():
        if isinstance(line_data, dict):
            product_id = str(line_key).split(":", 1)[0]
            product = product_map.get(product_id)
            if not product:
                continue
            quantity = max(1, _positive_int(line_data.get("quantity")))
            size = line_data.get("size") or ""
            lines.append(
                {
                    "product": product,
                    "quantity": quantity,
                    "size": size,
                    "subtotal": product.price * quantity,
                }
            )
    return lines


def _cart_summary(request):
    lines = _cart_lines(_cart(request))
    subtotal = sum((line["subtotal"] for line in lines), Decimal("0.00"))
    delivery_fee = DELIVERY_FEE if lines else Decimal("0.00")
    return {
        "cart_lines": lines,
        "cart_count": sum(line["quantity"] for line in lines),
        "cart_subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "cart_total": subtotal + delivery_fee,
    }


def _staff_required(user):
    return user.is_authenticated and user.is_staff


def client(request):
    query = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "").strip()
    timeout = settings.CACHE_TIMEOUT

    context = {
        "products": get_product_list(query, category_slug, timeout),
        "categories": get_categories(timeout),
        "selected_category": category_slug,
        "query": query,
        **_cart_summary(request),
    }
    return render(request, "client.html", context)


def productdetail(request, pk=None):
    if pk is None:
        product = Product.objects.filter(is_active=True).first()
        if not product:
            messages.info(request, "No products are available yet.")
            return redirect("client")
        return redirect(product.get_absolute_url())

    cached = get_product_detail(pk, settings.CACHE_TIMEOUT)
    if cached:
        product = cached["product"]
        related_products = cached["related_products"]
    else:
        product = get_object_or_404(Product.objects.select_related("category"), pk=pk, is_active=True)
        related_products = Product.objects.filter(is_active=True).exclude(pk=product.pk)
        if product.category_id:
            related_products = related_products.filter(category=product.category)
        related_products = related_products[:4]

    context = {
        "product": product,
        "related_products": related_products,
        **_cart_summary(request),
    }
    return render(request, "productdetail.html", context)

@ratelimit(key="ip", rate="30/m", method="POST", block=True)
def shoppingcart(request):
    return render(request, "shoppingcart.html", _cart_summary(request))


@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    quantity = max(1, _positive_int(request.POST.get("quantity"), default=1))
    size = (request.POST.get("size") or "").upper()

    if size not in dict(Product.SIZE_CHOICES):
        messages.error(request, "Please select a valid size.")
        return redirect(product.get_absolute_url())

    available_stock = product.get_stock_for_size(size)
    if available_stock <= 0:
        messages.error(request, f"{product.name} is currently out of stock in {size}.")
        return redirect(product.get_absolute_url())

    cart = _cart(request)
    line_key = f"{product.id}:{size}"
    current_line = cart.get(line_key, {})
    if isinstance(current_line, int):
        current_line = {"quantity": current_line, "size": size}
    current_quantity = _positive_int(current_line.get("quantity"), default=0)
    new_quantity = min(available_stock, current_quantity + quantity)
    added = new_quantity - current_quantity

    cart[line_key] = {"quantity": new_quantity, "size": size}
    product.size_stock = dict(product.size_stock or {})
    product.size_stock[size] = max(0, available_stock - added)
    product.save(update_fields=["size_stock", "stock", "updated_at"])
    _save_cart(request, cart)
    messages.success(request, f"{product.name} ({size}) was added to your cart.")
    return redirect(request.POST.get("next") or "shoppingcart")

@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@require_POST
def update_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    quantity = _positive_int(request.POST.get("quantity"), default=0)
    size = (request.POST.get("size") or "").upper()
    cart = _cart(request)
    line_key = f"{product.id}:{size}" if size else str(product.id)

    if quantity == 0:
        cart.pop(line_key, None)
        messages.info(request, f"{product.name} was removed from your cart.")
    else:
        available_stock = product.get_stock_for_size(size) if size else product.stock
        cart[line_key] = {"quantity": min(available_stock, quantity), "size": size}
        messages.success(request, f"{product.name} quantity was updated.")

    _save_cart(request, cart)
    return redirect("shoppingcart")


@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@require_POST
def remove_from_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    cart = _cart(request)
    size = (request.POST.get("size") or "").upper()
    line_key = f"{product.id}:{size}" if size else str(product.id)

    if line_key in cart:
        cart.pop(line_key, None)
        _save_cart(request, cart)
        messages.info(request, f"{product.name} was removed from your cart.")
    else:
        messages.error(request, f"Could not find {product.name} ({size}) in your cart.")

    return redirect("shoppingcart")
@ratelimit(key="ip", rate="10/h", method="POST", block=True)
def checkout(request):
    summary = _cart_summary(request)
    if not summary["cart_lines"]:
        messages.info(request, "Your cart is empty.")
        return redirect("shoppingcart")

    initial = {}
    if request.user.is_authenticated:
        initial = {
            "full_name": request.user.get_full_name() or request.user.username,
            "email": request.user.email,
        }
        if hasattr(request.user, "customer_profile"):
            customer = request.user.customer_profile
            initial.update(
                {
                    "phone": customer.phone,
                    "address": customer.address,
                    "location": customer.location,
                }
            )

    form = CheckoutForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            order = _create_order(request, form.cleaned_data)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("shoppingcart")

        _save_cart(request, {})
        messages.success(request, f"Order {order.order_id} has been placed.")
        return redirect('initiate_payment', order_id=order.order_id)

    return render(request, "checkout.html", {**summary, "form": form})


@transaction.atomic
def _create_order(request, customer_data):
    cart = _cart(request)
    product_ids = [int(product_id) for product_id in cart.keys()]
    products = Product.objects.select_for_update().filter(id__in=product_ids, is_active=True)
    product_map = {str(product.id): product for product in products}

    if not product_map:
        raise ValueError("Your cart does not contain available products.")

    customer = _get_or_create_customer(request, customer_data)
    order = Order.objects.create(
        customer=customer,
        delivery_address=customer_data["address"],
        notes=customer_data.get("notes", ""),
    )

    total = Decimal("0.00")
    for line_key, line_data in cart.items():
        if isinstance(line_data, dict):
            product_id = str(line_key).split(":", 1)[0]
            size = (line_data.get("size") or "").upper()
            product = product_map.get(product_id)
            if not product:
                continue
            quantity = max(1, _positive_int(line_data.get("quantity")))
            available_stock = product.get_stock_for_size(size)
            if quantity > available_stock:
                raise ValueError(f"Only {available_stock} of {product.name} ({size}) is available.")

            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=f"{product.name} ({size})",
                quantity=quantity,
                price=product.price,
            )
            new_size_stock = dict(product.size_stock or {})
            new_size_stock[size] = max(0, new_size_stock.get(size, 0) - quantity)
            product.size_stock = new_size_stock
            product.save(update_fields=["size_stock", "stock", "updated_at"])
            total += product.price * quantity
            continue

        product = product_map.get(str(line_key))
        if not product:
            continue
        quantity = max(1, _positive_int(line_data))
        if quantity > product.stock:
            raise ValueError(f"Only {product.stock} of {product.name} is available.")

        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            quantity=quantity,
            price=product.price,
        )
        product.stock -= quantity
        product.save(update_fields=["stock", "updated_at"])
        total += product.price * quantity

    order.total_amount = total + DELIVERY_FEE
    order.save(update_fields=["total_amount", "updated_at"])
    return order


def _get_or_create_customer(request, data):
    defaults = {
        "full_name": data["full_name"],
        "email": data.get("email", ""),
        "phone": data["phone"],
        "address": data["address"],
        "location": data.get("location", ""),
    }

    if request.user.is_authenticated:
        customer, _ = Customer.objects.update_or_create(user=request.user, defaults=defaults)
        return customer

    customer = Customer.objects.create(**defaults)
    return customer


def order_success(request, order_id):
    order = get_object_or_404(Order.objects.prefetch_related("items"), order_id=order_id)
    return render(request, "order_success.html", {"order": order})


@login_required(login_url="adminlog")
@user_passes_test(_staff_required, login_url="adminlog")
def admindashboard(request):
    orders = Order.objects.select_related("customer").prefetch_related("items")[:10]
    context = {
        "product_count": Product.objects.count(),
        "active_product_count": Product.objects.filter(is_active=True).count(),
        "order_count": Order.objects.count(),
        "pending_order_count": Order.objects.filter(status=Order.STATUS_PENDING).count(),
        "customer_count": Customer.objects.count(),
        "revenue": Order.objects.exclude(status=Order.STATUS_CANCELLED).aggregate(
            total=Sum("total_amount")
        )["total"]
        or Decimal("0.00"),
        "recent_orders": orders,
    }
    return render(request, "dashboard.html", context)


@login_required(login_url="adminlog")
@user_passes_test(_staff_required, login_url="adminlog")
@ratelimit(key="user", rate="30/h", method="POST", block=True)
def add_product(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'"{product.name}" was added to the store.')
            return redirect("admindash")
    else:
        form = ProductForm()

    return render(request, "add_product.html", {"form": form})


@ratelimit(key="ip", rate="3/h", method="POST", block=True)
def adminsignup(request):
    if User.objects.filter(is_staff=True).exists() and not request.user.is_superuser:
        messages.error(request, "Admin signup is locked. Ask the store owner to create staff users.")
        return redirect("adminlog")

    form = AdminSignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.email = form.cleaned_data.get("email", "")
        user.is_staff = True
        user.save()
        messages.success(request, "Admin account created. You can sign in now.")
        return redirect("adminlog")

    return render(request, "adminsignup.html", {"form": form})


@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def adminlogin(request):
    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user is not None and user.is_staff:
            auth_login(request, user)
            return redirect("admindash")

        messages.error(request, "Invalid staff username or password.")
        return redirect("adminlog")

    return render(request, "adminlogin.html")


def adminlogout(request):
    auth_logout(request)
    messages.info(request, "You have been signed out.")
    return redirect("adminlog")


@ratelimit(key="ip", rate="3/m", method="POST", block=True)
def resetpass(request):
    if request.method == "POST":
        username = request.POST.get("username", "")
        new_password = request.POST.get("new_password", "")

        if not username or not new_password:
            messages.error(request, "Please fill in all fields.")
            return redirect("resetpassword")

        try:
            user = User.objects.get(username=username, is_staff=True)
        except User.DoesNotExist:
            messages.error(request, "No staff account found with that username.")
            return redirect("resetpassword")

        user.set_password(new_password)
        user.save(update_fields=["password"])
        messages.success(request, "Password reset successfully. Please sign in.")
        return redirect("adminlog")

    return render(request, "resetpassword.html")




def initiate_payment(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)

    url = "https://api.paystack.co/transaction/initialize"
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    data = {
        "email": order.customer.email or order.customer.user.email,
        "amount": int(order.total_amount * 100),
        "currency": "GHS",
        "callback_url": request.build_absolute_uri('/payment/verify/'),
        "metadata": {"order_id": str(order.order_id)},
    }

    response = requests.post(url, headers=headers, json=data)
    res_data = response.json()

    if res_data.get('status'):
        order.payment_reference = res_data['data']['reference']
        order.save()
        return redirect(res_data['data']['authorization_url'])
    else:
        return redirect('checkout')


def verify_payment(request):
    reference = request.GET.get('reference')
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}

    response = requests.get(url, headers=headers)
    res_data = response.json()

    if res_data['data']['status'] == 'success':
        order_id = res_data['data']['metadata']['order_id']
        order = get_object_or_404(Order, order_id=order_id)
        order.payment_status = Order.PAYMENT_PAID
        order.status = Order.STATUS_CONFIRMED
        order.save()
        return redirect('order_success',order_id=order_id)
    else:
        order_id = res_data['data']['metadata'].get('order_id')
        if order_id:
            order = Order.objects.filter(order_id=order_id).first()
            if order:
                order.payment_status = Order.PAYMENT_FAILED
                order.save()
        return redirect('payment_failed')