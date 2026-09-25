import os

class AIModelConfig:
    def __init__(self):
        self.provider = os.getenv("KESTREL_AI_PROVIDER", "gemini").lower()
        self.model_id = os.getenv("KESTREL_AI_MODEL", "gemini-flash-lite-latest")
        
        # Determine the api key env var name based on provider
        if self.provider == "gemini" or self.provider == "google":
            self.api_key_env_name = "GEMINI_API_KEY"
            if not os.getenv(self.api_key_env_name):
                self.api_key_env_name = "GOOGLE_API_KEY"
        elif self.provider == "groq":
            self.api_key_env_name = "GROQ_API_KEY"
        elif self.provider == "qwen":
            self.api_key_env_name = "QWEN_API_KEY"
        else:
            self.api_key_env_name = f"{self.provider.upper()}_API_KEY"

        self.base_url = os.getenv("KESTREL_AI_BASE_URL", None)
        self.request_timeout_seconds = int(os.getenv("KESTREL_AI_TIMEOUT", "30"))

        # Capabilities
        # Assuming our canonical model supports everything for now, but we can refine if needed.
        self.supports_text = True
        self.supports_vision = True
        self.supports_structured_output = True

        # In case it's Groq, Groq's standard models don't support vision well except llama-3.2-90b-vision
        if self.provider == "groq" and "vision" not in self.model_id.lower():
            self.supports_vision = False

    def get_api_key(self):
        return os.getenv(self.api_key_env_name)

# Canonical singleton instance
get_model_config = AIModelConfig()
