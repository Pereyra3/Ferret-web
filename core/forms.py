from django import forms


def _widget_class(widget, base_class):
    existing = widget.attrs.get("class", "")
    if base_class not in existing.split():
        widget.attrs["class"] = (existing + " " + base_class).strip()


class StyledFormMixin:
    """Apply Bootstrap + ft-control classes to visible fields."""

    control_class = "form-control ft-control"
    select_class = "form-select ft-control"
    check_class = "form-check-input ft-check"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, forms.HiddenInput):
                continue
            if isinstance(w, forms.CheckboxInput):
                _widget_class(w, self.check_class)
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                _widget_class(w, self.select_class)
            elif isinstance(w, forms.Textarea):
                _widget_class(w, self.control_class + " ft-textarea")
                w.attrs.setdefault("rows", 3)
            elif isinstance(
                w,
                (
                    forms.TextInput,
                    forms.NumberInput,
                    forms.EmailInput,
                    forms.URLInput,
                    forms.DateInput,
                    forms.DateTimeInput,
                    forms.TimeInput,
                ),
            ):
                _widget_class(w, self.control_class)
