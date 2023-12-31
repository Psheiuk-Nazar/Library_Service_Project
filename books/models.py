from django.db import models


class Books(models.Model):
    class Enum(models.TextChoices):
        HARD = "HARD"
        SOFT = "SOFT"

    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    cover = models.CharField(
        max_length=5,
        choices=Enum.choices,
        default=Enum.HARD
    )
    inventory = models.IntegerField()
    daily_fee = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self) -> str:
        return f"{self.title}, Author: {self.author}"
