from rest_framework import serializers
from .models import FlowStep, ScheduledMessageTemplate, FlowTemplate, FlowStepTemplate, FlowAction, HotelFlowConfiguration


class FlowTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowTemplate
        fields = '__all__'
        read_only_fields = ('id',)


class FlowActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowAction
        fields = '__all__'
        read_only_fields = ('id',)


class FlowStepTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowStepTemplate
        fields = '__all__'
        read_only_fields = ('id',)


class FlowStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowStep
        fields = '__all__'
        read_only_fields = ('id',)

    def validate_step_id(self, value):
        """Ensure step_id is unique"""
        if FlowStep.objects.filter(step_id=value).exists():
            raise serializers.ValidationError("A flow step with this step_id already exists.")
        return value

    def validate_options(self, value):
        """Validate that options is a dictionary"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Options must be a dictionary.")
        return value


class FlowStepUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating FlowStep (without step_id validation)"""
    class Meta:
        model = FlowStep
        fields = '__all__'
        read_only_fields = ('id', 'step_id')


class HotelFlowConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelFlowConfiguration
        fields = '__all__'
        read_only_fields = ('id',)


class ScheduledMessageTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduledMessageTemplate
        fields = '__all__'
        read_only_fields = ('id',)

    def validate_trigger_condition(self, value):
        """Validate that trigger_condition is a dictionary"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Trigger condition must be a dictionary.")
        return value