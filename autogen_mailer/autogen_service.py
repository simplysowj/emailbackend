import os
import autogen
from autogen import AssistantAgent, UserProxyAgent
from typing import Dict, List
import logging
from datetime import datetime

class AutoGenEmailGenerator:
    def __init__(self):
        self.logger = self._setup_logger()
        self.llm_config = {
            "config_list": [
                {
                    "model": "gpt-3.5-turbo",  # Using GPT-4 for better quality
                    "api_key": "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",
                    "base_url": "https://api.openai.com/v1"
                }
            ],
            "timeout": 120,
            "temperature": 0.7,
            "seed": 42  # For reproducibility
        }
        self._initialize_agents()

    def _setup_logger(self):
        logger = logging.getLogger("EmailGenerator")
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def _initialize_agents(self):
        """Initialize agents with strict conversation rules"""
        # Content Creator with explicit instructions
        self.content_creator = AssistantAgent(
            name="ContentCreator",
            system_message="""
            You are a professional email copywriter. Create marketing emails with:
            1. A compelling subject line (< 60 chars)
            2. Engaging body (3-5 paragraphs)
            3. Clear call-to-action
            4. A subject line (prefix with 'Subject: ')
            5. Body text (after '---' separator)
            6. HTML version (auto-generated later)
            7.use Sowjanya instead of [Your Name] 
            8.Replace [Customer Name] with concerned person and [company name] with concerned company
            
            
            Respond STRICTLY in this format:
            Subject: [Your subject line]
            ---
            [Email body content]
            
            Rules:
            - Only return the email content
            - No additional commentary
            - Subject must be < 60 chars
            - Include a clear call-to-action
            - Strictly follow the format
            - Stop after one response
            """,
            llm_config=self.llm_config,
            human_input_mode="NEVER",
            max_consecutive_auto_reply=1  # Critical to prevent loops
        )

        # Editor with clear improvement criteria
        #self.editor = AssistantAgent(
         #   name="Editor",
          #  system_message="""
           # You are a senior editor. Improve emails by:
            #1. Enhancing subject line impact
            #2. Improving flow and clarity
            #3. Strengthening call-to-action
            
            #Respond STRICTLY in this format:
            #Subject: [Improved subject]
            #---
            #[Improved body]
            
            #Rules:
            #- Only return the improved email
            #- No additional comments
            #- One response only
            #""",
            #llm_config=self.llm_config,
            #human_input_mode="NEVER",
            #max_consecutive_auto_reply=1  # Critical to prevent loops
        #)

        # User proxy with strict termination
        self.user_proxy = UserProxyAgent(
            name="UserProxy",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=0,  # No automatic replies
            code_execution_config=False,
            default_auto_reply="TERMINATE",
            llm_config=self.llm_config
        )

    def generate_email(self, context: Dict) -> Dict:
        """Generate email content with minimal agent interaction"""
        try:
            prompt = f"""
            Create a {context.get('tone', 'professional')} email about:
            PURPOSE: {context.get('purpose', '')}
            
            KEY POINTS:
            {chr(10).join('- ' + kp for kp in context.get('key_points', []))}
            
            Respond STRICTLY in format:
            Subject: [subject here]
            ---
            [email body here]
            """
            
            self.user_proxy.initiate_chat(
                self.content_creator,
                message=prompt,
                clear_history=True,
                silent=True
            )
            
            # Extract the single response
            draft = self.user_proxy.last_message(self.content_creator)['content']
            return self._format_email(draft)
            
        except Exception as e:
            self.logger.error(f"Generation failed: {str(e)}")
            return self._error_response(str(e))

    def _format_email(self, content: str) -> Dict:
        """Convert raw text to structured email format"""
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        subject = ""
        body_lines = []
        
        for line in lines:
            if line.lower().startswith("subject:"):
                subject = line[len("Subject:"):].strip()
            elif line != "---":
                body_lines.append(line)
        
        body_text = "\n".join(body_lines)
        body_html = f"<html><body><h2>{subject}</h2>" + \
                   "".join(f"<p>{line}</p>" for line in body_lines) + \
                   "</body></html>"
        
        return {
            "subject": subject or "Important Update",
            "body_text": body_text,
            "body_html": body_html,
            "generated_at": datetime.now().isoformat(),
            "error": None
        }

    def _error_response(self, error_msg: str) -> Dict:
        """Standard error format"""
        return {
            "subject": "Email Generation Error",
            "body_text": f"Error: {error_msg}",
            "body_html": f"<p>Error: {error_msg}</p>",
            "generated_at": datetime.now().isoformat(),
            "error": error_msg
        }