from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from users.models import Profile

# Define an inline admin descriptor for Profile model
# which acts a bit like a singleton
class ProfileInline(admin.StackedInline):
    model = Profile
    fk_name = 'user'
    can_delete = False
    verbose_name_plural = 'Profile'

# Define a new User admin
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

from django.db.models import Sum
from .models import AIUsageLog, GlobalSettings, PageDescription, HeroSlide, CustomPage, BlogPost

@admin.register(AIUsageLog)
class AIUsageLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'request_type', 'total_cost', 'timestamp')
    list_filter = ('company', 'request_type', 'timestamp', 'user')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'company__name')
    readonly_fields = ('raw_response',)

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)
        try:
            qs = response.context_data['cl'].queryset
            total_cost_sum = qs.aggregate(Sum('total_cost'))['total_cost__sum'] or 0.0
            total_prompts = qs.aggregate(Sum('prompt_tokens'))['prompt_tokens__sum'] or 0
            total_completions = qs.aggregate(Sum('completion_tokens'))['completion_tokens__sum'] or 0
        except (AttributeError, KeyError):
            total_cost_sum = 0.0
            total_prompts = 0
            total_completions = 0
            
        extra_info = f"Atfiltruotų užklausų suma: {total_cost_sum:.6f}$, Prompt žetonai: {total_prompts}, Completion žetonai: {total_completions}"
        
        my_context = {
            'title': f'{self.opts.verbose_name_plural} | {extra_info}'
        }
        if extra_context:
            my_context.update(extra_context)
            
        if hasattr(response, 'context_data'):
            response.context_data.update(my_context)
        return response

@admin.register(GlobalSettings)
class GlobalSettingsAdmin(admin.ModelAdmin):
    list_display = ('personal_form_enabled', 'team_form_enabled', 'language_switcher_enabled')

@admin.register(PageDescription)
class PageDescriptionAdmin(admin.ModelAdmin):
    list_display = ('maintenance_mode', 'maintenance_title')

@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ('title', 'order', 'is_active', 'button_text', 'updated_at')
    list_editable = ('order', 'is_active')
    list_filter = ('is_active',)
    ordering = ('order', 'id')
    fieldsets = (
        ('Lietuvių kalba', {
            'fields': ('title', 'description', 'button_text', 'button_url')
        }),
        ('English', {
            'fields': ('title_en', 'description_en', 'button_text_en'),
        }),
        ('Nustatymai', {
            'fields': ('order', 'is_active')
        }),
    )

@admin.register(CustomPage)
class CustomPageAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'is_published', 'created_at', 'updated_at')
    list_filter = ('is_published', 'created_at')
    search_fields = ('title', 'slug', 'content')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'author_name', 'is_published', 'views_count', 'created_at')
    list_filter = ('is_published', 'created_at')
    search_fields = ('title', 'slug', 'excerpt', 'content', 'author_name')
    prepopulated_fields = {'slug': ('title',)}
