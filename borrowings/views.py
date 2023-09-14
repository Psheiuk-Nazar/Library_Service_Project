import os
from datetime import datetime

import requests
import stripe
from django.db import transaction
from django.http import request, HttpResponse
from django.http.request import HttpRequest
from django.template.loader import render_to_string
from rest_framework import mixins, status
from rest_framework.decorators import api_view
from django.shortcuts import get_object_or_404, redirect
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from books.models import Books
from borrowings.models import Borrowing, Payment
from borrowings.serializers import (
    BorrowingListSerializer,
    BorrowingCreateSerializer,
    BorrowingSerializer,
    BorrowingDetailSerializer,
    PaymentsListSerializer,
    PaymentsDetailSerializer,
    PaymentsSerializer,
)
from .send_messege_to_telegram import send_to_telegram


class BorrowingListViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    GenericViewSet,
):
    queryset = Borrowing.objects.all()
    permission_classes = (IsAuthenticated,)

    @staticmethod
    def _params_to_ints(qs):
        """Converts a list of string IDs to a list of integers"""
        return [int(str_id) for str_id in qs.split(",")]

    def get_queryset(self):
        is_active = self.request.query_params.get("is_active")
        if self.request.user.is_staff:
            queryset = self.queryset
            user = self.request.query_params.get("user_id")
            if user:
                actors_ids = self._params_to_ints(user)
                queryset = queryset.filter(user__id__in=actors_ids)
        else:
            queryset = Borrowing.objects.filter(user=self.request.user)

        if is_active:
            return queryset.filter(is_active=is_active)
        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return BorrowingListSerializer
        if self.action == "retrieve":
            return BorrowingDetailSerializer
        if self.action == "create":
            return BorrowingCreateSerializer

        return BorrowingSerializer

    def perform_create(self, serializer):
        with transaction.atomic():
            data = self.request.data
            book = Books.objects.get(id=int(data["book"]))
            book.inventory -= 1
            book.save()
            serializer.save(user=self.request.user)
            create_checkout_session(serializer.data["id"])
            send_to_telegram(
                f"Borrowing №: {serializer.data['id']} Title: {book.title} Borrowing at:{datetime.now()}. Expected return date: {data['expected_return_date']}"
            )


@api_view(["POST", "GET"])
def return_borrowing(request: Request, pk) -> Response:
    with transaction.atomic():
        borrowing = get_object_or_404(Borrowing, id=pk)
        if borrowing.is_active:
            borrowing.book.inventory += 1
            borrowing.actual_return_date = datetime.now()
            borrowing.is_active = False
            borrowing.save()
            serializer = BorrowingDetailSerializer(borrowing)
            send_to_telegram(
                f"Borrowing №: {borrowing.id}, Title: {borrowing.book} was returned at: {borrowing.actual_return_date}"
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(
            {"detail": "The book has already been returned."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class PaymentsViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    GenericViewSet,
):
    queryset = Payment.objects.all()

    def get_queryset(self):
        queryset = self.queryset
        if self.request.user.is_staff is False:
            queryset = self.queryset.filter(borrowing__user=self.request.user)
        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return PaymentsListSerializer
        if self.action == "retrieve":
            return PaymentsDetailSerializer
        return PaymentsSerializer


def calculate_price(pk):
    borrowing = Borrowing.objects.get(id=pk)
    price = borrowing.book.daily_fee
    borrowing_date = borrowing.borrow_date
    expected_return_date = borrowing.expected_return_date
    delta = expected_return_date - borrowing_date
    number_of_days = delta.days
    return number_of_days * price


def create_checkout_session(pk):
    borrowing = Borrowing.objects.get(id=pk)
    price = calculate_price(pk) * 100
    LOCAL_DOMAIN = "http://127.0.0.1:8000/"
    try:
        stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount_decimal": price,
                        "product_data": {
                            "name": borrowing.book.title,
                            "description": f"Author: {borrowing.book.author} ",
                        },
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=LOCAL_DOMAIN
            + "api/borrowings/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=LOCAL_DOMAIN + "api/borrowings/canceled/",
        )
        Payment.objects.create(
            borrowing=borrowing,
            session_url=checkout_session.url,
            session_id=checkout_session.stripe_id,
            money_to_pay=checkout_session.amount_total,
        )
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"])
def order_success(request):
    session = stripe.checkout.Session.retrieve(request.query_params["session_id"])
    payment = Payment.objects.get(session_id=session.stripe_id)
    payment.status = "PAID"
    payment.save()
    return redirect("http://127.0.0.1:8000/api/borrowings/borrowing/")

@api_view(["GET"])
def order_canceled(request):
    cancel_message = "Payment can be paid a bit later, but the session is available for only 24 hours."
    return HttpResponse(cancel_message)