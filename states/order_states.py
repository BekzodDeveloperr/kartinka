"""FSM state groups for user order flow and admin actions."""
from aiogram.fsm.state import State, StatesGroup


class OrderFlow(StatesGroup):
    waiting_language = State()
    waiting_name = State()
    waiting_phone = State()
    waiting_address = State()
    choosing_category = State()
    browsing_gallery = State()
    choosing_material = State()
    choosing_size = State()
    waiting_custom_size = State()
    confirming_item = State()
    asking_more_items = State()
    viewing_cart = State()
    choosing_deadline = State()
    asking_promo = State()
    waiting_promo_code = State()
    final_confirmation = State()
    finished = State()
    leaving_review = State()


class AdminFlow(StatesGroup):
    waiting_broadcast_text = State()
    waiting_order_search = State()
    waiting_product_category = State()
    waiting_product_photo = State()
    waiting_product_caption = State()
    waiting_edit_caption = State()
    waiting_price_input = State()
    waiting_admin_reply = State()
    waiting_new_admin_id = State()
    waiting_promo_code = State()
    waiting_promo_value = State()
    waiting_promo_until = State()
    waiting_review_comment = State()
    waiting_admin_username_setting = State()
