# Pizzeria MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir una app Django local para registrar ventas, recetas e insumos, y calcular ganancias y métricas operativas.

**Architecture:** Monolito Django con app `core`, SQLite local, servicios de dominio para ventas y métricas, y vistas simples con templates. CRUD principal en vistas + admin de soporte.

**Tech Stack:** Python, Django, SQLite, Django templates, unittest de Django.

---

## File Structure

- Crear `manage.py`, proyecto Django `pizzeria`, app `core`.
- Modelos de dominio en `core/models.py`.
- Servicios de negocio en `core/services/`.
- Formularios en `core/forms.py`.
- Vistas y URLs en `core/views.py`, `core/urls.py`, `pizzeria/urls.py`.
- Templates en `templates/`.
- Tests en `core/tests/`.

### Task 1: Bootstrap Django Project

**Files:**
- Create: `manage.py`, `pizzeria/settings.py`, `pizzeria/urls.py`, `pizzeria/wsgi.py`, `pizzeria/asgi.py`
- Create: `core/apps.py`, `core/__init__.py`, `core/migrations/__init__.py`
- Create: `requirements.txt`
- Modify: `pizzeria/settings.py`
- Test: `python manage.py check`

- [ ] **Step 1: Crear estructura base Django**
- [ ] **Step 1.1: Crear `requirements.txt` con Django**
- [ ] **Step 2: Configurar `INSTALLED_APPS` con `core` y templates**
- [ ] **Step 3: Ejecutar `python manage.py check`**
- [ ] **Step 4: Commit**

### Task 2: Domain Models and Admin

**Files:**
- Create/Modify: `core/models.py`, `core/admin.py`
- Test: `core/tests/test_models.py`

- [ ] **Step 1: Write failing test**
  - Crear tests de constraints y reglas básicas (`unique`, campos positivos, `business_date`).
  - Validar presencia de campos de spec: `Sale.notes`, `IngredientMovement.reference`, `IngredientMovement.direction`.
  - Validar regla de unidad: `RecipeItem.quantity` debe usar la misma unidad que `Ingredient.unit` (vía `clean()` o validación equivalente).
- [ ] **Step 2: Run tests to verify fail**
  - `python manage.py test core.tests.test_models -v 2`
- [ ] **Step 3: Write minimal implementation**
  - Modelos: `Ingredient`, `Pizza`, `RecipeItem`, `Sale`, `SaleItem`, `IngredientMovement`.
- [ ] **Step 4: Run tests to verify pass**
  - `python manage.py test core.tests.test_models -v 2`
- [ ] **Step 5: Crear y aplicar migraciones base**
  - `python manage.py makemigrations core`
  - `python manage.py migrate`
- [ ] **Step 6: Register models in admin**
- [ ] **Step 7: Commit**

### Task 3: Sales Service with Atomic Stock Updates

**Files:**
- Create: `core/services/__init__.py`
- Create: `core/services/sales.py`
- Create/Modify: `core/tests/test_sales_service.py`

- [ ] **Step 1: Write failing tests**
  - Caso feliz: venta descuenta stock y crea movements.
  - Error: venta sin receta falla.
  - Error: venta con `Pizza.is_active=False` falla.
  - Error: venta con `Ingredient.is_active=False` falla.
  - Validar snapshots en `SaleItem` (`applied_unit_price`, `calculated_unit_cost`, `calculated_unit_profit`).
  - Validar `IngredientMovement.reference` informado en movimientos de consumo.
- [ ] **Step 2: Run tests to verify fail**
  - `python manage.py test core.tests.test_sales_service -v 2`
- [ ] **Step 3: Write minimal implementation**
  - `create_sale()` con `transaction.atomic`.
- [ ] **Step 4: Run tests to verify pass**
  - `python manage.py test core.tests.test_sales_service -v 2`
- [ ] **Step 5: Commit**

### Task 4: Metrics Service

**Files:**
- Create: `core/services/metrics.py`
- Create/Modify: `core/tests/test_metrics_service.py`

- [ ] **Step 1: Write failing tests**
  - Ganancia por rango usando `business_date`.
  - Top pizzas por cantidad.
  - Top pizzas por ingreso.
  - Costo unitario y margen unitario por pizza.
  - Consumo de insumos por período.
  - Low stock y negative stock list.
  - Caso controlado: `applied_unit_price=1000`, `calculated_unit_cost=600`, `quantity=3` => ganancia período `1200`.
  - Carga `DAILY_CLOSE` preserva consistencia de snapshots (no recalcula históricos al cambiar precios después).
- [ ] **Step 2: Run tests to verify fail**
  - `python manage.py test core.tests.test_metrics_service -v 2`
- [ ] **Step 3: Write minimal implementation**
- [ ] **Step 4: Run tests to verify pass**
  - `python manage.py test core.tests.test_metrics_service -v 2`
- [ ] **Step 5: Commit**

### Task 5: Forms, Views, URLs, Templates

**Files:**
- Create: `core/forms.py`, `core/views.py`, `core/urls.py`
- Create: `templates/base.html`, `templates/core/dashboard.html`, `templates/core/sale_form.html`, `templates/core/daily_close_form.html`, `templates/core/report.html`, `templates/core/ingredient_list.html`, `templates/core/ingredient_form.html`, `templates/core/ingredient_adjust_stock_form.html`, `templates/core/pizza_list.html`, `templates/core/pizza_form.html`, `templates/core/recipe_form.html`
- Modify: `pizzeria/urls.py`
- Test: `core/tests/test_views.py`

- [ ] **Step 1: Write failing tests**
  - Dashboard responde 200.
  - Crear venta `REAL_TIME` desde formulario persiste correctamente.
  - Crear venta `DAILY_CLOSE` desde formulario persiste correctamente.
  - Ajuste manual de stock crea `IngredientMovement` con `movement_type` y `direction` correctos.
  - Formulario `REAL_TIME` muestra subtotal, costo estimado y ganancia estimada antes de guardar.
  - Reportes aceptan filtro por rango de fechas (`start_date`, `end_date`) en UI/URL.
- [ ] **Step 2: Run tests to verify fail**
  - `python manage.py test core.tests.test_views -v 2`
- [ ] **Step 3: Write minimal implementation**
  - Vistas para dashboard, ventas `REAL_TIME`, carga `DAILY_CLOSE`, reportes, CRUD Ingredient/Pizza y gestión de receta por pizza.
  - Vista de ajuste manual de stock.
  - Cálculo de estimados pre-guardado en venta `REAL_TIME`.
  - Filtro de fechas en vista y template de reportes.
- [ ] **Step 4: Run tests to verify pass**
  - `python manage.py test core.tests.test_views -v 2`
- [ ] **Step 5: Commit**

### Task 6: Migrations and End-to-End Verification

**Files:**
- Modify: docs if needed

- [ ] **Step 1: Ejecutar migraciones**
  - `python manage.py makemigrations`
  - `python manage.py migrate`
- [ ] **Step 2: Ejecutar test suite completa**
  - `python manage.py test -v 2`
- [ ] **Step 3: Smoke check de servidor**
  - `python manage.py runserver` y validar dashboard/sales/report
- [ ] **Step 4: Commit**

## Verification Criteria

- Todos los tests verdes.
- Venta sin receta falla con mensaje explícito.
- Venta con pizza/insumo inactivos falla con mensaje explícito.
- Venta válida descuenta stock y registra movements.
- Venta válida setea snapshots de precio/costo/ganancia en `SaleItem`.
- Métricas por período usan `business_date`.
- Caso controlado devuelve ganancia esperada `1200`.
- Reportes incluyen top por cantidad y por ingreso, consumo de insumos, y alertas de low/negative stock.
- Carga diaria no rompe consistencia de snapshots.
- Dashboard y formularios principales disponibles.
- Pantalla de venta en tiempo real muestra estimados antes de guardar.
- Pantalla de reportes soporta filtro por rango de fechas.
