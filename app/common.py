from aiogram.filters.callback_data import CallbackData

class ChangeUserRole(CallbackData, prefix="change_role"):
    data: str

class DeleteDomain(CallbackData, prefix="domain_remove"):
    data: str

class CloudFlareTokens(CallbackData, prefix="cf"):
    id: str

class CloudFlareDeleteTokens(CallbackData, prefix="cfd"):
    id: str