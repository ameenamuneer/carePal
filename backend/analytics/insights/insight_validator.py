import logging

logger = logging.getLogger(__name__)


class InsightValidator:
    """
    Validate AI-generated insights against source data
    Prevents hallucinations and ensures accuracy
    """
    
    def validate_insight(self, insight, source_metrics):
        """
        Validate a single insight
        Returns (is_valid, validation_result)
        """
        checks = {
            'structure': self._check_structure(insight),
            'data_accuracy': self._check_data_accuracy(insight, source_metrics),
            'severity_appropriate': self._check_severity(insight),
            'no_hallucinations': self._check_hallucinations(insight, source_metrics),
            'safety': self._check_safety(insight),
        }
        
        # Calculate validation score
        passed_checks = sum(1 for check in checks.values() if check['passed'])
        total_checks = len(checks)
        validation_score = passed_checks / total_checks
        
        # Must pass all critical checks
        critical_checks = ['structure', 'data_accuracy', 'safety']
        critical_passed = all(checks[c]['passed'] for c in critical_checks)
        
        is_valid = critical_passed and validation_score >= 0.8
        
        return is_valid, {
            'score': validation_score,
            'checks': checks,
            'critical_passed': critical_passed,
            'reason': self._get_failure_reason(checks) if not is_valid else 'validated'
        }
    
    def _check_structure(self, insight):
        """Check if insight has required structure"""
        required_fields = ['category', 'text', 'recommendation', 'severity']
        
        missing_fields = [f for f in required_fields if f not in insight]
        
        return {
            'passed': len(missing_fields) == 0,
            'details': f"Missing fields: {missing_fields}" if missing_fields else "All required fields present"
        }
    
    def _check_data_accuracy(self, insight, source_metrics):
        """Verify numerical values match source data"""
        data_points = insight.get('data_points', {})
        
        if not data_points:
            return {
                'passed': True,
                'details': "No data points to verify"
            }
        
        # Check each data point against metrics
        mismatches = []
        
        for key, value in data_points.items():
            # Search for this value in source metrics
            found = self._find_value_in_metrics(key, value, source_metrics)
            
            if not found:
                mismatches.append(f"{key}={value}")
        
        return {
            'passed': len(mismatches) == 0,
            'details': f"Data mismatches: {mismatches}" if mismatches else "All data points verified"
        }
    
    def _check_severity(self, insight):
        """Check if severity level is appropriate"""
        valid_severities = ['positive', 'normal', 'moderate', 'high']
        severity = insight.get('severity', '').lower()
        
        return {
            'passed': severity in valid_severities,
            'details': f"Severity '{severity}' is {'valid' if severity in valid_severities else 'invalid'}"
        }
    
    def _check_hallucinations(self, insight, source_metrics):
        """Check for invented data or facts"""
        text = insight.get('text', '').lower()
        
        # Check for specific numbers mentioned in text
        import re
        numbers_in_text = re.findall(r'\d+\.?\d*', text)
        
        # If numbers are mentioned, they should be in data_points or metrics
        if numbers_in_text:
            data_points = insight.get('data_points', {})
            
            # Convert all metric values to strings for comparison
            all_values = self._extract_all_values(source_metrics)
            all_values.update(str(v) for v in data_points.values())
            
            unverified_numbers = [
                num for num in numbers_in_text
                if num not in all_values and not self._is_reasonable_derived_value(num, all_values)
            ]
            
            if unverified_numbers:
                return {
                    'passed': False,
                    'details': f"Unverified numbers in text: {unverified_numbers}"
                }
        
        return {
            'passed': True,
            'details': "No hallucinations detected"
        }
    
    def _check_safety(self, insight):
        """Check for unsafe recommendations"""
        recommendation = insight.get('recommendation', '').lower()
        text = insight.get('text', '').lower()
        
        # Forbidden phrases
        forbidden = [
            'stop taking medication',
            'discontinue medication',
            'ignore doctor',
            'no need to see doctor',
            'definitely diagnosed',
            'certainly have',
            'guaranteed to',
        ]
        
        for phrase in forbidden:
            if phrase in recommendation or phrase in text:
                return {
                    'passed': False,
                    'details': f"Unsafe phrase detected: '{phrase}'"
                }
        
        return {
            'passed': True,
            'details': "No safety concerns"
        }
    
    def _find_value_in_metrics(self, key, value, metrics, tolerance=0.1):
        """Recursively search for value in nested metrics"""
        if isinstance(metrics, dict):
            for k, v in metrics.items():
                if k == key:
                    # Check if values match (with tolerance for floats)
                    if isinstance(value, (int, float)) and isinstance(v, (int, float)):
                        if abs(value - v) <= tolerance:
                            return True
                    elif str(value).lower() == str(v).lower():
                        return True
                
                # Recursively search nested dicts
                if isinstance(v, dict):
                    if self._find_value_in_metrics(key, value, v, tolerance):
                        return True
        
        return False
    
    def _extract_all_values(self, obj, values=None):
        """Extract all numerical values from nested structure"""
        if values is None:
            values = set()
        
        if isinstance(obj, dict):
            for v in obj.values():
                self._extract_all_values(v, values)
        elif isinstance(obj, list):
            for item in obj:
                self._extract_all_values(item, values)
        elif isinstance(obj, (int, float)):
            values.add(str(obj))
            values.add(str(int(obj)))  # Also add integer version
        
        return values
    
    def _is_reasonable_derived_value(self, num_str, all_values):
        """Check if number could be reasonably derived from metrics"""
        try:
            num = float(num_str)
            
            # Check if it's a percentage that could be calculated
            if 0 <= num <= 100:
                return True
            
            # Check if it's close to any known value
            for val_str in all_values:
                try:
                    val = float(val_str)
                    # Within 10% tolerance
                    if abs(num - val) / val < 0.1:
                        return True
                except:
                    continue
        except:
            pass
        
        return False
    
    def _get_failure_reason(self, checks):
        """Get human-readable failure reason"""
        failed_checks = [name for name, result in checks.items() if not result['passed']]
        
        if not failed_checks:
            return "Unknown validation failure"
        
        return f"Failed checks: {', '.join(failed_checks)}"
