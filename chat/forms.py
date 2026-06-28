from django import forms
from .models import Document


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["file"]

    def clean_file(self):
        file = self.cleaned_data.get("file")
        if file:
            name = file.name.lower()
            if not name.endswith(".pdf"):
                raise forms.ValidationError("Only PDF files are accepted.")
            # Guard against excessively large uploads (50 MB limit)
            if file.size > 50 * 1024 * 1024:
                raise forms.ValidationError("File size must not exceed 50 MB.")
        return file