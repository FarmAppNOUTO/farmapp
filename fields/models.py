import uuid

from django.db import models


class Field(models.Model):
    external_id = models.IntegerField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=100)
    crop = models.CharField(max_length=50, blank=True)
    area = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.name


class FieldRecord(models.Model):
    field = models.ForeignKey(
        Field,
        on_delete=models.CASCADE,
        related_name="records"
    )
    client_uuid = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    date = models.DateField()
    worker = models.CharField(max_length=50)
    content = models.CharField(max_length=100)
    target_crop = models.CharField(max_length=50)
    chemical = models.CharField(max_length=100, blank=True)
    quantity = models.CharField(max_length=50, blank=True)
    note = models.TextField(blank=True)
    created_by = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.field.name} {self.date}"


class SelectOption(models.Model):
    KIND_CHOICES = (
        ("workers", "workers"),
        ("crops", "crops"),
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, db_index=True)
    value = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["kind", "value"], name="unique_option_kind_value"),
        ]
        ordering = ["kind", "value"]

    def __str__(self):
        return f"{self.kind}: {self.value}"
