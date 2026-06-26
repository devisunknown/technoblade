from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Product

INPUT_CLASS = (
    "w-full rounded-lg border-slate-300 dark:border-slate-700 bg-white dark:bg-[#111] "
    "text-[#191c1b] dark:text-slate-100 focus:border-emerald-900 dark:focus:border-emerald-500"
)


class AdminSignupForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": INPUT_CLASS})


class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=20)
    address = forms.CharField(widget=forms.Textarea)
    location = forms.CharField(max_length=100, required=False)
    notes = forms.CharField(widget=forms.Textarea, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.update({"class": INPUT_CLASS})
            if name in {"address", "notes"}:
                field.widget.attrs.update({"rows": 4})


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "category", "description", "price", "size", "stock", "image", "is_active"]
        labels = {
            "name": "Product name",
            "category": "Category",
            "description": "Description",
            "price": "Price (GHS)",
            "size": "Size",
            "stock": "Stock quantity",
            "image": "Product image",
            "is_active": "Visible on storefront",
        }
        help_texts = {
            "category": "Optional. Add categories in Django Admin if none are listed.",
            "image": "JPEG or PNG recommended. Leave blank to use a placeholder on the storefront.",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "is_active": forms.CheckboxInput(),
            "price": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "size": forms.Select(choices=Product.SIZE_CHOICES),
            "stock": forms.NumberInput(attrs={"min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].empty_label = "No category"
        self.fields["is_active"].initial = True
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update(
                    {"class": "rounded border-slate-300 dark:border-slate-700 dark:bg-[#111]"}
                )
            else:
                field.widget.attrs.update({"class": INPUT_CLASS})
