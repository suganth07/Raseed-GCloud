"""
Enhanced Question Classification System for Economic Bot

This module provides intelligent classification of user financial queries
to understand intent and provide more targeted responses.
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from ..utils.logging import LoggerMixin


class QuestionIntent(Enum):
    """Enumeration of possible user intents for financial queries."""
    
    # Basic Information Queries
    SPENDING_SUMMARY = "spending_summary"           # "How much did I spend?"
    BALANCE_INQUIRY = "balance_inquiry"             # "What's my balance?"
    TRANSACTION_DETAILS = "transaction_details"     # "Show me my last purchase"
    
    # Analysis & Insights
    SPENDING_ANALYSIS = "spending_analysis"         # "Analyze my spending pattern"
    CATEGORY_ANALYSIS = "category_analysis"         # "How much on food?"
    TREND_ANALYSIS = "trend_analysis"               # "Compare this month vs last"
    MERCHANT_ANALYSIS = "merchant_analysis"         # "How much at Starbucks?"
    
    # Budgeting & Planning
    BUDGET_INQUIRY = "budget_inquiry"               # "Am I over budget?"
    BUDGET_ADVICE = "budget_advice"                 # "Help me create a budget"
    SAVINGS_ADVICE = "savings_advice"               # "How can I save money?"
    EXPENSE_OPTIMIZATION = "expense_optimization"   # "Reduce my spending"
    
    # Predictions & Forecasting
    SPENDING_PREDICTION = "spending_prediction"     # "Will I exceed budget?"
    TREND_PREDICTION = "trend_prediction"           # "What will I spend next month?"
    
    # Recommendations
    PRODUCT_RECOMMENDATION = "product_recommendation" # "Should I buy this?"
    MERCHANT_RECOMMENDATION = "merchant_recommendation" # "Where should I shop?"
    
    # Alerts & Warnings
    OVERSPENDING_ALERT = "overspending_alert"       # "Am I spending too much?"
    UNUSUAL_ACTIVITY = "unusual_activity"           # "Any weird transactions?"
    
    # Comparative Queries
    COMPARATIVE_ANALYSIS = "comparative_analysis"   # "This month vs last month"
    BENCHMARK_COMPARISON = "benchmark_comparison"   # "Am I spending like others?"
    
    # Goal Tracking
    GOAL_PROGRESS = "goal_progress"                 # "How's my savings goal?"
    MILESTONE_TRACKING = "milestone_tracking"       # "When will I reach my goal?"
    
    # Context-Dependent
    FOLLOW_UP_QUESTION = "follow_up_question"       # "What about that?", "And?"
    CLARIFICATION_REQUEST = "clarification_request" # "Tell me more", "Explain"
    
    # General
    GREETING = "greeting"                           # "Hello", "Hi"
    HELP_REQUEST = "help_request"                   # "Help me", "What can you do?"
    GENERAL_FINANCIAL = "general_financial"         # General financial advice
    UNKNOWN = "unknown"                             # Unclassified queries


@dataclass
class ClassificationResult:
    """Result of question classification with confidence and context."""
    
    intent: QuestionIntent
    confidence: float
    entities: Dict[str, Any]  # Extracted entities (amounts, dates, categories, etc.)
    context_type: str         # "follow_up", "new_topic", "continuation"
    requires_data: List[str]  # What data is needed: ["spending_data", "budget_data", etc.]
    time_scope: Optional[str] # "today", "this_month", "last_month", "this_year"
    category_filter: Optional[str]  # Specific category if mentioned
    merchant_filter: Optional[str]  # Specific merchant if mentioned
    amount_filter: Optional[Dict[str, float]]  # Amount ranges if mentioned


class EnhancedQuestionClassifier(LoggerMixin):
    """
    Advanced question classifier that understands financial query intents.
    
    Features:
    - Intent classification with confidence scoring
    - Entity extraction (amounts, dates, categories)
    - Context awareness (follow-up questions)
    - Time scope detection
    - Category and merchant filtering
    """
    
    def __init__(self):
        self.logger.info("🔍 Initializing Enhanced Question Classifier")
        
        # Intent pattern mappings
        self.intent_patterns = self._build_intent_patterns()
        
        # Entity extraction patterns
        self.entity_patterns = self._build_entity_patterns()
        
        # Context keywords
        self.context_keywords = self._build_context_keywords()
        
        # Time scope patterns
        self.time_patterns = self._build_time_patterns()
        
        self.logger.info("✅ Question Classifier initialized with enhanced patterns")
    
    async def classify_question(
        self, 
        question: str, 
        conversation_history: Optional[List[Dict]] = None,
        user_context: Optional[Dict] = None
    ) -> ClassificationResult:
        """
        Classify a user question with enhanced intent recognition.
        
        Args:
            question: User's question/message
            conversation_history: Previous conversation messages
            user_context: User's financial context and preferences
            
        Returns:
            ClassificationResult with intent, confidence, and extracted entities
        """
        try:
            self.logger.info(f"🔍 Classifying question: '{question[:50]}...'")
            
            # Normalize question
            normalized_question = self._normalize_question(question)
            
            # Extract entities first
            entities = self._extract_entities(normalized_question)
            
            # Determine context type
            context_type = self._determine_context_type(question, conversation_history)
            
            # Classify intent
            intent, confidence = self._classify_intent(normalized_question, entities, context_type)
            
            # Extract time scope
            time_scope = self._extract_time_scope(normalized_question)
            
            # Extract filters
            category_filter = self._extract_category_filter(normalized_question)
            merchant_filter = self._extract_merchant_filter(normalized_question)
            amount_filter = self._extract_amount_filter(normalized_question)
            
            # Determine required data
            requires_data = self._determine_required_data(intent, entities)
            
            result = ClassificationResult(
                intent=intent,
                confidence=confidence,
                entities=entities,
                context_type=context_type,
                requires_data=requires_data,
                time_scope=time_scope,
                category_filter=category_filter,
                merchant_filter=merchant_filter,
                amount_filter=amount_filter
            )
            
            self.logger.info(f"✅ Classified as: {intent.value} (confidence: {confidence:.2f})")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Error classifying question: {e}")
            # Return safe fallback
            return ClassificationResult(
                intent=QuestionIntent.UNKNOWN,
                confidence=0.0,
                entities={},
                context_type="new_topic",
                requires_data=["spending_data"],
                time_scope=None,
                category_filter=None,
                merchant_filter=None,
                amount_filter=None
            )
    
    def _build_intent_patterns(self) -> Dict[QuestionIntent, List[str]]:
        """Build regex patterns for each intent type."""
        return {
            QuestionIntent.SPENDING_SUMMARY: [
                r"how much.*spend|spending.*total|total.*spent|spent.*much",
                r"what.*spent|spending.*amount|expenditure",
                r"money.*spent|cash.*used|expenses.*total"
            ],
            
            QuestionIntent.SPENDING_ANALYSIS: [
                r"analyze.*spending|spending.*pattern|spending.*habit",
                r"breakdown.*spending|spending.*breakdown|spending.*analysis",
                r"where.*money.*go|spending.*insight|expense.*analysis"
            ],
            
            QuestionIntent.CATEGORY_ANALYSIS: [
                r"spent.*on.*food|food.*expense|grocery.*spending",
                r"spent.*on.*transport|transport.*cost|fuel.*expense",
                r"entertainment.*spending|shopping.*expense|dining.*cost",
                r"how much.*category|category.*spending|spent.*category"
            ],
            
            QuestionIntent.BUDGET_INQUIRY: [
                r"budget.*status|over.*budget|budget.*limit",
                r"remaining.*budget|budget.*left|within.*budget",
                r"budget.*check|budget.*progress"
            ],
            
            QuestionIntent.BUDGET_ADVICE: [
                r"create.*budget|budget.*help|budget.*advice",
                r"budget.*plan|budget.*strategy|budgeting.*tips",
                r"help.*budget|budget.*guidance"
            ],
            
            QuestionIntent.SAVINGS_ADVICE: [
                r"save.*money|savings.*tips|how.*save",
                r"reduce.*spending|cut.*expenses|save.*more",
                r"savings.*advice|money.*saving|frugal.*tips"
            ],
            
            QuestionIntent.COMPARATIVE_ANALYSIS: [
                r"compare.*month|this.*vs.*last|month.*comparison",
                r"last.*month.*vs|compared.*to.*last|difference.*between",
                r"this.*year.*vs|year.*comparison|compared.*to.*previous"
            ],
            
            QuestionIntent.TREND_ANALYSIS: [
                r"spending.*trend|trend.*analysis|spending.*over.*time",
                r"pattern.*spending|spending.*pattern|expense.*trend",
                r"spending.*increase|spending.*decrease|trend.*spending"
            ],
            
            QuestionIntent.OVERSPENDING_ALERT: [
                r"spending.*too.*much|overspending|exceed.*budget",
                r"spending.*high|expensive.*month|costly.*month",
                r"money.*problem|financial.*issue|spending.*concern"
            ],
            
            QuestionIntent.FOLLOW_UP_QUESTION: [
                r"what.*about|and.*what|also.*show|tell.*more",
                r"^and|^also|^what.*that|^explain",
                r"more.*detail|elaborate|continue|go.*on"
            ],
            
            QuestionIntent.GREETING: [
                r"^hi|^hello|^hey|good.*morning|good.*afternoon|good.*evening",
                r"how.*are.*you|nice.*to.*meet|pleased.*to.*meet"
            ],
            
            QuestionIntent.HELP_REQUEST: [
                r"help.*me|what.*can.*you|how.*can.*you|assistance",
                r"guide.*me|show.*me.*how|teach.*me|explain.*how",
                r"what.*do.*you.*do|capabilities|features"
            ]
        }
    
    def _build_entity_patterns(self) -> Dict[str, str]:
        """Build patterns for extracting entities from questions."""
        return {
            # Amount patterns
            "amount": r"₹?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)",
            "amount_range": r"between\s+₹?\s*(\d+)\s+and\s+₹?\s*(\d+)",
            
            # Date patterns
            "date": r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            "month_year": r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})",
            
            # Category patterns
            "category": r"(food|grocery|transport|fuel|entertainment|shopping|medical|education|utilities|rent)",
            
            # Merchant patterns
            "merchant": r"at\s+([a-zA-Z0-9\s]+)|from\s+([a-zA-Z0-9\s]+)",
            
            # Time scope patterns
            "time_scope": r"(today|yesterday|this\s+week|last\s+week|this\s+month|last\s+month|this\s+year|last\s+year)"
        }
    
    def _build_context_keywords(self) -> Dict[str, List[str]]:
        """Build keywords that indicate context type."""
        return {
            "follow_up": ["and", "also", "what about", "tell me more", "elaborate", "continue"],
            "comparison": ["vs", "versus", "compared to", "difference", "than", "better"],
            "time_reference": ["last", "previous", "this", "current", "next", "future"],
            "clarification": ["explain", "clarify", "what do you mean", "unclear", "confused"]
        }
    
    def _build_time_patterns(self) -> Dict[str, str]:
        """Build patterns for time scope detection."""
        return {
            "today": r"\btoday|\bthis\s+day",
            "yesterday": r"\byesterday|\blast\s+day",
            "this_week": r"\bthis\s+week|\bcurrent\s+week",
            "last_week": r"\blast\s+week|\bprevious\s+week",
            "this_month": r"\bthis\s+month|\bcurrent\s+month",
            "last_month": r"\blast\s+month|\bprevious\s+month",
            "this_year": r"\bthis\s+year|\bcurrent\s+year",
            "last_year": r"\blast\s+year|\bprevious\s+year"
        }
    
    def _normalize_question(self, question: str) -> str:
        """Normalize question for better pattern matching."""
        # Convert to lowercase
        normalized = question.lower().strip()
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove punctuation at the end
        normalized = re.sub(r'[?!.]+$', '', normalized)
        
        return normalized
    
    def _extract_entities(self, question: str) -> Dict[str, Any]:
        """Extract entities like amounts, dates, categories from the question."""
        entities = {}
        
        for entity_type, pattern in self.entity_patterns.items():
            matches = re.findall(pattern, question, re.IGNORECASE)
            if matches:
                entities[entity_type] = matches
        
        return entities
    
    def _determine_context_type(
        self, 
        question: str, 
        conversation_history: Optional[List[Dict]]
    ) -> str:
        """Determine if this is a follow-up, new topic, or continuation."""
        
        question_lower = question.lower()
        
        # Check for follow-up indicators
        follow_up_indicators = ["and", "also", "what about", "tell me more", "that"]
        if any(indicator in question_lower for indicator in follow_up_indicators):
            return "follow_up"
        
        # Check if it's a short question (likely follow-up)
        if len(question.split()) <= 3 and conversation_history:
            return "follow_up"
        
        # Check for comparison keywords
        comparison_keywords = ["vs", "compared to", "difference", "than"]
        if any(keyword in question_lower for keyword in comparison_keywords):
            return "comparison"
        
        return "new_topic"
    
    def _classify_intent(
        self, 
        question: str, 
        entities: Dict[str, Any], 
        context_type: str
    ) -> Tuple[QuestionIntent, float]:
        """Classify the intent with confidence scoring."""
        
        intent_scores = {}
        
        # Pattern matching
        for intent, patterns in self.intent_patterns.items():
            max_score = 0
            for pattern in patterns:
                if re.search(pattern, question, re.IGNORECASE):
                    max_score = max(max_score, 0.8)
            
            if max_score > 0:
                intent_scores[intent] = max_score
        
        # Context-based adjustments
        if context_type == "follow_up":
            intent_scores[QuestionIntent.FOLLOW_UP_QUESTION] = 0.9
        
        # Entity-based scoring
        if "category" in entities:
            intent_scores[QuestionIntent.CATEGORY_ANALYSIS] = intent_scores.get(QuestionIntent.CATEGORY_ANALYSIS, 0) + 0.3
        
        if "merchant" in entities:
            intent_scores[QuestionIntent.MERCHANT_ANALYSIS] = intent_scores.get(QuestionIntent.MERCHANT_ANALYSIS, 0) + 0.3
        
        # Get highest scoring intent
        if intent_scores:
            best_intent = max(intent_scores.items(), key=lambda x: x[1])
            return best_intent[0], best_intent[1]
        
        # Fallback
        return QuestionIntent.GENERAL_FINANCIAL, 0.5
    
    def _extract_time_scope(self, question: str) -> Optional[str]:
        """Extract time scope from the question."""
        for scope, pattern in self.time_patterns.items():
            if re.search(pattern, question, re.IGNORECASE):
                return scope
        return None
    
    def _extract_category_filter(self, question: str) -> Optional[str]:
        """Extract category filter from the question."""
        category_mapping = {
            "food": ["food", "dining", "restaurant", "grocery"],
            "transport": ["transport", "fuel", "gas", "uber", "taxi"],
            "entertainment": ["entertainment", "movie", "game", "fun"],
            "shopping": ["shopping", "clothes", "retail"],
            "utilities": ["utilities", "electric", "water", "internet"]
        }
        
        question_lower = question.lower()
        for category, keywords in category_mapping.items():
            if any(keyword in question_lower for keyword in keywords):
                return category
        
        return None
    
    def _extract_merchant_filter(self, question: str) -> Optional[str]:
        """Extract merchant filter from the question."""
        # Look for "at [merchant]" or "from [merchant]" patterns
        merchant_match = re.search(r'(?:at|from)\s+([a-zA-Z0-9\s]+)', question, re.IGNORECASE)
        if merchant_match:
            return merchant_match.group(1).strip()
        return None
    
    def _extract_amount_filter(self, question: str) -> Optional[Dict[str, float]]:
        """Extract amount filters from the question."""
        # Look for "more than X", "less than X", "between X and Y"
        more_than_match = re.search(r'more\s+than\s+₹?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', question, re.IGNORECASE)
        if more_than_match:
            return {"min": float(more_than_match.group(1).replace(',', ''))}
        
        less_than_match = re.search(r'less\s+than\s+₹?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', question, re.IGNORECASE)
        if less_than_match:
            return {"max": float(less_than_match.group(1).replace(',', ''))}
        
        range_match = re.search(r'between\s+₹?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)\s+and\s+₹?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', question, re.IGNORECASE)
        if range_match:
            return {
                "min": float(range_match.group(1).replace(',', '')),
                "max": float(range_match.group(2).replace(',', ''))
            }
        
        return None
    
    def _determine_required_data(self, intent: QuestionIntent, entities: Dict[str, Any]) -> List[str]:
        """Determine what data is required to answer this question."""
        data_requirements = {
            QuestionIntent.SPENDING_SUMMARY: ["spending_data"],
            QuestionIntent.SPENDING_ANALYSIS: ["spending_data", "category_data"],
            QuestionIntent.CATEGORY_ANALYSIS: ["spending_data", "category_data"],
            QuestionIntent.BUDGET_INQUIRY: ["spending_data", "budget_data"],
            QuestionIntent.BUDGET_ADVICE: ["spending_data", "budget_data", "user_preferences"],
            QuestionIntent.SAVINGS_ADVICE: ["spending_data", "user_preferences"],
            QuestionIntent.COMPARATIVE_ANALYSIS: ["spending_data", "historical_data"],
            QuestionIntent.TREND_ANALYSIS: ["spending_data", "historical_data"],
            QuestionIntent.MERCHANT_ANALYSIS: ["spending_data", "merchant_data"],
            QuestionIntent.FOLLOW_UP_QUESTION: ["conversation_context"]
        }
        
        return data_requirements.get(intent, ["spending_data"])


# Create global instance
question_classifier = EnhancedQuestionClassifier()
