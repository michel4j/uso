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
    :icon:`bi bi-star-fill;xl`

    Resulting HTML:
    <i class="bi bi-star-fill"></i>
    """

    # The 'text' argument contains the content of the role and optionally the size
    # We'll use this as the class for our <i> element and set the size using CSS.

    parts = text.split(';')
    if len(parts) > 1:
        # If there are multiple parts, the first part is the icon class,
        # and the second part is the size (if provided).
        icon_class = parts[0].strip()
        size = parts[1].strip()
    else:
        icon_class = text.strip()
        size = '1em'

    icon_node = nodes.raw(rawtext, f'<i class="{icon_class}" style="font-size: {size};"></i>', format='html')
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
    app.add_role("icon", icon_role)

    # Return a dictionary identifying the extension version.
    # 'parallel_read_safe' tells Sphinx it can use this extension in parallel builds.
    return {
        "version": "1.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
