# retention/services/chatbot.py
from typing import Dict, List
import os

# Your existing LangGraph setup

from retention.models import Conversation, Employee, Signal

try:
    import dotenv
    dotenv.load_dotenv()
except ImportError:  # pragma: no cover - env comes from settings in the platform
    pass
# Use your preferred LLM (Claude/Gemini/GPT)
try:
    from openai import OpenAI
    client = OpenAI(
        base_url="https://api.tokenfactory.nebius.com/v1/",
        api_key=os.environ.get("NEBIUS_API_KEY")
    )
    LLM_AVAILABLE = bool(os.environ.get("NEBIUS_API_KEY"))
except Exception:  # pragma: no cover - LLM optional, keyword fallback used
    LLM_AVAILABLE = False

class RetentionChatbotService:
    """Chatbot for retention conversations"""
    
    @staticmethod
    def initiate_conversation(employee: Employee, signal: Signal) -> Conversation:
        """Start a proactive conversation with at-risk employee"""
        
        # Create conversation record
        conversation = Conversation.objects.create(
            employee=employee,
            signal=signal,
            completed=False,
            messages=[]
        )
        
        # Generate initial message based on signal type
        initial_message = RetentionChatbotService._generate_initial_message(
            employee.name, 
            signal.signal_type
        )
        
        conversation.messages.append({
            "role": "assistant",
            "content": initial_message
        })
        conversation.save()
        
        return conversation
    
    @staticmethod
    def _generate_initial_message(employee_name: str, signal_type: str) -> str:
        """Generate personalized opening message"""
        
        messages = {
            'low_engagement': f"Bonjour {employee_name}, j'ai remarqué que vous semblez moins engagé récemment. Pouvez-vous me dire ce qui ne va pas?",
            'poor_performance': f"Bonjour {employee_name}, je voulais prendre de vos nouvelles. Y a-t-il quelque chose qui vous empêche de donner le meilleur de vous-même?",
            'high_absence': f"Bonjour {employee_name}, j'ai noté plusieurs absences récentes. Est-ce que tout va bien?",
        }
        
        return messages.get(signal_type, f"Bonjour {employee_name}, comment allez-vous?")
    
    @staticmethod
    def process_employee_response(conversation: Conversation, user_message: str) -> Dict:
        """Process employee's response and extract needs"""
        
        # Add user message to conversation
        conversation.messages.append({
            "role": "user",
            "content": user_message
        })
        
        # Use LLM to analyze and extract need
        if LLM_AVAILABLE:
            need = RetentionChatbotService._extract_need_with_llm(conversation.messages)
        else:
            # Fallback: simple keyword matching
            need = RetentionChatbotService._extract_need_simple(user_message)
        
        conversation.identified_need = need
        conversation.completed = True
        conversation.save()
        
        return {
            "conversation_id": conversation.id,
            "identified_need": need,
            "messages": conversation.messages
        }
    
    @staticmethod
    def _extract_need_with_llm(messages: List[Dict]) -> str:
        """Use LLM to extract employee's primary need"""
        
        prompt = f"""
Analyze this conversation and identify the employee's PRIMARY need.
Return ONLY ONE of these words: salary, growth, workload, recognition, flexibility

Conversation:
{messages[-1]['content']}

Answer with just one word:"""
        
        message = client.chat.completions.create(
            model="moonshotai/Kimi-K2-Instruct",
            messages=[{"role": "user", "content": prompt}]
        )
        
        return message.choices[0].message.content.strip().lower()
    
    @staticmethod
    def _extract_need_simple(text: str) -> str:
        """Simple keyword-based need extraction (fallback)"""
        
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['salaire', 'augmentation', 'payé', 'argent']):
            return 'salary'
        elif any(word in text_lower for word in ['évoluer', 'promotion', 'carrière', 'grandir']):
            return 'growth'
        elif any(word in text_lower for word in ['surchargé', 'trop', 'stress', 'burnout']):
            return 'workload'
        elif any(word in text_lower for word in ['reconnaissance', 'apprécié', 'valorisé']):
            return 'recognition'
        elif any(word in text_lower for word in ['télétravail', 'flexible', 'horaires']):
            return 'flexibility'
        else:
            return 'general'