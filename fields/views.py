import json, os
from django.http import JsonResponse
from django.shortcuts import render
from django.conf import settings

def map_view(request):
    """圃場マップページ"""
    config_path = os.path.join(settings.BASE_DIR, 'fields', 'static', 'fields', 'data', 'options.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        options = json.load(f)
    return render(request, 'fields/map.html', {'options': options})

def save_option(request):
    """新しい選択肢を options.json に追加"""
    if request.method == 'POST':
        data = json.loads(request.body)
        option_type = data.get('type')   # 'workers' または 'crops'
        value = data.get('value')

        config_path = os.path.join(settings.BASE_DIR, 'fields', 'static', 'fields', 'data', 'options.json')

        with open(config_path, 'r', encoding='utf-8') as f:
            options = json.load(f)

        # すでに存在しない場合のみ追加
        if value not in options[option_type]:
            options[option_type].append(value)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(options, f, ensure_ascii=False, indent=2)

        return JsonResponse({'status': 'ok', 'added': value})

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

def delete_option(request):
    """options.json から指定の選択肢を削除"""
    if request.method == 'POST':
        data = json.loads(request.body)
        option_type = data.get('type')  # 'workers' または 'crops'
        value = data.get('value')

        config_path = os.path.join(settings.BASE_DIR, 'fields', 'static', 'fields', 'data', 'options.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            options = json.load(f)

        if value in options[option_type]:
            options[option_type].remove(value)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(options, f, ensure_ascii=False, indent=2)
            return JsonResponse({'status': 'ok', 'deleted': value})

        return JsonResponse({'status': 'error', 'message': '項目が見つかりません'}, status=404)

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

from django.shortcuts import render