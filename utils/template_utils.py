from pathlib import Path
import re

def load_template(template_path):
    """Load the template file from the given path."""
    if not Path(template_path).exists():
        raise FileNotFoundError(f"Template file does not exist: {template_path}")
    
    with open(template_path, 'r', encoding='utf-8') as file:
        return file.read()

def save_template(content, output_path):
    """Save the modified content to the output file."""
    with open(output_path, 'w', encoding='utf-8') as file:
        file.write(content)

def replace_placeholder(template, placeholder, value):
    """Replace the specified placeholder in the template with the given value."""
    return template.replace(placeholder, value)

def prepare_template(template_path, output_path, replacements):
    """
    Prepare the template by loading it, replacing placeholders, and saving it.
    
    Args:
        template_path (str): The path to the template file.
        output_path (str): The path to save the modified template.
        replacements (dict): A dictionary of placeholders and their replacement values.
    """
    template = load_template(template_path)
    
    if replacements.get('!description!') and '!description!' not in template:
        template += '\n\n!description!'
    for placeholder, value in replacements.items():
        template = replace_placeholder(template, placeholder, value)

    # Empty optional sections should not leave a screen of blank lines.
    blocks = []
    def protect(match):
        blocks.append(match.group(0))
        return '\ue100' + str(len(blocks) - 1) + '\ue101'
    template = re.sub(r'\[(code|nfo|pre)(?:=[^\]]*)?\][\s\S]*?\[/\1\]', protect, template, flags=re.I)
    previous = None
    while previous != template:
        previous = template
        template = re.sub(r'\[(c|center|b|i|u|s|size|color)(?:=[^\]]*)?\]\s*\[/\1\]', '', template, flags=re.I)
    template = re.sub(r'\n{3,}', '\n\n', template).strip()
    template = re.sub(r'\ue100(\d+)\ue101', lambda match: blocks[int(match.group(1))], template)
    save_template(template, output_path)
