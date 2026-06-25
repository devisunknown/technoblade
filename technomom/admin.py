from django.contrib import admin

from .models import Category, Customer, Order, OrderItem, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock", "is_active", "created_at")
    list_filter = ("is_active", "category")
    list_editable = ("price", "stock", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "description")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "email", "location", "created_at")
    search_fields = ("full_name", "phone", "email", "location")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("subtotal",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_id",
        "customer",
        "status",
        "payment_status",
        "total_amount",
        "created_at",
    )
    list_filter = ("status", "payment_status", "created_at")
    search_fields = ("order_id", "customer__full_name", "customer__phone")
    readonly_fields = ("order_id", "created_at", "updated_at")
    inlines = [OrderItemInline]
