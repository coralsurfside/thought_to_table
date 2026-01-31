#!/usr/bin/env python3
"""
Recipe CLI - Process recipe URLs for OpenClaw integration.
Returns JSON output for easy parsing.

Usage:
    python recipe_cli.py <url> [servings]
    python recipe_cli.py --help
"""
import os
import sys
import json
from typing import Optional

# Add repo to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

import anthropic
from bs4 import BeautifulSoup
import requests

MODELID = "claude-sonnet-4-20250514"


def extract_recipe_text(url: str) -> str:
    """Fetch and extract text from recipe URL"""
    response = requests.get(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }, timeout=30)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    for el in soup(["script", "style", "nav", "footer", "header", "aside"]):
        el.decompose()
    
    return soup.get_text(separator='\n', strip=True)


def call_claude(client: anthropic.Anthropic, prompt: str) -> dict:
    """Make Claude API call and parse JSON response"""
    response = client.messages.create(
        model=MODELID,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt + "\n\nRespond with valid JSON only."}]
    )
    
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
        if "```" in text:
            text = text.rsplit("```", 1)[0]
    
    return json.loads(text.strip())


def process_recipe(url: str, servings: int = 7) -> dict:
    """
    Process a recipe URL and return scaled shopping list.
    
    Returns dict with:
    - success: bool
    - recipe_name: str
    - original_servings: int
    - scaled_servings: int  
    - shopping_list: list of items
    - estimated_cost: float
    - storage_tips: dict
    - error: str (if failed)
    """
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        return {"success": False, "error": "ANTHROPIC_API_KEY not set"}
    
    client = anthropic.Anthropic(api_key=api_key)
    
    try:
        # Extract recipe
        recipe_text = extract_recipe_text(url)
        
        # Parse with Claude
        parse_prompt = f"""Analyze this recipe and extract:
- recipe_name
- original_servings (number)
- ingredients: array of {{name, amount, unit, category, notes}}

Categories: produce, dairy, meat, seafood, pantry, spices, frozen, bakery

Recipe:
{recipe_text[:6000]}

Return JSON only."""

        parsed = call_claude(client, parse_prompt)
        
        # Scale recipe
        scale_prompt = f"""Scale this recipe from {parsed.get('original_servings', 4)} to {servings} servings.

Recipe: {json.dumps(parsed, indent=2)}

Return JSON with:
- recipe_name
- scaled_servings: {servings}
- shopping_list: array of {{name, amount, unit, category, estimated_price}}
- estimated_total_cost: number
- storage_tips: {{ingredient: tip}}

Round to practical amounts. Use common package sizes."""

        scaled = call_claude(client, scale_prompt)
        
        return {
            "success": True,
            "url": url,
            "recipe_name": scaled.get('recipe_name', parsed.get('recipe_name', 'Recipe')),
            "original_servings": parsed.get('original_servings', 4),
            "scaled_servings": servings,
            "shopping_list": scaled.get('shopping_list', []),
            "estimated_cost": scaled.get('estimated_total_cost', 0),
            "storage_tips": scaled.get('storage_tips', {})
        }
        
    except requests.RequestException as e:
        return {"success": False, "error": f"Failed to fetch recipe: {e}"}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Failed to parse Claude response: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def format_for_chat(result: dict) -> str:
    """Format result as a chat-friendly message"""
    if not result.get('success'):
        return f"❌ Error: {result.get('error', 'Unknown error')}"
    
    lines = [
        f"🍽️ **{result['recipe_name']}**",
        f"📊 Scaled for {result['scaled_servings']} servings",
        "",
        "**Shopping List:**"
    ]
    
    for item in result.get('shopping_list', []):
        name = item.get('name', 'Unknown')
        amount = item.get('amount', '')
        unit = item.get('unit', '')
        price = item.get('estimated_price', 0)
        
        price_str = f" ~${price:.2f}" if price else ""
        lines.append(f"• {name}: {amount} {unit}{price_str}")
    
    lines.append("")
    lines.append(f"💰 **Estimated Total:** ${result.get('estimated_cost', 0):.2f}")
    
    if result.get('storage_tips'):
        lines.append("")
        lines.append("**Storage Tips:**")
        for ingredient, tip in list(result['storage_tips'].items())[:5]:
            lines.append(f"• {ingredient}: {tip}")
    
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        print("Usage: python recipe_cli.py <url> [servings]")
        print("       python recipe_cli.py <url> [servings] --json")
        print("       python recipe_cli.py <url> [servings] --chat")
        sys.exit(0 if '--help' in sys.argv else 1)
    
    url = sys.argv[1]
    servings = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 7
    
    output_format = "json"
    if "--chat" in sys.argv:
        output_format = "chat"
    elif "--json" in sys.argv:
        output_format = "json"
    
    result = process_recipe(url, servings)
    
    if output_format == "chat":
        print(format_for_chat(result))
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
