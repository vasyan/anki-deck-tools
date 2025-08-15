# Anki Card Template JavaScript Integration

## Summary
Implemented JavaScript support for Anki card templates using Jinja2 template inheritance pattern. This allows both front and back card templates to share common HTML structure and JavaScript functionality.

## Implementation Details

### Files Modified

1. **Created: `templates/card/base.jinja`**
   - Base template with HTML5 structure
   - JavaScript toggle functionality for font switching
   - Fixed bottom bar with "Switch" button
   - CSS styles for modern font option
   - LocalStorage persistence for user preferences

2. **Updated: `templates/card/front.jinja`**
   - Now extends base.jinja template
   - Content wrapped in `{% block content %}` block
   - Inherits all JavaScript and styling from base

3. **Updated: `templates/card/back.jinja`**
   - Now extends base.jinja template
   - Content wrapped in `{% block content %}` block
   - Inherits all JavaScript and styling from base

### Features Added

#### Font Toggle Functionality
- **Toggle Button**: Fixed "Switch" button at bottom of card
- **Font Classes**: Toggles `.font-modern` class on body element
- **Font Styles**:
  - Default: Arial, sans-serif
  - Modern: System font stack (-apple-system, BlinkMacSystemFont, etc.)
- **Persistence**: User preference saved to localStorage

#### Template Structure
```
base.jinja (parent)
├── HTML structure
├── CSS styles (extendable)
├── JavaScript (extendable)
└── Content block (overridden by children)
    ├── front.jinja (extends base)
    └── back.jinja (extends base)
```

### Technical Benefits

1. **DRY Principle**: Single source of truth for JavaScript and HTML structure
2. **Maintainability**: Changes to common functionality only need to be made once
3. **Extensibility**: Easy to add more JavaScript features in the future
4. **Backward Compatibility**: No changes required to CardTemplateService
5. **Clean Separation**: Structure (base) vs content (front/back) clearly separated

### Usage
The templates work seamlessly with the existing `CardTemplateService.render_card()` method. The Jinja2 template engine automatically resolves the inheritance chain when rendering.

### Future Enhancements
The base template structure now makes it easy to add:
- Additional JavaScript functionality
- Custom CSS themes
- Interactive elements
- Analytics or tracking code
- Accessibility features