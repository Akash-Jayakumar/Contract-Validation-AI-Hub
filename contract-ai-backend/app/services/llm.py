from typing import Dict, List, Optional
import os
import requests
import json
import re
from app.config import GEMINI_API_KEY


def gemini_flash_complete(prompt: str, model_id: str = "gemini-2.0-flash-exp") -> str:
    """Generate content using Gemini Flash model"""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable is not set")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    try:
        resp = requests.post(url, headers=headers, json=data)
        resp.raise_for_status()
        result = resp.json()
        
        # Extract generated text from result
        if "candidates" in result and result["candidates"]:
            candidate = result["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                parts = candidate["content"]["parts"]
                if parts and "text" in parts[0]:
                    return parts[0]["text"]
        
        # Fallback if the response structure is different
        return "No response generated from Gemini"
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Gemini API request failed: {e}")
    except (KeyError, IndexError) as e:
        raise Exception(f"Failed to parse Gemini response: {e}")


class LLMJsonError(Exception):
    pass


def gemini_json(prompt: str, response_schema: dict | None = None, temperature: float = 0.1, timeout: int = 90) -> dict:
    """Generate structured JSON response using Gemini Flash model with optional schema"""
    if not GEMINI_API_KEY:
        raise LLMJsonError("GEMINI_API_KEY not set")
    
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    gen_cfg = {
        "temperature": temperature,
        "responseMimeType": "application/json"
    }
    if response_schema:
        gen_cfg["responseSchema"] = response_schema
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": gen_cfg
    }
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        
        # Extract text from response
        text = data["candidates"][0]["content"]["parts"][0].get("text", "")
        try:
            return json.loads(text)
        except Exception:
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                return json.loads(m.group(0))
            raise LLMJsonError(f"Non-JSON output: {text[:200]}")
            
    except requests.exceptions.RequestException as e:
        raise LLMJsonError(f"Gemini API request failed: {e}")


class LLMService:
    """Service for handling LLM interactions"""
    
    @staticmethod
    def generate_response(prompt: str, context: str, max_tokens: int = 500, use_gemini: bool = True) -> str:
        """Generate response using LLM"""
        if use_gemini:
            try:
                full_prompt = f"Context: {context}\n\nQuestion: {prompt}\n\nPlease provide a helpful response based on the context."
                return gemini_flash_complete(full_prompt)
            except Exception as e:
                # Fallback to placeholder if Gemini fails
                return f"Generated response based on context: {context[:100]}... (Gemini error: {str(e)})"
        else:
            # Placeholder for other LLM integrations
            return f"Generated response based on context: {context[:100]}..."
    
    @staticmethod
    def analyze_contract(text: str, use_gemini: bool = True) -> Dict:
        """Analyze contract text for key insights"""
        if use_gemini:
            try:
                prompt = f"""Analyze the following contract text and provide key insights about financial health, risks, and important clauses:

{text}

Please provide a structured analysis with the following sections:
1. Financial Health Assessment
2. Risk Identification
3. Key Clauses Summary
4. Recommendations"""
                
                analysis = gemini_flash_complete(prompt)
                return {"insights": analysis}
            except Exception as e:
                # Fallback to placeholder if Gemini fails
                return {"insights": f"Analysis results would go here. (Gemini error: {str(e)})"}
        else:
            # Placeholder for other analysis methods
            return {"insights": "Analysis results would go here."}
