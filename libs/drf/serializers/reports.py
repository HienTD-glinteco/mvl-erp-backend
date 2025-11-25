from rest_framework import serializers


class BaseTypeNameSerializer(serializers.Serializer):
    type = serializers.CharField()
    name = serializers.CharField()


class BaseStatisticsSerializer(BaseTypeNameSerializer):
    statistics = serializers.ListField(child=serializers.FloatField())
