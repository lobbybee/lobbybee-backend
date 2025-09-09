from rest_framework import serializers
from .models import FlowStep, ScheduledMessageTemplate, FlowTemplate, FlowStepTemplate, FlowAction, WhatsappMedia


class WhatsappMediaSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = WhatsappMedia
        fields = ['id', 'mime_type', 'file_size', 'file', 'file_url', 'created_at']
        read_only_fields = ['id', 'mime_type', 'file_size', 'file_url', 'created_at']
        extra_kwargs = {
            'file': {'write_only': True, 'required': True}
        }

    def get_file_url(self, obj):
        if obj.file:
            return obj.file.url
        return None

    def create(self, validated_data):
        uploaded_file = validated_data.get('file')
        validated_data['mime_type'] = uploaded_file.content_type
        validated_data['file_size'] = uploaded_file.size
        return super().create(validated_data)


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