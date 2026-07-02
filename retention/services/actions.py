from retention.models import Action, Conversation


class ActionGenerationService:
    """Generate HR actions based on identified needs"""
    
    ACTION_TEMPLATES = {
        'salary': {
            'description': 'Proposer une révision salariale de 10-15%',
            'priority': 'high'
        },
        'growth': {
            'description': 'Identifier opportunités de mobilité interne ou promotion',
            'priority': 'high'
        },
        'workload': {
            'description': 'Réévaluer la charge de travail et redistribuer les tâches',
            'priority': 'medium'
        },
        'recognition': {
            'description': 'Organiser un entretien de reconnaissance et valorisation',
            'priority': 'medium'
        },
        'flexibility': {
            'description': 'Proposer aménagement horaires ou télétravail partiel',
            'priority': 'medium'
        },
        'general': {
            'description': 'Organiser un entretien approfondi avec le manager',
            'priority': 'low'
        }
    }
    
    @staticmethod
    def generate_action(conversation: Conversation) -> Action:
        """Generate action based on conversation outcome"""
        
        need = conversation.identified_need or 'general'
        template = ActionGenerationService.ACTION_TEMPLATES.get(need)
        
        action = Action.objects.create(
            conversation=conversation,
            employee=conversation.employee,
            description=f"{template['description']} pour {conversation.employee.name}",
            priority=template['priority'],
            status='pending'
        )
        
        return action