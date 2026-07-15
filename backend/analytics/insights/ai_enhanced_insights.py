from django.conf import settings
import google.generativeai as genai
import json
import logging
from .insight_validator import InsightValidator

logger = logging.getLogger(__name__)


class AIEnhancedInsights:
    """
    AI-enhanced insights using Gemini API with strict validation
    """
    
    def __init__(self, patient):
        self.patient = patient
        self.validator = InsightValidator()
        
        # Configure Gemini
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
    
    def generate_insights(self, metrics, rule_based_insights):
        """
        Generate AI-enhanced insights with validation
        Always includes rule-based fallback
        """
        try:
            # Build structured prompt
            prompt = self._build_prompt(metrics, rule_based_insights)
            
            # Call Gemini with low temperature for consistency
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0,  # Most deterministic
                    top_p=0.1,
                    max_output_tokens=2048,
                )
            )
            
            # Parse response
            ai_insights = self._parse_response(response.text)
            
            # Validate each insight
            validated_insights = []
            for insight in ai_insights:
                is_valid, validation_result = self.validator.validate_insight(
                    insight,
                    metrics
                )
                
                if is_valid:
                    insight['validation_passed'] = True
                    insight['validation_score'] = validation_result['score']
                    insight['source'] = 'ai_enhanced'
                    insight['confidence'] = 0.85  # Lower than rule-based
                    validated_insights.append(insight)
                else:
                    logger.warning(
                        f"AI insight failed validation: {validation_result['reason']}"
                    )
            
            # If all AI insights failed validation, use rule-based
            if not validated_insights:
                logger.warning("All AI insights failed validation, using rule-based fallback")
                return {
                    'insights': rule_based_insights,
                    'ai_enhanced': False,
                    'fallback_used': True,
                    'fallback_reason': 'validation_failed'
                }
            
            return {
                'insights': validated_insights,
                'ai_enhanced': True,
                'fallback_available': True,
                'rule_based_backup': rule_based_insights
            }
        
        except Exception as e:
            logger.error(f"Error generating AI insights: {str(e)}")
            # ALWAYS fallback to rule-based on error
            return {
                'insights': rule_based_insights,
                'ai_enhanced': False,
                'fallback_used': True,
                'fallback_reason': f'error: {str(e)}'
            }
    
    def _build_prompt(self, metrics, rule_based_insights):
        """Build structured prompt for Gemini"""
        prompt = f"""You are a healthcare analytics assistant analyzing patient health data.

Patient: {self.patient.user.get_full_name()}
Analysis Period: Recent health metrics

HEALTH METRICS:
{json.dumps(metrics, indent=2)}

RULE-BASED INSIGHTS (for reference):
{json.dumps([{
    'text': i['text'],
    'category': i['category'],
    'severity': i['severity']
} for i in rule_based_insights], indent=2)}

TASK:
Generate 3-5 enhanced insights that:
1. Add context beyond statistical observations
2. Identify patterns or correlations not obvious from individual metrics
3. Provide actionable, patient-friendly recommendations
4. Use specific numbers from the metrics (don't invent data)
5. Maintain medical accuracy and safety

STRICT RULES:
- Use ONLY the numbers provided in HEALTH METRICS
- Do NOT make up values or statistics
- Do NOT make definitive medical diagnoses
- Keep insights practical and actionable
- Each insight must reference specific metrics

OUTPUT FORMAT (JSON array):
[
  {{
    "category": "vitals|medications|alerts|overall|correlation",
    "subcategory": "specific_area",
    "severity": "positive|normal|moderate|high",
    "text": "Clear, patient-friendly insight statement",
    "recommendation": "Specific, actionable recommendation",
    "data_points": {{"metric_name": value}},
    "reasoning": "Brief explanation of the insight"
  }}
]

Generate insights now:"""
        
        return prompt
    
    def _parse_response(self, response_text):
        """Parse Gemini response into structured insights"""
        try:
            # Remove markdown code blocks if present
            cleaned_text = response_text.strip()
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.startswith('```'):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]
            
            cleaned_text = cleaned_text.strip()
            
            # Parse JSON
            insights = json.loads(cleaned_text)
            
            if not isinstance(insights, list):
                logger.error("AI response is not a list")
                return []
            
            return insights
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {str(e)}")
            logger.error(f"Response text: {response_text}")
            return []
        except Exception as e:
            logger.error(f"Error parsing AI response: {str(e)}")
            return []
