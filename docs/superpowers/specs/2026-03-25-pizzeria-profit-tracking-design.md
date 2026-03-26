# Pizzeria App - Design Spec (MVP Local)

Fecha: 2026-03-25  
Estado: Aprobado para plan de implementación  
Owner: Mateo

## 1) Objetivo

Construir una app local para una pizzería que permita:
- Cargar ventas en tiempo real y también en cierre diario.
- Gestionar insumos con precios fijos y stock.
- Gestionar recetas por pizza con cantidades por unidad.
- Calcular costo, ganancia y métricas clave de operación.

## 2) Alcance del MVP

Incluye:
- Uso local en una sola PC.
- Un solo usuario operativo.
- Panel web interno.
- Métricas de ganancia, margen, top ventas y stock.

No incluye en MVP:
- Multiusuario con permisos.
- Nube o acceso remoto.
- Historial de precios por fecha.
- Integración con POS o apps de delivery.

## 3) Stack técnico

- Backend: Django
- Base de datos: SQLite (local)
- UI: templates Django + formularios simples
- Administración: Django Admin

## 4) Modelo de datos

### Ingredient
- `name` (unique)
- `unit` (`g`, `ml`, `un`)
- `unit_price` (decimal `max_digits=12`, `decimal_places=2`)
- `current_stock` (decimal `max_digits=12`, `decimal_places=3`)
- `min_stock` (decimal `max_digits=12`, `decimal_places=3`)
- `is_active` (bool)
- timestamps (`created_at`, `updated_at`)

### Pizza
- `name` (unique)
- `sale_price` (decimal `max_digits=12`, `decimal_places=2`)
- `is_active` (bool)
- timestamps (`created_at`, `updated_at`)

### RecipeItem
- `pizza` (FK -> Pizza)
- `ingredient` (FK -> Ingredient)
- `quantity` (decimal `max_digits=12`, `decimal_places=3`, cantidad por 1 pizza)
- unique constraint: (`pizza`, `ingredient`)

### Sale
- `created_at` (datetime)
- `business_date` (date, obligatorio para reportes por día operativo)
- `source` (`REAL_TIME`, `DAILY_CLOSE`)
- `notes` (text nullable)

### SaleItem
- `sale` (FK -> Sale)
- `pizza` (FK -> Pizza)
- `quantity` (integer)
- `applied_unit_price` (decimal snapshot `max_digits=12`, `decimal_places=2`)
- `calculated_unit_cost` (decimal snapshot `max_digits=12`, `decimal_places=2`)
- `calculated_unit_profit` (decimal snapshot `max_digits=12`, `decimal_places=2`)

### IngredientMovement
- `ingredient` (FK -> Ingredient)
- `movement_type` (`SALE_CONSUMPTION`, `MANUAL_ADJUSTMENT`)
- `quantity` (decimal `max_digits=12`, `decimal_places=3`, siempre positivo)
- `direction` (`IN`, `OUT`) obligatorio para `MANUAL_ADJUSTMENT`; fijo en `OUT` para `SALE_CONSUMPTION`
- `created_at` (datetime)
- `reference` (string)

## 5) Reglas de negocio

- No se puede vender una pizza sin receta cargada.
- Cantidades y precios no pueden ser negativos.
- `RecipeItem.quantity` siempre debe estar expresado en la misma unidad de `Ingredient.unit`.
- Al guardar una venta se calculan snapshots de precio/costo/ganancia en `SaleItem`.
- Al guardar una venta se descuenta stock de cada insumo según receta y cantidad vendida.
- Se registra un `IngredientMovement` por cada consumo/ajuste.
- Convención de movimientos:
  - `SALE_CONSUMPTION`: resta stock.
  - `MANUAL_ADJUSTMENT`: suma stock con `direction=IN` y resta stock con `direction=OUT`.
  - El campo `quantity` en movimientos se guarda siempre como valor positivo.
- Se permite stock negativo en MVP, con alerta visible.
- Operación de guardado de venta debe ser atómica (todo o nada).
- No se permite vender pizzas o usar ingredientes con `is_active=False`.

## 6) Flujos operativos

### Flujo A: Venta en tiempo real
1. Seleccionar pizza y cantidad.
2. Calcular subtotal, costo y ganancia estimada.
3. Guardar venta con `source=REAL_TIME`.
4. Descontar stock y registrar movimientos.

### Flujo B: Cierre diario
1. Cargar cantidades agregadas por pizza al final del día.
2. Guardar venta con `source=DAILY_CLOSE`.
3. Aplicar mismo cálculo y descuento de stock.

Regla operativa para evitar duplicación:
- Usar cierre diario solo para pedidos no cargados en tiempo real.
- En MVP no habrá deduplicación automática; la responsabilidad operativa es del usuario.

## 7) Métricas requeridas (dashboard/reportes)

- Ganancia diaria/semanal/mensual.
- Costo unitario y margen unitario por pizza.
- Top pizzas más vendidas (por cantidad y por ingreso).
- Consumo de insumos por período.
- Alertas de stock bajo (`current_stock < min_stock`) y stock negativo.
- Las métricas por día operativo se agrupan por `Sale.business_date`, no por `created_at`.

## 8) Pantallas del MVP

- Dashboard
- Ingredients (CRUD + ajuste de stock)
- Pizzas (CRUD)
- Recipes (gestión por pizza)
- Real-time Sales (carga rápida)
- Daily Close Entry (carga agregada)
- Reports (filtros por rango de fechas)
- Nota de alcance MVP: el ingreso de stock se hace vía ajuste manual; no hay flujo de compras separado.

## 9) Roadmap de implementación

Fase 1:
- Estructura Django base y modelos.
- Migraciones y admin inicial.

Fase 2:
- Servicios de cálculo y persistencia transaccional.
- Validaciones de negocio.

Fase 3:
- Pantallas operativas de carga y mantenimiento.

Fase 4:
- Dashboard y reportes de métricas.

Fase 5:
- Pruebas, endurecimiento y mejora de mensajes.

## 10) Criterios de aceptación MVP

- Se pueden crear ingredientes, pizzas y recetas.
- Se puede cargar venta en tiempo real y cierre diario.
- El sistema calcula correctamente costo y ganancia por ítem.
- El stock se actualiza automáticamente por ventas.
- Se visualizan métricas pedidas en dashboard/reportes.

## 11) Pruebas mínimas

- Venta con receta completa descuenta stock esperado.
- Venta de pizza sin receta falla con mensaje claro.
- Recalcular métricas por período devuelve valores correctos con caso controlado:
  - Pizza A: `applied_unit_price=1000`, `calculated_unit_cost=600`, cantidad vendida=3.
  - Ganancia esperada del período para Pizza A: `1200`.
- Carga diaria no rompe consistencia de snapshots.
- Ajuste manual de stock impacta alertas.

## 12) Operación local

Comandos base:
- `python -m venv .venv`
- `.venv\Scripts\activate`
- `pip install django`
- `python manage.py makemigrations`
- `python manage.py migrate`
- `python manage.py createsuperuser`
- `python manage.py runserver`

## 13) Rollback operativo (etapa temprana)

- Si falla código: volver al último estado estable de archivos.
- Si falla migración: revertir con `python manage.py migrate <app_name> <migracion_previa>` y/o restaurar backup de `db.sqlite3`.
- Si se requiere reinicio completo en etapa temprana:
  - eliminar `db.sqlite3`
  - mantener migraciones versionadas existentes (no recrearlas)
  - ejecutar `python manage.py migrate`
  - ejecutar `python manage.py makemigrations` solo si hubo cambios reales en modelos

## 14) Riesgos y mitigaciones

- Riesgo: duplicar datos al mezclar tiempo real y cierre.
  - Mitigación: regla operativa explícita y validaciones en UI.
- Riesgo: desviación por stock negativo permanente.
  - Mitigación: alertas visibles en dashboard y rutina diaria de ajuste.
- Riesgo: cambios de precio futuros afecten histórico.
  - Mitigación: snapshots en `SaleItem`.
