from django.contrib import admin

from core.models import Customer, Ingredient, IngredientMovement, Order, OrderItem, Pizza, RecipeItem, Sale, SaleItem


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "phone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("first_name", "last_name", "phone")


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "unit_price", "current_stock", "min_stock", "is_active")
    list_filter = ("unit", "is_active")
    search_fields = ("name",)


@admin.register(Pizza)
class PizzaAdmin(admin.ModelAdmin):
    list_display = ("name", "sale_price", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(RecipeItem)
class RecipeItemAdmin(admin.ModelAdmin):
    list_display = ("pizza", "ingredient", "quantity")
    search_fields = ("pizza__name", "ingredient__name")


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "business_date", "total_revenue", "total_cost", "total_profit", "created_at")
    list_filter = ("business_date",)
    search_fields = ("customer__first_name", "customer__last_name", "customer__phone")
    inlines = [SaleItemInline]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "business_date", "status", "total_envio", "direccion_envio", "created_at")
    list_filter = ("status", "business_date")
    search_fields = ("customer__first_name", "customer__last_name", "customer__phone", "direccion_envio", "notes")
    inlines = [OrderItemInline]


@admin.register(IngredientMovement)
class IngredientMovementAdmin(admin.ModelAdmin):
    list_display = ("ingredient", "movement_type", "direction", "quantity", "reference", "created_at")
    list_filter = ("movement_type", "direction")
    search_fields = ("ingredient__name", "reference")
