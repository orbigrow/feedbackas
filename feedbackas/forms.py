from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from users.models import Department, Profile
from django import forms
from .models import Feedback
from django.utils.translation import gettext_lazy as _

class RegistrationForm(UserCreationForm):
    email = forms.EmailField(
        max_length=254,
        required=True,
        help_text='Required. Inform a valid email address.'
    )
    first_name = forms.CharField(max_length=30, required=True, help_text='Required.')
    last_name = forms.CharField(max_length=30, required=True, help_text='Required.')
    company = forms.CharField(max_length=100, required=False)
    password1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput, strip=False)
    password2 = forms.CharField(
        label=_("Password confirmation"),
        widget=forms.PasswordInput,
        strip=False,
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'last_name', 'email', 'company')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        css_class = 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-purple-500 focus:border-purple-500 sm:text-sm'
        # The fields dictionary includes the fields from the form and the inherited ones
        self.fields['password1'].widget.attrs.update({'class': css_class})
        self.fields['password2'].widget.attrs.update({'class': css_class})
        self.fields['email'].widget.attrs.update({'class': css_class})
        self.fields['first_name'].widget.attrs.update({'class': css_class})
        self.fields['last_name'].widget.attrs.update({'class': css_class})
        self.fields['company'].widget.attrs.update({'class': css_class})

    def clean_email(self):
        from users.models import Company, Profile
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Vartotojas su tokiu el. pašto adresu jau egzistuoja.")

        # Tikrinti ar el. pašto domenas susietas su įmone
        if email and '@' in email:
            domain = email.split('@')[1].lower()
            company_exists = Company.objects.filter(
                email_domain__iexact=domain,
                is_active=True,
            ).exists()
            # Fallback: tikrinti ar yra esamų vartotojų su tuo domenu
            if not company_exists:
                profile_exists = Profile.objects.filter(
                    user__email__iendswith=f'@{domain}',
                    company_link__isnull=False,
                    company_link__is_active=True,
                ).exists()
                if not profile_exists:
                    raise forms.ValidationError(
                        "Jūsų įmonė sistemoje neužregistruota. Susisiekite su administratoriumi."
                    )
        return email

    def save(self, commit=True):
        self.instance.username = self.cleaned_data["email"]
        user = super().save(commit=commit)
        return user

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = [
            'rating', 
            'teamwork_rating', 
            'communication_rating', 
            'initiative_rating', 
            'technical_skills_rating', 
            'problem_solving_rating',
            'keywords', 
            'comments',
            'feedback'
        ]

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'parent', 'manager']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-purple-500 focus:border-purple-500 sm:text-sm'}),
            'parent': forms.Select(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-purple-500 focus:border-purple-500 sm:text-sm'}),
            'manager': forms.Select(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-purple-500 focus:border-purple-500 sm:text-sm'}),
        }

    def __init__(self, user, *args, **kwargs):
        super(DepartmentForm, self).__init__(*args, **kwargs)
        # Filtruojame tėvinius departamentus ir vadovus tik iš tos pačios įmonės
        # Naudojame getattr, kad išvengtume klaidų, jei vartotojas neturi profilio (pvz. admin)
        profile = getattr(user, 'profile', None)
        company_link = profile.company_link if profile else None

        if company_link:
            self.fields['parent'].queryset = Department.objects.filter(company=company_link)
            self.fields['manager'].queryset = User.objects.filter(profile__company_link=company_link)

class PageDescriptionForm(forms.ModelForm):
    class Meta:
        model = __import__('feedbackas.models').models.PageDescription
        fields = '__all__'
        widgets = {}
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': 'w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-primary focus:border-purple-500 outline-none transition-all resize-none', 'rows': 4})
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'w-6 h-6 text-primary rounded focus:ring-primary border-gray-300'})
            else:
                field.widget.attrs.update({'class': 'w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-primary focus:border-purple-500 outline-none transition-all'})

class EmailTemplateForm(forms.ModelForm):
    class Meta:
        model = __import__('feedbackas.models').models.EmailTemplate
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': 'w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-primary focus:border-purple-500 outline-none transition-all resize-none', 'rows': 8})
            else:
                field.widget.attrs.update({'class': 'w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-primary focus:border-purple-500 outline-none transition-all'})