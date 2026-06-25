from django.core.cache import cache
from django.db.models import Count, Q

from .models import Category, Product

CATALOG_CACHE_VERSION_KEY = "catalog_cache_version"
CATEGORIES_CACHE_KEY = "categories_with_counts"
PRODUCT_LIST_PREFIX = "product_list"
PRODUCT_DETAIL_PREFIX = "product_detail"


def _catalog_version():
    return cache.get(CATALOG_CACHE_VERSION_KEY, 1)


def invalidate_catalog_cache():
    cache.set(CATALOG_CACHE_VERSION_KEY, _catalog_version() + 1, None)


def get_categories(timeout):
    version = _catalog_version()
    cache_key = f"{CATEGORIES_CACHE_KEY}:v{version}"
    categories = cache.get(cache_key)
    if categories is None:
        categories = list(Category.objects.annotate(active_product_count=Count("products")))
        cache.set(cache_key, categories, timeout)
    return categories


def get_product_list(query, category_slug, timeout):
    version = _catalog_version()
    cache_key = f"{PRODUCT_LIST_PREFIX}:v{version}:{query}:{category_slug}"
    products = cache.get(cache_key)
    if products is None:
        qs = Product.objects.filter(is_active=True).select_related("category")
        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(category__name__icontains=query)
            )
        if category_slug:
            qs = qs.filter(category__slug=category_slug)
        products = list(qs)
        cache.set(cache_key, products, timeout)
    return products


def get_product_detail(pk, timeout):
    version = _catalog_version()
    cache_key = f"{PRODUCT_DETAIL_PREFIX}:v{version}:{pk}"
    data = cache.get(cache_key)
    if data is None:
        try:
            product = Product.objects.select_related("category").get(pk=pk, is_active=True)
        except Product.DoesNotExist:
            return None
        related = Product.objects.filter(is_active=True).exclude(pk=product.pk)
        if product.category_id:
            related = related.filter(category=product.category)
        data = {"product": product, "related_products": list(related[:4])}
        cache.set(cache_key, data, timeout)
    return data
