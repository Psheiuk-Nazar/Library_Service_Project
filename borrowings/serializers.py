from rest_framework import serializers

from borrowings.models import Borrowing
from books.serializers import BooksSerializer

class BorrowingListSerializer(serializers.ModelSerializer):
    book = BooksSerializer(many=False, read_only=True)

    class Meta:
        model = Borrowing
        fields = ("id", "borrow_date", "expected_return_date", "actual_return_date", "book", "user" )

