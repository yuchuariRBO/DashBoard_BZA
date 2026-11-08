from pathlib import Path

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from .models import Category, Priority, Status
from .permissions import agents_for


def validate_attachment(upload):
    limit = settings.SUPPORT_MAX_UPLOAD_BYTES
    if upload.size > limit:
        raise ValidationError(f"El archivo supera {limit // 1048576} MB.")
    ext = Path(upload.name).suffix.lower()
    head = upload.read(32)
    upload.seek(0)
    signatures = {
        ".png": (b"\x89PNG\r\n\x1a\n", "image/png"),
        ".jpg": (b"\xff\xd8\xff", "image/jpeg"),
        ".jpeg": (b"\xff\xd8\xff", "image/jpeg"),
        ".pdf": (b"%PDF-", "application/pdf"),
    }
    if ext in signatures and head.startswith(signatures[ext][0]):
        upload.support_content_type = signatures[ext][1]
    elif ext == ".txt":
        try:
            raw = upload.read()
            raw.decode("utf-8")
            if b"\0" in raw:
                raise ValueError()
        except (UnicodeError, ValueError):
            raise ValidationError("El archivo de texto debe ser UTF-8 y no binario.")
        finally:
            upload.seek(0)
        upload.support_content_type = "text/plain"
    else:
        raise ValidationError(
            "Formato no permitido o contenido inválido. Use PNG, JPEG, PDF o TXT."
        )
    return upload


class BootstrapForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "form-check-input"
                if isinstance(field.widget, forms.CheckboxInput)
                else (
                    "form-select"
                    if isinstance(field.widget, forms.Select)
                    else "form-control"
                )
            )


class TicketForm(BootstrapForm):
    subject = forms.CharField(label="Asunto", max_length=180)
    category = forms.ModelChoiceField(
        label="Categoría", queryset=Category.objects.filter(active=True)
    )
    description = forms.CharField(
        label="Descripción", max_length=20000, widget=forms.Textarea(attrs={"rows": 6})
    )
    attachment = forms.FileField(
        label="Adjunto (PNG, JPEG, PDF o TXT)",
        required=False,
        validators=[validate_attachment],
    )


class CommentForm(BootstrapForm):
    version = forms.IntegerField(widget=forms.HiddenInput)
    body = forms.CharField(
        label="Respuesta o comentario",
        max_length=20000,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    attachment = forms.FileField(
        label="Adjunto", required=False, validators=[validate_attachment]
    )
    internal = forms.BooleanField(label="Nota interna", required=False)

    def __init__(self, *args, staff=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not staff:
            self.fields.pop("internal")


class UpdateForm(BootstrapForm):
    version = forms.IntegerField(widget=forms.HiddenInput)
    status = forms.ChoiceField(label="Estado", choices=Status.choices)
    priority = forms.ChoiceField(label="Prioridad", choices=Priority.choices)
    assignee = forms.ModelChoiceField(
        label="Responsable", queryset=None, required=False
    )

    def __init__(self, *args, user, manager, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignee"].queryset = agents_for(user)
        if not manager:
            self.fields.pop("assignee")


class FilterForm(BootstrapForm):
    q = forms.CharField(label="Identificador o asunto", required=False, max_length=180)
    status = forms.ChoiceField(
        label="Estado", required=False, choices=[("", "Todos")] + list(Status.choices)
    )
    priority = forms.ChoiceField(
        label="Prioridad",
        required=False,
        choices=[("", "Todas")] + list(Priority.choices),
    )
    category = forms.ModelChoiceField(
        label="Categoría", required=False, queryset=Category.objects.all()
    )
    start = forms.DateField(
        label="Desde", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    end = forms.DateField(
        label="Hasta", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    overdue = forms.BooleanField(label="Solo vencidos", required=False)

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end") and data["start"] > data["end"]:
            raise forms.ValidationError(
                "La fecha inicial debe ser anterior a la final."
            )
        return data


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "active"]
        widgets = {"name": forms.TextInput(attrs={"class": "form-control"})}


from .models import SLAPolicy


class PolicyForm(forms.ModelForm):
    class Meta:
        model = SLAPolicy
        fields = ["response_hours", "resolution_hours", "reopen_days", "enabled"]
        widgets = {
            name: forms.NumberInput(attrs={"class": "form-control"})
            for name in ["response_hours", "resolution_hours", "reopen_days"]
        }


class AgentForm(BootstrapForm):
    user = forms.ModelChoiceField(label="Usuario", queryset=None)
    enabled = forms.BooleanField(
        label="Habilitar como agente de soporte", required=False
    )

    def __init__(self, *args, **kwargs):
        from django.contrib.auth import get_user_model

        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = (
            get_user_model().objects.filter(is_active=True).order_by("username")
        )
