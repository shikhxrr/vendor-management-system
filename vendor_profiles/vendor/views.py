from django.shortcuts import render
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.views import APIView
from .models import Vendor, PurchaseOrder, HistoricalPerformance
from .serializers import VendorSerializer, PurchaseOrderSerializer, HistoricalPerformanceSerializer


class VendorList(APIView):
    def get(self, request):
        vendor_list = Vendor.objects.all()
        serializer = VendorSerializer(vendor_list, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = VendorSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Vendor created successfully", "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response({"message": "Error creating vendor", "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)



class VendorDetails(APIView):
    def get(self, request, id):
        try:
            vendor_details = Vendor.objects.get(id=id)
            serializer = VendorSerializer(vendor_details)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

    def put(self, request, id):
        try:
            vendor_details = Vendor.objects.get(id=id)
            serializer = VendorSerializer(vendor_details, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, id):
        try:
            vendor_details = Vendor.objects.get(id=id)
            vendor_details.delete()
            return Response({"status": status.HTTP_200_OK, "message": "Vendor removed."})
        except:
            return Response({"status": status.HTTP_404_NOT_FOUND, "message": "Vendor doesn't exist."})


class PurchaseOrderList(APIView):
    def post(self, request):
        serializer = PurchaseOrderSerializer(data=request.data, many=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        purchase_order_list = PurchaseOrder.objects.all()
        serializer = PurchaseOrderSerializer(purchase_order_list, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    
class PurchaseOrderDetails(APIView):
    def get(self, request, id):
        try:
            po_details = PurchaseOrder.objects.get(pk=id)
            serializer = PurchaseOrderSerializer(po_details)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

    def put(self, request, id):
        try:
            po_details = PurchaseOrder.objects.get(id=id)
            serializer = PurchaseOrderSerializer(po_details, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, id):
        try:
            po_details = PurchaseOrder.objects.get(pk=id)
            po_details.delete()
            return Response(status=status.HTTP_200_OK)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
def vendor_performance_metrics(request, id):
    vendor_exists = Vendor.objects.filter(id=id).exists()
    if vendor_exists:
        vendor_performance = HistoricalPerformance.objects.get(id=id)
        serializer = HistoricalPerformanceSerializer(vendor_performance)
        return Response(serializer.data, status=status.HTTP_200_OK)
    else:
        return Response(status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
def acknowledge_purchase_order(request, po_id):
    try:
        purchase_order = PurchaseOrder.objects.get(pk=po_id)
    except PurchaseOrder.DoesNotExist:
        return Response({"status": 404, "message": "Purchase Order not found."}, status=status.HTTP_404_NOT_FOUND)

    if purchase_order.acknowledgement_date:
        return Response({"status": 400, "message": "Purchase Order has already been acknowledged."}, status=status.HTTP_400_BAD_REQUEST)

    purchase_order.acknowledgement_date = timezone.now()
    purchase_order.save()

    vendor = purchase_order.vendor
    response_times = PurchaseOrder.objects.filter(vendor=vendor, acknowledgement_date__isnull=False).values_list('acknowledgement_date', 'issue_date')
    average_response_time = sum([(ack_date - issue_date).total_seconds() for ack_date, issue_date in response_times]) / len(response_times) if len(response_times) > 0 else None

    vendor_performance, _ = HistoricalPerformance.objects.get_or_create(vendor=vendor)
    vendor_performance.average_response_time = average_response_time
    vendor_performance.save()

    return Response({"status": 200, "message": "Purchase Order acknowledged successfully."}, status=status.HTTP_200_OK)


@receiver(post_save, sender=PurchaseOrder)
def update_performance_metrics(sender, instance, created, **kwargs):
    if not created and instance.status == 'completed':
        # Update On-Time Delivery Rate
        vendor = instance.vendor
        completed_pos = PurchaseOrder.objects.filter(vendor=vendor, status='completed')
        on_time_pos = completed_pos.filter(delivery_date__lte=instance.delivery_date)
        on_time_delivery_rate = on_time_pos.count() / completed_pos.count() if completed_pos.count() > 0 else 0

        # Update Quality Rating Average
        quality_ratings = completed_pos.exclude(quality_rating=None).values_list('quality_rating', flat=True)
        quality_rating_avg = sum(quality_ratings) / len(quality_ratings) if len(quality_ratings) > 0 else None

        vendor_performance, _ = HistoricalPerformance.objects.get_or_create(vendor=vendor)
        vendor_performance.on_time_delivery_rate = on_time_delivery_rate
        vendor_performance.quality_rating_avg = quality_rating_avg
        vendor_performance.save()

@receiver(post_save, sender=PurchaseOrder)
def update_acknowledgment(sender, instance, created, **kwargs):
    if created:
        return
    if instance.acknowledgement_date:
        # Update Average Response Time
        vendor = instance.vendor
        response_times = PurchaseOrder.objects.filter(vendor=vendor, acknowledgement_date__isnull=False).values_list('acknowledgement_date', 'issue_date')
        average_response_time = sum([(ack_date - issue_date).total_seconds() for ack_date, issue_date in response_times]) / len(response_times) if len(response_times) > 0 else None

        vendor_performance, _ = HistoricalPerformance.objects.get_or_create(vendor=vendor)
        vendor_performance.average_response_time = average_response_time
        vendor_performance.save()

@receiver(pre_delete, sender=PurchaseOrder)
def update_fulfillment_rate(sender, instance, **kwargs):
    if instance.status == 'completed':
        vendor = instance.vendor
        fulfilled_pos = PurchaseOrder.objects.filter(vendor=vendor, status='completed', quality_rating__isnull=False)
        fulfillment_rate = fulfilled_pos.count() / PurchaseOrder.objects.filter(vendor=vendor).count() if PurchaseOrder.objects.filter(vendor=vendor).count() > 0 else 0

        vendor_performance, _ = HistoricalPerformance.objects.get_or_create(vendor=vendor)
        vendor_performance.fulfillment_rate = fulfillment_rate
        vendor_performance.save()