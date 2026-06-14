from aiogram.fsm.state import State, StatesGroup

class ToneOfVoiceStates(StatesGroup):
    choosing_channel = State()
    choosing_method = State()
    waiting_import_handle = State()
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

class PostAuditStates(StatesGroup):
    waiting_input = State()

class CommentDrafterStates(StatesGroup):
    waiting_input = State()

class ReplyHandlerStates(StatesGroup):
    waiting_input = State()

class HookExtractorStates(StatesGroup):
    waiting_input = State()

class EngagementStates(StatesGroup):
    waiting_input = State()

class ProfileOptimizerStates(StatesGroup):
    waiting_input = State()

class EmployeeAdvocacyStates(StatesGroup):
    waiting_input = State()

class ContentPlannerStates(StatesGroup):
    waiting_role = State()
    waiting_audience = State()

class TikTokStates(StatesGroup):
    waiting_subtype = State()
    waiting_product_url = State()
    recording = State()

class VeoStates(StatesGroup):
    choosing_video_mode = State()
    waiting_description = State()
    collecting_materials = State()
    reviewing_prompt = State()
    editing_prompt = State()
    refining_prompt = State()
    generating_veo = State()
