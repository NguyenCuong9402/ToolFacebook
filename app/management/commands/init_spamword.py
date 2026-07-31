from pathlib import Path

from django.core.management.base import BaseCommand

from app.utils import import_spam_words


class Command(BaseCommand):
    help = "Import spam words from app/resource/spam_word.txt"

    def handle(self, *args, **options):
        file_path = Path("app/resource/spam_word.txt")

        if not file_path.exists():
            self.stderr.write(
                self.style.ERROR(
                    f"Không tìm thấy file: {file_path}"
                )
            )
            return

        with file_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            keywords = [
                line.strip()
                for line in file
                if line.strip()
            ]

        result = import_spam_words(keywords)

        self.stdout.write(
            self.style.SUCCESS(
                "Import spam word thành công!"
            )
        )

        self.stdout.write(f"Tổng: {result['total']}")
        self.stdout.write(f"Thêm mới: {result['created']}")
        self.stdout.write(f"Đã tồn tại: {result['existed']}")