from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache_utils import invalidate_catalog_cache
from .models import Category, Product


@receiver([post_save, post_delete], sender=Product)
@receiver([post_save, post_delete], sender=Category)
def clear_catalog_cache(sender, **kwargs):
    invalidate_catalog_cache()
