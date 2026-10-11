import uuid

from django.db import migrations, models


def assign_uuids(apps, schema_editor):
    FieldRecord = apps.get_model("fields", "FieldRecord")
    for record in FieldRecord.objects.all():
        record.client_uuid = uuid.uuid4()
        record.save(update_fields=["client_uuid"])


class Migration(migrations.Migration):

    dependencies = [
        ("fields", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="fieldrecord",
            name="client_uuid",
            field=models.UUIDField(default=uuid.uuid4, null=True),
        ),
        migrations.AddField(
            model_name="fieldrecord",
            name="created_by",
            field=models.CharField(blank=True, default="", max_length=150),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="fieldrecord",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="fieldrecord",
            name="is_deleted",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="fieldrecord",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.RunPython(assign_uuids, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name="fieldrecord",
            name="client_uuid",
            field=models.UUIDField(db_index=True, default=uuid.uuid4, unique=True),
        ),
        migrations.AlterModelOptions(
            name="fieldrecord",
            options={"ordering": ["-date", "-id"]},
        ),
    ]
