from django.contrib import admin

from core.models import Ingredient, IngredientMovement, Pizza, RecipeItem, Sale, SaleItem


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


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("id", "business_date", "total_revenue", "total_cost", "total_profit", "created_at")
    list_filter = ("business_date",)
    inlines = [SaleItemInline]


@admin.register(IngredientMovement)
class IngredientMovementAdmin(admin.ModelAdmin):
    list_display = ("ingredient", "movement_type", "direction", "quantity", "reference", "created_at")
    list_filter = ("movement_type", "direction")
    search_fields = ("ingredient__name", "reference")
