import json
import os
import uuid
from datetime import datetime

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_GET

from .models import Field, FieldRecord, SelectOption


def _options_path():
    return os.path.join(
        settings.BASE_DIR, "fields", "static", "fields", "data", "options.json"
    )


def _load_options():
    try:
        return {
            "workers": list(
                SelectOption.objects.filter(kind="workers").values_list("value", flat=True)
            ),
            "crops": list(
                SelectOption.objects.filter(kind="crops").values_list("value", flat=True)
            ),
        }
    except Exception:
        with open(_options_path(), "r", encoding="utf-8") as f:
            return json.load(f)


def _get_or_create_field(external_id, name="", crop="", area=""):
    field, _ = Field.objects.get_or_create(
        external_id=external_id,
        defaults={"name": name or f"{external_id}番", "crop": crop or "", "area": area or ""},
    )
    updated = False
    if name and field.name != name:
        field.name = name
        updated = True
    if crop is not None and field.crop != crop:
        field.crop = crop
        updated = True
    if area is not None and field.area != area:
        field.area = area
        updated = True
    if updated:
        field.save()
    return field


def _record_to_dict(record):
    return {
        "id": record.id,
        "uuid": str(record.client_uuid),
        "date": str(record.date),
        "worker": record.worker,
        "content": record.content,
        "target_crop": record.target_crop,
        "chemical": record.chemical,
        "quantity": record.quantity,
        "note": record.note,
        "created_by": record.created_by,
        "is_deleted": record.is_deleted,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def _parse_updated_since(value):
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        try:
            parsed_date = parse_date(value)
        except (TypeError, ValueError):
            return None
        if parsed_date is None:
            return None
        parsed = datetime.combine(parsed_date, datetime.min.time())
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def map_view(request):
    return render(request, "fields/map.html", {"options": _load_options()})


@require_GET
def get_records(request, field_id):
    """常に最新の確定情報を返す。削除済みは含めない。"""
    updated_since = _parse_updated_since(request.GET.get("updated_since"))
    field = Field.objects.filter(external_id=field_id).first()
    if field is None:
        return JsonResponse(
            {"status": "ok", "records": [], "server_time": timezone.now().isoformat()}
        )
    qs = field.records.filter(is_deleted=False)
    if updated_since is not None:
        qs = qs.filter(updated_at__gt=updated_since)
    records = [_record_to_dict(r) for r in qs.order_by("-date", "-id")]
    deleted_qs = field.records.filter(is_deleted=True)
    if updated_since is not None:
        deleted_qs = deleted_qs.filter(updated_at__gt=updated_since)
    deleted_uuids = [str(r.client_uuid) for r in deleted_qs.only("client_uuid", "updated_at")]
    return JsonResponse({
        "status": "ok",
        "records": records,
        "deleted_uuids": deleted_uuids,
        "server_time": timezone.now().isoformat(),
    })


def _clean_str(value):
    return (value or "").strip() if isinstance(value, str) else ""


@transaction.atomic
def _upsert_record(data, username):
    try:
        external_id = int(data.get("field_id"))
    except (TypeError, ValueError):
        return None, JsonResponse(
            {"status": "ng", "message": "field_id is required", "uuid": data.get("uuid")},
            status=400,
        )

    raw_uuid = data.get("uuid")
    try:
        client_uuid = uuid.UUID(str(raw_uuid)) if raw_uuid else uuid.uuid4()
    except (ValueError, AttributeError, TypeError):
        return None, JsonResponse(
            {"status": "ng", "message": "uuid is invalid", "uuid": raw_uuid},
            status=400,
        )

    date = _clean_str(data.get("date"))
    worker = _clean_str(data.get("worker"))
    content = _clean_str(data.get("content"))
    target_crop = _clean_str(data.get("target_crop"))
    is_delete = bool(data.get("is_deleted"))
    if not date or not worker or not content or not target_crop:
        return None, JsonResponse(
            {
                "status": "ng",
                "message": "date/worker/content/target_crop are required",
                "uuid": str(client_uuid),
            },
            status=400,
        )

    existing = FieldRecord.objects.select_for_update().filter(client_uuid=client_uuid).first()
    if existing is not None and existing.is_deleted and not is_delete:
        # 一度確定した削除は復活させない（オフライン削除の復活防止）。
        # 再登録したい場合は別UUIDで新規作成扱いにする。
        return existing, JsonResponse(
            {
                "status": "conflict",
                "code": "already_deleted",
                "message": "already deleted on server",
                "uuid": str(client_uuid),
                "record": _record_to_dict(existing),
            },
            status=409,
        )

    field = _get_or_create_field(
        external_id,
        name=_clean_str(data.get("field_name")),
        crop=_clean_str(data.get("field_crop")),
        area=_clean_str(data.get("field_area")),
    )
    values = {
        "field": field,
        "date": date,
        "worker": worker,
        "content": content,
        "target_crop": target_crop,
        "chemical": _clean_str(data.get("chemical")),
        "quantity": _clean_str(data.get("quantity")),
        "note": _clean_str(data.get("note")),
        "is_deleted": False,
    }
    try:
        if existing is None:
            record = FieldRecord.objects.create(
                client_uuid=client_uuid,
                created_by=username,
                **values,
            )
            created = True
        else:
            for key, value in values.items():
                setattr(existing, key, value)
            if not existing.created_by:
                existing.created_by = username
            existing.save()
            record = existing
            created = False
    except IntegrityError:
        # 同時登録のUUID衝突は既存を返して重複作成にしない。
        record = FieldRecord.objects.filter(client_uuid=client_uuid).first()
        created = False
    return record, JsonResponse({
        "status": "ok",
        "created": created,
        "uuid": str(record.client_uuid),
        "record": _record_to_dict(record),
    })


def save_record(request):
    if request.method != "POST":
        return JsonResponse({"status": "ng", "message": "POST only"}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "ng", "message": "invalid json"}, status=400)
    username = request.user.username if getattr(request, "user", None) and request.user.is_authenticated else ""
    _, response = _upsert_record(data, username)
    return response


@transaction.atomic
def sync_records(request):
    """オフライン分の一括アップロード＋最新取得を1回で確定させる。"""
    if request.method != "POST":
        return JsonResponse({"status": "ng", "message": "POST only"}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "ng", "message": "invalid json"}, status=400)

    username = request.user.username if getattr(request, "user", None) and request.user.is_authenticated else ""
    changes = data.get("changes") or []
    if not isinstance(changes, list):
        return JsonResponse({"status": "ng", "message": "changes must be a list"}, status=400)

    results = []
    for change in changes:
        if not isinstance(change, dict):
            results.append({"status": "ng", "message": "invalid change"})
            continue
        op = change.get("op", "upsert")
        if op == "delete":
            result = _apply_delete(change, username)
        else:
            _, response = _upsert_record(change, username)
            result = json.loads(response.content.decode("utf-8"))
        results.append(result)

    try:
        external_id = int(data.get("field_id"))
    except (TypeError, ValueError):
        return JsonResponse({"status": "ng", "message": "field_id is required", "results": results}, status=400)

    updated_since = _parse_updated_since(data.get("updated_since"))
    field = Field.objects.filter(external_id=external_id).first()
    records = []
    deleted_uuids = []
    if field is not None:
        qs = field.records.filter(is_deleted=False)
        deleted_qs = field.records.filter(is_deleted=True)
        if updated_since is not None:
            qs = qs.filter(updated_at__gt=updated_since)
            deleted_qs = deleted_qs.filter(updated_at__gt=updated_since)
        records = [_record_to_dict(r) for r in qs.order_by("-date", "-id")]
        deleted_uuids = [str(r.client_uuid) for r in deleted_qs.only("client_uuid", "updated_at")]

    return JsonResponse({
        "status": "ok",
        "results": results,
        "records": records,
        "deleted_uuids": deleted_uuids,
        "server_time": timezone.now().isoformat(),
    })


@transaction.atomic
def _apply_delete(change, username):
    raw_uuid = change.get("uuid")
    try:
        client_uuid = uuid.UUID(str(raw_uuid))
    except (ValueError, AttributeError, TypeError):
        return {"status": "ng", "message": "uuid is required", "uuid": raw_uuid}
    record = FieldRecord.objects.select_for_update().filter(client_uuid=client_uuid).first()
    if record is None:
        # 削除対象が未同期の新規なら、その場で削除済みとして作って確定させる。
        # これで「他端末で復活」を防ぐ。
        try:
            external_id = int(change.get("field_id"))
        except (TypeError, ValueError):
            return {"status": "ng", "message": "field_id is required", "uuid": str(client_uuid)}
        field = _get_or_create_field(external_id)
        now = timezone.now()
        record = FieldRecord.objects.create(
            field=field,
            client_uuid=client_uuid,
            date=_clean_str(change.get("date")) or now.date().isoformat(),
            worker=_clean_str(change.get("worker")) or username or "unknown",
            content=_clean_str(change.get("content")) or "(deleted before sync)",
            target_crop=_clean_str(change.get("target_crop")) or "-",
            created_by=username,
            is_deleted=True,
            deleted_at=now,
        )
        return {"status": "ok", "uuid": str(client_uuid), "record": _record_to_dict(record)}
    if not record.is_deleted:
        record.is_deleted = True
        record.deleted_at = timezone.now()
        record.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
    return {"status": "ok", "uuid": str(record.client_uuid), "record": _record_to_dict(record)}


def delete_record(request):
    if request.method != "POST":
        return JsonResponse({"status": "ng", "message": "POST only"}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "ng", "message": "invalid json"}, status=400)
    username = request.user.username if getattr(request, "user", None) and request.user.is_authenticated else ""
    return JsonResponse(_apply_delete(data, username))


def record_view(request, field_id):
    field = _get_or_create_field(external_id=field_id)
    records = field.records.filter(is_deleted=False).order_by("-date", "-id")
    return render(request, "fields/record.html", {"field": field, "records": records})


def save_option(request):
    if request.method != "POST":
        return JsonResponse({"status": "ng", "message": "POST only"}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "ng", "message": "invalid json"}, status=400)
    option_type = data.get("type")
    value = (data.get("value") or "").strip()
    if option_type not in ("workers", "crops") or not value:
        return JsonResponse({"status": "ng", "message": "invalid data"}, status=400)

    obj, _ = SelectOption.objects.get_or_create(kind=option_type, value=value)
    return JsonResponse({"status": "ok", "added": obj.value})


def delete_option(request):
    if request.method != "POST":
        return JsonResponse({"status": "ng", "message": "POST only"}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "ng", "message": "invalid json"}, status=400)
    option_type = data.get("type")
    value = data.get("value")
    if option_type not in ("workers", "crops") or not value:
        return JsonResponse({"status": "ng", "message": "invalid data"}, status=400)

    deleted, _ = SelectOption.objects.filter(kind=option_type, value=value).delete()
    if deleted:
        return JsonResponse({"status": "ok", "deleted": value})
    return JsonResponse({"status": "ng", "message": "not found"}, status=404)
