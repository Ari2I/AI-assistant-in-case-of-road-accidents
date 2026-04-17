import os
import shutil

# Переименовываем файлы с кириллицей на латиницу
files_to_rename = {
    'Аварийный знак.png': 'step2_warning.png',
    'Позвонить 112.png': 'step3_call112.png',
    'Полис ОСАГО.png': 'step4_osago.png',
    'Фото ДТП.png': 'step5_photo.png',
    'Фото европротокола.png': 'step7_europrotocol.png',
}

static_dir = r'c:\Dev\Projekt_V2\backend\static\png'
frontend_dir = r'c:\Dev\Projekt_V2\frontend\png'

# Сначала копируем из frontend если нет в static
for ru_name, en_name in files_to_rename.items():
    src = os.path.join(frontend_dir, ru_name)
    dst = os.path.join(static_dir, en_name)
    
    if os.path.exists(src):
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
            print(f"Copied: {ru_name} -> {en_name}")
        else:
            print(f"Already exists: {en_name}")
    else:
        print(f"Source not found: {ru_name}")

print("\nDone!")
