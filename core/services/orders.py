from django.core.exceptions import ValidationError

from core.models import Order

ALLOWED_TRANSITIONS = {
    Order.Status.PENDING: {Order.Status.IN_PROGRESS, Order.Status.CANCELLED},
    Order.Status.IN_PROGRESS: {Order.Status.DELIVERED, Order.Status.CANCELLED},
    Order.Status.DELIVERED: set(),
    Order.Status.CANCELLED: set(),
}


def change_order_status(order, new_status):
    if order.sale_id:
        raise ValidationError("El pedido ya fue cerrado en ventas y no puede cambiar de estado.")

    if new_status not in dict(Order.Status.choices):
        raise ValidationError("Estado de pedido inválido.")

    allowed = ALLOWED_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise ValidationError(
            f"No se puede pasar de {order.get_status_display()} a "
            f"{dict(Order.Status.choices).get(new_status, new_status)}. Esta acción no tiene rollback."
        )

    order.status = new_status
    order.save(update_fields=["status"])
    return order
