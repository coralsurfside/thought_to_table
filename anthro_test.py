"""
Test script for Claude-based recipe analysis
Now actually using Anthropic's Claude API!
"""
import os
from dotenv import load_dotenv
import anthropic
import json

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
MODELID = "claude-sonnet-4-20250514"


def _call_claude(prompt: str) -> dict:
    """Make a Claude API call and return parsed JSON response"""
    response = client.messages.create(
        model=MODELID,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": prompt + "\n\nRespond with valid JSON only, no markdown formatting."
            }
        ]
    )
    
    text = response.content[0].text
    
    # Clean up potential markdown code blocks
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
        elif "```" in text:
            text = text.rsplit("```", 1)[0]
    
    return json.loads(text.strip())


def analyze_recipe(recipe_text: str) -> dict:
    """Analyze recipe for ingredients, serving size, and scaling information."""
    prompt = f"""Analyze this recipe and provide the following information in JSON format:
1. List of ingredients with:
   - name
   - amount
   - unit
   - notes (e.g., "organic", "fresh", "canned")
2. Number of servings this recipe makes
3. Type of meal (breakfast, lunch, dinner)
4. Portion size per serving
5. Estimated calories per serving

Format your response as a JSON object with these keys:
- ingredients: array of ingredient objects
- servings: number
- meal_type: string
- portion_size: string
- calories_per_serving: number

Recipe text:
{recipe_text}"""
    
    return _call_claude(prompt)


def scale_recipe(recipe_data: dict, target_meals: int) -> dict:
    """Scale recipe ingredients for desired number of meals."""
    prompt = f"""Scale this recipe to make {target_meals} meals.

Current recipe data:
{json.dumps(recipe_data, indent=2)}

Calculate the new quantities needed and provide:
1. Scaled ingredients list with adjusted amounts
2. Shopping list optimized for bulk buying
3. Storage recommendations for bulk ingredients
4. Estimated total cost

Format as JSON with these keys:
- scaled_ingredients: array of adjusted ingredients
- shopping_list: array of optimized items to buy (each with: name, amount, units, notes)
- storage_tips: object with storage advice
- estimated_cost: number

Consider:
- Rounding to practical purchase amounts
- Bulk packaging sizes
- Common store quantities
- Ingredient shelf life"""
    
    return _call_claude(prompt)


def process_recipe(recipe_text: str, meals_per_week: int = 7):
    """Main function to analyze and scale recipe."""
    print("Analyzing recipe with Claude...")
    recipe_data = analyze_recipe(recipe_text)
    
    print("\nOriginal Recipe Analysis:")
    print(f"Serves: {recipe_data.get('servings', 'Unknown')} people")
    print(f"Meal Type: {recipe_data.get('meal_type', 'Unknown')}")
    print(f"Calories per serving: {recipe_data.get('calories_per_serving', 'Unknown')}")
    
    servings_needed = meals_per_week
    print(f"\nScaling recipe for {servings_needed} meals...")
    
    scaled_data = scale_recipe(recipe_data, servings_needed)
    
    print("\nScaled Recipe Information:")
    print("\nShopping List:")
    for item in scaled_data.get('shopping_list', []):
        if isinstance(item, dict):
            print(f"- {item.get('name', 'Unknown')}: {item.get('amount', '')} {item.get('units', '')}")
        else:
            print(f"- {item}")
    
    print("\nStorage Tips:")
    for ingredient, tip in scaled_data.get('storage_tips', {}).items():
        print(f"- {ingredient}: {tip}")
    
    print(f"\nEstimated Total Cost: ${scaled_data.get('estimated_cost', 0):.2f}")
    
    return {
        'original_recipe': recipe_data,
        'scaled_recipe': scaled_data
    }


if __name__ == "__main__":
    example_recipe = """
    Classic Chicken Stir-Fry
    
    Ingredients:
    2 chicken breasts, sliced
    3 cups mixed vegetables
    2 tablespoons soy sauce
    1 tablespoon oil
    2 cloves garlic, minced
    1 cup rice
    
    Instructions:
    Cook rice according to package directions. Heat oil in a large pan...
    """
    
    result = process_recipe(
        recipe_text=example_recipe,
        meals_per_week=7
    )
    print("\n" + "="*50)
    print("Full Result:")
    print(json.dumps(result, indent=2))
