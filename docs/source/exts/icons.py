# sphinx_icon_extension/icon_role.py
# Save this file in your Sphinx project, for example, in an `_ext` directory.

from docutils import nodes
from docutils.parsers.rst import roles


def icon_role(name, rawtext, text, lineno, inliner, options={}, content=[]):
    """
    Custom Sphinx role to insert an icon.

    This role takes a string of CSS classes and wraps them in an
    HTML `<i>` tag. It's designed for icon libraries like Bootstrap Icons.

    Usage in .rst file:
    :icon:`bi bi-star-fill;label;1em`

    Resulting HTML:
    <span class="icon-tool">
        <i class="bi bi-star-fill" style="font-size: 1em;"></i>
        <span class="tool-label">label</span>
    </span>

    :icon:`bi bi-star-fill`  # Default size will be used and no label will be shown.

    Resulting HTML:
    <i class="bi bi-star-fill" style="font-size: 1.25em;"></i>
    """

    # The 'text' argument contains the content of the role and optionally the size and also a label
    # We'll use this as the class for our <i> element and set the size using CSS.

    parts = text.split(';', 2)
    if len(parts) == 2:
        # If there are two parts, the first part is the icon class,
        # and the second part is the label (if provided).
        icon_class = parts[0].strip()
        label = parts[1].strip()
        size = '1.25em'  # Default size if not specified
    elif len(parts) == 3:
        # If there are three parts, the first part is the icon class,
        # the second part is the label, and the third part is a size.
        icon_class = parts[0].strip()
        label = parts[1].strip()
        size = parts[2].strip()
    else:
        icon_class = text.strip()
        size = '1.25em'
        label = None

    size = size or '1.25em'
    if label:
        # If a label is provided, we can add it as a title attribute or as a span next to the icon.
        html = (
            f'<span class="icon-tool">'
            f'<i class="{icon_class}" style="font-size: {size};" title="{label}"></i>'
            f'<span class="tool-label">{label}</span>'
            f'</span>'
        )
    else:
        html = f'<i class="{icon_class}" style="font-size: {size};"></i>'

    icon_node = nodes.raw(rawtext, html, format='html')
    roles.register_local_role(name, icon_role)
    return [icon_node], []


def setup(app):
    """
    Setup function for the Sphinx extension.

    This function is called by Sphinx when the extension is loaded.
    It registers the new 'icon' role.
    """
    # Register the custom role so Sphinx knows about :icon:
    app.add_css_file("https://cdn.jsdelivr.net/npm/bootstrap-icons@1.13.1/font/bootstrap-icons.min.css")
    app.add_css_file('css/icons.min.css')  # Optional: custom CSS for icons
    app.add_role("icon", icon_role)

    # Return a dictionary identifying the extension version.
    # 'parallel_read_safe' tells Sphinx it can use this extension in parallel builds.
    return {
        "version": "1.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
