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


class HotelFlowStepDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for individual flow steps, combining template data with
    hotel-specific customizations.
    """
    customized_message_template = serializers.SerializerMethodField()
    customized_options = serializers.SerializerMethodField()

    class Meta:
        model = FlowStepTemplate
        fields = (
            'id',
            'step_name',
            'message_template',
            'message_type',
            'options',
            'customized_message_template',
            'customized_options',
        )

    def get_customized_message_template(self, obj):
        """
        Gets the customized message from the 'customizations' attribute
        attached by the parent serializer.
        """
        return getattr(obj, 'customizations', {}).get('message_template', '')

    def get_customized_options(self, obj):
        """
        Gets the customized options from the 'customizations' attribute
        attached by the parent serializer.
        """
        return getattr(obj, 'customizations', {}).get('options')


class HotelFlowDetailSerializer(serializers.ModelSerializer):
    """
    Provides a detailed view of a FlowTemplate, including its steps with
    any hotel-specific customizations applied.
    """
    steps = serializers.SerializerMethodField()

    class Meta:
        model = FlowTemplate
        fields = (
            'id',
            'name',
            'description',
            'category',
            'steps',
        )

    def get_steps(self, instance):
        hotel = self.context.get('hotel')
        if not hotel:
            return []

        config = HotelFlowConfiguration.objects.filter(hotel=hotel, flow_template=instance).first()
        customizations = config.customization_data.get('step_customizations', {}) if config and config.customization_data else {}

        steps = instance.flowsteptemplate_set.all().order_by('id')

        # Attach customization data to each step object for the child serializer
        for step in steps:
            step.customizations = customizations.get(str(step.id), {})

        serializer = HotelFlowStepDetailSerializer(steps, many=True, context=self.context)
        return serializer.data


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