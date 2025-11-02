from django import forms
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.models import User
from .models import Profile, ProgressLog

class UserUpdateForm(UserChangeForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['native_language', 'learning_language', 'bio', 'profile_picture']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'native_language': forms.Select(attrs={'class': 'form-select'}),
            'learning_language': forms.Select(attrs={'class': 'form-select'}),
            'profile_picture': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make the language fields required
        self.fields['native_language'].required = True
        self.fields['learning_language'].required = True
        
        # Ensure a user can't select the same language for both native and learning
        native_lang = self.data.get('native_language') or (self.instance and self.instance.native_language)
        learning_lang = self.data.get('learning_language') or (self.instance and self.instance.learning_language)
        
        if native_lang and learning_lang and native_lang == learning_lang:
            self.add_error('learning_language', 'Native and learning languages must be different.')


class MessageForm(forms.Form):
    content = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Type your message here...',
            'id': 'chat-message-input'
        }),
        label='',
        required=True
    )


class ProgressLogForm(forms.ModelForm):
    class Meta:
        model = ProgressLog
        fields = ['minutes_studied', 'words_learned', 'notes']
        widgets = {
            'minutes_studied': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'required': True
            }),
            'words_learned': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'required': True
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'What did you learn today?'
            }),
        }
    
    def clean_minutes_studied(self):
        minutes = self.cleaned_data.get('minutes_studied')
        if minutes <= 0:
            raise forms.ValidationError("Study time must be greater than 0 minutes.")
        return minutes
