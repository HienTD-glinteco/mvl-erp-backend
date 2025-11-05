from rest_framework import serializers


class BaseStatisticsSerializer(serializers.Serializer):
    type = serializers.CharField()
    name = serializers.CharField()
    statistics = serializers.ListField(child=serializers.IntegerField())
