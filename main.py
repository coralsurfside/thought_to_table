import os
from typing import Dict
from urllib.parse import quote
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import anthropic
import json
import time
from bs4 import BeautifulSoup
import requests
from dotenv import load_dotenv

load_dotenv()

# Using Claude for all LLM calls
MODELID = "claude-sonnet-4-20250514"

class RecipeAssistant:
    def __init__(self, num_meals: int):
        """
        Initialize the Recipe Assistant with Anthropic API key
        
        Args:
            num_meals (int): Number of meals to scale recipe for
        """
        self.client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.servings_needed = num_meals
        self.debug_walmart_search = False
        self.driver = None  # Lazy init browser
        
    def _ensure_browser(self):
        """Lazily initialize browser only when needed"""
        if self.driver is None:
            self.driver = uc.Chrome()
            self.driver.maximize_window()

    def wait_for_manual_login(self):
        """Wait for user to manually log in to Walmart"""
        print("\nPlease log in to Walmart in the browser window that just opened.")
        print("After logging in, type 'done' and press Enter: ")
        input()
        print("Continuing with recipe processing...")

    def extract_recipe_text(self, recipe_url: str) -> str:
        """Extract text content from recipe URL"""
        response = requests.get(recipe_url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for script in soup(["script", "style"]):
            script.decompose()
            
        return soup.get_text()

    def _call_claude(self, prompt: str) -> dict:
        """Make a Claude API call and return parsed JSON response"""
        response = self.client.messages.create(
            model=MODELID,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": prompt + "\n\nRespond with valid JSON only, no markdown formatting."
                }
            ]
        )
        
        # Extract text from response
        text = response.content[0].text
        
        # Clean up potential markdown code blocks
        if text.startswith("```"):
            text = text.split("\n", 1)[1]  # Remove first line
            if text.endswith("```"):
                text = text[:-3]
            elif "```" in text:
                text = text.rsplit("```", 1)[0]
        
        return json.loads(text.strip())

    def parse_recipe_with_claude(self, recipe_text: str) -> dict:
        """Use Claude to parse recipe ingredients"""
        try:
            prompt = f"""Analyze this recipe and convert ingredients into Walmart-optimized shopping format.

For each ingredient provide:
- name: Use standard grocery shopping terms. Format specifically for Walmart grocery search (e.g., "garlic cloves" instead of "whole fresh garlic bulb", "sour cream" instead of just "dairy sour cream")
- amount: numerical quantity
- unit: Use common retail units:
    - For produce: "whole", "bunch", "head", "lb"
    - For dairy/liquid: "oz", "fl oz", "gallon"
    - For packaged goods: "oz", "lb", "count"
- category: Specify one of: "produce", "dairy", "meat", "pantry", "spices"
- notes: Include any specifics that do not fit in the other details

Consider common Walmart packaging and product names. Format ingredient names as you would find them on Walmart.com.

Format response as JSON with:
- ingredients: array of ingredient objects
- servings: number
- meal_type: string
- portion_size: string  
- calories_per_serving: number

Recipe text:
{recipe_text}"""
            
            return self._call_claude(prompt)
        except Exception as e:
            print(f"Error parsing ingredients: {e}")
            return {"ingredients": [], "servings": 0}

    def add_to_cart(self, search_query: str):
        """Search for and add item to cart"""
        self._ensure_browser()
        try:
            self.driver.get(f"https://www.walmart.com/search?q={search_query}")
            
            # Wait for search results
            item = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-item-id]"))
            )
            
            # Wait for and click Add to Cart button
            add_button = WebDriverWait(item, 10).until(
                EC.element_to_be_clickable((By.XPATH, ".//button[contains(text(), 'Add to cart')]"))
            )
            add_button.click()
            
            time.sleep(2)  # Wait for cart update
            
        except Exception as e:
            print(f"Error adding {search_query} to cart: {e}")

    def process_recipe_url(self, recipe_url: str, search_walmart: bool = True):
        """Main function to process recipe and optionally search Walmart"""
        if self.debug_walmart_search:
            scaled_data = None
            with open('shopping_list.json', 'r') as f:
                data = json.loads(f.read())
            print(data)
            scaled_data = data['scaled_recipe']
            recipe_text = data['original_recipe']
        else:
            print("Extracting recipe text...")
            recipe_text = self.extract_recipe_text(recipe_url)
            
            print("Parsing ingredients with Claude...")
            ingredients = self.parse_recipe_with_claude(recipe_text)
            print(f"Found {len(ingredients.get('ingredients', []))} ingredients")
            
            print(f"\nScaling recipe for {self.servings_needed} meals...")
            scaled_data = self.scale_recipe(ingredients)
            
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

        result = {
            'recipe_url': recipe_url,
            'original_recipe': recipe_text if not self.debug_walmart_search else recipe_text,
            'scaled_recipe': scaled_data,
            'walmart_products': []
        }

        if search_walmart:
            print("\nSearching Walmart for ingredients...")
            self._ensure_browser()
            
            for ingredient in scaled_data.get('scaled_ingredients', []):
                print(f"Searching for {ingredient.get('name', 'Unknown')}...")
                search_result = self.search_walmart_product(ingredient)
                result['walmart_products'].append(search_result)
                time.sleep(2)  # Prevent rate limiting

        return result

    def cleanup(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()

    def scale_recipe(self, recipe_data: dict) -> dict:
        """Scale recipe ingredients for desired number of meals."""
        prompt = f"""Scale this recipe to make {self.servings_needed} meals.

Current recipe data:
{json.dumps(recipe_data, indent=2)}

Calculate the new quantities needed and provide:
1. Scaled ingredients list with adjusted amounts
2. Shopping list optimized for bulk buying
3. Storage recommendations for bulk ingredients
4. Estimated total cost

Format as JSON with these keys:
- scaled_ingredients: array of adjusted ingredients (each with: name, amount, unit, category, notes)
- shopping_list: array of optimized items to buy (each with: name, amount, units, notes)
- storage_tips: object with storage advice (ingredient name -> tip)
- estimated_cost: number

Consider:
- Rounding to practical purchase amounts
- Bulk packaging sizes
- Common store quantities
- Ingredient shelf life"""

        return self._call_claude(prompt)

    def search_walmart_product(self, ingredient: dict) -> dict:
        """Search for a single ingredient on Walmart.com and return product info."""
        self._ensure_browser()
        try:
            category = ingredient.get('category', '').lower()
            name = ingredient.get('name', '')
            notes = ingredient.get('notes', '')

            if category == 'produce':
                search_query = f"fresh {name}"
            elif category == 'dairy':
                search_query = f"dairy {name}"
            elif category == 'meat':
                search_query = f"fresh {name}"
            elif category == 'spices':
                search_query = f"{name} spice"
            else:
                search_query = name

            encoded_query = quote(search_query)
            url = f"https://www.walmart.com/search?q={encoded_query}"
            
            self.driver.get(url)
            time.sleep(2)
            
            product = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-item-id]"))
            )
            
            product_name = None
            product_url = None
            price = None
            
            name_selectors = [
                "span[data-automation-id='product-title']",
                "span.normal",
                "span.f6"
            ]
            for selector in name_selectors:
                try:
                    product_name = product.find_element(By.CSS_SELECTOR, selector).text
                    if self.is_valid_product(product_name, ingredient):
                        break
                except:
                    continue
            
            try:
                link_element = product.find_element(By.CSS_SELECTOR, "a[href*='/ip/']")
                product_url = link_element.get_attribute('href')
            except:
                try:
                    links = product.find_elements(By.TAG_NAME, "a")
                    for link in links:
                        href = link.get_attribute('href')
                        if href and '/ip/' in href:
                            product_url = href
                            break
                except:
                    pass
            
            price_selectors = [
                "[data-automation-id='product-price']",
                "div.price-main",
                "span.price"
            ]
            for selector in price_selectors:
                try:
                    price = product.find_element(By.CSS_SELECTOR, selector).text
                    if price:
                        break
                except:
                    continue
            
            print(f"\nDebug info for {ingredient.get('name', 'Unknown')}:")
            print(f"Name found: {product_name}")
            print(f"URL found: {product_url}")
            print(f"Price found: {price}")
            
            return {
                "ingredient": ingredient,
                "product": {
                    "name": product_name or "Name not found",
                    "url": product_url or "URL not found",
                    "price": price or "Price not found",
                    "quantity_needed": f"{ingredient.get('amount', '')} {ingredient.get('unit', '')}"
                }
            }
                
        except Exception as e:
            print(f"Error searching for {ingredient.get('name', 'Unknown')}: {e}")
            return {
                "ingredient": ingredient,
                "product": {
                    "name": "Search failed",
                    "url": "URL not found",
                    "price": "Price not found",
                    "quantity_needed": f"{ingredient.get('amount', '')} {ingredient.get('unit', '')}"
                }
            }

    def save_results(self, results: Dict, filename: str = "shopping_list.json"):
        """Save results to a JSON file."""
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {filename}")

    def is_valid_product(self, product_name: str, ingredient: dict) -> bool:
        """Validate if the found product matches what we're looking for"""
        category = ingredient.get('category', '').lower()
        name = ingredient.get('name', '').lower()
        
        invalid_keywords = {
            'produce': ['seeds', 'plant', 'garden', 'growing'],
            'dairy': ['chips', 'snacks', 'artificial'],
            'meat': ['pet', 'dog', 'cat', 'toy']
        }
        
        if category in invalid_keywords:
            if any(kw in product_name.lower() for kw in invalid_keywords[category]):
                return False
        
        if name and name not in product_name.lower():
            return False
            
        return True


# Example usage
if __name__ == "__main__":
    assistant = RecipeAssistant(num_meals=7)
    
    recipe_url = "https://www.bonappetit.com/recipe/loaded-scalloped-potatoes"
    
    try:
        # Process without Walmart search first (for testing)
        results = assistant.process_recipe_url(recipe_url, search_walmart=False)
        assistant.save_results(results)
        
        print("\n" + "="*50)
        print("RECIPE PROCESSING COMPLETE")
        print("="*50)
        print(f"\nRecipe scaled for {assistant.servings_needed} servings")
        print(f"Estimated cost: ${results['scaled_recipe'].get('estimated_cost', 0):.2f}")
        print(f"\nResults saved to shopping_list.json")
        
    except KeyboardInterrupt:
        print("\nStopping the script...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        assistant.cleanup()
