# Web Interface Guide - Example Generation

## Overview

The Anki Vector web interface provides a user-friendly way to generate AI-powered examples for your Anki cards without using the command line.

## Getting Started

1. **Start the server:**
   ```bash
   python -m uvicorn api:app --reload --port 8000
   ```

2. **Access the admin panel:**
   Open your browser and navigate to `http://localhost:8000/admin`

3. **Click on "Generate Examples"** to access the example generation interface

## Example Generation Interface

### Configuration Options

- **Deck Name**: 
  - Select "All decks" to process all decks
  - Select a specific deck name to process only that deck

- **Card ID** (optional):
  - Enter a specific card ID to process only that card
  - Useful for testing and debugging specific cards
  - When specified, overrides deck selection and limit settings
  - If the card ID doesn't exist, the task will complete with "No cards found"

- **Card Columns**: 
  - Comma-separated list of card columns to use in the template
  - Default: `front_text,back_text`
  - Available columns: `front_text`, `back_text`, `deck_name`, `model_name`, `tags`

- **Instruction Template**:
  - Select from available instruction templates in the `instructions/` directory
  - Templates use Jinja2 syntax with card data variables

- **Limit** (optional):
  - Maximum number of cards to process
  - Leave empty for no limit

### Processing Options

- **With Preview**: 
  - Shows sample results before processing
  - Automatically disables parallel processing
  - Useful for testing templates

- **Enable Parallel Processing**:
  - Process cards in parallel for faster performance
  - Disabled when "With Preview" is enabled

- **Dry Run**:
  - Generate examples without saving to database
  - Useful for testing and debugging

## Features

### 1. Template Preview
- Check "With Preview" to see sample results before processing
- Shows generated examples for 5 sample cards
- Helps validate your template and columns

### 2. Real-time Progress
- Progress bar shows completion percentage
- Status messages indicate current processing stage
- Live updates every 2 seconds

### 3. Results Display
- Summary statistics: processed, successful, failed, processing time
- Failed cards list with error messages
- Dry run results with sample generated examples

### 4. Error Handling
- Continues processing even if individual cards fail
- Detailed error messages for troubleshooting
- Retry functionality for failed operations

## Example Workflow

1. **Select Template**: Choose an instruction template from the dropdown
2. **Configure**: Set deck name, columns, and processing options
3. **Preview** (optional): Check "With Preview" to see sample results
4. **Process**: Click "Generate Examples" to start processing
5. **Monitor**: Watch progress bar and status messages
6. **Review**: Check results and failed cards if any

## Instruction Templates

Templates are stored in the `instructions/` directory and use Jinja2 syntax:

```jinja2
You are a helpful assistant. Based on the card data:
- Front: {{ front_text }}
- Back: {{ back_text }}

Create an example sentence...
```

### Available Variables
- `front_text`: Front text of the card
- `back_text`: Back text of the card
- `deck_name`: Name of the deck
- `model_name`: Anki model name
- `tags`: List of tags (if any)

## Tips

- Use "With Preview" to test new templates
- Use "Dry Run" for debugging without saving
- Process specific decks first to test on smaller datasets
- Use Card ID for testing specific problematic cards
- Monitor failed cards to identify template issues
- Keep instruction templates simple and clear

### Finding Card IDs
- Card IDs are displayed in API responses and database queries
- Use the stats endpoint (`/stats`) to see card counts
- Check the cards endpoint (`/cards`) to browse available cards

## Troubleshooting

### Common Issues

1. **No instruction templates available**
   - Check that `.txt` files exist in the `instructions/` directory
   - Ensure templates have proper Jinja2 syntax

2. **Preview shows errors**
   - Check template syntax
   - Verify column names exist in your cards
   - Test with simpler templates first

3. **Processing fails**
   - Check server logs for detailed error messages
   - Verify OpenAI API key is set (if using OpenAI)
   - Test with smaller limits first

### Support

- Check server logs for detailed error messages
- Use the preview feature to debug templates
- Test with small limits before processing large datasets 
