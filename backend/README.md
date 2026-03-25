Выполните миграции

python manage.py makemigrations
python manage.py migrate

Убедитесь, что ключ Яндекс.Карт добавлен в .env

Я не смог протестировать, потому что  выдавало ошибку, вроде со связью связана

(.venv) D:\python_programming\for_git_repositories\AI-assistant-in-case-of-road-accidents\backend>pip install -r requirements.txt
Collecting Django==4.0 (from -r requirements.txt (line 1))
  WARNING: Retrying (Retry(total=4, connect=None, read=None, redirect=None, status=None)) after connection broken by 'ReadTimeoutError("HTTPSConnectionPool(host='files.pythonhosted.org', port=443): Read timed out. (read timeout=15)")': /packages/80/70/52fce3520b7a1421685828b04f76d5a26aabc7603fdb7af26c4ca7bb0512/Django-4.0-py3-none-any.whl.metadata                                                                                           
  WARNING: Retrying (Retry(total=3, connect=None, read=None, redirect=None, status=None)) after connection broken by 'ReadTimeoutError("HTTPSConnectionPool(host='files.pythonhosted.org', port=443): Read timed out. (read timeout=15)")': /packages/80/70/52fce3520b7a1421685828b04f76d5a26aabc7603fdb7af26c4ca7bb0512/Django-4.0-py3-none-any.whl.metadata                                                                                           
  WARNING: Retrying (Retry(total=2, connect=None, read=None, redirect=None, status=None)) after connection broken by 'ReadTimeoutError("HTTPSConnectionPool(host='files.pythonhosted.org', port=443): Read timed out. (read timeout=15)")': /packages/80/70/52fce3520b7a1421685828b04f76d5a26aabc7603fdb7af26c4ca7bb0512/Django-4.0-py3-none-any.whl.metadata                                                                                           
  WARNING: Retrying (Retry(total=1, connect=None, read=None, redirect=None, status=None)) after connection broken by 'ReadTimeoutError("HTTPSConnectionPool(host='files.pythonhosted.org', port=443): Read timed out. (read timeout=15)")': /packages/80/70/52fce3520b7a1421685828b04f76d5a26aabc7603fdb7af26c4ca7bb0512/Django-4.0-py3-none-any.whl.metadata                                                                                           
  WARNING: Retrying (Retry(total=0, connect=None, read=None, redirect=None, status=None)) after connection broken by 'ReadTimeoutError("HTTPSConnectionPool(host='files.pythonhosted.org', port=443): Read timed out. (read timeout=15)")': /packages/80/70/52fce3520b7a1421685828b04f76d5a26aabc7603fdb7af26c4ca7bb0512/Django-4.0-py3-none-any.whl.metadata
ERROR: Could not install packages due to an OSError: HTTPSConnectionPool(host='files.pythonhosted.org', port=443): Max retries exceeded with url: /packages/80/70/52fce3520b7a1421685828b04f76d5a26aabc7603fdb7af26c4ca7bb0512/Django-4.0-py3-none-any.whl.metadata (Caused by ReadTimeoutError("HTTPSConnectionPool(host='files.pythonhosted.org', port=443): Read timed out. (read timeout=15)"))