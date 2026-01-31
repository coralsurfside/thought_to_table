# 🪸 Thought to Table (Coral Fork)

Recipe URL → Scaled Ingredients → Walmart Shopping List

Forked from [EribertoLopez/thought_to_table](https://github.com/EribertoLopez/thought_to_table) and refactored to use **Anthropic Claude** instead of OpenAI.

## Features

- 📝 Extract ingredients from any recipe URL
- 📊 Scale recipes for meal prep (e.g., 7 servings for a week)
- 🛒 Generate Walmart-optimized shopping lists
- 💾 Storage tips for bulk ingredients
- 💰 Cost estimation

## Setup

### 1. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

### 2. Configure API key

Copy the example env file and add your Anthropic API key:

```bash
cp .env.example .env
```

Edit `.env` and add your key:
```
ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Run

**Test with sample recipe:**
```bash
python anthro_test.py
```

**Process a recipe URL:**
```bash
python main.py
```

Edit `main.py` to change the recipe URL and number of servings.

## Usage

```python
from main import RecipeAssistant

assistant = RecipeAssistant(num_meals=7)

# Process recipe (without Walmart search)
results = assistant.process_recipe_url(
    "https://www.bonappetit.com/recipe/loaded-scalloped-potatoes",
    search_walmart=False  # Set True to also search Walmart
)

# Save results
assistant.save_results(results, "my_shopping_list.json")
assistant.cleanup()
```

## Output

The tool generates a JSON file with:
- Original recipe text
- Scaled ingredients
- Shopping list (optimized for bulk buying)
- Storage tips
- Estimated total cost
- Walmart product matches (if search_walmart=True)

## Roadmap

- [ ] Coral slash command integration (`/recipe <url> [servings]`)
- [ ] Preview UI before adding to cart
- [ ] Improved Walmart search accuracy
- [ ] Support for other grocery stores

---

*Part of the Coral 🪸 toolkit for Surfside*
