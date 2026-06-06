from aiogram.fsm.state import State, StatesGroup

class ToneOfVoiceStates(StatesGroup):
    waiting_role = State()
    waiting_audience = State()
    waiting_style = State()
    waiting_examples = State()
    confirming_profile = State()

class LinkedInStates(StatesGroup):
    collecting_inputs = State()
    editing = State()

class TikTokStates(StatesGroup):
    waiting_subtype = State()
    waiting_product_url = State()
    recording = State()
    waiting_description = State()
    collecting_materials = State()
    generating_video = State()
    choosing_video_mode = State()
    reviewing_prompt = State()
    editing_prompt = State()
    generating_veo = State()
