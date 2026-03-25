from django.core.management.base import BaseCommand
from ai_assistant.services import build_index

class Command(BaseCommand):
    help = 'Инициализирует базу знаний для AI'

    def handle(self, *args, **options):
        self.stdout.write('Начинаю индексацию документов...')
        build_index()
        self.stdout.write(self.style.SUCCESS('База знаний готова!'))