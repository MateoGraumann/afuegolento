from django.urls import path

from core.views import (
    DashboardView,
    IngredientAdjustStockView,
    IngredientCreateView,
    IngredientDeleteView,
    IngredientListView,
    IngredientUpdateView,
    PizzaCreateView,
    PizzaDeleteView,
    PizzaListView,
    PizzaUpdateView,
    RecipeItemCreateView,
    RecipeItemDeleteView,
    RecipeItemListView,
    RecipeItemUpdateView,
    SaleCreateView,
    SaleDeleteView,
    SaleListView,
    SaleUpdateView,
)

app_name = "core"

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("sales/", SaleListView.as_view(), name="sale_list"),
    path("sales/new/", SaleCreateView.as_view(), name="sale_create"),
    path("sales/<int:pk>/edit/", SaleUpdateView.as_view(), name="sale_update"),
    path("sales/<int:pk>/delete/", SaleDeleteView.as_view(), name="sale_delete"),
    path("ingredients/", IngredientListView.as_view(), name="ingredient_list"),
    path("ingredients/new/", IngredientCreateView.as_view(), name="ingredient_create"),
    path("ingredients/<int:pk>/edit/", IngredientUpdateView.as_view(), name="ingredient_update"),
    path("ingredients/<int:pk>/adjust-stock/", IngredientAdjustStockView.as_view(), name="ingredient_adjust_stock"),
    path("ingredients/<int:pk>/delete/", IngredientDeleteView.as_view(), name="ingredient_delete"),
    path("pizzas/", PizzaListView.as_view(), name="pizza_list"),
    path("pizzas/new/", PizzaCreateView.as_view(), name="pizza_create"),
    path("pizzas/<int:pk>/edit/", PizzaUpdateView.as_view(), name="pizza_update"),
    path("pizzas/<int:pk>/delete/", PizzaDeleteView.as_view(), name="pizza_delete"),
    path("recipes/", RecipeItemListView.as_view(), name="recipe_list"),
    path("recipes/new/", RecipeItemCreateView.as_view(), name="recipe_create"),
    path("recipes/<int:pk>/edit/", RecipeItemUpdateView.as_view(), name="recipe_update"),
    path("recipes/<int:pk>/delete/", RecipeItemDeleteView.as_view(), name="recipe_delete"),
]
