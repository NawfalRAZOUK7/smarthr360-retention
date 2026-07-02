from retention.models import Employee, Signal

class RiskDetectionService:
    """Simple rule-based risk detection"""
    
    @staticmethod
    def detect_risk(employee: Employee) -> Signal | None:
        """
        Detect if employee is at risk of leaving
        Returns Signal if risk detected, None otherwise
        """
        
        # Rule 1: Low engagement score
        if employee.engagement_score < 60:
            signal = Signal.objects.create(
                employee=employee,
                signal_type='low_engagement',
                intensity=100 - employee.engagement_score,
                resolved=False
            )
            return signal
        
        # Rule 2: Poor performance (could indicate disengagement)
        if employee.performance_score < 50:
            signal = Signal.objects.create(
                employee=employee,
                signal_type='poor_performance',
                intensity=100 - employee.performance_score,
                resolved=False
            )
            return signal

        # Rule 3: High absence rate (spec: absenteeism is a departure signal)
        if employee.absence_days_90d > 8:
            signal = Signal.objects.create(
                employee=employee,
                signal_type='high_absence',
                intensity=min(100, employee.absence_days_90d * 10),
                resolved=False
            )
            return signal

        return None
    
    @staticmethod
    def check_all_employees():
        """Batch check all employees for risks"""
        at_risk_employees = []
        
        for employee in Employee.objects.all():
            signal = RiskDetectionService.detect_risk(employee)
            if signal:
                at_risk_employees.append({
                    'employee': employee,
                    'signal': signal
                })
        
        return at_risk_employees