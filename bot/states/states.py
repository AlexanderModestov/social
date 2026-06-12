from aiogram.fsm.state import State, StatesGroup

class ToneOfVoiceStates(StatesGroup):
    choosing_method = State()
    waiting_instagram_handle = State()
    waiting_role = State()
    waiting_audience = State()
    waiting_style = State()
    waiting_examples = State()
    confirming_profile = State()

class LinkedInStates(StatesGroup):
    collecting_inputs = State()
    editing = State()

class HumanizerStates(StatesGroup):
    waiting_input = State()
    reviewing = State()

class TikTokStates(StatesGroup):
    waiting_subtype = State()
    waiting_product_url = State()
    recording = State()
    waiting_description = State()
    collecting_materials = State()
    choosing_video_mode = State()
    reviewing_prompt = State()
    editing_prompt = State()
    generating_veo = State()
