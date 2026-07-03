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
            'burnout_risk': f"Bonjour {employee_name}, votre charge de travail semble très élevée ces derniers temps. Comment vous sentez-vous? Peut-on en parler?",
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

# ---------------------------------------------------------------------------
# Multi-turn dialogue engine (v1.5): the bot keeps asking targeted
# follow-up questions until it identifies the employee's primary need
# (or the turn budget runs out), instead of closing after one reply.
# ---------------------------------------------------------------------------

MAX_EMPLOYEE_TURNS = 4

FOLLOW_UP_QUESTIONS = [
    "Merci de partager cela. Pouvez-vous m'en dire plus? Est-ce plutôt lié à votre rémunération, votre évolution, votre charge de travail, ou autre chose?",
    "Je comprends. Si vous deviez choisir UNE chose que l'entreprise pourrait améliorer pour vous, ce serait quoi?",
    "D'accord. Concrètement, qu'est-ce qui vous ferait rester dans l'entreprise à long terme?",
]

CLOSING_MESSAGES = {
    "salary": "Merci pour votre franchise. Je transmets aux RH une proposition de révision de votre rémunération. Ils reviendront vers vous rapidement.",
    "growth": "Merci. Je signale aux RH votre souhait d'évolution — ils étudieront les opportunités de mobilité interne ou de promotion.",
    "workload": "Merci de me l'avoir dit. Je transmets aux RH une demande de rééquilibrage de votre charge de travail.",
    "recognition": "Merci pour ce partage. Je propose aux RH d'organiser un entretien de reconnaissance et de valorisation de votre travail.",
    "flexibility": "Merci. Je transmets aux RH votre demande d'aménagement (horaires flexibles / télétravail).",
    "general": "Merci pour cet échange. Je transmets vos retours aux RH qui organiseront un entretien approfondi avec votre manager.",
}


class DialogueEngine:
    """Stateful multi-turn conversation logic over Conversation.messages."""

    @staticmethod
    def _employee_turns(conversation) -> int:
        return sum(1 for m in conversation.messages if m.get("role") == "user")

    @staticmethod
    def advance(conversation: "Conversation", user_message: str) -> Dict:
        """Process one employee message; returns the bot's reply and
        whether the conversation completed (need identified)."""
        conversation.messages.append({"role": "user", "content": user_message})

        if LLM_AVAILABLE:
            need = RetentionChatbotService._extract_need_with_llm(
                conversation.messages
            )
        else:
            need = RetentionChatbotService._extract_need_simple(user_message)

        turns = DialogueEngine._employee_turns(conversation)

        if need != "general":
            conversation.identified_need = need
            conversation.completed = True
            reply = CLOSING_MESSAGES.get(need, CLOSING_MESSAGES["general"])
        elif turns >= MAX_EMPLOYEE_TURNS:
            conversation.identified_need = "general"
            conversation.completed = True
            reply = CLOSING_MESSAGES["general"]
        else:
            # keep the dialogue going with a targeted follow-up
            reply = FOLLOW_UP_QUESTIONS[
                min(turns - 1, len(FOLLOW_UP_QUESTIONS) - 1)
            ]

        conversation.messages.append({"role": "assistant", "content": reply})
        conversation.save()

        return {
            "conversation_id": conversation.id,
            "bot_reply": reply,
            "completed": conversation.completed,
            "identified_need": conversation.identified_need,
            "employee_turns": turns,
            "messages": conversation.messages,
        }
