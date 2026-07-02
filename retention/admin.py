from django.contrib import admin

from .models import Action, Conversation, Employee, Signal

admin.site.register(Employee)
admin.site.register(Signal)
admin.site.register(Conversation)
admin.site.register(Action)
